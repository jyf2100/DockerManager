"""Kubernetes管理API路由"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from ..k8s_manager import (
    K8sManager, PodManager, DeploymentManager, 
    ServiceManager, NamespaceManager
)
from ..common.exceptions import K8sManagerError, K8sConnectionError
from ..common.config import ConfigManager


# 创建路由器
k8s_router = APIRouter()

# 全局配置管理器实例
_config_manager = None

def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def get_k8s_manager() -> K8sManager:
    """获取K8s管理器实例，包含错误处理"""
    try:
        config_manager = get_config_manager()
        return K8sManager(config_manager)
    except K8sConnectionError as e:
        raise HTTPException(status_code=500, detail=f"Kubernetes连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"K8s管理器初始化失败: {str(e)}")


# Pydantic模型定义
class PodCreateRequest(BaseModel):
    """创建Pod请求模型"""
    name: str = Field(..., description="Pod名称")
    image: str = Field(..., description="容器镜像")
    namespace: Optional[str] = Field(None, description="命名空间")
    labels: Optional[Dict[str, str]] = Field(None, description="标签")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    ports: Optional[List[int]] = Field(None, description="端口列表")
    resources: Optional[Dict[str, Any]] = Field(None, description="资源限制")
    restart_policy: str = Field("Always", description="重启策略")


class DeploymentCreateRequest(BaseModel):
    """创建Deployment请求模型"""
    name: str = Field(..., description="Deployment名称")
    image: str = Field(..., description="容器镜像")
    replicas: int = Field(1, description="副本数")
    namespace: Optional[str] = Field(None, description="命名空间")
    labels: Optional[Dict[str, str]] = Field(None, description="标签")
    env: Optional[Dict[str, str]] = Field(None, description="环境变量")
    ports: Optional[List[int]] = Field(None, description="端口列表")
    resources: Optional[Dict[str, Any]] = Field(None, description="资源限制")
    strategy: str = Field("RollingUpdate", description="更新策略")


class ServiceCreateRequest(BaseModel):
    """创建Service请求模型"""
    name: str = Field(..., description="Service名称")
    selector: Dict[str, str] = Field(..., description="Pod选择器")
    ports: List[Dict[str, Any]] = Field(..., description="端口配置")
    namespace: Optional[str] = Field(None, description="命名空间")
    service_type: str = Field("ClusterIP", description="Service类型")
    labels: Optional[Dict[str, str]] = Field(None, description="标签")
    external_ips: Optional[List[str]] = Field(None, description="外部IP列表")


class NamespaceCreateRequest(BaseModel):
    """创建Namespace请求模型"""
    name: str = Field(..., description="Namespace名称")
    labels: Optional[Dict[str, str]] = Field(None, description="标签")
    annotations: Optional[Dict[str, str]] = Field(None, description="注解")


class ScaleRequest(BaseModel):
    """扩缩容请求模型"""
    replicas: int = Field(..., description="目标副本数")


# 集群信息接口
@k8s_router.get("/info", summary="获取Kubernetes集群信息")
async def get_cluster_info():
    """获取Kubernetes集群信息"""
    try:
        k8s_manager = get_k8s_manager()
        return k8s_manager.get_cluster_info()
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/nodes", summary="获取集群节点信息")
async def get_nodes():
    """获取集群节点信息"""
    try:
        k8s_manager = get_k8s_manager()
        return k8s_manager.get_nodes()
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/current-namespace", summary="获取当前命名空间")
async def get_current_namespace():
    """获取当前命名空间"""
    try:
        k8s_manager = get_k8s_manager()
        return {"current_namespace": k8s_manager.current_namespace}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.post("/current-namespace", summary="设置当前命名空间")
async def set_current_namespace(namespace: str = Body(..., description="命名空间名称")):
    """设置当前命名空间"""
    try:
        k8s_manager = get_k8s_manager()
        k8s_manager.set_namespace(namespace)
        return {"message": f"当前命名空间已设置为: {namespace}"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 命名空间管理接口
@k8s_router.get("/namespaces", summary="列出命名空间")
async def list_namespaces(
    label_selector: Optional[str] = Query(None, description="标签选择器")
):
    """列出命名空间"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        return namespace_manager.list_namespaces(label_selector=label_selector)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/namespaces/{namespace}", summary="获取命名空间详细信息")
