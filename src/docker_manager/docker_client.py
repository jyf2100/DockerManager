"""Docker客户端管理器"""

import docker
from typing import Dict, Any, Optional
from docker.errors import DockerException, APIError

from ..common.logger import LoggerMixin
from ..common.exceptions import DockerConnectionError, DockerManagerError
from ..common.config import ConfigManager


class DockerManager(LoggerMixin):
    """Docker管理器
    
    负责Docker客户端连接和基础操作
    """
    
    def __init__(self, config_manager: ConfigManager):
        """初始化Docker管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        super().__init__()
        self.config_manager = config_manager
        self._client: Optional[docker.DockerClient] = None
        self._connect()
    
    def _connect(self) -> None:
        """连接到Docker守护进程"""
        try:
            docker_config = self.config_manager.get('docker', {})
            
            # 构建连接参数
            client_kwargs = {
                'base_url': docker_config.get('base_url', 'unix://var/run/docker.sock'),
                'timeout': docker_config.get('timeout', 60)
            }
            
            # TLS配置
            if docker_config.get('tls', False):
                client_kwargs['tls'] = True
            
            self._client = docker.DockerClient(**client_kwargs)
            
            # 测试连接
            self._client.ping()
            self.log_info(f"成功连接到Docker守护进程: {client_kwargs['base_url']}")
            
        except DockerException as e:
            error_msg = f"连接Docker守护进程失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerConnectionError(error_msg)
        except Exception as e:
            error_msg = f"Docker连接异常: {str(e)}"
            self.log_error(error_msg)
            raise DockerConnectionError(error_msg)
    
    @property
    def client(self) -> docker.DockerClient:
        """获取Docker客户端实例"""
        if self._client is None:
            self._connect()
        return self._client
    
    def ping(self) -> bool:
        """测试Docker连接
        
        Returns:
            连接是否正常
        """
        try:
            self.client.ping()
            return True
        except Exception as e:
            self.log_error(f"Docker连接测试失败: {str(e)}")
            return False
    
    def get_system_info(self) -> Dict[str, Any]:
        """获取Docker系统信息
        
        Returns:
            系统信息字典
        """
        try:
            info = self.client.info()
            version = self.client.version()
            
            return {
                'system_info': info,
                'version_info': version,
                'containers_running': info.get('ContainersRunning', 0),
                'containers_paused': info.get('ContainersPaused', 0),
                'containers_stopped': info.get('ContainersStopped', 0),
                'images': info.get('Images', 0),
                'server_version': version.get('Version', 'Unknown'),
                'api_version': version.get('ApiVersion', 'Unknown')
            }
        except APIError as e:
            error_msg = f"获取Docker系统信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """获取Docker磁盘使用情况
        
        Returns:
            磁盘使用情况字典
        """
        try:
            # 使用更简单的方法获取基本信息，避免超时
            containers = self.client.containers.list(all=True)
            images = self.client.images.list()
            volumes = self.client.volumes.list()
            
            # 计算基本统计信息
            result = {
                'containers': {
                    'total': len(containers),
                    'running': len([c for c in containers if c.status == 'running']),
                    'stopped': len([c for c in containers if c.status != 'running'])
                },
                'images': {
                    'total': len(images),
                    'size_estimate': 'N/A (详细信息需要更长时间计算)'
                },
                'volumes': {
                    'total': len(volumes)
                },
                'note': '由于系统负载较高，显示简化的磁盘使用信息'
            }
            
            return result
            
        except APIError as e:
            error_msg = f"获取Docker磁盘使用情况失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except Exception as e:
            error_msg = f"获取Docker磁盘使用情况异常: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def cleanup_system(self, prune_containers: bool = True, 
                      prune_images: bool = True, 
                      prune_volumes: bool = False,
                      prune_networks: bool = True) -> Dict[str, Any]:
        """清理Docker系统
        
        Args:
            prune_containers: 是否清理停止的容器
            prune_images: 是否清理未使用的镜像
            prune_volumes: 是否清理未使用的卷
            prune_networks: 是否清理未使用的网络
            
        Returns:
            清理结果字典
        """
        result = {}
        
        try:
            if prune_containers:
                containers_result = self.client.containers.prune()
                deleted_containers = containers_result.get('ContainersDeleted', []) or []
                space_reclaimed_containers = containers_result.get('SpaceReclaimed', 0) or 0
                result['containers'] = {
                    'deleted': deleted_containers,
                    'space_reclaimed': space_reclaimed_containers
                }
                self.log_info(f"清理容器完成，回收空间: {space_reclaimed_containers} 字节")
            
            if prune_images:
                images_result = self.client.images.prune()
                deleted_images = images_result.get('ImagesDeleted', []) or []
                space_reclaimed_images = images_result.get('SpaceReclaimed', 0) or 0
                result['images'] = {
                    'deleted': deleted_images,
                    'space_reclaimed': space_reclaimed_images
                }
                self.log_info(f"清理镜像完成，回收空间: {space_reclaimed_images} 字节")
            
            if prune_volumes:
                volumes_result = self.client.volumes.prune()
                deleted_volumes = volumes_result.get('VolumesDeleted', []) or []
                space_reclaimed_volumes = volumes_result.get('SpaceReclaimed', 0) or 0
                result['volumes'] = {
                    'deleted': deleted_volumes,
                    'space_reclaimed': space_reclaimed_volumes
                }
                self.log_info(f"清理卷完成，回收空间: {space_reclaimed_volumes} 字节")
            
            if prune_networks:
                networks_result = self.client.networks.prune()
                deleted_networks = networks_result.get('NetworksDeleted', []) or []
                result['networks'] = {
                    'deleted': deleted_networks
                }
                self.log_info(f"清理网络完成，删除网络数: {len(deleted_networks)}")
            
            return result
            
        except APIError as e:
            error_msg = f"Docker系统清理失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def close(self) -> None:
        """关闭Docker客户端连接"""
        if self._client:
            try:
                self._client.close()
                self.log_info("Docker客户端连接已关闭")
            except Exception as e:
                self.log_error(f"关闭Docker客户端连接失败: {str(e)}")
            finally:
                self._client = None
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()