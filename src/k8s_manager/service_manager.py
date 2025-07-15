"""Kubernetes Service管理器"""

from typing import List, Dict, Any, Optional
from kubernetes import client
from kubernetes.client.rest import ApiException

from ..common.logger import LoggerMixin
from ..common.exceptions import K8sServiceError
from .k8s_client import K8sManager


class ServiceManager(LoggerMixin):
    """Kubernetes Service管理器
    
    负责Service的创建、更新、删除等操作
    """
    
    def __init__(self, k8s_manager: K8sManager):
        """初始化Service管理器
        
        Args:
            k8s_manager: Kubernetes管理器实例
        """
        super().__init__()
        self.k8s_manager = k8s_manager
    
    def list_services(self, namespace: Optional[str] = None,
                     label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出Service
        
        Args:
            namespace: 命名空间，不指定则使用当前命名空间
            label_selector: 标签选择器
            
        Returns:
            Service信息列表
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            if namespace == 'all':
                services = self.k8s_manager.core_v1.list_service_for_all_namespaces(
                    label_selector=label_selector
                )
            else:
                services = self.k8s_manager.core_v1.list_namespaced_service(
                    namespace=namespace,
                    label_selector=label_selector
                )
            
            result = []
            for service in services.items:
                service_info = {
                    'name': service.metadata.name,
                    'namespace': service.metadata.namespace,
                    'type': service.spec.type,
                    'cluster_ip': service.spec.cluster_ip,
                    'external_ips': service.spec.external_i_ps or [],
                    'ports': self._get_service_ports(service),
                    'selector': service.spec.selector or {},
                    'age': service.metadata.creation_timestamp,
                    'labels': service.metadata.labels or {},
                    'session_affinity': service.spec.session_affinity
                }
                
                # 添加LoadBalancer特定信息
                if service.spec.type == 'LoadBalancer':
                    service_info['load_balancer_ip'] = service.spec.load_balancer_ip
                    if service.status.load_balancer and service.status.load_balancer.ingress:
                        service_info['external_endpoints'] = [
                            ingress.ip or ingress.hostname
                            for ingress in service.status.load_balancer.ingress
                        ]
                
                # 添加NodePort特定信息
                if service.spec.type == 'NodePort':
                    service_info['node_ports'] = [
                        port.node_port for port in service.spec.ports if port.node_port
                    ]
                
                result.append(service_info)
            
            self.log_info(f"获取Service列表成功，共 {len(result)} 个Service")
            return result
            
        except ApiException as e:
            error_msg = f"获取Service列表失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def get_service(self, name: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """获取Service详细信息
        
        Args:
            name: Service名称
            namespace: 命名空间
            
        Returns:
            Service详细信息
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            service = self.k8s_manager.core_v1.read_namespaced_service(name, namespace)
            
            service_info = {
                'name': service.metadata.name,
                'namespace': service.metadata.namespace,
                'uid': service.metadata.uid,
                'type': service.spec.type,
                'cluster_ip': service.spec.cluster_ip,
                'external_ips': service.spec.external_i_ps or [],
                'ports': self._get_service_ports(service),
                'selector': service.spec.selector or {},
                'session_affinity': service.spec.session_affinity,
                'age': service.metadata.creation_timestamp,
                'labels': service.metadata.labels or {},
                'annotations': service.metadata.annotations or {},
                'endpoints': self._get_service_endpoints(name, namespace)
            }
            
            # LoadBalancer特定信息
            if service.spec.type == 'LoadBalancer':
                service_info['load_balancer_ip'] = service.spec.load_balancer_ip
                service_info['load_balancer_source_ranges'] = service.spec.load_balancer_source_ranges or []
                if service.status.load_balancer and service.status.load_balancer.ingress:
                    service_info['external_endpoints'] = [
                        {
                            'ip': ingress.ip,
                            'hostname': ingress.hostname,
                            'ports': ingress.ports or []
                        }
                        for ingress in service.status.load_balancer.ingress
                    ]
            
            # NodePort特定信息
            if service.spec.type == 'NodePort':
                service_info['node_ports'] = [
                    {
                        'port': port.port,
                        'target_port': port.target_port,
                        'node_port': port.node_port,
                        'protocol': port.protocol
                    }
                    for port in service.spec.ports if port.node_port
                ]
            
            # ExternalName特定信息
            if service.spec.type == 'ExternalName':
                service_info['external_name'] = service.spec.external_name
            
            return service_info
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Service {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"获取Service {name} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def create_service(self, name: str, selector: Dict[str, str],
                      ports: List[Dict[str, Any]],
                      namespace: Optional[str] = None,
                      service_type: str = 'ClusterIP',
                      labels: Optional[Dict[str, str]] = None,
                      external_ips: Optional[List[str]] = None,
                      load_balancer_ip: Optional[str] = None,
                      external_name: Optional[str] = None) -> str:
        """创建Service
        
        Args:
            name: Service名称
            selector: Pod选择器
            ports: 端口配置列表，格式: [{'port': 80, 'target_port': 8080, 'protocol': 'TCP'}]
            namespace: 命名空间
            service_type: Service类型 (ClusterIP, NodePort, LoadBalancer, ExternalName)
            labels: 标签
            external_ips: 外部IP列表
            load_balancer_ip: LoadBalancer IP
            external_name: 外部名称 (仅ExternalName类型)
            
        Returns:
            Service名称
        """
        namespace = namespace or self.k8s_manager.current_namespace
        labels = labels or {'app': name}
        
        try:
            # 构建端口配置
            service_ports = []
            for port_config in ports:
                service_port = client.V1ServicePort(
                    port=port_config['port'],
                    target_port=port_config.get('target_port', port_config['port']),
                    protocol=port_config.get('protocol', 'TCP'),
                    name=port_config.get('name', f"port-{port_config['port']}")
                )
                
                # NodePort类型需要指定node_port
                if service_type == 'NodePort' and 'node_port' in port_config:
                    service_port.node_port = port_config['node_port']
                
                service_ports.append(service_port)
            
            # 构建Service规格
            service_spec = client.V1ServiceSpec(
                type=service_type,
                ports=service_ports
            )
            
            # 根据Service类型设置不同的配置
            if service_type != 'ExternalName':
                service_spec.selector = selector
                
                if external_ips:
                    service_spec.external_i_ps = external_ips
                
                if service_type == 'LoadBalancer' and load_balancer_ip:
                    service_spec.load_balancer_ip = load_balancer_ip
            else:
                if not external_name:
                    raise K8sServiceError("ExternalName类型的Service必须指定external_name")
                service_spec.external_name = external_name
            
            # 创建Service
            service = client.V1Service(
                metadata=client.V1ObjectMeta(name=name, labels=labels),
                spec=service_spec
            )
            
            self.k8s_manager.core_v1.create_namespaced_service(
                namespace=namespace,
                body=service
            )
            
            self.log_info(f"Service创建成功: {name} ({service_type}) 在命名空间 {namespace}")
            return name
            
        except ApiException as e:
            error_msg = f"创建Service {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def update_service(self, name: str, namespace: Optional[str] = None,
                      selector: Optional[Dict[str, str]] = None,
                      ports: Optional[List[Dict[str, Any]]] = None,
                      external_ips: Optional[List[str]] = None) -> bool:
        """更新Service
        
        Args:
            name: Service名称
            namespace: 命名空间
            selector: 新的Pod选择器
            ports: 新的端口配置
            external_ips: 新的外部IP列表
            
        Returns:
            是否更新成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            # 获取当前Service
            service = self.k8s_manager.core_v1.read_namespaced_service(name, namespace)
            
            # 更新选择器
            if selector is not None:
                service.spec.selector = selector
            
            # 更新端口配置
            if ports is not None:
                service_ports = []
                for port_config in ports:
                    service_port = client.V1ServicePort(
                        port=port_config['port'],
                        target_port=port_config.get('target_port', port_config['port']),
                        protocol=port_config.get('protocol', 'TCP'),
                        name=port_config.get('name', f"port-{port_config['port']}")
                    )
                    
                    if 'node_port' in port_config:
                        service_port.node_port = port_config['node_port']
                    
                    service_ports.append(service_port)
                
                service.spec.ports = service_ports
            
            # 更新外部IP
            if external_ips is not None:
                service.spec.external_i_ps = external_ips
            
            # 应用更新
            self.k8s_manager.core_v1.patch_namespaced_service(
                name=name,
                namespace=namespace,
                body=service
            )
            
            self.log_info(f"Service更新成功: {name} 在命名空间 {namespace}")
            return True
            
        except ApiException as e:
            error_msg = f"更新Service {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def delete_service(self, name: str, namespace: Optional[str] = None) -> bool:
        """删除Service
        
        Args:
            name: Service名称
            namespace: 命名空间
            
        Returns:
            是否删除成功
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            self.k8s_manager.core_v1.delete_namespaced_service(
                name=name,
                namespace=namespace
            )
            
            self.log_info(f"Service删除成功: {name} 在命名空间 {namespace}")
            return True
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Service {name} 在命名空间 {namespace} 中不存在"
            else:
                error_msg = f"删除Service {name} 失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def expose_deployment(self, deployment_name: str, port: int,
                         target_port: Optional[int] = None,
                         service_type: str = 'ClusterIP',
                         namespace: Optional[str] = None,
                         service_name: Optional[str] = None) -> str:
        """为Deployment创建Service
        
        Args:
            deployment_name: Deployment名称
            port: Service端口
            target_port: 目标端口
            service_type: Service类型
            namespace: 命名空间
            service_name: Service名称，不指定则使用Deployment名称
            
        Returns:
            Service名称
        """
        namespace = namespace or self.k8s_manager.current_namespace
        service_name = service_name or deployment_name
        target_port = target_port or port
        
        try:
            # 获取Deployment的标签作为选择器
            deployment = self.k8s_manager.apps_v1.read_namespaced_deployment(
                deployment_name, namespace
            )
            selector = deployment.spec.selector.match_labels
            
            # 创建Service
            ports = [{
                'port': port,
                'target_port': target_port,
                'protocol': 'TCP'
            }]
            
            return self.create_service(
                name=service_name,
                selector=selector,
                ports=ports,
                namespace=namespace,
                service_type=service_type
            )
            
        except ApiException as e:
            error_msg = f"为Deployment {deployment_name} 创建Service失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def get_service_endpoints(self, name: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取Service的Endpoints
        
        Args:
            name: Service名称
            namespace: 命名空间
            
        Returns:
            Endpoints列表
        """
        namespace = namespace or self.k8s_manager.current_namespace
        
        try:
            endpoints = self.k8s_manager.core_v1.read_namespaced_endpoints(name, namespace)
            
            result = []
            if endpoints.subsets:
                for subset in endpoints.subsets:
                    addresses = []
                    if subset.addresses:
                        addresses.extend([{
                            'ip': addr.ip,
                            'hostname': addr.hostname,
                            'node_name': addr.node_name,
                            'target_ref': {
                                'kind': addr.target_ref.kind,
                                'name': addr.target_ref.name,
                                'namespace': addr.target_ref.namespace
                            } if addr.target_ref else None
                        } for addr in subset.addresses])
                    
                    not_ready_addresses = []
                    if subset.not_ready_addresses:
                        not_ready_addresses.extend([{
                            'ip': addr.ip,
                            'hostname': addr.hostname,
                            'node_name': addr.node_name
                        } for addr in subset.not_ready_addresses])
                    
                    ports = []
                    if subset.ports:
                        ports.extend([{
                            'name': port.name,
                            'port': port.port,
                            'protocol': port.protocol
                        } for port in subset.ports])
                    
                    result.append({
                        'addresses': addresses,
                        'not_ready_addresses': not_ready_addresses,
                        'ports': ports
                    })
            
            return result
            
        except ApiException as e:
            if e.status == 404:
                return []
            error_msg = f"获取Service {name} 的Endpoints失败: {str(e)}"
            self.log_error(error_msg)
            raise K8sServiceError(error_msg)
    
    def _get_service_ports(self, service) -> List[Dict[str, Any]]:
        """获取Service端口信息"""
        if not service.spec.ports:
            return []
        
        return [{
            'name': port.name,
            'port': port.port,
            'target_port': port.target_port,
            'protocol': port.protocol,
            'node_port': port.node_port
        } for port in service.spec.ports]
    
    def _get_service_endpoints(self, name: str, namespace: str) -> List[str]:
        """获取Service的Endpoint IP列表"""
        try:
            endpoints = self.get_service_endpoints(name, namespace)
            ips = []
            for subset in endpoints:
                for addr in subset.get('addresses', []):
                    ips.append(addr['ip'])
            return ips
        except:
            return []