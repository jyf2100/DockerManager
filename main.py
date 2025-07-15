#!/usr/bin/env python3
"""容器生命周期管理项目主入口"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.common.config import ConfigManager
from src.common.logger import setup_logger
from src.cli import cli


def setup_environment():
    """设置环境"""
    # 确保配置目录存在
    config_dir = project_root / 'config'
    config_dir.mkdir(exist_ok=True)
    
    # 如果config.yaml不存在，复制示例配置
    config_file = config_dir / 'config.yaml'
    example_config = config_dir / 'config.example.yaml'
    
    if not config_file.exists() and example_config.exists():
        import shutil
        shutil.copy2(example_config, config_file)
        print(f"已创建配置文件: {config_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='容器生命周期管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 启动API服务
  python main.py api
  
  # 使用CLI工具
  python main.py cli docker ps
  python main.py cli k8s pods
  
  # 显示Docker信息
  python main.py cli docker info
  
  # 运行容器
  python main.py cli docker run nginx --name web --port 8080:80
  
  # 查看K8s集群信息
  python main.py cli k8s info
  
  # 扩缩容Deployment
  python main.py cli k8s scale my-app 3
"""
    )
    
    subparsers = parser.add_subparsers(dest='mode', help='运行模式')
    
    # API模式
    api_parser = subparsers.add_parser('api', help='启动API服务')
    api_parser.add_argument('--host', default='0.0.0.0', help='服务主机地址')
    api_parser.add_argument('--port', type=int, default=8000, help='服务端口')
    api_parser.add_argument('--reload', action='store_true', help='开发模式（自动重载）')
    api_parser.add_argument('--config', '-c', help='配置文件路径')
    
    # CLI模式
    cli_parser = subparsers.add_parser('cli', help='使用CLI工具')
    cli_parser.add_argument('args', nargs=argparse.REMAINDER, help='CLI参数')
    
    # 解析参数
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        return
    
    # 设置环境
    setup_environment()
    
    if args.mode == 'api':
        start_api_server(args)
    elif args.mode == 'cli':
        start_cli(args)


def start_api_server(args):
    """启动API服务"""
    try:
        import uvicorn
        from src.api.main import app
        
        # 初始化配置和日志
        config_manager = ConfigManager(config_path=args.config)
        log_config = config_manager.get('logging', {})
        
        # 设置日志
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file')
        setup_logger(name="docker_manager_api", level=log_level, log_file=log_file)
        
        print(f"启动API服务: http://{args.host}:{args.port}")
        print(f"API文档: http://{args.host}:{args.port}/docs")
        
        uvicorn.run(
            "src.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info"
        )
        
    except ImportError:
        print("错误: 缺少依赖包，请运行: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"启动API服务失败: {e}")
        sys.exit(1)


def start_cli(args):
    """启动CLI工具"""
    try:
        # 设置CLI参数
        sys.argv = ['cli'] + args.args
        cli()
        
    except Exception as e:
        print(f"CLI执行失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()