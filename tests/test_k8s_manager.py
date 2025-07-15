#!/usr/bin/env python3
"""Kubernetes管理器测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.k8s_manager.k8s_client import K8sManager
from src.k8s_manager.pod_manager import PodManager
from src.k8s_manager.deployment_manager import DeploymentManager
from src.k8s_manager.service_manager import ServiceManager
from src.common.exceptions import K8sConnectionError, PodNotFoundError


class TestK8sManager:
    """Kubernetes管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.k8s_manager = K8sManager()
    
    @patch('kubernetes.config.load_incluster_config')
    @patch('kubernetes.client.ApiClient')
    def test_connect_in_cluster(self, mock_api_client, mock_load_config):
        """测试集群内连接"""
        mock_client = Mock()
        mock_api_client.return_value = mock_client
        
        self.k8s_manager.connect(config_type='in_cluster')
        
        mock_load_config.assert_called_once()
        assert self.k8s_manager.api_client is not None
    
    @patch('kubernetes.config.load_kube_config')
    @patch('kubernetes.client.ApiClient')
    def test_connect_kube_config(self, mock_api_client, mock_load_config):
        """测试kubeconfig连接"""
        mock_client = Mock()
        mock_api_client.return_value = mock_client
        
        self.k8s_manager.connect(config_type='kube_config')
        
        mock_load_config.assert_called_once()
        assert self.k8s_manager.api_client is not None
    
    @patch('kubernetes.config.load_incluster_config')
    def test_connect_failure(self, mock_load_config):
        """测试连接失败"""
        mock_load_config.side_effect = Exception("Connection failed")
        
        with pytest.raises(K8sConnectionError):
            self.k8s_manager.connect()
    
    def test_get_cluster_info(self):
        """测试获取集群信息"""
        mock_version_api = Mock()
        mock_version_api.get_code.return_value = Mock(
            git_version='v1.21.0',
            platform='linux/amd64'
        )
        
        with patch('kubernetes.client.VersionApi', return_value=mock_version_api):
            self.k8s_manager.api_client = Mock()
            info = self.k8s_manager.get_cluster_info()
            
            assert 'server_version' in info
            assert info['server_version'] == 'v1.21.0'
    
    def test_get_nodes(self):
        """测试获取节点列表"""
        mock_core_api = Mock()
        mock_node = Mock()
        mock_node.metadata.name = 'node-1'
        mock_node.metadata.creation_timestamp = datetime.now()
        mock_node.metadata.labels = {'kubernetes.io/role': 'master'}
        mock_node.status.conditions = [
            Mock(type='Ready', status='True')
        ]
        mock_node.status.node_info.kubelet_version = 'v1.21.0'
        
        mock_core_api.list_node.return_value = Mock(items=[mock_node])
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            nodes = self.k8s_manager.get_nodes()
            
            assert len(nodes) == 1
            assert nodes[0]['name'] == 'node-1'
            assert nodes[0]['status'] == 'Ready'
            assert 'master' in nodes[0]['roles']


