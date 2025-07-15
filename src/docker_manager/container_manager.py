"""Docker容器管理器"""

import time
from typing import List, Dict, Any, Optional, Union
from docker.models.containers import Container
from docker.errors import APIError, NotFound

from ..common.logger import LoggerMixin
from ..common.exceptions import DockerContainerError
from .docker_client import DockerManager


class ContainerManager(LoggerMixin):
    """Docker容器管理器
    
    负责容器的创建、启动、停止、删除等生命周期管理
    """
    
    def __init__(self, docker_manager: DockerManager):
        """初始化容器管理器
        
        Args:
            docker_manager: Docker管理器实例
        """
        super().__init__()
        self.docker_manager = docker_manager
    
    def list_containers(self, all_containers: bool = True) -> List[Dict[str, Any]]:
        """列出容器
        
        Args:
            all_containers: 是否包含停止的容器
            
        Returns:
            容器信息列表
        """
        try:
            containers = self.docker_manager.client.containers.list(all=all_containers)
            
            result = []
            for container in containers:
                container_info = {
                    'id': container.id,
                    'short_id': container.short_id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'created': container.attrs.get('Created'),
                    'ports': container.ports,
                    'labels': container.labels,
                    'networks': list(container.attrs.get('NetworkSettings', {}).get('Networks', {}).keys())
                }
                result.append(container_info)
            
            self.log_info(f"获取容器列表成功，共 {len(result)} 个容器")
            return result
            
        except APIError as e:
            error_msg = f"获取容器列表失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def get_container(self, container_id: str) -> Dict[str, Any]:
        """获取容器详细信息
        
        Args:
            container_id: 容器ID或名称
            
        Returns:
            容器详细信息
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            
            # 获取容器统计信息
            stats = None
            try:
                stats_stream = container.stats(stream=False)
                stats = stats_stream
            except Exception:
                pass
            
            container_info = {
                'id': container.id,
                'short_id': container.short_id,
                'name': container.name,
                'status': container.status,
                'image': container.image.tags[0] if container.image.tags else container.image.id,
                'created': container.attrs.get('Created'),
                'started': container.attrs.get('State', {}).get('StartedAt'),
                'finished': container.attrs.get('State', {}).get('FinishedAt'),
                'ports': container.ports,
                'labels': container.labels,
                'env': container.attrs.get('Config', {}).get('Env', []),
                'mounts': container.attrs.get('Mounts', []),
                'networks': container.attrs.get('NetworkSettings', {}).get('Networks', {}),
                'restart_policy': container.attrs.get('HostConfig', {}).get('RestartPolicy', {}),
                'stats': stats
            }
            
            return container_info
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"获取容器 {container_id} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def create_container(self, image: str, name: Optional[str] = None, 
                        command: Optional[str] = None,
                        environment: Optional[Dict[str, str]] = None,
                        ports: Optional[Dict[str, int]] = None,
                        volumes: Optional[Dict[str, Dict[str, str]]] = None,
                        network: Optional[str] = None,
                        restart_policy: Optional[Dict[str, Any]] = None,
                        **kwargs) -> str:
        """创建容器
        
        Args:
            image: 镜像名称
            name: 容器名称
            command: 启动命令
            environment: 环境变量
            ports: 端口映射 {'80/tcp': 8080}
            volumes: 卷挂载 {'/host/path': {'bind': '/container/path', 'mode': 'rw'}}
            network: 网络名称
            restart_policy: 重启策略 {'Name': 'always'}
            **kwargs: 其他参数
            
        Returns:
            容器ID
        """
        try:
            # 构建创建参数
            create_kwargs = {
                'image': image,
                'detach': True
            }
            
            if name:
                create_kwargs['name'] = name
            if command:
                create_kwargs['command'] = command
            if environment:
                create_kwargs['environment'] = environment
            if ports:
                create_kwargs['ports'] = ports
            if volumes:
                create_kwargs['volumes'] = volumes
            if network:
                create_kwargs['network'] = network
            if restart_policy:
                create_kwargs['restart_policy'] = restart_policy
            
            # 合并其他参数
            create_kwargs.update(kwargs)
            
            container = self.docker_manager.client.containers.create(**create_kwargs)
            
            self.log_info(f"容器创建成功: {container.name} ({container.short_id})")
            return container.id
            
        except APIError as e:
            error_msg = f"创建容器失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def start_container(self, container_id: str) -> bool:
        """启动容器
        
        Args:
            container_id: 容器ID或名称
            
        Returns:
            是否启动成功
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            container.start()
            
            self.log_info(f"容器启动成功: {container.name} ({container.short_id})")
            return True
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"启动容器 {container_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """停止容器
        
        Args:
            container_id: 容器ID或名称
            timeout: 超时时间（秒）
            
        Returns:
            是否停止成功
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            container.stop(timeout=timeout)
            
            self.log_info(f"容器停止成功: {container.name} ({container.short_id})")
            return True
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"停止容器 {container_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def restart_container(self, container_id: str, timeout: int = 10) -> bool:
        """重启容器
        
        Args:
            container_id: 容器ID或名称
            timeout: 超时时间（秒）
            
        Returns:
            是否重启成功
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            container.restart(timeout=timeout)
            
            self.log_info(f"容器重启成功: {container.name} ({container.short_id})")
            return True
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"重启容器 {container_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def remove_container(self, container_id: str, force: bool = False, 
                        remove_volumes: bool = False) -> bool:
        """删除容器
        
        Args:
            container_id: 容器ID或名称
            force: 是否强制删除（即使容器正在运行）
            remove_volumes: 是否同时删除关联的匿名卷
            
        Returns:
            是否删除成功
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            container_name = container.name
            container_short_id = container.short_id
            
            container.remove(force=force, v=remove_volumes)
            
            self.log_info(f"容器删除成功: {container_name} ({container_short_id})")
            return True
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"删除容器 {container_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def get_container_logs(self, container_id: str, tail: int = 100, 
                          follow: bool = False, timestamps: bool = True) -> Union[str, Any]:
        """获取容器日志
        
        Args:
            container_id: 容器ID或名称
            tail: 获取最后N行日志
            follow: 是否持续跟踪日志
            timestamps: 是否包含时间戳
            
        Returns:
            日志内容（字符串或生成器）
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            
            logs = container.logs(
                tail=tail,
                follow=follow,
                timestamps=timestamps,
                stream=follow
            )
            
            if follow:
                return logs  # 返回生成器
            else:
                return logs.decode('utf-8')  # 返回字符串
                
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"获取容器 {container_id} 日志失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def execute_command(self, container_id: str, command: str, 
                       workdir: Optional[str] = None) -> Dict[str, Any]:
        """在容器中执行命令
        
        Args:
            container_id: 容器ID或名称
            command: 要执行的命令
            workdir: 工作目录
            
        Returns:
            执行结果字典
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            
            exec_kwargs = {'cmd': command}
            if workdir:
                exec_kwargs['workdir'] = workdir
            
            result = container.exec_run(**exec_kwargs)
            
            return {
                'exit_code': result.exit_code,
                'output': result.output.decode('utf-8') if result.output else '',
                'success': result.exit_code == 0
            }
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"在容器 {container_id} 中执行命令失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
    
    def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """获取容器资源使用统计
        
        Args:
            container_id: 容器ID或名称
            
        Returns:
            资源使用统计信息
        """
        try:
            container = self.docker_manager.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # 计算CPU使用率
            cpu_percent = 0.0
            if 'cpu_stats' in stats and 'precpu_stats' in stats:
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']
                
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * \
                                 len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
            
            # 计算内存使用
            memory_usage = stats.get('memory_stats', {}).get('usage', 0)
            memory_limit = stats.get('memory_stats', {}).get('limit', 0)
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
            
            return {
                'cpu_percent': round(cpu_percent, 2),
                'memory_usage': memory_usage,
                'memory_limit': memory_limit,
                'memory_percent': round(memory_percent, 2),
                'network_rx': stats.get('networks', {}).get('eth0', {}).get('rx_bytes', 0),
                'network_tx': stats.get('networks', {}).get('eth0', {}).get('tx_bytes', 0),
                'block_read': stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [{}])[0].get('value', 0),
                'block_write': stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [{}])[-1].get('value', 0) if len(stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [])) > 1 else 0
            }
            
        except NotFound:
            error_msg = f"容器 {container_id} 不存在"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)
        except APIError as e:
            error_msg = f"获取容器 {container_id} 统计信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerContainerError(error_msg)