"""Docker管理API路由"""

import json
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from ..docker_manager import (
    DockerManager, ContainerManager, ImageManager, 
    NetworkManager, VolumeManager
)
from ..common.exceptions import DockerManagerError
from ..common.config import ConfigManager


# 创建路由器
docker_router = APIRouter()


# Pydantic模型定义
class ContainerCreateRequest(BaseModel):
    """创建容器请求模型"""
    name: str = Field(..., description="容器名称")
    image: str = Field(..., description="镜像名称")
    command: Optional[str] = Field(None, description="启动命令")
    environment: Optional[Dict[str, str]] = Field(None, description="环境变量")
    ports: Optional[Dict[str, int]] = Field(None, description="端口映射")
    volumes: Optional[Dict[str, str]] = Field(None, description="卷挂载")
    working_dir: Optional[str] = Field(None, description="工作目录")
    detach: bool = Field(True, description="是否后台运行")
    remove: bool = Field(False, description="退出时是否自动删除")
    restart_policy: Optional[str] = Field(None, description="重启策略")


class ImageBuildRequest(BaseModel):
    """构建镜像请求模型"""
    path: str = Field(..., description="Dockerfile路径")
    tag: str = Field(..., description="镜像标签")
    dockerfile: Optional[str] = Field(None, description="Dockerfile文件名")
    build_args: Optional[Dict[str, str]] = Field(None, description="构建参数")
    no_cache: bool = Field(False, description="是否禁用缓存")


class NetworkCreateRequest(BaseModel):
    """创建网络请求模型"""
    name: str = Field(..., description="网络名称")
    driver: str = Field("bridge", description="网络驱动")
    options: Optional[Dict[str, str]] = Field(None, description="网络选项")
    ipam: Optional[Dict[str, Any]] = Field(None, description="IP地址管理配置")


class VolumeCreateRequest(BaseModel):
    """创建卷请求模型"""
    name: str = Field(..., description="卷名称")
    driver: str = Field("local", description="卷驱动")
    options: Optional[Dict[str, str]] = Field(None, description="卷选项")
    labels: Optional[Dict[str, str]] = Field(None, description="卷标签")


# 系统信息接口
@docker_router.get("/info", summary="获取Docker系统信息")
async def get_docker_info():
    """获取Docker系统信息"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        return docker_manager.get_system_info()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.get("/version", summary="获取Docker版本信息")
async def get_docker_version():
    """获取Docker版本信息"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        return docker_manager.client.version()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.get("/disk-usage", summary="获取Docker磁盘使用情况")
async def get_docker_disk_usage():
    """获取Docker磁盘使用情况"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        return docker_manager.get_disk_usage()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/system/prune", summary="清理Docker系统")
async def prune_docker_system():
    """清理Docker系统（删除未使用的容器、网络、镜像等）"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        return docker_manager.cleanup_system()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 容器管理接口
@docker_router.get("/containers", summary="列出容器")
async def list_containers(
    all: bool = Query(False, description="是否包含停止的容器"),
    filters: Optional[str] = Query(None, description="过滤条件（JSON格式）")
):
    """列出容器"""
    import json
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        
        # 解析过滤条件
        filter_dict = None
        if filters:
            filter_dict = json.loads(filters)
        
        return container_manager.list_containers(all_containers=all)
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="过滤条件格式错误")


@docker_router.get("/containers/{container_id}", summary="获取容器详细信息")
async def get_container(container_id: str):
    """获取容器详细信息"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        return container_manager.get_container(container_id)
    except DockerManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@docker_router.post("/containers", summary="创建容器")
async def create_container(request: ContainerCreateRequest):
    """创建容器"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        
        container_id = container_manager.create_container(
            image=request.image,
            name=request.name,
            command=request.command,
            environment=request.environment,
            ports=request.ports,
            volumes=request.volumes,
            working_dir=request.working_dir,
            detach=request.detach,
            remove=request.remove,
            restart_policy=request.restart_policy
        )
        
        return {"container_id": container_id, "message": "容器创建成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/containers/{container_id}/start", summary="启动容器")
async def start_container(container_id: str):
    """启动容器"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        container_manager.start_container(container_id)
        return {"message": "容器启动成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/containers/{container_id}/stop", summary="停止容器")
async def stop_container(
    container_id: str,
    timeout: int = Query(10, description="停止超时时间（秒）")
):
    """停止容器"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        container_manager.stop_container(container_id, timeout=timeout)
        return {"message": "容器停止成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/containers/{container_id}/restart", summary="重启容器")
