"""日志配置模块"""

import os
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logger(name: str = "docker_manager", 
                 level: str = "INFO",
                 log_file: Optional[str] = None,
                 max_size: str = "10MB",
                 backup_count: int = 5) -> logging.Logger:
    """设置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        max_size: 日志文件最大大小
        backup_count: 备份文件数量
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 解析文件大小
        max_bytes = _parse_size(max_size)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def _parse_size(size_str: str) -> int:
    """解析大小字符串为字节数
    
    Args:
        size_str: 大小字符串，如 '10MB', '1GB'
        
    Returns:
        字节数
    """
    size_str = size_str.upper().strip()
    
    # 单位映射
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024 * 1024,
        'GB': 1024 * 1024 * 1024
    }
    
    # 提取数字和单位
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            try:
                number = float(size_str[:-len(unit)])
                return int(number * multiplier)
            except ValueError:
                break
    
    # 如果解析失败，默认返回10MB
    return 10 * 1024 * 1024


class LoggerMixin:
    """日志记录器混入类
    
    为其他类提供日志记录功能
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def log_info(self, message: str) -> None:
        """记录信息日志"""
        self.logger.info(message)
    
    def log_warning(self, message: str) -> None:
        """记录警告日志"""
        self.logger.warning(message)
    
    def log_error(self, message: str) -> None:
        """记录错误日志"""
        self.logger.error(message)
    
    def log_debug(self, message: str) -> None:
        """记录调试日志"""
        self.logger.debug(message)