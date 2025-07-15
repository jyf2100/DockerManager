"""自定义异常模块"""


class DockerManagerError(Exception):
    """Docker管理器基础异常类"""
    
    def __init__(self, message: str, error_code: str = None):
        """初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class DockerConnectionError(DockerManagerError):
    """Docker连接异常"""
    pass


class DockerContainerError(DockerManagerError):
    """Docker容器操作异常"""
    pass


class DockerImageError(DockerManagerError):
    """Docker镜像操作异常"""
    pass


class K8sManagerError(Exception):
    """Kubernetes管理器基础异常类"""
    
    def __init__(self, message: str, error_code: str = None):
        """初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class K8sConnectionError(K8sManagerError):
    """Kubernetes连接异常"""
    pass


class K8sPodError(K8sManagerError):
    """Kubernetes Pod操作异常"""
    pass


class K8sDeploymentError(K8sManagerError):
    """Kubernetes Deployment操作异常"""
    pass


class K8sServiceError(K8sManagerError):
    """Kubernetes Service操作异常"""
    pass


class K8sNamespaceError(K8sManagerError):
    """Kubernetes Namespace操作异常"""
    pass


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


class ValidationError(Exception):
    """数据验证错误异常"""
    pass