async def get_namespace(namespace: str):
    """获取命名空间详细信息"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        return namespace_manager.get_namespace(namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@k8s_router.post("/namespaces", summary="创建命名空间")
async def create_namespace(request: NamespaceCreateRequest):
    """创建命名空间"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        
        namespace_name = namespace_manager.create_namespace(
            name=request.name,
            labels=request.labels,
            annotations=request.annotations
        )
        
        return {"namespace": namespace_name, "message": "命名空间创建成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.delete("/namespaces/{namespace}", summary="删除命名空间")
async def delete_namespace(
    namespace: str,
    force: bool = Query(False, description="是否强制删除")
):
    """删除命名空间"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        namespace_manager.delete_namespace(namespace, force=force)
        return {"message": "命名空间删除成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/namespaces/{namespace}/events", summary="获取命名空间事件")
async def get_namespace_events(
    namespace: str,
    limit: int = Query(100, description="事件数量限制")
):
    """获取命名空间事件"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        return namespace_manager.get_namespace_events(namespace, limit=limit)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/namespaces/{namespace}/resources", summary="获取命名空间资源统计")
async def get_namespace_resources(namespace: str):
    """获取命名空间资源统计"""
    try:
        k8s_manager = get_k8s_manager()
        namespace_manager = NamespaceManager(k8s_manager)
        return namespace_manager.get_namespace_resources(namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Pod管理接口
@k8s_router.get("/pods", summary="列出Pod")
async def list_pods(
    namespace: Optional[str] = Query(None, description="命名空间"),
    label_selector: Optional[str] = Query(None, description="标签选择器")
):
    """列出Pod"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        return pod_manager.list_pods(namespace=namespace, label_selector=label_selector)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/pods/{pod_name}", summary="获取Pod详细信息")
async def get_pod(
    pod_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """获取Pod详细信息"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        return pod_manager.get_pod(pod_name, namespace=namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@k8s_router.post("/pods", summary="创建Pod")
async def create_pod(request: PodCreateRequest):
    """创建Pod"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        
        pod_name = pod_manager.create_pod(
            name=request.name,
            image=request.image,
            namespace=request.namespace,
            labels=request.labels,
            env=request.env,
            ports=request.ports,
            resources=request.resources,
            restart_policy=request.restart_policy
        )
        
        return {"pod_name": pod_name, "message": "Pod创建成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.delete("/pods/{pod_name}", summary="删除Pod")
async def delete_pod(
    pod_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """删除Pod"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        pod_manager.delete_pod(pod_name, namespace=namespace)
        return {"message": "Pod删除成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/pods/{pod_name}/logs", summary="获取Pod日志")
async def get_pod_logs(
    pod_name: str,
    namespace: Optional[str] = Query(None, description="命名空间"),
    container: Optional[str] = Query(None, description="容器名称"),
    tail_lines: int = Query(100, description="显示最后N行日志"),
    follow: bool = Query(False, description="是否实时跟踪日志")
):
    """获取Pod日志"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        logs = pod_manager.get_pod_logs(
            pod_name, 
            namespace=namespace,
            container=container,
            tail_lines=tail_lines,
            follow=follow
        )
        return {"logs": logs}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.post("/pods/{pod_name}/exec", summary="在Pod中执行命令")
async def exec_pod(
    pod_name: str,
    command: str = Body(..., description="要执行的命令"),
    namespace: Optional[str] = Query(None, description="命名空间"),
    container: Optional[str] = Query(None, description="容器名称")
):
    """在Pod中执行命令"""
    try:
        k8s_manager = get_k8s_manager()
        pod_manager = PodManager(k8s_manager)
        result = pod_manager.exec_command(
            pod_name, 
            command, 
            namespace=namespace,
            container=container
        )
        return {"output": result}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Deployment管理接口
@k8s_router.get("/deployments", summary="列出Deployment")
async def list_deployments(
    namespace: Optional[str] = Query(None, description="命名空间"),
    label_selector: Optional[str] = Query(None, description="标签选择器")
):
    """列出Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        return deployment_manager.list_deployments(namespace=namespace, label_selector=label_selector)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/deployments/{deployment_name}", summary="获取Deployment详细信息")
async def get_deployment(
    deployment_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """获取Deployment详细信息"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        return deployment_manager.get_deployment(deployment_name, namespace=namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@k8s_router.post("/deployments", summary="创建Deployment")
async def create_deployment(request: DeploymentCreateRequest):
    """创建Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        
        deployment_name = deployment_manager.create_deployment(
            name=request.name,
            image=request.image,
            replicas=request.replicas,
            namespace=request.namespace,
            labels=request.labels,
            env=request.env,
            ports=request.ports,
            resources=request.resources,
            strategy=request.strategy
        )
        
        return {"deployment_name": deployment_name, "message": "Deployment创建成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.put("/deployments/{deployment_name}", summary="更新Deployment")
async def update_deployment(
    deployment_name: str,
    namespace: Optional[str] = Query(None, description="命名空间"),
    image: Optional[str] = Body(None, description="新的容器镜像"),
    replicas: Optional[int] = Body(None, description="新的副本数"),
    env: Optional[Dict[str, str]] = Body(None, description="新的环境变量"),
    resources: Optional[Dict[str, Any]] = Body(None, description="新的资源限制")
):
    """更新Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        deployment_manager.update_deployment(
            deployment_name,
            namespace=namespace,
            image=image,
            replicas=replicas,
            env=env,
            resources=resources
        )
        return {"message": "Deployment更新成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.post("/deployments/{deployment_name}/scale", summary="扩缩容Deployment")
async def scale_deployment(
    deployment_name: str,
    request: ScaleRequest,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """扩缩容Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        deployment_manager.scale_deployment(
            deployment_name, 
            request.replicas, 
            namespace=namespace
        )
        return {"message": f"Deployment扩缩容成功，目标副本数: {request.replicas}"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.delete("/deployments/{deployment_name}", summary="删除Deployment")
async def delete_deployment(
    deployment_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """删除Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        deployment_manager.delete_deployment(deployment_name, namespace=namespace)
        return {"message": "Deployment删除成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.post("/deployments/{deployment_name}/rollback", summary="回滚Deployment")
async def rollback_deployment(
    deployment_name: str,
    namespace: Optional[str] = Query(None, description="命名空间"),
    revision: Optional[int] = Body(None, description="目标版本号")
):
    """回滚Deployment"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        deployment_manager.rollback_deployment(
            deployment_name, 
            namespace=namespace,
            revision=revision
        )
        return {"message": "Deployment回滚成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/deployments/{deployment_name}/history", summary="获取Deployment历史版本")
async def get_deployment_history(
    deployment_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """获取Deployment历史版本"""
    try:
        k8s_manager = get_k8s_manager()
        deployment_manager = DeploymentManager(k8s_manager)
        return deployment_manager.get_deployment_history(deployment_name, namespace=namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Service管理接口
@k8s_router.get("/services", summary="列出Service")
async def list_services(
    namespace: Optional[str] = Query(None, description="命名空间"),
    label_selector: Optional[str] = Query(None, description="标签选择器")
):
    """列出Service"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        return service_manager.list_services(namespace=namespace, label_selector=label_selector)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/services/{service_name}", summary="获取Service详细信息")
async def get_service(
    service_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """获取Service详细信息"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        return service_manager.get_service(service_name, namespace=namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=404, detail=str(e))


@k8s_router.post("/services", summary="创建Service")
async def create_service(request: ServiceCreateRequest):
    """创建Service"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        
        service_name = service_manager.create_service(
            name=request.name,
            selector=request.selector,
            ports=request.ports,
            namespace=request.namespace,
            service_type=request.service_type,
            labels=request.labels,
            external_ips=request.external_ips
        )
        
        return {"service_name": service_name, "message": "Service创建成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.delete("/services/{service_name}", summary="删除Service")
async def delete_service(
    service_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """删除Service"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        service_manager.delete_service(service_name, namespace=namespace)
        return {"message": "Service删除成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.post("/services/expose", summary="为Deployment创建Service")
async def expose_deployment(
    deployment_name: str = Body(..., description="Deployment名称"),
    port: int = Body(..., description="Service端口"),
    target_port: Optional[int] = Body(None, description="目标端口"),
    service_type: str = Body("ClusterIP", description="Service类型"),
    namespace: Optional[str] = Body(None, description="命名空间"),
    service_name: Optional[str] = Body(None, description="Service名称")
):
    """为Deployment创建Service"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        
        service_name = service_manager.expose_deployment(
            deployment_name=deployment_name,
            port=port,
            target_port=target_port,
            service_type=service_type,
            namespace=namespace,
            service_name=service_name
        )
        
        return {"service_name": service_name, "message": "Service创建成功"}
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@k8s_router.get("/services/{service_name}/endpoints", summary="获取Service的Endpoints")
async def get_service_endpoints(
    service_name: str,
    namespace: Optional[str] = Query(None, description="命名空间")
):
    """获取Service的Endpoints"""
    try:
        k8s_manager = get_k8s_manager()
        service_manager = ServiceManager(k8s_manager)
        return service_manager.get_service_endpoints(service_name, namespace=namespace)
    except K8sManagerError as e:
        raise HTTPException(status_code=400, detail=str(e))