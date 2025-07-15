"""Docker卷管理器"""

from typing import List, Dict, Any, Optional
from docker.models.volumes import Volume
from docker.errors import APIError, NotFound

from ..common.logger import LoggerMixin
from ..common.exceptions import DockerManagerError
from .docker_client import DockerManager


class VolumeManager(LoggerMixin):
    """Docker卷管理器
    
    负责卷的创建、删除、挂载等操作
    """
    
    def __init__(self, docker_manager: DockerManager):
        """初始化卷管理器
        
        Args:
            docker_manager: Docker管理器实例
        """
        super().__init__()
        self.docker_manager = docker_manager
    
    def list_volumes(self) -> List[Dict[str, Any]]:
        """列出卷
        
        Returns:
            卷信息列表
        """
        try:
            volumes = self.docker_manager.client.volumes.list()
            
            result = []
            for volume in volumes:
                volume_info = {
                    'name': volume.name,
                    'driver': volume.attrs.get('Driver'),
                    'mountpoint': volume.attrs.get('Mountpoint'),
                    'created': volume.attrs.get('CreatedAt'),
                    'labels': volume.attrs.get('Labels') or {},
                    'options': volume.attrs.get('Options') or {},
                    'scope': volume.attrs.get('Scope'),
                    'status': volume.attrs.get('Status', {}),
                    'usage_data': volume.attrs.get('UsageData', {})
                }
                result.append(volume_info)
            
            self.log_info(f"获取卷列表成功，共 {len(result)} 个卷")
            return result
            
        except APIError as e:
            error_msg = f"获取卷列表失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def get_volume(self, volume_name: str) -> Dict[str, Any]:
        """获取卷详细信息
        
        Args:
            volume_name: 卷名称
            
        Returns:
            卷详细信息
        """
        try:
            volume = self.docker_manager.client.volumes.get(volume_name)
            
            volume_info = {
                'name': volume.name,
                'driver': volume.attrs.get('Driver'),
                'mountpoint': volume.attrs.get('Mountpoint'),
                'created': volume.attrs.get('CreatedAt'),
                'labels': volume.attrs.get('Labels') or {},
                'options': volume.attrs.get('Options') or {},
                'scope': volume.attrs.get('Scope'),
                'status': volume.attrs.get('Status', {}),
                'usage_data': volume.attrs.get('UsageData', {})
            }
            
            return volume_info
            
        except NotFound:
            error_msg = f"卷 {volume_name} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"获取卷 {volume_name} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def create_volume(self, name: Optional[str] = None,
                     driver: str = 'local',
                     driver_opts: Optional[Dict[str, str]] = None,
                     labels: Optional[Dict[str, str]] = None) -> str:
        """创建卷
        
        Args:
            name: 卷名称（可选，不指定则自动生成）
            driver: 卷驱动
            driver_opts: 驱动选项
            labels: 标签
            
        Returns:
            卷名称
        """
        try:
            create_kwargs = {'driver': driver}
            
            if name:
                create_kwargs['name'] = name
            if driver_opts:
                create_kwargs['driver_opts'] = driver_opts
            if labels:
                create_kwargs['labels'] = labels
            
            volume = self.docker_manager.client.volumes.create(**create_kwargs)
            
            self.log_info(f"卷创建成功: {volume.name}")
            return volume.name
            
        except APIError as e:
            error_msg = f"创建卷失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def remove_volume(self, volume_name: str, force: bool = False) -> bool:
        """删除卷
        
        Args:
            volume_name: 卷名称
            force: 是否强制删除
            
        Returns:
            是否删除成功
        """
        try:
            volume = self.docker_manager.client.volumes.get(volume_name)
            volume.remove(force=force)
            
            self.log_info(f"卷删除成功: {volume_name}")
            return True
            
        except NotFound:
            error_msg = f"卷 {volume_name} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"删除卷 {volume_name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def inspect_volume(self, volume_name: str) -> Dict[str, Any]:
        """检查卷的详细信息
        
        Args:
            volume_name: 卷名称
            
        Returns:
            卷的完整属性信息
        """
        try:
            volume = self.docker_manager.client.volumes.get(volume_name)
            return volume.attrs
            
        except NotFound:
            error_msg = f"卷 {volume_name} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"检查卷 {volume_name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def get_volume_usage(self, volume_name: str) -> Dict[str, Any]:
        """获取卷使用情况
        
        Args:
            volume_name: 卷名称
            
        Returns:
            卷使用情况信息
        """
        try:
            volume = self.docker_manager.client.volumes.get(volume_name)
            usage_data = volume.attrs.get('UsageData', {})
            
            # 查找使用该卷的容器
            containers = self.docker_manager.client.containers.list(all=True)
            using_containers = []
            
            for container in containers:
                mounts = container.attrs.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume' and mount.get('Name') == volume_name:
                        using_containers.append({
                            'id': container.id,
                            'name': container.name,
                            'status': container.status,
                            'destination': mount.get('Destination'),
                            'mode': mount.get('Mode')
                        })
            
            return {
                'volume_name': volume_name,
                'size': usage_data.get('Size', 0),
                'ref_count': usage_data.get('RefCount', 0),
                'using_containers': using_containers,
                'mountpoint': volume.attrs.get('Mountpoint'),
                'driver': volume.attrs.get('Driver'),
                'created': volume.attrs.get('CreatedAt')
            }
            
        except NotFound:
            error_msg = f"卷 {volume_name} 不存在"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
        except APIError as e:
            error_msg = f"获取卷 {volume_name} 使用情况失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def prune_volumes(self) -> Dict[str, Any]:
        """清理未使用的卷
        
        Returns:
            清理结果
        """
        try:
            result = self.docker_manager.client.volumes.prune()
            
            deleted_volumes = result.get('VolumesDeleted', [])
            space_reclaimed = result.get('SpaceReclaimed', 0)
            
            self.log_info(f"卷清理完成，删除 {len(deleted_volumes)} 个卷，回收空间 {space_reclaimed} 字节")
            
            return {
                'deleted_volumes': deleted_volumes,
                'space_reclaimed': space_reclaimed,
                'deleted_count': len(deleted_volumes)
            }
            
        except APIError as e:
            error_msg = f"清理卷失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def backup_volume(self, volume_name: str, backup_path: str,
                     container_image: str = 'alpine:latest') -> bool:
        """备份卷数据
        
        Args:
            volume_name: 要备份的卷名称
            backup_path: 备份文件路径
            container_image: 用于备份的容器镜像
            
        Returns:
            是否备份成功
        """
        try:
            # 创建临时容器来备份卷数据
            container = self.docker_manager.client.containers.create(
                image=container_image,
                command='tar czf /backup.tar.gz -C /data .',
                volumes={volume_name: {'bind': '/data', 'mode': 'ro'}},
                detach=True
            )
            
            try:
                container.start()
                container.wait()
                
                # 复制备份文件
                with open(backup_path, 'wb') as f:
                    bits, _ = container.get_archive('/backup.tar.gz')
                    for chunk in bits:
                        f.write(chunk)
                
                self.log_info(f"卷 {volume_name} 备份成功: {backup_path}")
                return True
                
            finally:
                container.remove(force=True)
                
        except Exception as e:
            error_msg = f"备份卷 {volume_name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)
    
    def restore_volume(self, volume_name: str, backup_path: str,
                      container_image: str = 'alpine:latest') -> bool:
        """恢复卷数据
        
        Args:
            volume_name: 要恢复的卷名称
            backup_path: 备份文件路径
            container_image: 用于恢复的容器镜像
            
        Returns:
            是否恢复成功
        """
        try:
            # 创建临时容器来恢复卷数据
            container = self.docker_manager.client.containers.create(
                image=container_image,
                command='sh -c "cd /data && tar xzf /backup.tar.gz"',
                volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
                detach=True
            )
            
            try:
                # 复制备份文件到容器
                with open(backup_path, 'rb') as f:
                    container.put_archive('/backup.tar.gz', f.read())
                
                container.start()
                container.wait()
                
                self.log_info(f"卷 {volume_name} 恢复成功: {backup_path}")
                return True
                
            finally:
                container.remove(force=True)
                
        except Exception as e:
            error_msg = f"恢复卷 {volume_name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerManagerError(error_msg)