async def restart_container(
    container_id: str,
    timeout: int = Query(10, description="重启超时时间（秒）")
):
    """重启容器"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        container_manager.restart_container(container_id, timeout=timeout)
        return {"message": "容器重启成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.delete("/containers/{container_id}", summary="删除容器")
async def remove_container(
    container_id: str,
    force: bool = Query(False, description="是否强制删除")
):
    """删除容器"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        container_manager.remove_container(container_id, force=force)
        return {"message": "容器删除成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.get("/containers/{container_id}/logs", summary="获取容器日志")
async def get_container_logs(
    container_id: str,
    tail: int = Query(100, description="显示最后N行日志"),
    follow: bool = Query(False, description="是否实时跟踪日志"),
    timestamps: bool = Query(False, description="是否显示时间戳")
):
    """获取容器日志"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        logs = container_manager.get_container_logs(
            container_id, tail=tail, follow=follow, timestamps=timestamps
        )
        return {"logs": logs}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.get("/containers/{container_id}/stats", summary="获取容器资源统计")
async def get_container_stats(container_id: str):
    """获取容器资源统计"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        return container_manager.get_container_stats(container_id)
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/containers/{container_id}/exec", summary="在容器中执行命令")
async def exec_container(
    container_id: str,
    command: str = Body(..., description="要执行的命令")
):
    """在容器中执行命令"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        container_manager = ContainerManager(docker_manager)
        result = container_manager.exec_command(container_id, command)
        return {"output": result}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 镜像管理接口
@docker_router.get("/images", summary="列出镜像")
async def list_images(
    all: bool = Query(False, description="是否包含中间镜像"),
    filters: Optional[str] = Query(None, description="过滤条件（JSON格式）")
):
    """列出镜像"""
    import json
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        image_manager = ImageManager(docker_manager)
        
        filter_dict = None
        if filters:
            filter_dict = json.loads(filters)
        
        return image_manager.list_images(all_images=all)
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="过滤条件格式错误")


@docker_router.get("/images/{image_id}", summary="获取镜像详细信息")
async def get_image(image_id: str):
    """获取镜像详细信息"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        image_manager = ImageManager(docker_manager)
        return image_manager.get_image(image_id)
    except DockerManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@docker_router.post("/images/pull", summary="拉取镜像")
async def pull_image(
    repository: str = Body(..., description="镜像仓库"),
    tag: str = Body("latest", description="镜像标签")
):
    """拉取镜像"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        image_manager = ImageManager(docker_manager)
        image_manager.pull_image(repository, tag=tag)
        return {"message": f"镜像 {repository}:{tag} 拉取成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/images/build", summary="构建镜像")
async def build_image(request: ImageBuildRequest):
    """构建镜像"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        image_manager = ImageManager(docker_manager)
        
        image_id = image_manager.build_image(
            path=request.path,
            tag=request.tag,
            dockerfile=request.dockerfile,
            build_args=request.build_args,
            no_cache=request.no_cache
        )
        
        return {"image_id": image_id, "message": "镜像构建成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.delete("/images/{image_id}", summary="删除镜像")
async def remove_image(
    image_id: str,
    force: bool = Query(False, description="是否强制删除")
):
    """删除镜像"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        image_manager = ImageManager(docker_manager)
        image_manager.remove_image(image_id, force=force)
        return {"message": "镜像删除成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 网络管理接口
@docker_router.get("/networks", summary="列出网络")
async def list_networks():
    """列出网络"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        network_manager = NetworkManager(docker_manager)
        return network_manager.list_networks()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/networks", summary="创建网络")
async def create_network(request: NetworkCreateRequest):
    """创建网络"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        network_manager = NetworkManager(docker_manager)
        
        network_id = network_manager.create_network(
            name=request.name,
            driver=request.driver,
            options=request.options,
            ipam=request.ipam
        )
        
        return {"network_id": network_id, "message": "网络创建成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.delete("/networks/{network_id}", summary="删除网络")
async def remove_network(network_id: str):
    """删除网络"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        network_manager = NetworkManager(docker_manager)
        network_manager.remove_network(network_id)
        return {"message": "网络删除成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 卷管理接口
@docker_router.get("/volumes", summary="列出卷")
async def list_volumes():
    """列出卷"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        volume_manager = VolumeManager(docker_manager)
        return volume_manager.list_volumes()
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.post("/volumes", summary="创建卷")
async def create_volume(request: VolumeCreateRequest):
    """创建卷"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        volume_manager = VolumeManager(docker_manager)
        
        volume_name = volume_manager.create_volume(
            name=request.name,
            driver=request.driver,
            options=request.options,
            labels=request.labels
        )
        
        return {"volume_name": volume_name, "message": "卷创建成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.delete("/volumes/{volume_name}", summary="删除卷")
async def remove_volume(
    volume_name: str,
    force: bool = Query(False, description="是否强制删除")
):
    """删除卷"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        volume_manager = VolumeManager(docker_manager)
        volume_manager.remove_volume(volume_name, force=force)
        return {"message": "卷删除成功"}
    except DockerManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@docker_router.get("/volumes/{volume_name}", summary="获取卷详细信息")
async def get_volume(volume_name: str):
    """获取卷详细信息"""
    try:
        config_manager = ConfigManager()
        docker_manager = DockerManager(config_manager)
        volume_manager = VolumeManager(docker_manager)
        return volume_manager.get_volume(volume_name)
    except DockerManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))