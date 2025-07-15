"""Docker网络管理器"""

from typing import List, Dict, Any, Optional
from docker.models.networks import Network
from docker.errors import APIError, NotFound

from ..common.logger import LoggerMixin
from ..common.exceptions import DockerManagerError
from .docker_client import DockerManager


class NetworkManager(LoggerMixin):
    """Docker网络管理器
    
    负责网络的创建、删除、连接等操作
    """
    
    def __init__(self, docker_manager: DockerManager):
        """初始化网络管理器
        
        Args:
            docker_manager: Docker管理器实例
        """
        super().__init__()
        self.docker_manager = docker_manager
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """列出网络
        
        Returns:
            网络信息列表
        """
        try:
            networks = self.docker_manager.client.networks.list()
            
            result = []
            for network in networks:
                network_info = {
                    'id': network.id,
                    'short_id': network.short_id,
                    'name': network.name,
                    'driver': network.attrs.get('Driver'),
                    'scope': network.attrs.get('Scope'),
                    'created': network.attrs.get('Created'),
                    'labels': network.attrs.get('Labels') or {},
                    'options': network.attrs.get('Options') or {},
                    'containers': list(network.attrs.get('Containers', {}).keys()),
                    'ipam': network.attrs.get('IPAM', {}),
                    'internal': network.attrs.get('Internal', False),
                    'attachable': network.attrs.get('Attachable', False)
                }
                result.append(network_info)
            
            self.log_info(f"获取网络列表成功，共 {len(result)} 个网络")
            return result
            
        except APIError as e:
            error_msg = f"获取网络列表失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def get_network(self, network_id: str) -> Dict[str, Any]:
        """获取网络详细信息
        
        Args:
            network_id: 网络ID或名称
            
        Returns:
            网络详细信息
        """
        try:
            network = self.docker_manager.client.networks.get(network_id)
            
            network_info = {
                'id': network.id,
                'short_id': network.short_id,
                'name': network.name,
                'driver': network.attrs.get('Driver'),
                'scope': network.attrs.get('Scope'),
                'created': network.attrs.get('Created'),
                'labels': network.attrs.get('Labels') or {},
                'options': network.attrs.get('Options') or {},
                'containers': network.attrs.get('Containers', {}),
                'ipam': network.attrs.get('IPAM', {}),
                'internal': network.attrs.get('Internal', False),
                'attachable': network.attrs.get('Attachable', False),
                'ingress': network.attrs.get('Ingress', False),
                'config_from': network.attrs.get('ConfigFrom', {}),
                'config_only': network.attrs.get('ConfigOnly', False)
            }
            
            return network_info
            
        except NotFound:
            error_msg = f"网络 {network_id} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"获取网络 {network_id} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def create_network(self, name: str, driver: str = 'bridge',
                      options: Optional[Dict[str, str]] = None,
                      ipam: Optional[Dict[str, Any]] = None,
                      check_duplicate: bool = True,
                      internal: bool = False,
                      labels: Optional[Dict[str, str]] = None,
                      enable_ipv6: bool = False,
                      attachable: bool = False) -> str:
        """创建网络
        
        Args:
            name: 网络名称
            driver: 网络驱动（bridge, overlay, host, none等）
            options: 驱动选项
            ipam: IP地址管理配置
            check_duplicate: 是否检查重复名称
            internal: 是否为内部网络
            labels: 标签
            enable_ipv6: 是否启用IPv6
            attachable: 是否可附加
            
        Returns:
            网络ID
        """
        try:
            create_kwargs = {
                'name': name,
                'driver': driver,
                'check_duplicate': check_duplicate,
                'internal': internal,
                'enable_ipv6': enable_ipv6,
                'attachable': attachable
            }
            
            if options:
                create_kwargs['options'] = options
            if ipam:
                create_kwargs['ipam'] = ipam
            if labels:
                create_kwargs['labels'] = labels
            
            network = self.docker_manager.client.networks.create(**create_kwargs)
            
            self.log_info(f"网络创建成功: {name} ({network.short_id})")
            return network.id
            
        except APIError as e:
            error_msg = f"创建网络 {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def remove_network(self, network_id: str) -> bool:
        """删除网络
        
        Args:
            network_id: 网络ID或名称
            
        Returns:
            是否删除成功
        """
        try:
            network = self.docker_manager.client.networks.get(network_id)
            network_name = network.name
            
            network.remove()
            
            self.log_info(f"网络删除成功: {network_name}")
            return True
            
        except NotFound:
            error_msg = f"网络 {network_id} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"删除网络 {network_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def connect_container(self, network_id: str, container_id: str,
                         aliases: Optional[List[str]] = None,
                         links: Optional[List[str]] = None,
                         ipv4_address: Optional[str] = None,
                         ipv6_address: Optional[str] = None) -> bool:
        """将容器连接到网络
        
        Args:
            network_id: 网络ID或名称
            container_id: 容器ID或名称
            aliases: 网络别名
            links: 容器链接
            ipv4_address: IPv4地址
            ipv6_address: IPv6地址
            
        Returns:
            是否连接成功
        """
        try:
            network = self.docker_manager.client.networks.get(network_id)
            
            connect_kwargs = {'container': container_id}
            
            if aliases or links or ipv4_address or ipv6_address:
                endpoint_config = {}
                if aliases:
                    endpoint_config['Aliases'] = aliases
                if links:
                    endpoint_config['Links'] = links
                if ipv4_address:
                    endpoint_config['IPAMConfig'] = {'IPv4Address': ipv4_address}
                if ipv6_address:
                    if 'IPAMConfig' not in endpoint_config:
                        endpoint_config['IPAMConfig'] = {}
                    endpoint_config['IPAMConfig']['IPv6Address'] = ipv6_address
                
                connect_kwargs['endpoint_config'] = endpoint_config
            
            network.connect(**connect_kwargs)
            
            self.log_info(f"容器 {container_id} 成功连接到网络 {network.name}")
            return True
            
        except NotFound as e:
            error_msg = f"网络或容器不存在: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"连接容器到网络失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def disconnect_container(self, network_id: str, container_id: str,
                           force: bool = False) -> bool:
        """从网络断开容器
        
        Args:
            network_id: 网络ID或名称
            container_id: 容器ID或名称
            force: 是否强制断开
            
        Returns:
            是否断开成功
        """
        try:
            network = self.docker_manager.client.networks.get(network_id)
            network.disconnect(container_id, force=force)
            
            self.log_info(f"容器 {container_id} 成功从网络 {network.name} 断开")
            return True
            
        except NotFound as e:
            error_msg = f"网络或容器不存在: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"从网络断开容器失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def prune_networks(self) -> Dict[str, Any]:
        """清理未使用的网络
        
        Returns:
            清理结果
        """
        try:
            result = self.docker_manager.client.networks.prune()
            
            deleted_count = len(result.get('NetworksDeleted', []))
            self.log_info(f"网络清理完成，删除 {deleted_count} 个网络")
            
            return result
            
        except APIError as e:
            error_msg = f"清理网络失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)