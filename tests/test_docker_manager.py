#!/usr/bin/env python3
"""Docker管理器测试"""

import pytest
import docker
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.docker_manager.docker_client import DockerManager
from src.docker_manager.container_manager import ContainerManager
from src.docker_manager.image_manager import ImageManager
from src.common.exceptions import DockerConnectionError, ContainerNotFoundError


class TestDockerManager:
    """Docker管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.docker_manager = DockerManager()
    
    def teardown_method(self):
        """测试后清理"""
        if hasattr(self.docker_manager, 'client'):
            self.docker_manager.disconnect()
    
    @patch('docker.from_env')
    def test_connect_success(self, mock_docker):
        """测试连接成功"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_docker.return_value = mock_client
        
        self.docker_manager.connect()
        
        assert self.docker_manager.client is not None
        mock_client.ping.assert_called_once()
    
    @patch('docker.from_env')
    def test_connect_failure(self, mock_docker):
        """测试连接失败"""
        mock_docker.side_effect = docker.errors.DockerException("Connection failed")
        
        with pytest.raises(DockerConnectionError):
            self.docker_manager.connect()
    
    @patch('docker.from_env')
    def test_get_system_info(self, mock_docker):
        """测试获取系统信息"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.info.return_value = {
            'ServerVersion': '20.10.0',
            'Containers': 5,
            'Images': 10
        }
        mock_docker.return_value = mock_client
        
        self.docker_manager.connect()
        info = self.docker_manager.get_system_info()
        
        assert info['ServerVersion'] == '20.10.0'
        assert info['Containers'] == 5
        assert info['Images'] == 10
    
    @patch('docker.from_env')
    def test_get_disk_usage(self, mock_docker):
        """测试获取磁盘使用情况"""
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.df.return_value = {
            'LayersSize': 1000000,
            'Images': [{'Size': 500000}],
            'Containers': [{'SizeRw': 100000}]
        }
        mock_docker.return_value = mock_client
        
        self.docker_manager.connect()
        usage = self.docker_manager.get_disk_usage()
        
        assert 'LayersSize' in usage
        assert 'Images' in usage
        assert 'Containers' in usage


class TestContainerManager:
    """容器管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.docker_manager = Mock()
        self.container_manager = ContainerManager(self.docker_manager)
    
    def test_list_containers(self):
        """测试列出容器"""
        mock_container = Mock()
        mock_container.attrs = {
            'Id': 'container123',
            'Name': '/test-container',
            'Config': {'Image': 'nginx:latest'},
            'State': {'Status': 'running'},
            'Created': '2023-01-01T00:00:00Z',
            'NetworkSettings': {'Ports': {}}
        }
        
        self.docker_manager.client.containers.list.return_value = [mock_container]
        
        containers = self.container_manager.list_containers()
        
        assert len(containers) == 1
        assert containers[0]['id'] == 'container123'
        assert containers[0]['name'] == 'test-container'
        assert containers[0]['image'] == 'nginx:latest'
        assert containers[0]['status'] == 'running'
    
    def test_get_container_success(self):
        """测试获取容器成功"""
        mock_container = Mock()
        mock_container.attrs = {
            'Id': 'container123',
            'Name': '/test-container',
            'Config': {'Image': 'nginx:latest'},
            'State': {'Status': 'running'},
            'Created': '2023-01-01T00:00:00Z'
        }
        
        self.docker_manager.client.containers.get.return_value = mock_container
        
        container = self.container_manager.get_container('container123')
        
        assert container['id'] == 'container123'
        assert container['name'] == 'test-container'
    
    def test_get_container_not_found(self):
        """测试获取不存在的容器"""
        self.docker_manager.client.containers.get.side_effect = docker.errors.NotFound("Container not found")
        
        with pytest.raises(ContainerNotFoundError):
            self.container_manager.get_container('nonexistent')
    
    def test_create_container(self):
        """测试创建容器"""
        mock_container = Mock()
        mock_container.id = 'new_container123'
        
        self.docker_manager.client.containers.create.return_value = mock_container
        
        container_id = self.container_manager.create_container(
            image='nginx:latest',
            name='test-nginx'
        )
        
        assert container_id == 'new_container123'
        self.docker_manager.client.containers.create.assert_called_once()
    
    def test_start_container(self):
        """测试启动容器"""
        mock_container = Mock()
        self.docker_manager.client.containers.get.return_value = mock_container
        
        self.container_manager.start_container('container123')
        
        mock_container.start.assert_called_once()
    
    def test_stop_container(self):
        """测试停止容器"""
        mock_container = Mock()
        self.docker_manager.client.containers.get.return_value = mock_container
        
        self.container_manager.stop_container('container123', timeout=10)
        
        mock_container.stop.assert_called_once_with(timeout=10)
    
    def test_remove_container(self):
        """测试删除容器"""
        mock_container = Mock()
        self.docker_manager.client.containers.get.return_value = mock_container
        
        self.container_manager.remove_container('container123', force=True)
        
        mock_container.remove.assert_called_once_with(force=True)
    
    def test_get_container_logs(self):
        """测试获取容器日志"""
        mock_container = Mock()
        mock_container.logs.return_value = b'log line 1\nlog line 2\n'
        self.docker_manager.client.containers.get.return_value = mock_container
        
        logs = self.container_manager.get_container_logs('container123', tail=10)
        
        assert 'log line 1' in logs
        assert 'log line 2' in logs
        mock_container.logs.assert_called_once()


class TestImageManager:
    """镜像管理器测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.docker_manager = Mock()
        self.image_manager = ImageManager(self.docker_manager)
    
    def test_list_images(self):
        """测试列出镜像"""
        mock_image = Mock()
        mock_image.attrs = {
            'Id': 'sha256:image123',
            'RepoTags': ['nginx:latest'],
            'Created': '2023-01-01T00:00:00Z',
            'Size': 1000000
        }
        
        self.docker_manager.client.images.list.return_value = [mock_image]
        
        images = self.image_manager.list_images()
        
        assert len(images) == 1
        assert images[0]['id'] == 'sha256:image123'
        assert images[0]['repo_tags'] == ['nginx:latest']
        assert images[0]['size'] == 1000000
    
    def test_pull_image(self):
        """测试拉取镜像"""
        mock_image = Mock()
        mock_image.id = 'pulled_image123'
        
        self.docker_manager.client.images.pull.return_value = mock_image
        
        image_id = self.image_manager.pull_image('nginx:latest')
        
        assert image_id == 'pulled_image123'
        self.docker_manager.client.images.pull.assert_called_once_with('nginx:latest', tag=None)
    
    def test_remove_image(self):
        """测试删除镜像"""
        self.image_manager.remove_image('nginx:latest', force=True)
        
        self.docker_manager.client.images.remove.assert_called_once_with('nginx:latest', force=True)
    
    def test_build_image(self):
        """测试构建镜像"""
        mock_image = Mock()
        mock_image.id = 'built_image123'
        
        self.docker_manager.client.images.build.return_value = (mock_image, [])
        
        image_id = self.image_manager.build_image(
            path='/path/to/dockerfile',
            tag='my-app:latest'
        )
        
        assert image_id == 'built_image123'
        self.docker_manager.client.images.build.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__])