class TestPodManager:
    """Pod管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.k8s_manager = Mock()
        self.pod_manager = PodManager(self.k8s_manager)
    
    def test_list_pods(self):
        """测试列出Pod"""
        mock_core_api = Mock()
        mock_pod = Mock()
        mock_pod.metadata.name = 'test-pod'
        mock_pod.metadata.namespace = 'default'
        mock_pod.metadata.creation_timestamp = datetime.now()
        mock_pod.status.phase = 'Running'
        mock_pod.status.container_statuses = [
            Mock(ready=True, restart_count=0),
            Mock(ready=True, restart_count=1)
        ]
        mock_pod.spec.containers = [Mock(), Mock()]
        
        mock_core_api.list_namespaced_pod.return_value = Mock(items=[mock_pod])
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            pods = self.pod_manager.list_pods(namespace='default')
            
            assert len(pods) == 1
            assert pods[0]['name'] == 'test-pod'
            assert pods[0]['namespace'] == 'default'
            assert pods[0]['status'] == 'Running'
            assert pods[0]['ready_containers'] == 2
            assert pods[0]['total_containers'] == 2
            assert pods[0]['restart_count'] == 1
    
    def test_get_pod_success(self):
        """测试获取Pod成功"""
        mock_core_api = Mock()
        mock_pod = Mock()
        mock_pod.metadata.name = 'test-pod'
        mock_pod.metadata.namespace = 'default'
        mock_pod.metadata.creation_timestamp = datetime.now()
        mock_pod.status.phase = 'Running'
        mock_pod.status.container_statuses = [Mock(ready=True, restart_count=0)]
        mock_pod.spec.containers = [Mock()]
        
        mock_core_api.read_namespaced_pod.return_value = mock_pod
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            pod = self.pod_manager.get_pod('test-pod', namespace='default')
            
            assert pod['name'] == 'test-pod'
            assert pod['namespace'] == 'default'
            assert pod['status'] == 'Running'
    
    def test_get_pod_not_found(self):
        """测试获取不存在的Pod"""
        mock_core_api = Mock()
        mock_core_api.read_namespaced_pod.side_effect = Exception("Pod not found")
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            with pytest.raises(PodNotFoundError):
                self.pod_manager.get_pod('nonexistent', namespace='default')
    
    def test_create_pod(self):
        """测试创建Pod"""
        mock_core_api = Mock()
        mock_pod = Mock()
        mock_pod.metadata.name = 'new-pod'
        mock_core_api.create_namespaced_pod.return_value = mock_pod
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            pod_spec = {
                'apiVersion': 'v1',
                'kind': 'Pod',
                'metadata': {'name': 'new-pod'},
                'spec': {
                    'containers': [{
                        'name': 'nginx',
                        'image': 'nginx:latest'
                    }]
                }
            }
            
            result = self.pod_manager.create_pod(pod_spec, namespace='default')
            
            assert result['name'] == 'new-pod'
            mock_core_api.create_namespaced_pod.assert_called_once()
    
    def test_delete_pod(self):
        """测试删除Pod"""
        mock_core_api = Mock()
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            self.pod_manager.delete_pod('test-pod', namespace='default')
            
            mock_core_api.delete_namespaced_pod.assert_called_once_with(
                name='test-pod',
                namespace='default'
            )
    
    def test_get_pod_logs(self):
        """测试获取Pod日志"""
        mock_core_api = Mock()
        mock_core_api.read_namespaced_pod_log.return_value = 'log line 1\nlog line 2\n'
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            logs = self.pod_manager.get_pod_logs(
                'test-pod',
                namespace='default',
                tail_lines=10
            )
            
            assert 'log line 1' in logs
            assert 'log line 2' in logs
            mock_core_api.read_namespaced_pod_log.assert_called_once()


class TestDeploymentManager:
    """Deployment管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.k8s_manager = Mock()
        self.deployment_manager = DeploymentManager(self.k8s_manager)
    
    def test_list_deployments(self):
        """测试列出Deployment"""
        mock_apps_api = Mock()
        mock_deployment = Mock()
        mock_deployment.metadata.name = 'test-deployment'
        mock_deployment.metadata.namespace = 'default'
        mock_deployment.metadata.creation_timestamp = datetime.now()
        mock_deployment.spec.replicas = 3
        mock_deployment.status.replicas = 3
        mock_deployment.status.ready_replicas = 2
        mock_deployment.status.updated_replicas = 3
        mock_deployment.status.available_replicas = 2
        
        mock_apps_api.list_namespaced_deployment.return_value = Mock(items=[mock_deployment])
        
        with patch('kubernetes.client.AppsV1Api', return_value=mock_apps_api):
            self.k8s_manager.api_client = Mock()
            deployments = self.deployment_manager.list_deployments(namespace='default')
            
            assert len(deployments) == 1
            assert deployments[0]['name'] == 'test-deployment'
            assert deployments[0]['namespace'] == 'default'
            assert deployments[0]['replicas'] == 3
            assert deployments[0]['ready_replicas'] == 2
    
    def test_scale_deployment(self):
        """测试扩缩容Deployment"""
        mock_apps_api = Mock()
        mock_deployment = Mock()
        mock_deployment.spec.replicas = 5
        mock_apps_api.read_namespaced_deployment.return_value = mock_deployment
        
        with patch('kubernetes.client.AppsV1Api', return_value=mock_apps_api):
            self.k8s_manager.api_client = Mock()
            
            self.deployment_manager.scale_deployment(
                'test-deployment',
                replicas=5,
                namespace='default'
            )
            
            mock_apps_api.patch_namespaced_deployment.assert_called_once()
            # 验证replicas被设置为5
            call_args = mock_apps_api.patch_namespaced_deployment.call_args
            assert call_args[1]['body']['spec']['replicas'] == 5
    
    def test_create_deployment(self):
        """测试创建Deployment"""
        mock_apps_api = Mock()
        mock_deployment = Mock()
        mock_deployment.metadata.name = 'new-deployment'
        mock_apps_api.create_namespaced_deployment.return_value = mock_deployment
        
        with patch('kubernetes.client.AppsV1Api', return_value=mock_apps_api):
            self.k8s_manager.api_client = Mock()
            
            deployment_spec = {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {'name': 'new-deployment'},
                'spec': {
                    'replicas': 3,
                    'selector': {'matchLabels': {'app': 'nginx'}},
                    'template': {
                        'metadata': {'labels': {'app': 'nginx'}},
                        'spec': {
                            'containers': [{
                                'name': 'nginx',
                                'image': 'nginx:latest'
                            }]
                        }
                    }
                }
            }
            
            result = self.deployment_manager.create_deployment(
                deployment_spec,
                namespace='default'
            )
            
            assert result['name'] == 'new-deployment'
            mock_apps_api.create_namespaced_deployment.assert_called_once()


