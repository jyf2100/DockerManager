#!/usr/bin/env python3
"""容器生命周期管理CLI工具"""

import click
import json
import sys
from typing import Optional, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

from .common.config import ConfigManager
from .common.logger import setup_logger
from .common.exceptions import DockerManagerError, K8sManagerError
from .docker_manager import DockerManager, ContainerManager, ImageManager
from .k8s_manager import K8sManager, PodManager, DeploymentManager, ServiceManager


# 全局控制台对象
console = Console()


def handle_error(func):
    """错误处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (DockerManagerError, K8sManagerError) as e:
            console.print(f"[red]错误: {str(e)}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]未知错误: {str(e)}[/red]")
            sys.exit(1)
    return wrapper


def format_table(data: list, headers: list, title: str = None) -> Table:
    """格式化表格"""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    for header in headers:
        table.add_column(header)
    
    for row in data:
        table.add_row(*[str(row.get(h.lower().replace(' ', '_'), '')) for h in headers])
    
    return table


@click.group()
@click.option('--config', '-c', help='配置文件路径')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
@click.pass_context
def cli(ctx, config, verbose):
    """容器生命周期管理CLI工具"""
    ctx.ensure_object(dict)
    
    # 初始化配置
    try:
        config_manager = ConfigManager(config_path=config)
        ctx.obj['config'] = config_manager
        
        # 设置日志
        if verbose:
            log_config = config_manager.get('logging', {})
            log_config['level'] = 'DEBUG'
            setup_logger(log_config)
        
    except Exception as e:
        console.print(f"[red]配置初始化失败: {str(e)}[/red]")
        sys.exit(1)


# Docker命令组
@cli.group()
def docker():
    """Docker容器管理"""
    pass


@docker.command()
@click.pass_context
@handle_error
def info(ctx):
    """显示Docker系统信息"""
    docker_manager = DockerManager()
    info_data = docker_manager.get_system_info()
    
    panel = Panel.fit(
        f"""[bold]Docker系统信息[/bold]

