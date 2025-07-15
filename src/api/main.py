"""FastAPI主应用"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import traceback

from ..common.config import ConfigManager
from ..common.logger import setup_logger
from ..common.exceptions import DockerManagerError, K8sManagerError
from .docker_api import docker_router
from .k8s_api import k8s_router


# 全局变量
config_manager = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global config_manager, logger
    
    # 启动时初始化
    try:
        config_manager = ConfigManager()
        log_config = config_manager.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file')
        logger = setup_logger(name="docker_manager_api", level=log_level, log_file=log_file)
        logger.info("容器生命周期管理API服务启动")
        yield
    except Exception as e:
        if logger:
            logger.error(f"应用启动失败: {str(e)}")
        raise
    finally:
        # 关闭时清理
        if logger:
            logger.info("容器生命周期管理API服务关闭")


# 创建FastAPI应用
app = FastAPI(
    title="容器生命周期管理API",
    description="支持Docker和Kubernetes容器管理的REST API服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录请求日志"""
    start_time = time.time()
    
    # 记录请求信息
    if logger:
        logger.info(
            f"请求开始: {request.method} {request.url.path} "
            f"来源IP: {request.client.host if request.client else 'unknown'}"
        )
    
    # 处理请求
    response = await call_next(request)
    
    # 记录响应信息
    process_time = time.time() - start_time
    if logger:
        logger.info(
            f"请求完成: {request.method} {request.url.path} "
            f"状态码: {response.status_code} 耗时: {process_time:.3f}s"
        )
    
    # 添加响应头
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


# 全局异常处理
@app.exception_handler(DockerManagerError)
async def docker_exception_handler(request: Request, exc: DockerManagerError):
    """Docker异常处理"""
    if logger:
        logger.error(f"Docker操作异常: {str(exc)}")
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Docker操作失败",
            "message": str(exc),
            "type": "DockerError"
        }
    )


@app.exception_handler(K8sManagerError)
async def k8s_exception_handler(request: Request, exc: K8sManagerError):
    """Kubernetes异常处理"""
    if logger:
        logger.error(f"Kubernetes操作异常: {str(exc)}")
    
    return JSONResponse(
        status_code=400,
        content={
            "error": "Kubernetes操作失败",
            "message": str(exc),
            "type": "K8sError"
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    if logger:
        logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP错误",
            "message": exc.detail,
            "type": "HTTPError"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    if logger:
        logger.error(f"未处理的异常: {str(exc)}\n{traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "message": "服务器发生未知错误，请联系管理员",
            "type": "InternalError"
        }
    )


# 健康检查端点
@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "services": {
            "api": "running",
            "docker": "available",
            "kubernetes": "available"
        }
    }


# 系统信息端点
@app.get("/info", tags=["系统信息"])
async def system_info():
    """获取系统信息"""
    try:
        from ..docker_manager import DockerManager
        from ..k8s_manager import K8sManager
        
        info = {
            "api_version": "1.0.0",
            "services": {},
            "config": {}
        }
        
        # Docker信息
        try:
            from ..common.config import ConfigManager
            config_mgr = ConfigManager()
            docker_manager = DockerManager(config_mgr)
            docker_info = docker_manager.get_system_info()
            info["services"]["docker"] = {
                "status": "connected",
                "version": docker_info.get("ServerVersion", "unknown"),
                "api_version": docker_info.get("ApiVersion", "unknown")
            }
        except Exception as e:
            info["services"]["docker"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Kubernetes信息
        try:
            k8s_manager = K8sManager()
            cluster_info = k8s_manager.get_cluster_info()
            info["services"]["kubernetes"] = {
                "status": "connected",
                "version": cluster_info.get("server_version", "unknown"),
                "current_namespace": k8s_manager.current_namespace
            }
        except Exception as e:
            info["services"]["kubernetes"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 配置信息（隐藏敏感信息）
        if config_manager:
            config = config_manager.get_all()
            safe_config = {
                "api": config.get("api", {}),
                "logging": {
                    "level": config.get("logging", {}).get("level", "INFO"),
                    "format": config.get("logging", {}).get("format", "default")
                }
            }
            info["config"] = safe_config
        
        return info
        
    except Exception as e:
        if logger:
            logger.error(f"获取系统信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取系统信息失败")


# 配置端点
@app.get("/config", tags=["配置管理"])
async def get_config():
    """获取当前配置（隐藏敏感信息）"""
    if not config_manager:
        raise HTTPException(status_code=500, detail="配置管理器未初始化")
    
    config = config_manager.get_all()
    
    # 隐藏敏感信息
    safe_config = {
        "api": config.get("api", {}),
        "logging": config.get("logging", {}),
        "docker": {
            "host": config.get("docker", {}).get("host", "unix:///var/run/docker.sock"),
            "timeout": config.get("docker", {}).get("timeout", 60)
        },
        "kubernetes": {
            "config_type": config.get("kubernetes", {}).get("config_type", "in_cluster"),
            "namespace": config.get("kubernetes", {}).get("namespace", "default")
        }
    }
    
    return safe_config


# 注册路由
app.include_router(docker_router, prefix="/api/v1/docker", tags=["Docker管理"])
app.include_router(k8s_router, prefix="/api/v1/k8s", tags=["Kubernetes管理"])


# 根路径重定向到文档
@app.get("/", include_in_schema=False)
async def root():
    """根路径重定向到API文档"""
    return {
        "message": "容器生命周期管理API服务",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "info": "/info"
    }


if __name__ == "__main__":
    import uvicorn
    
    # 从配置文件读取服务器配置
    try:
        config = ConfigManager()
        api_config = config.get('api', {})
        
        host = api_config.get('host', '0.0.0.0')
        port = api_config.get('port', 8000)
        workers = api_config.get('workers', 1)
        
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            workers=workers,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        print(f"启动API服务失败: {e}")
        exit(1)