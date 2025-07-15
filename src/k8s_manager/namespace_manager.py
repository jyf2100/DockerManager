"""Kubernetes Namespace管理器"""

from typing import List, Dict, Any, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..common.logger import LoggerMixin
from ..common.exceptions import K8sNamespaceError
from .k8s_client import K8sManager


class NamespaceManager(LoggerMixin):
    """Kubernetes Namespace管理器
    
    负责Namespace的创建、删除、查询等操作
    """
    
    def __init__(self, k8s_manager: K8sManager):
        """初始化Namespace管理器
        
        Args:
            k8s_manager: Kubernetes管理器实例
        """
        super().__init__()
        self.k8s_manager = k8s_manager
    
    def list_namespaces(self, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有Namespace
        
        Args:
            label_selector: 标签选择器
            
        Returns:
            Namespace信息列表
        """
        try:
            namespaces = self.k8s_manager.core_v1.list_namespace(
                label_selector=label_selector
            )
            
            result = []
            for namespace in namespaces.items:
                namespace_info = {
                    'name': namespace.metadata.name,
                    'uid': namespace.metadata.uid,
                    'status': namespace.status.phase,
                    'age': namespace.metadata.creation_timestamp,
                    'labels': namespace.metadata.labels or {},
                    'annotations': namespace.metadata.annotations or {},
                    'resource_version': namespace.metadata.resource_version,
                    'conditions': self._get_namespace_conditions(namespace)
                }
                result.append(namespace_info)
            
            self.log_info(f"获取Namespace列表成功，共 {len(result)} 个Namespace")
            return result
            
        except ApiException as e:
            error_msg = f"获取Namespace列表失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def get_namespace(self, name: str) -> Dict[str, Any]:
        """获取Namespace详细信息
        
        Args:
            name: Namespace名称
            
        Returns:
            Namespace详细信息
        """
        try:
            namespace = self.k8s_manager.core_v1.read_namespace(name)
            
            namespace_info = {
                'name': namespace.metadata.name,
                'uid': namespace.metadata.uid,
                'status': namespace.status.phase,
                'age': namespace.metadata.creation_timestamp,
                'labels': namespace.metadata.labels or {},
                'annotations': namespace.metadata.annotations or {},
                'resource_version': namespace.metadata.resource_version,
                'finalizers': namespace.metadata.finalizers or [],
                'conditions': self._get_namespace_conditions(namespace),
                'resource_quota': self._get_namespace_resource_quota(name),
                'limit_ranges': self._get_namespace_limit_ranges(name),
                'resource_usage': self._get_namespace_resource_usage(name)
            }
            
            return namespace_info
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Namespace {name} 不存在"
            else:
                error_msg = f"获取Namespace {name} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def create_namespace(self, name: str, labels: Optional[Dict[str, str]] = None,
                        annotations: Optional[Dict[str, str]] = None) -> str:
        """创建Namespace
        
        Args:
            name: Namespace名称
            labels: 标签
            annotations: 注解
            
        Returns:
            Namespace名称
        """
        try:
            # 构建Namespace对象
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels or {},
                    annotations=annotations or {}
                )
            )
            
            self.k8s_manager.core_v1.create_namespace(body=namespace)
            
            self.log_info(f"Namespace创建成功: {name}")
            return name
            
        except ApiException as e:
            if e.status == 409:
                error_msg = f"Namespace {name} 已存在"
            else:
                error_msg = f"创建Namespace {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def delete_namespace(self, name: str, force: bool = False) -> bool:
        """删除Namespace
        
        Args:
            name: Namespace名称
            force: 是否强制删除
            
        Returns:
            是否删除成功
        """
        try:
            # 检查是否为系统命名空间
            system_namespaces = ['default', 'kube-system', 'kube-public', 'kube-node-lease']
            if name in system_namespaces and not force:
                raise K8sNamespaceError(f"不能删除系统命名空间 {name}，如需强制删除请设置force=True")
            
            # 删除选项
            delete_options = client.V1DeleteOptions()
            if force:
                delete_options.grace_period_seconds = 0
                delete_options.propagation_policy = 'Background'
            
            self.k8s_manager.core_v1.delete_namespace(
                name=name,
                body=delete_options
            )
            
            self.log_info(f"Namespace删除成功: {name}")
            return True
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Namespace {name} 不存在"
            else:
                error_msg = f"删除Namespace {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def update_namespace(self, name: str, labels: Optional[Dict[str, str]] = None,
                        annotations: Optional[Dict[str, str]] = None) -> bool:
        """更新Namespace
        
        Args:
            name: Namespace名称
            labels: 新的标签
            annotations: 新的注解
            
        Returns:
            是否更新成功
        """
        try:
            # 获取当前Namespace
            namespace = self.k8s_manager.core_v1.read_namespace(name)
            
            # 更新标签
            if labels is not None:
                if namespace.metadata.labels:
                    namespace.metadata.labels.update(labels)
                else:
                    namespace.metadata.labels = labels
            
            # 更新注解
            if annotations is not None:
                if namespace.metadata.annotations:
                    namespace.metadata.annotations.update(annotations)
                else:
                    namespace.metadata.annotations = annotations
            
            # 应用更新
            self.k8s_manager.core_v1.patch_namespace(
                name=name,
                body=namespace
            )
            
            self.log_info(f"Namespace更新成功: {name}")
            return True
            
        except ApiException as e:
            error_msg = f"更新Namespace {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def create_resource_quota(self, namespace: str, name: str,
                             hard_limits: Dict[str, str]) -> str:
        """为Namespace创建资源配额
        
        Args:
            namespace: 命名空间名称
            name: ResourceQuota名称
            hard_limits: 资源限制，如 {'cpu': '2', 'memory': '4Gi', 'pods': '10'}
            
        Returns:
            ResourceQuota名称
        """
        try:
            resource_quota = client.V1ResourceQuota(
                metadata=client.V1ObjectMeta(name=name),
                spec=client.V1ResourceQuotaSpec(hard=hard_limits)
            )
            
            self.k8s_manager.core_v1.create_namespaced_resource_quota(
                namespace=namespace,
                body=resource_quota
            )
            
            self.log_info(f"ResourceQuota创建成功: {name} 在命名空间 {namespace}")
            return name
            
        except ApiException as e:
            error_msg = f"创建ResourceQuota {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def create_limit_range(self, namespace: str, name: str,
                          limits: List[Dict[str, Any]]) -> str:
        """为Namespace创建资源限制范围
        
        Args:
            namespace: 命名空间名称
            name: LimitRange名称
            limits: 限制配置列表
            
        Returns:
            LimitRange名称
        """
        try:
            limit_range_items = []
            for limit_config in limits:
                limit_range_item = client.V1LimitRangeItem(
                    type=limit_config['type'],  # Container, Pod, PersistentVolumeClaim
                    default=limit_config.get('default'),
                    default_request=limit_config.get('default_request'),
                    max=limit_config.get('max'),
                    min=limit_config.get('min'),
                    max_limit_request_ratio=limit_config.get('max_limit_request_ratio')
                )
                limit_range_items.append(limit_range_item)
            
            limit_range = client.V1LimitRange(
                metadata=client.V1ObjectMeta(name=name),
                spec=client.V1LimitRangeSpec(limits=limit_range_items)
            )
            
            self.k8s_manager.core_v1.create_namespaced_limit_range(
                namespace=namespace,
                body=limit_range
            )
            
            self.log_info(f"LimitRange创建成功: {name} 在命名空间 {namespace}")
            return name
            
        except ApiException as e:
            error_msg = f"创建LimitRange {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def get_namespace_events(self, namespace: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取Namespace中的事件
        
        Args:
            namespace: 命名空间名称
            limit: 事件数量限制
            
        Returns:
            事件列表
        """
        try:
            events = self.k8s_manager.core_v1.list_namespaced_event(
                namespace=namespace,
                limit=limit
            )
            
            result = []
            for event in events.items:
                event_info = {
                    'name': event.metadata.name,
                    'namespace': event.metadata.namespace,
                    'type': event.type,
                    'reason': event.reason,
                    'message': event.message,
                    'source': event.source.component if event.source else '',
                    'object': {
                        'kind': event.involved_object.kind,
                        'name': event.involved_object.name,
                        'namespace': event.involved_object.namespace
                    } if event.involved_object else {},
                    'first_timestamp': event.first_timestamp,
                    'last_timestamp': event.last_timestamp,
                    'count': event.count
                }
                result.append(event_info)
            
            # 按时间排序
            result.sort(key=lambda x: x['last_timestamp'] or x['first_timestamp'], reverse=True)
            
            return result
            
        except ApiException as e:
            error_msg = f"获取命名空间 {namespace} 的事件失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def get_namespace_resources(self, namespace: str) -> Dict[str, Any]:
        """获取Namespace中的资源统计
        
        Args:
            namespace: 命名空间名称
            
        Returns:
            资源统计信息
        """
        try:
            resources = {
                'pods': 0,
                'services': 0,
                'deployments': 0,
                'replica_sets': 0,
                'config_maps': 0,
                'secrets': 0,
                'persistent_volume_claims': 0,
                'ingresses': 0
            }
            
            # 统计各种资源数量
            try:
                pods = self.k8s_manager.core_v1.list_namespaced_pod(namespace)
                resources['pods'] = len(pods.items)
            except:
                pass
            
            try:
                services = self.k8s_manager.core_v1.list_namespaced_service(namespace)
                resources['services'] = len(services.items)
            except:
                pass
            
            try:
                deployments = self.k8s_manager.apps_v1.list_namespaced_deployment(namespace)
                resources['deployments'] = len(deployments.items)
            except:
                pass
            
            try:
                replica_sets = self.k8s_manager.apps_v1.list_namespaced_replica_set(namespace)
                resources['replica_sets'] = len(replica_sets.items)
            except:
                pass
            
            try:
                config_maps = self.k8s_manager.core_v1.list_namespaced_config_map(namespace)
                resources['config_maps'] = len(config_maps.items)
            except:
                pass
            
            try:
                secrets = self.k8s_manager.core_v1.list_namespaced_secret(namespace)
                resources['secrets'] = len(secrets.items)
            except:
                pass
            
            try:
                pvcs = self.k8s_manager.core_v1.list_namespaced_persistent_volume_claim(namespace)
                resources['persistent_volume_claims'] = len(pvcs.items)
            except:
                pass
            
            return resources
            
        except ApiException as e:
            error_msg = f"获取命名空间 {namespace} 的资源统计失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sNamespaceError(error_msg)
    
    def _get_namespace_conditions(self, namespace) -> List[Dict[str, Any]]:
        """获取Namespace条件"""
        if not namespace.status.conditions:
            return []
        
        return [{
            'type': condition.type,
            'status': condition.status,
            'last_transition_time': condition.last_transition_time,
            'reason': condition.reason,
            'message': condition.message
        } for condition in namespace.status.conditions]
    
    def _get_namespace_resource_quota(self, namespace: str) -> List[Dict[str, Any]]:
        """获取Namespace的ResourceQuota"""
        try:
            quotas = self.k8s_manager.core_v1.list_namespaced_resource_quota(namespace)
            
            result = []
            for quota in quotas.items:
                quota_info = {
                    'name': quota.metadata.name,
                    'hard': quota.spec.hard or {},
                    'used': quota.status.used or {}
                }
                result.append(quota_info)
            
            return result
        except:
            return []
    
    def _get_namespace_limit_ranges(self, namespace: str) -> List[Dict[str, Any]]:
        """获取Namespace的LimitRange"""
        try:
            limit_ranges = self.k8s_manager.core_v1.list_namespaced_limit_range(namespace)
            
            result = []
            for lr in limit_ranges.items:
                limits = []
                for limit in lr.spec.limits:
                    limits.append({
                        'type': limit.type,
                        'default': limit.default or {},
                        'default_request': limit.default_request or {},
                        'max': limit.max or {},
                        'min': limit.min or {}
                    })
                
                result.append({
                    'name': lr.metadata.name,
                    'limits': limits
                })
            
            return result
        except:
            return []
    
    def _get_namespace_resource_usage(self, namespace: str) -> Dict[str, Any]:
        """获取Namespace的资源使用情况"""
        try:
            # 这里可以通过metrics API获取实际的资源使用情况
            # 由于需要metrics-server，这里返回基本信息
            return {
                'cpu_usage': 'N/A',
                'memory_usage': 'N/A',
                'storage_usage': 'N/A'
            }
        except:
            return {}