class TestServiceManager:
    """Service管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.k8s_manager = Mock()
        self.service_manager = ServiceManager(self.k8s_manager)
    
    def test_list_services(self):
        """测试列出Service"""
        mock_core_api = Mock()
        mock_service = Mock()
        mock_service.metadata.name = 'test-service'
        mock_service.metadata.namespace = 'default'
        mock_service.metadata.creation_timestamp = datetime.now()
        mock_service.spec.type = 'ClusterIP'
        mock_service.spec.cluster_ip = '10.0.0.1'
        mock_service.spec.ports = [
            Mock(port=80, protocol='TCP', target_port=8080)
        ]
        mock_service.status.load_balancer.ingress = None
        
        mock_core_api.list_namespaced_service.return_value = Mock(items=[mock_service])
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            services = self.service_manager.list_services(namespace='default')
            
            assert len(services) == 1
            assert services[0]['name'] == 'test-service'
            assert services[0]['namespace'] == 'default'
            assert services[0]['type'] == 'ClusterIP'
            assert services[0]['cluster_ip'] == '10.0.0.1'
    
    def test_create_service(self):
        """测试创建Service"""
        mock_core_api = Mock()
        mock_service = Mock()
        mock_service.metadata.name = 'new-service'
        mock_core_api.create_namespaced_service.return_value = mock_service
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            service_spec = {
                'apiVersion': 'v1',
                'kind': 'Service',
                'metadata': {'name': 'new-service'},
                'spec': {
                    'selector': {'app': 'nginx'},
                    'ports': [{
                        'port': 80,
                        'targetPort': 8080
                    }]
                }
            }
            
            result = self.service_manager.create_service(
                service_spec,
                namespace='default'
            )
            
            assert result['name'] == 'new-service'
            mock_core_api.create_namespaced_service.assert_called_once()
    
    def test_delete_service(self):
        """测试删除Service"""
        mock_core_api = Mock()
        
        with patch('kubernetes.client.CoreV1Api', return_value=mock_core_api):
            self.k8s_manager.api_client = Mock()
            
            self.service_manager.delete_service('test-service', namespace='default')
            
            mock_core_api.delete_namespaced_service.assert_called_once_with(
                name='test-service',
                namespace='default'
            )


if __name__ == '__main__':
    pytest.main([__file__])