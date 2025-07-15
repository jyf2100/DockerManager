"""配置管理模块"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器
    
    负责加载和管理应用程序配置
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 config/config.yaml
        """
        if config_path is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                # 如果配置文件不存在，尝试加载示例配置
                example_config = self.config_path.parent / "config.example.yaml"
                if example_config.exists():
                    with open(example_config, 'r', encoding='utf-8') as f:
                        self._config = yaml.safe_load(f) or {}
                    print(f"警告: 配置文件 {self.config_path} 不存在，已加载示例配置")
                else:
                    self._config = self._get_default_config()
                    print("警告: 未找到配置文件，使用默认配置")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "docker": {
                "base_url": "unix://var/run/docker.sock",
                "timeout": 60,
                "tls": False
            },
            "kubernetes": {
                "clusters": [
                    {
                        "name": "local-cluster",
                        "config_file": "~/.kube/config",
                        "context": "",
                        "namespace": "default"
                    }
                ],
                "default_cluster": "local-cluster"
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": True,
                "reload": True
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "logs/docker_manager.log",
                "max_size": "10MB",
                "backup_count": 5
            },
            "monitoring": {
                "interval": 30,
                "enabled": True,
                "retention_hours": 24
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键（如 'docker.base_url'）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        # 创建嵌套字典结构
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self) -> None:
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, 
                         allow_unicode=True, indent=2)
        except Exception as e:
            raise Exception(f"保存配置文件失败: {e}")
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self._load_config()
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        return self._config.copy()