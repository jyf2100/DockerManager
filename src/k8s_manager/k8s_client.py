"""Kubernetes客户端管理器"""

import os
from typing import Dict, Any, Optional, List
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ..common.logger import LoggerMixin
from ..common.exceptions import K8sConnectionError, K8sManagerError
from ..common.config import ConfigManager


class K8sManager(LoggerMixin):
    """Kubernetes管理器
    
    负责Kubernetes集群连接和基础操作
    """
    
    def __init__(self, config_manager: ConfigManager, cluster_name: Optional[str] = None):
        """初始化Kubernetes管理器
        
        Args:
            config_manager: 配置管理器实例
            cluster_name: 集群名称，不指定则使用默认集群
        """
        super().__init__()
        self.config_manager = config_manager
        self.cluster_name = cluster_name or config_manager.get('kubernetes.default_cluster', 'local-cluster')
        self.current_namespace = 'default'
        
        # Kubernetes API客户端
        self.core_v1 = None
        self.apps_v1 = None
        self.networking_v1 = None
        self.rbac_v1 = None
        
        self._connect()
    
    def _connect(self) -> None:
        """连接到Kubernetes集群"""
        try:
            # 获取集群配置
            clusters = self.config_manager.get('kubernetes.clusters', [])
            cluster_config = None
            
            for cluster in clusters:
                if cluster.get('name') == self.cluster_name:
                    cluster_config = cluster
                    break
            
            if not cluster_config:
                raise K8sConnectionError(f"未找到集群配置: {self.cluster_name}")
            
            # 加载kubeconfig
            config_file = os.path.expanduser(cluster_config.get('config_file', '~/.kube/config'))
            context = cluster_config.get('context')
            self.current_namespace = cluster_config.get('namespace', 'default')
            
            if os.path.exists(config_file):
                config.load_kube_config(config_file=config_file, context=context)
            else:
                # 尝试集群内配置
                config.load_incluster_config()
            
            # 初始化API客户端
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.networking_v1 = client.NetworkingV1Api()
            self.rbac_v1 = client.RbacAuthorizationV1Api()
            
            # 测试连接
            self.core_v1.list_namespace(limit=1)
            
            self.log_info(f"成功连接到Kubernetes集群: {self.cluster_name}")
            
        except Exception as e:
            error_msg = f"连接Kubernetes集群失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sConnectionError(error_msg)
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """获取集群信息
        
        Returns:
            集群信息字典
        """
        try:
            # 获取集群版本信息
            version_info = client.VersionApi().get_code()
            
            # 获取节点信息
            nodes = self.core_v1.list_node()
            
            # 获取命名空间信息
            namespaces = self.core_v1.list_namespace()
            
            # 统计资源
            pods = self.core_v1.list_pod_for_all_namespaces()
            services = self.core_v1.list_service_for_all_namespaces()
            deployments = self.apps_v1.list_deployment_for_all_namespaces()
            
            cluster_info = {
                'cluster_name': self.cluster_name,
                'version': {
                    'major': version_info.major,
                    'minor': version_info.minor,
                    'git_version': version_info.git_version,
                    'git_commit': version_info.git_commit,
                    'platform': version_info.platform
                },
                'nodes': {
                    'total': len(nodes.items),
                    'ready': sum(1 for node in nodes.items 
                               if any(condition.type == 'Ready' and condition.status == 'True' 
                                    for condition in node.status.conditions))
                },
                'namespaces': {
                    'total': len(namespaces.items),
                    'active': sum(1 for ns in namespaces.items 
                                if ns.status.phase == 'Active')
                },
                'resources': {
                    'pods': len(pods.items),
                    'services': len(services.items),
                    'deployments': len(deployments.items)
                },
                'current_namespace': self.current_namespace
            }
            
            return cluster_info
            
        except ApiException as e:
            error_msg = f"获取集群信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def get_node_info(self) -> List[Dict[str, Any]]:
        """获取节点信息
        
        Returns:
            节点信息列表
        """
        try:
            nodes = self.core_v1.list_node()
            
            result = []
            for node in nodes.items:
                # 获取节点状态
                conditions = {condition.type: condition.status 
                            for condition in node.status.conditions}
                
                # 获取节点资源
                capacity = node.status.capacity or {}
                allocatable = node.status.allocatable or {}
                
                # 获取节点标签和注解
                labels = node.metadata.labels or {}
                annotations = node.metadata.annotations or {}
                
                node_info = {
                    'name': node.metadata.name,
                    'status': 'Ready' if conditions.get('Ready') == 'True' else 'NotReady',
                    'roles': self._get_node_roles(labels),
                    'age': node.metadata.creation_timestamp,
                    'version': node.status.node_info.kubelet_version,
                    'internal_ip': self._get_node_internal_ip(node),
                    'external_ip': self._get_node_external_ip(node),
                    'os': f"{node.status.node_info.operating_system}/{node.status.node_info.architecture}",
                    'kernel': node.status.node_info.kernel_version,
                    'container_runtime': node.status.node_info.container_runtime_version,
                    'capacity': {
                        'cpu': capacity.get('cpu', '0'),
                        'memory': capacity.get('memory', '0'),
                        'pods': capacity.get('pods', '0'),
                        'storage': capacity.get('ephemeral-storage', '0')
                    },
                    'allocatable': {
                        'cpu': allocatable.get('cpu', '0'),
                        'memory': allocatable.get('memory', '0'),
                        'pods': allocatable.get('pods', '0'),
                        'storage': allocatable.get('ephemeral-storage', '0')
                    },
                    'conditions': conditions,
                    'labels': labels,
                    'taints': [{'key': taint.key, 'value': taint.value, 'effect': taint.effect} 
                             for taint in (node.spec.taints or [])]
                }
                
                result.append(node_info)
            
            self.log_info(f"获取节点信息成功，共 {len(result)} 个节点")
            return result
            
        except ApiException as e:
            error_msg = f"获取节点信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def _get_node_roles(self, labels: Dict[str, str]) -> List[str]:
        """获取节点角色"""
        roles = []
        for label_key in labels:
            if label_key.startswith('node-role.kubernetes.io/'):
                role = label_key.split('/')[-1]
                if role:
                    roles.append(role)
        return roles or ['worker']
    
    def _get_node_internal_ip(self, node) -> str:
        """获取节点内部IP"""
        for address in node.status.addresses or []:
            if address.type == 'InternalIP':
                return address.address
        return ''
    
    def _get_node_external_ip(self, node) -> str:
        """获取节点外部IP"""
        for address in node.status.addresses or []:
            if address.type == 'ExternalIP':
                return address.address
        return ''
    
    def get_namespaces(self) -> List[Dict[str, Any]]:
        """获取命名空间列表
        
        Returns:
            命名空间信息列表
        """
        try:
            namespaces = self.core_v1.list_namespace()
            
            result = []
            for ns in namespaces.items:
                ns_info = {
                    'name': ns.metadata.name,
                    'status': ns.status.phase,
                    'age': ns.metadata.creation_timestamp,
                    'labels': ns.metadata.labels or {},
                    'annotations': ns.metadata.annotations or {}
                }
                result.append(ns_info)
            
            self.log_info(f"获取命名空间列表成功，共 {len(result)} 个命名空间")
            return result
            
        except ApiException as e:
            error_msg = f"获取命名空间列表失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def set_namespace(self, namespace: str) -> None:
        """设置当前命名空间
        
        Args:
            namespace: 命名空间名称
        """
        try:
            # 验证命名空间是否存在
            self.core_v1.read_namespace(namespace)
            self.current_namespace = namespace
            self.log_info(f"切换到命名空间: {namespace}")
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"命名空间 {namespace} 不存在"
            else:
                error_msg = f"切换命名空间失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def create_namespace(self, name: str, labels: Optional[Dict[str, str]] = None) -> bool:
        """创建命名空间
        
        Args:
            name: 命名空间名称
            labels: 标签
            
        Returns:
            是否创建成功
        """
        try:
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels or {}
                )
            )
            
            self.core_v1.create_namespace(namespace)
            self.log_info(f"命名空间创建成功: {name}")
            return True
            
        except ApiException as e:
            error_msg = f"创建命名空间 {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def delete_namespace(self, name: str) -> bool:
        """删除命名空间
        
        Args:
            name: 命名空间名称
            
        Returns:
            是否删除成功
        """
        try:
            self.core_v1.delete_namespace(name)
            self.log_info(f"命名空间删除成功: {name}")
            return True
            
        except ApiException as e:
            error_msg = f"删除命名空间 {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def get_resource_quota(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取资源配额信息
        
        Args:
            namespace: 命名空间，不指定则使用当前命名空间
            
        Returns:
            资源配额信息
        """
        namespace = namespace or self.current_namespace
        
        try:
            # 获取ResourceQuota
            quotas = self.core_v1.list_namespaced_resource_quota(namespace)
            
            # 获取LimitRange
            limit_ranges = self.core_v1.list_namespaced_limit_range(namespace)
            
            result = {
                'namespace': namespace,
                'resource_quotas': [],
                'limit_ranges': []
            }
            
            for quota in quotas.items:
                quota_info = {
                    'name': quota.metadata.name,
                    'hard': quota.status.hard or {},
                    'used': quota.status.used or {}
                }
                result['resource_quotas'].append(quota_info)
            
            for limit_range in limit_ranges.items:
                lr_info = {
                    'name': limit_range.metadata.name,
                    'limits': []
                }
                
                for limit in limit_range.spec.limits or []:
                    lr_info['limits'].append({
                        'type': limit.type,
                        'default': limit.default or {},
                        'default_request': limit.default_request or {},
                        'max': limit.max or {},
                        'min': limit.min or {}
                    })
                
                result['limit_ranges'].append(lr_info)
            
            return result
            
        except ApiException as e:
            error_msg = f"获取资源配额信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sManagerError(error_msg)
    
    def switch_cluster(self, cluster_name: str) -> None:
        """切换集群
        
        Args:
            cluster_name: 集群名称
        """
        self.cluster_name = cluster_name
        self._connect()