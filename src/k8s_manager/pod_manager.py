"""Kubernetes Pod管理器"""

from typing import List, Dict, Any, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..common.logger import LoggerMixin
from ..common.exceptions import K8sPodError
from .k8s_client import K8sManager


class PodManager(LoggerMixin):
    """Kubernetes Pod管理器
    
    负责Pod的创建、删除、监控等生命周期管理
    """
    
    def __init__(self, k8s_manager: K8sManager):
        """初始化Pod管理器
        
        Args:
            k8s_manager: Kubernetes管理器实例
        """
        super().__init__()
        self.k8s_manager = k8s_manager
    
    def list_pods(self, namespace: Optional[str] = None, 
                  label_selector: Optional[str] = None,
                  field_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出Pod
        
        Args:
            namespace: 命名空间，不指定则使用当前命名空间
            label_selector: 标签选择器
            field_selector: 字段选择器
            
        Returns:
            Pod信息列表
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            if namespace == 'all':
                pods = self.k8s_manager.core_v1.list_pod_for_all_namespaces(
                    label_selector=label_selector,
                    field_selector=field_selector
                )
            else:
                pods = self.k8s_manager.core_v1.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=label_selector,
                    field_selector=field_selector
                )
            
            result = []
            for pod in pods.items:
                pod_info = {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'status': pod.status.phase,
                    'ready': self._get_pod_ready_status(pod),
                    'restarts': self._get_pod_restart_count(pod),
                    'age': pod.metadata.creation_timestamp,
                    'node': pod.spec.node_name,
                    'ip': pod.status.pod_ip,
                    'labels': pod.metadata.labels or {},
                    'annotations': pod.metadata.annotations or {},
                    'containers': self._get_container_info(pod),
                    'conditions': self._get_pod_conditions(pod)
                }
                result.append(pod_info)
            
            self.log_info(f"获取Pod列表成功，共 {len(result)} 个Pod")
            return result
            
        except ApiException as e:
            error_msg = f"获取Pod列表失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sPodError(error_msg)
    
    def get_pod(self, name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取Pod详细信息
        
        Args:
            name: Pod名称
            namespace: 命名空间
            
        Returns:
            Pod详细信息
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            pod = self.k8s_manager.core_v1.read_namespaced_pod(name, namespace)
            
            pod_info = {
                'name': pod.metadata.name,
                'namespace': pod.metadata.namespace,
                'uid': pod.metadata.uid,
                'status': pod.status.phase,
                'ready': self._get_pod_ready_status(pod),
                'restarts': self._get_pod_restart_count(pod),
                'age': pod.metadata.creation_timestamp,
                'node': pod.spec.node_name,
                'ip': pod.status.pod_ip,
                'host_ip': pod.status.host_ip,
                'qos_class': pod.status.qos_class,
                'start_time': pod.status.start_time,
                'labels': pod.metadata.labels or {},
                'annotations': pod.metadata.annotations or {},
                'owner_references': pod.metadata.owner_references or [],
                'containers': self._get_container_detailed_info(pod),
                'conditions': self._get_pod_conditions(pod),
                'volumes': self._get_volume_info(pod),
                'tolerations': pod.spec.tolerations or [],
                'node_selector': pod.spec.node_selector or {},
                'service_account': pod.spec.service_account_name,
                'security_context': pod.spec.security_context,
                'dns_policy': pod.spec.dns_policy,
                'restart_policy': pod.spec.restart_policy
            }
            
            return pod_info
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Pod {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"获取Pod {name} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sPodError(error_msg)
    
    def create_pod(self, name: str, image: str, namespace: Optional[str] = None,
                   command: Optional[List[str]] = None,
                   args: Optional[List[str]] = None,
                   env: Optional[Dict[str, str]] = None,
                   ports: Optional[List[int]] = None,
                   labels: Optional[Dict[str, str]] = None,
                   resources: Optional[Dict[str, Any]] = None,
                   volumes: Optional[List[Dict[str, Any]]] = None,
                   volume_mounts: Optional[List[Dict[str, Any]]] = None) -> str:
        """创建Pod
        
        Args:
            name: Pod名称
            image: 容器镜像
            namespace: 命名空间
            command: 启动命令
            args: 命令参数
            env: 环境变量
            ports: 端口列表
            labels: 标签
            resources: 资源限制
            volumes: 卷定义
            volume_mounts: 卷挂载
            
        Returns:
            Pod名称
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            # 构建容器定义
            container = client.V1Container(
                name=name,
                image=image,
                command=command,
                args=args
            )
            
            # 环境变量
            if env:
                container.env = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]
            
            # 端口
            if ports:
                container.ports = [client.V1ContainerPort(container_port=port) for port in ports]
            
            # 资源限制
            if resources:
                container.resources = client.V1ResourceRequirements(
                    limits=resources.get('limits'),
                    requests=resources.get('requests')
                )
            
            # 卷挂载
            if volume_mounts:
                container.volume_mounts = [
                    client.V1VolumeMount(
                        name=vm['name'],
                        mount_path=vm['mount_path'],
                        read_only=vm.get('read_only', False)
                    ) for vm in volume_mounts
                ]
            
            # 构建Pod规格
            pod_spec = client.V1PodSpec(containers=[container])
            
            # 卷定义
            if volumes:
                pod_spec.volumes = []
                for vol in volumes:
                    if vol['type'] == 'empty_dir':
                        volume = client.V1Volume(
                            name=vol['name'],
                            empty_dir=client.V1EmptyDirVolumeSource()
                        )
                    elif vol['type'] == 'host_path':
                        volume = client.V1Volume(
                            name=vol['name'],
                            host_path=client.V1HostPathVolumeSource(path=vol['path'])
                        )
                    elif vol['type'] == 'config_map':
                        volume = client.V1Volume(
                            name=vol['name'],
                            config_map=client.V1ConfigMapVolumeSource(name=vol['config_map'])
                        )
                    else:
                        continue
                    pod_spec.volumes.append(volume)
            
            # 构建Pod
            pod = client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels or {}
                ),
                spec=pod_spec
            )
            
            # 创建Pod
            self.k8s_manager.core_v1.create_namespaced_pod(namespace, pod)
            
            self.log_info(f"Pod创建成功: {name} 在命名空间 {namespace}")
            return name
            
        except ApiException as e:
            error_msg = f"创建Pod {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sPodError(error_msg)
    
    def delete_pod(self, name: str, namespace: Optional[str] = None,
                   grace_period_seconds: int = 30) -> bool:
        """删除Pod
        
        Args:
            name: Pod名称
            namespace: 命名空间
            grace_period_seconds: 优雅删除时间
            
        Returns:
            是否删除成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            self.k8s_manager.core_v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                grace_period_seconds=grace_period_seconds
            )
            
            self.log_info(f"Pod删除成功: {name} 在命名空间 {namespace}")
            return True
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Pod {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"删除Pod {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sPodError(error_msg)
    
    def get_pod_logs(self, name: str, namespace: Optional[str] = None,
                     container: Optional[str] = None,
                     tail_lines: Optional[int] = None,
                     since_seconds: Optional[int] = None,
                     follow: bool = False) -> str:
        """获取Pod日志
        
        Args:
            name: Pod名称
            namespace: 命名空间
            container: 容器名称
            tail_lines: 获取最后N行
            since_seconds: 获取最近N秒的日志
            follow: 是否持续跟踪
            
        Returns:
            日志内容
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            logs = self.k8s_manager.core_v1.read_namespaced_pod_log(
                name=name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
                follow=follow,
                timestamps=True
            )
            
            return logs
            
        except ApiException as e:
            error_msg = f"获取Pod {name} 日志失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sPodError(error_msg)
    
    def execute_command(self, name: str, command: List[str],
                       namespace: Optional[str] = None,
                       container: Optional[str] = None) -> Dict[str, Any]:
        """在Pod中执行命令
        
        Args:
            name: Pod名称
            command: 要执行的命令
            namespace: 命名空间
            container: 容器名称
            
        Returns:
            执行结果
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            from kubernetes.stream import stream
            
            exec_command = [
                '/bin/sh',
                '-c',
                ' '.join(command)
            ]
            
            resp = stream(
                self.k8s_manager.core_v1.connect_get_namespaced_pod_exec,
                name,
                namespace,
                command=exec_command,
                container=container,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False
            )
            
            return {
                'output': resp,
                'success': True
            }
            
        except Exception as e:
            error_msg = f"在Pod {name} 中执行命令失败: {str(e)}"
            self.log_error(error_msg)
            return {
                'output': error_msg,
                'success': False
            }
    
    def _get_pod_ready_status(self, pod) -> str:
        """获取Pod就绪状态"""
        if not pod.status.container_statuses:
            return "0/0"
        
        ready_count = sum(1 for status in pod.status.container_statuses if status.ready)
        total_count = len(pod.status.container_statuses)
        return f"{ready_count}/{total_count}"
    
    def _get_pod_restart_count(self, pod) -> int:
        """获取Pod重启次数"""
        if not pod.status.container_statuses:
            return 0
        return sum(status.restart_count for status in pod.status.container_statuses)
    
    def _get_container_info(self, pod) -> List[Dict[str, Any]]:
        """获取容器基本信息"""
        containers = []
        for container in pod.spec.containers:
            containers.append({
                'name': container.name,
                'image': container.image,
                'ports': [port.container_port for port in (container.ports or [])]
            })
        return containers
    
    def _get_container_detailed_info(self, pod) -> List[Dict[str, Any]]:
        """获取容器详细信息"""
        containers = []
        
        # 规格信息
        for container in pod.spec.containers:
            container_info = {
                'name': container.name,
                'image': container.image,
                'command': container.command,
                'args': container.args,
                'ports': [{
                    'container_port': port.container_port,
                    'protocol': port.protocol,
                    'name': port.name
                } for port in (container.ports or [])],
                'env': [{
                    'name': env.name,
                    'value': env.value
                } for env in (container.env or [])],
                'resources': container.resources,
                'volume_mounts': [{
                    'name': vm.name,
                    'mount_path': vm.mount_path,
                    'read_only': vm.read_only
                } for vm in (container.volume_mounts or [])]
            }
            
            # 状态信息
            if pod.status.container_statuses:
                for status in pod.status.container_statuses:
                    if status.name == container.name:
                        container_info.update({
                            'ready': status.ready,
                            'restart_count': status.restart_count,
                            'image_id': status.image_id,
                            'container_id': status.container_id,
                            'state': status.state
                        })
                        break
            
            containers.append(container_info)
        
        return containers
    
    def _get_pod_conditions(self, pod) -> List[Dict[str, Any]]:
        """获取Pod条件"""
        if not pod.status.conditions:
            return []
        
        return [{
            'type': condition.type,
            'status': condition.status,
            'last_transition_time': condition.last_transition_time,
            'reason': condition.reason,
            'message': condition.message
        } for condition in pod.status.conditions]
    
    def _get_volume_info(self, pod) -> List[Dict[str, Any]]:
        """获取卷信息"""
        if not pod.spec.volumes:
            return []
        
        volumes = []
        for volume in pod.spec.volumes:
            volume_info = {'name': volume.name}
            
            if volume.empty_dir:
                volume_info['type'] = 'EmptyDir'
            elif volume.host_path:
                volume_info['type'] = 'HostPath'
                volume_info['path'] = volume.host_path.path
            elif volume.config_map:
                volume_info['type'] = 'ConfigMap'
                volume_info['config_map'] = volume.config_map.name
            elif volume.secret:
                volume_info['type'] = 'Secret'
                volume_info['secret'] = volume.secret.secret_name
            elif volume.persistent_volume_claim:
                volume_info['type'] = 'PVC'
                volume_info['claim_name'] = volume.persistent_volume_claim.claim_name
            else:
                volume_info['type'] = 'Unknown'
            
            volumes.append(volume_info)
        
        return volumes