版本: {info_data.get('ServerVersion', 'N/A')}
API版本: {info_data.get('ApiVersion', 'N/A')}
容器数量: {info_data.get('Containers', 0)}
运行中: {info_data.get('ContainersRunning', 0)}
已停止: {info_data.get('ContainersStopped', 0)}
镜像数量: {info_data.get('Images', 0)}
内存: {info_data.get('MemTotal', 0) // (1024**3)} GB
CPU数量: {info_data.get('NCPU', 0)}""",
        title="Docker信息",
        border_style="blue"
    )
    console.print(panel)


@docker.command()
@click.option('--all', '-a', is_flag=True, help='显示所有容器（包括停止的）')
@click.pass_context
@handle_error
def ps(ctx, all):
    """列出容器"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    containers = container_manager.list_containers(all=all)
    
    if not containers:
        console.print("[yellow]没有找到容器[/yellow]")
        return
    
    table_data = []
    for container in containers:
        table_data.append({
            'id': container['id'][:12],
            'name': container['name'],
            'image': container['image'],
            'status': container['status'],
            'ports': ', '.join([f"{p['PrivatePort']}/{p['Type']}" for p in container.get('ports', [])]),
            'created': container['created']
        })
    
    table = format_table(
        table_data,
        ['ID', 'Name', 'Image', 'Status', 'Ports', 'Created'],
        "Docker容器列表"
    )
    console.print(table)


@docker.command()
@click.argument('image')
@click.option('--name', help='容器名称')
@click.option('--port', '-p', multiple=True, help='端口映射 (host:container)')
@click.option('--env', '-e', multiple=True, help='环境变量 (KEY=VALUE)')
@click.option('--volume', '-v', multiple=True, help='卷挂载 (host:container)')
@click.option('--detach', '-d', is_flag=True, default=True, help='后台运行')
@click.pass_context
@handle_error
def run(ctx, image, name, port, env, volume, detach):
    """运行容器"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    
    # 解析端口映射
    ports = {}
    for p in port:
        if ':' in p:
            host_port, container_port = p.split(':', 1)
            ports[container_port] = int(host_port)
    
    # 解析环境变量
    environment = {}
    for e in env:
        if '=' in e:
            key, value = e.split('=', 1)
            environment[key] = value
    
    # 解析卷挂载
    volumes = {}
    for v in volume:
        if ':' in v:
            host_path, container_path = v.split(':', 1)
            volumes[container_path] = {'bind': host_path, 'mode': 'rw'}
    
    container_id = container_manager.create_container(
        image=image,
        name=name,
        ports=ports if ports else None,
        environment=environment if environment else None,
        volumes=volumes if volumes else None,
        detach=detach
    )
    
    console.print(f"[green]容器创建成功: {container_id[:12]}[/green]")
    
    # 启动容器
    container_manager.start_container(container_id)
    console.print(f"[green]容器启动成功[/green]")


@docker.command()
@click.argument('container_id')
@click.pass_context
@handle_error
def start(ctx, container_id):
    """启动容器"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    container_manager.start_container(container_id)
    console.print(f"[green]容器 {container_id} 启动成功[/green]")


@docker.command()
@click.argument('container_id')
@click.option('--timeout', '-t', default=10, help='停止超时时间')
@click.pass_context
@handle_error
def stop(ctx, container_id):
    """停止容器"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    container_manager.stop_container(container_id, timeout=timeout)
    console.print(f"[green]容器 {container_id} 停止成功[/green]")


@docker.command()
@click.argument('container_id')
@click.option('--force', '-f', is_flag=True, help='强制删除')
@click.pass_context
@handle_error
def rm(ctx, container_id):
    """删除容器"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    container_manager.remove_container(container_id, force=force)
    console.print(f"[green]容器 {container_id} 删除成功[/green]")


@docker.command()
@click.argument('container_id')
@click.option('--tail', default=100, help='显示最后N行日志')
@click.option('--follow', '-f', is_flag=True, help='实时跟踪日志')
@click.pass_context
@handle_error
def logs(ctx, container_id, tail, follow):
    """查看容器日志"""
    docker_manager = DockerManager()
    container_manager = ContainerManager(docker_manager)
    logs_output = container_manager.get_container_logs(
        container_id, tail=tail, follow=follow, timestamps=True
    )
    console.print(logs_output)


@docker.command()
@click.option('--all', '-a', is_flag=True, help='显示所有镜像')
@click.pass_context
@handle_error
def images(ctx, all):
    """列出镜像"""
    docker_manager = DockerManager()
    image_manager = ImageManager(docker_manager)
    images_list = image_manager.list_images(all=all)
    
    if not images_list:
        console.print("[yellow]没有找到镜像[/yellow]")
        return
    
    table_data = []
    for image in images_list:
        tags = image.get('repo_tags', ['<none>'])
        tag = tags[0] if tags else '<none>'
        
        table_data.append({
            'repository': tag.split(':')[0] if ':' in tag else tag,
            'tag': tag.split(':')[1] if ':' in tag else 'latest',
            'id': image['id'][:12],
            'created': image['created'],
            'size': f"{image['size'] // (1024**2)} MB"
        })
    
    table = format_table(
        table_data,
        ['Repository', 'Tag', 'ID', 'Created', 'Size'],
        "Docker镜像列表"
    )
    console.print(table)


# Kubernetes命令组
@cli.group()
def k8s():
    """Kubernetes集群管理"""
    pass


@k8s.command()
@click.pass_context
@handle_error
def info(ctx):
    """显示Kubernetes集群信息"""
    k8s_manager = K8sManager()
    cluster_info = k8s_manager.get_cluster_info()
    
    panel = Panel.fit(
        f"""[bold]Kubernetes集群信息[/bold]

服务器版本: {cluster_info.get('server_version', 'N/A')}
当前命名空间: {k8s_manager.current_namespace}
节点数量: {len(k8s_manager.get_nodes())}""",
        title="K8s集群信息",
        border_style="green"
    )
    console.print(panel)


@k8s.command()
@click.pass_context
@handle_error
def nodes(ctx):
    """列出集群节点"""
    k8s_manager = K8sManager()
    nodes_list = k8s_manager.get_nodes()
    
    if not nodes_list:
        console.print("[yellow]没有找到节点[/yellow]")
        return
    
    table_data = []
    for node in nodes_list:
        table_data.append({
            'name': node['name'],
            'status': node['status'],
            'roles': ', '.join(node['roles']),
            'age': node['age'],
            'version': node['version']
        })
    
    table = format_table(
        table_data,
        ['Name', 'Status', 'Roles', 'Age', 'Version'],
        "Kubernetes节点列表"
    )
    console.print(table)


@k8s.command()
@click.option('--namespace', '-n', help='命名空间')
@click.option('--all-namespaces', '-A', is_flag=True, help='所有命名空间')
@click.pass_context
@handle_error
def pods(ctx, namespace, all_namespaces):
    """列出Pod"""
    k8s_manager = K8sManager()
    pod_manager = PodManager(k8s_manager)
    
    ns = 'all' if all_namespaces else namespace
    pods_list = pod_manager.list_pods(namespace=ns)
    
    if not pods_list:
        console.print("[yellow]没有找到Pod[/yellow]")
        return
    
    table_data = []
    for pod in pods_list:
        table_data.append({
            'name': pod['name'],
            'namespace': pod['namespace'],
            'ready': f"{pod['ready_containers']}/{pod['total_containers']}",
            'status': pod['status'],
            'restarts': pod['restart_count'],
            'age': pod['age']
        })
    
    table = format_table(
        table_data,
        ['Name', 'Namespace', 'Ready', 'Status', 'Restarts', 'Age'],
        "Kubernetes Pod列表"
    )
    console.print(table)


@k8s.command()
@click.option('--namespace', '-n', help='命名空间')
@click.option('--all-namespaces', '-A', is_flag=True, help='所有命名空间')
@click.pass_context
@handle_error
def deployments(ctx, namespace, all_namespaces):
    """列出Deployment"""
    k8s_manager = K8sManager()
    deployment_manager = DeploymentManager(k8s_manager)
    
    ns = 'all' if all_namespaces else namespace
    deployments_list = deployment_manager.list_deployments(namespace=ns)
    
    if not deployments_list:
        console.print("[yellow]没有找到Deployment[/yellow]")
        return
    
    table_data = []
    for deployment in deployments_list:
        table_data.append({
            'name': deployment['name'],
            'namespace': deployment['namespace'],
            'ready': f"{deployment['ready_replicas']}/{deployment['replicas']}",
            'up_to_date': deployment['updated_replicas'],
            'available': deployment['available_replicas'],
            'age': deployment['age']
        })
    
    table = format_table(
        table_data,
        ['Name', 'Namespace', 'Ready', 'Up-to-date', 'Available', 'Age'],
        "Kubernetes Deployment列表"
    )
    console.print(table)


@k8s.command()
@click.option('--namespace', '-n', help='命名空间')
@click.option('--all-namespaces', '-A', is_flag=True, help='所有命名空间')
@click.pass_context
@handle_error
def services(ctx, namespace, all_namespaces):
    """列出Service"""
    k8s_manager = K8sManager()
    service_manager = ServiceManager(k8s_manager)
    
    ns = 'all' if all_namespaces else namespace
    services_list = service_manager.list_services(namespace=ns)
    
    if not services_list:
        console.print("[yellow]没有找到Service[/yellow]")
        return
    
    table_data = []
    for service in services_list:
        external_ip = 'None'
        if service['type'] == 'LoadBalancer' and service.get('external_endpoints'):
            external_ip = ', '.join(service['external_endpoints'])
        elif service.get('external_ips'):
            external_ip = ', '.join(service['external_ips'])
        
        ports = ', '.join([f"{p['port']}/{p['protocol']}" for p in service.get('ports', [])])
        
        table_data.append({
            'name': service['name'],
            'namespace': service['namespace'],
            'type': service['type'],
            'cluster_ip': service['cluster_ip'],
            'external_ip': external_ip,
            'ports': ports,
            'age': service['age']
        })
    
    table = format_table(
        table_data,
        ['Name', 'Namespace', 'Type', 'Cluster-IP', 'External-IP', 'Ports', 'Age'],
        "Kubernetes Service列表"
    )
    console.print(table)


@k8s.command()
@click.argument('deployment_name')
@click.argument('replicas', type=int)
@click.option('--namespace', '-n', help='命名空间')
@click.pass_context
@handle_error
def scale(ctx, deployment_name, replicas, namespace):
    """扩缩容Deployment"""
    k8s_manager = K8sManager()
    deployment_manager = DeploymentManager(k8s_manager)
    deployment_manager.scale_deployment(deployment_name, replicas, namespace=namespace)
    console.print(f"[green]Deployment {deployment_name} 扩缩容成功，目标副本数: {replicas}[/green]")


@k8s.command()
@click.argument('pod_name')
@click.option('--namespace', '-n', help='命名空间')
@click.option('--container', '-c', help='容器名称')
@click.option('--tail', default=100, help='显示最后N行日志')
@click.option('--follow', '-f', is_flag=True, help='实时跟踪日志')
@click.pass_context
@handle_error
def logs(ctx, pod_name, namespace, container, tail, follow):
    """查看Pod日志"""
    k8s_manager = K8sManager()
    pod_manager = PodManager(k8s_manager)
    logs_output = pod_manager.get_pod_logs(
        pod_name, 
        namespace=namespace,
        container=container,
        tail_lines=tail,
        follow=follow
    )
    console.print(logs_output)


@k8s.command()
@click.argument('pod_name')
@click.argument('command')
@click.option('--namespace', '-n', help='命名空间')
@click.option('--container', '-c', help='容器名称')
@click.pass_context
@handle_error
def exec(ctx, pod_name, command, namespace, container):
    """在Pod中执行命令"""
    k8s_manager = K8sManager()
    pod_manager = PodManager(k8s_manager)
    result = pod_manager.exec_command(
        pod_name, 
        command, 
        namespace=namespace,
        container=container
    )
    console.print(result)


# 配置命令
@cli.command()
@click.pass_context
def config(ctx):
    """显示当前配置"""
    config_manager = ctx.obj['config']
    config_data = config_manager.get_all()
    
    # 隐藏敏感信息
    safe_config = {
        'api': config_data.get('api', {}),
        'logging': config_data.get('logging', {}),
        'docker': {
            'host': config_data.get('docker', {}).get('host', 'unix:///var/run/docker.sock'),
            'timeout': config_data.get('docker', {}).get('timeout', 60)
        },
        'kubernetes': {
            'config_type': config_data.get('kubernetes', {}).get('config_type', 'in_cluster'),
            'namespace': config_data.get('kubernetes', {}).get('namespace', 'default')
        }
    }
    
    console.print(Panel(
        json.dumps(safe_config, indent=2, ensure_ascii=False),
        title="当前配置",
        border_style="cyan"
    ))


if __name__ == '__main__':
    cli()