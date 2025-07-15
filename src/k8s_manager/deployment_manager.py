"""Kubernetes Deployment管理器"""

from typing import List, Dict, Any, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..common.logger import LoggerMixin
from ..common.exceptions import K8sDeploymentError
from .k8s_client import K8sManager


class DeploymentManager(LoggerMixin):
    """Kubernetes Deployment管理器
    
    负责Deployment的创建、更新、删除、扩缩容等操作
    """
    
    def __init__(self, k8s_manager: K8sManager):
        """初始化Deployment管理器
        
        Args:
            k8s_manager: Kubernetes管理器实例
        """
        super().__init__()
        self.k8s_manager = k8s_manager
    
    def list_deployments(self, namespace: Optional[str] = None,
                        label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出Deployment
        
        Args:
            namespace: 命名空间，不指定则使用当前命名空间
            label_selector: 标签选择器
            
        Returns:
            Deployment信息列表
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            if namespace == 'all':
                deployments = self.k8s_manager.apps_v1.list_deployment_for_all_namespaces(
                    label_selector=label_selector
                )
            else:
                deployments = self.k8s_manager.apps_v1.list_namespaced_deployment(
                    namespace=namespace,
                    label_selector=label_selector
                )
            
            result = []
            for deployment in deployments.items:
                deployment_info = {
                    'name': deployment.metadata.name,
                    'namespace': deployment.metadata.namespace,
                    'replicas': deployment.spec.replicas,
                    'ready_replicas': deployment.status.ready_replicas or 0,
                    'available_replicas': deployment.status.available_replicas or 0,
                    'updated_replicas': deployment.status.updated_replicas or 0,
                    'age': deployment.metadata.creation_timestamp,
                    'labels': deployment.metadata.labels or {},
                    'selector': deployment.spec.selector.match_labels or {},
                    'strategy': deployment.spec.strategy.type if deployment.spec.strategy else 'RollingUpdate',
                    'conditions': self._get_deployment_conditions(deployment)
                }
                result.append(deployment_info)
            
            self.log_info(f"获取Deployment列表成功，共 {len(result)} 个Deployment")
            return result
            
        except ApiException as e:
            error_msg = f"获取Deployment列表失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def get_deployment(self, name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取Deployment详细信息
        
        Args:
            name: Deployment名称
            namespace: 命名空间
            
        Returns:
            Deployment详细信息
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            deployment = self.k8s_manager.apps_v1.read_namespaced_deployment(name, namespace)
            
            deployment_info = {
                'name': deployment.metadata.name,
                'namespace': deployment.metadata.namespace,
                'uid': deployment.metadata.uid,
                'generation': deployment.metadata.generation,
                'replicas': deployment.spec.replicas,
                'ready_replicas': deployment.status.ready_replicas or 0,
                'available_replicas': deployment.status.available_replicas or 0,
                'updated_replicas': deployment.status.updated_replicas or 0,
                'unavailable_replicas': deployment.status.unavailable_replicas or 0,
                'observed_generation': deployment.status.observed_generation,
                'age': deployment.metadata.creation_timestamp,
                'labels': deployment.metadata.labels or {},
                'annotations': deployment.metadata.annotations or {},
                'selector': deployment.spec.selector.match_labels or {},
                'strategy': self._get_deployment_strategy(deployment),
                'template': self._get_pod_template_info(deployment),
                'conditions': self._get_deployment_conditions(deployment),
                'revision_history_limit': deployment.spec.revision_history_limit
            }
            
            return deployment_info
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Deployment {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"获取Deployment {name} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def create_deployment(self, name: str, image: str, replicas: int = 1,
                         namespace: Optional[str] = None,
                         labels: Optional[Dict[str, str]] = None,
                         env: Optional[Dict[str, str]] = None,
                         ports: Optional[List[int]] = None,
                         resources: Optional[Dict[str, Any]] = None,
                         strategy: str = 'RollingUpdate') -> str:
        """创建Deployment
        
        Args:
            name: Deployment名称
            image: 容器镜像
            replicas: 副本数
            namespace: 命名空间
            labels: 标签
            env: 环境变量
            ports: 端口列表
            resources: 资源限制
            strategy: 更新策略
            
        Returns:
            Deployment名称
        """
        namespace = namespace or self.k8s_manager.current_namespace
        labels = labels or {'app': name}
        
        try:
            # 构建容器定义
            container = client.V1Container(
                name=name,
                image=image
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
            
            # Pod模板
            pod_template = client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=client.V1PodSpec(containers=[container])
            )
            
            # 更新策略
            deployment_strategy = client.V1DeploymentStrategy(type=strategy)
            if strategy == 'RollingUpdate':
                deployment_strategy.rolling_update = client.V1RollingUpdateDeployment(
                    max_surge='25%',
                    max_unavailable='25%'
                )
            
            # Deployment规格
            deployment_spec = client.V1DeploymentSpec(
                replicas=replicas,
                selector=client.V1LabelSelector(match_labels=labels),
                template=pod_template,
                strategy=deployment_strategy
            )
            
            # 创建Deployment
            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(name=name, labels=labels),
                spec=deployment_spec
            )
            
            self.k8s_manager.apps_v1.create_namespaced_deployment(
                namespace=namespace,
                body=deployment
            )
            
            self.log_info(f"Deployment创建成功: {name} 在命名空间 {namespace}")
            return name
            
        except ApiException as e:
            error_msg = f"创建Deployment {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def update_deployment(self, name: str, namespace: Optional[str] = None,
                         image: Optional[str] = None,
                         replicas: Optional[int] = None,
                         env: Optional[Dict[str, str]] = None,
                         resources: Optional[Dict[str, Any]] = None) -> bool:
        """更新Deployment
        
        Args:
            name: Deployment名称
            namespace: 命名空间
            image: 新的容器镜像
            replicas: 新的副本数
            env: 新的环境变量
            resources: 新的资源限制
            
        Returns:
            是否更新成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            # 获取当前Deployment
            deployment = self.k8s_manager.apps_v1.read_namespaced_deployment(name, namespace)
            
            # 更新副本数
            if replicas is not None:
                deployment.spec.replicas = replicas
            
            # 更新容器配置
            if image or env or resources:
                container = deployment.spec.template.spec.containers[0]
                
                if image:
                    container.image = image
                
                if env:
                    container.env = [client.V1EnvVar(name=k, value=v) for k, v in env.items()]
                
                if resources:
                    container.resources = client.V1ResourceRequirements(
                        limits=resources.get('limits'),
                        requests=resources.get('requests')
                    )
            
            # 应用更新
            self.k8s_manager.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            self.log_info(f"Deployment更新成功: {name} 在命名空间 {namespace}")
            return True
            
        except ApiException as e:
            error_msg = f"更新Deployment {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def scale_deployment(self, name: str, replicas: int,
                        namespace: Optional[str] = None) -> bool:
        """扩缩容Deployment
        
        Args:
            name: Deployment名称
            replicas: 目标副本数
            namespace: 命名空间
            
        Returns:
            是否扩缩容成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            # 构建扩缩容对象
            scale = client.V1Scale(
                spec=client.V1ScaleSpec(replicas=replicas)
            )
            
            self.k8s_manager.apps_v1.patch_namespaced_deployment_scale(
                name=name,
                namespace=namespace,
                body=scale
            )
            
            self.log_info(f"Deployment扩缩容成功: {name} -> {replicas} 副本")
            return True
            
        except ApiException as e:
            error_msg = f"扩缩容Deployment {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def delete_deployment(self, name: str, namespace: Optional[str] = None) -> bool:
        """删除Deployment
        
        Args:
            name: Deployment名称
            namespace: 命名空间
            
        Returns:
            是否删除成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            self.k8s_manager.apps_v1.delete_namespaced_deployment(
                name=name,
                namespace=namespace
            )
            
            self.log_info(f"Deployment删除成功: {name} 在命名空间 {namespace}")
            return True
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Deployment {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"删除Deployment {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def rollback_deployment(self, name: str, namespace: Optional[str] = None,
                           revision: Optional[int] = None) -> bool:
        """回滚Deployment
        
        Args:
            name: Deployment名称
            namespace: 命名空间
            revision: 目标版本号，不指定则回滚到上一版本
            
        Returns:
            是否回滚成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            # 获取ReplicaSet历史
            replica_sets = self.k8s_manager.apps_v1.list_namespaced_replica_set(
                namespace=namespace,
                label_selector=f"app={name}"
            )
            
            if not replica_sets.items:
                raise K8sDeploymentError(f"未找到Deployment {name} 的ReplicaSet")
            
            # 按revision排序
            sorted_rs = sorted(
                replica_sets.items,
                key=lambda rs: int(rs.metadata.annotations.get('deployment.kubernetes.io/revision', '0')),
                reverse=True
            )
            
            target_rs = None
            if revision:
                for rs in sorted_rs:
                    if int(rs.metadata.annotations.get('deployment.kubernetes.io/revision', '0')) == revision:
                        target_rs = rs
                        break
            else:
                # 回滚到上一版本
                if len(sorted_rs) > 1:
                    target_rs = sorted_rs[1]
            
            if not target_rs:
                raise K8sDeploymentError(f"未找到目标版本的ReplicaSet")
            
            # 获取当前Deployment
            deployment = self.k8s_manager.apps_v1.read_namespaced_deployment(name, namespace)
            
            # 更新Pod模板为目标版本
            deployment.spec.template = target_rs.spec.template
            
            # 应用更新
            self.k8s_manager.apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            self.log_info(f"Deployment回滚成功: {name} 回滚到版本 {revision or '上一版本'}")
            return True
            
        except ApiException as e:
            error_msg = f"回滚Deployment {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def get_deployment_history(self, name: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取Deployment历史版本
        
        Args:
            name: Deployment名称
            namespace: 命名空间
            
        Returns:
            历史版本列表
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            replica_sets = self.k8s_manager.apps_v1.list_namespaced_replica_set(
                namespace=namespace,
                label_selector=f"app={name}"
            )
            
            history = []
            for rs in replica_sets.items:
                revision = rs.metadata.annotations.get('deployment.kubernetes.io/revision', '0')
                change_cause = rs.metadata.annotations.get('kubernetes.io/change-cause', '')
                
                history.append({
                    'revision': int(revision),
                    'change_cause': change_cause,
                    'creation_timestamp': rs.metadata.creation_timestamp,
                    'replicas': rs.spec.replicas,
                    'ready_replicas': rs.status.ready_replicas or 0,
                    'image': rs.spec.template.spec.containers[0].image if rs.spec.template.spec.containers else ''
                })
            
            # 按revision排序
            history.sort(key=lambda x: x['revision'], reverse=True)
            
            return history
            
        except ApiException as e:
            error_msg = f"获取Deployment {name} 历史版本失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sDeploymentError(error_msg)
    
    def _get_deployment_conditions(self, deployment) -> List[Dict[str, Any]]:
        """获取Deployment条件"""
        if not deployment.status.conditions:
            return []
        
        return [{
            'type': condition.type,
            'status': condition.status,
            'last_transition_time': condition.last_transition_time,
            'last_update_time': condition.last_update_time,
            'reason': condition.reason,
            'message': condition.message
        } for condition in deployment.status.conditions]
    
    def _get_deployment_strategy(self, deployment) -> Dict[str, Any]:
        """获取Deployment策略"""
        strategy = {'type': deployment.spec.strategy.type}
        
        if deployment.spec.strategy.rolling_update:
            strategy['rolling_update'] = {
                'max_surge': deployment.spec.strategy.rolling_update.max_surge,
                'max_unavailable': deployment.spec.strategy.rolling_update.max_unavailable
            }
        
        return strategy
    
    def _get_pod_template_info(self, deployment) -> Dict[str, Any]:
        """获取Pod模板信息"""
        template = deployment.spec.template
        
        containers = []
        for container in template.spec.containers:
            containers.append({
                'name': container.name,
                'image': container.image,
                'ports': [port.container_port for port in (container.ports or [])],
                'env': [{'name': env.name, 'value': env.value} for env in (container.env or [])],
                'resources': container.resources
            })
        
        return {
            'labels': template.metadata.labels or {},
            'annotations': template.metadata.annotations or {},
            'containers': containers,
            'restart_policy': template.spec.restart_policy,
            'service_account': template.spec.service_account_name
        }