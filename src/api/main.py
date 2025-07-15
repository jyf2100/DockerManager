"""FastAPI主应用"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
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
    docs_url=None,  # 禁用默认文档
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
                "version": docker_info.get("server_version", "unknown"),
                "api_version": docker_info.get("api_version", "unknown")
            }
        except Exception as e:
            info["services"]["docker"] = {
                "status": "error",
                "error": str(e)
            }
        
        # Kubernetes信息
        try:
            from ..common.config import ConfigManager
            config_mgr = ConfigManager()
            k8s_manager = K8sManager(config_mgr)
            cluster_info = k8s_manager.get_cluster_info()
            info["services"]["kubernetes"] = {
                "status": "connected",
                "version": cluster_info.get("version", {}).get("git_version", "unknown"),
                "current_namespace": k8s_manager.current_namespace
            }
        except Exception as e:
            info["services"]["kubernetes"] = {
                "status": "error",
                "error": str(e)
            }
        
        # 配置信息（隐藏敏感信息）
        if config_manager:
            config = config_manager.config
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


# 自定义 Swagger UI 端点
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """自定义 Swagger UI 页面，使用国内可访问的 CDN"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="容器生命周期管理API - Swagger UI",
        swagger_js_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True
        }
    )


# 完全离线的文档端点
@app.get("/docs-offline", include_in_schema=False)
async def offline_swagger_ui_html():
    """完全离线的 API 文档页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>容器生命周期管理API - 离线文档</title>
        <meta charset="utf-8">
        <style>
            * { box-sizing: border-box; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0; padding: 20px; background: #fafafa; color: #333;
            }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            .endpoint { 
                border: 1px solid #e1e8ed; margin: 15px 0; border-radius: 6px; overflow: hidden;
                transition: box-shadow 0.2s ease;
            }
            .endpoint:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            .method-header { 
                padding: 15px 20px; font-weight: bold; color: white; cursor: pointer;
                display: flex; justify-content: space-between; align-items: center;
            }
            .method-get { background: #61affe; }
            .method-post { background: #49cc90; }
            .method-put { background: #fca130; }
            .method-delete { background: #f93e3e; }
            .method-patch { background: #50e3c2; }
            .endpoint-details { 
                padding: 20px; background: #f8f9fa; display: none;
                border-top: 1px solid #e1e8ed;
            }
            .endpoint-details.active { display: block; }
            .parameter { 
                background: white; padding: 10px; margin: 5px 0; border-radius: 4px;
                border-left: 4px solid #3498db;
            }
            .response { 
                background: #e8f5e8; padding: 10px; margin: 5px 0; border-radius: 4px;
                border-left: 4px solid #27ae60;
            }
            .tag { 
                background: #3498db; color: white; padding: 2px 8px; border-radius: 12px;
                font-size: 12px; margin-right: 5px;
            }
            .try-button {
                background: #3498db; color: white; border: none; padding: 8px 16px;
                border-radius: 4px; cursor: pointer; margin-top: 10px;
            }
            .try-button:hover { background: #2980b9; }
            .loading { text-align: center; padding: 40px; color: #7f8c8d; }
            .error { background: #fee; border: 1px solid #fcc; padding: 15px; border-radius: 4px; color: #c33; }
            .toggle-icon { transition: transform 0.2s ease; }
            .toggle-icon.rotated { transform: rotate(180deg); }
        </style>
    </head>
    <body>
        <div class="container">
            <div id="loading" class="loading">
                <h2>正在加载 API 文档...</h2>
                <p>请稍候</p>
            </div>
            <div id="content" style="display: none;"></div>
        </div>
        
        <script>
            // 完全离线的 API 文档实现
            function toggleEndpoint(element) {
                const details = element.nextElementSibling;
                const icon = element.querySelector('.toggle-icon');
                
                if (details.classList.contains('active')) {
                    details.classList.remove('active');
                    icon.classList.remove('rotated');
                } else {
                    details.classList.add('active');
                    icon.classList.add('rotated');
                }
            }
            
            function tryEndpoint(method, path) {
                const baseUrl = window.location.origin;
                const url = baseUrl + path;
                
                if (method.toLowerCase() === 'get') {
                    window.open(url, '_blank');
                } else {
                    alert(`请使用 curl 或其他工具测试:\n\ncurl -X ${method.toUpperCase()} ${url}`);
                }
            }
            
            function renderEndpoint(path, method, operation) {
                const methodClass = `method-${method.toLowerCase()}`;
                const tags = operation.tags ? operation.tags.map(tag => `<span class="tag">${tag}</span>`).join('') : '';
                
                let parametersHtml = '';
                if (operation.parameters && operation.parameters.length > 0) {
                    parametersHtml = '<h4>参数:</h4>';
                    operation.parameters.forEach(param => {
                        parametersHtml += `
                            <div class="parameter">
                                <strong>${param.name}</strong> 
                                <em>(${param.in})</em>
                                ${param.required ? '<span style="color: red;">*</span>' : ''}
                                <br>
                                <small>${param.description || '无描述'}</small>
                            </div>
                        `;
                    });
                }
                
                let responsesHtml = '';
                if (operation.responses) {
                    responsesHtml = '<h4>响应:</h4>';
                    Object.keys(operation.responses).forEach(code => {
                        const response = operation.responses[code];
                        responsesHtml += `
                            <div class="response">
                                <strong>HTTP ${code}</strong><br>
                                <small>${response.description || '无描述'}</small>
                            </div>
                        `;
                    });
                }
                
                return `
                    <div class="endpoint">
                        <div class="method-header ${methodClass}" onclick="toggleEndpoint(this)">
                            <div>
                                <span style="font-family: monospace;">${method.toUpperCase()}</span>
                                <span style="margin-left: 15px;">${path}</span>
                            </div>
                            <span class="toggle-icon">▼</span>
                        </div>
                        <div class="endpoint-details">
                            <p><strong>描述:</strong> ${operation.summary || operation.description || '无描述'}</p>
                            ${tags ? `<p><strong>标签:</strong> ${tags}</p>` : ''}
                            ${parametersHtml}
                            ${responsesHtml}
                            <button class="try-button" onclick="tryEndpoint('${method}', '${path}')">
                                测试接口
                            </button>
                        </div>
                    </div>
                `;
            }
            
            // 加载 API 规范
            fetch('/openapi.json')
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(spec => {
                    const content = document.getElementById('content');
                    const loading = document.getElementById('loading');
                    
                    let html = `
                        <h1>${spec.info.title}</h1>
                        <p style="font-size: 16px; color: #7f8c8d;">${spec.info.description}</p>
                        <p><strong>版本:</strong> ${spec.info.version}</p>
                        <h2>API 端点 (${Object.keys(spec.paths).length} 个)</h2>
                    `;
                    
                    // 按标签分组
                    const endpointsByTag = {};
                    const untagged = [];
                    
                    Object.keys(spec.paths).forEach(path => {
                        const methods = Object.keys(spec.paths[path]);
                        methods.forEach(method => {
                            const operation = spec.paths[path][method];
                            const tags = operation.tags || ['未分类'];
                            
                            tags.forEach(tag => {
                                if (!endpointsByTag[tag]) {
                                    endpointsByTag[tag] = [];
                                }
                                endpointsByTag[tag].push({ path, method, operation });
                            });
                        });
                    });
                    
                    // 渲染分组的端点
                    Object.keys(endpointsByTag).sort().forEach(tag => {
                        html += `<h3 style="color: #2c3e50; margin-top: 30px;">${tag}</h3>`;
                        endpointsByTag[tag].forEach(({ path, method, operation }) => {
                            html += renderEndpoint(path, method, operation);
                        });
                    });
                    
                    content.innerHTML = html;
                    loading.style.display = 'none';
                    content.style.display = 'block';
                })
                .catch(error => {
                    const loading = document.getElementById('loading');
                    loading.innerHTML = `
                        <div class="error">
                            <h2>API 文档加载失败</h2>
                            <p><strong>错误:</strong> ${error.message}</p>
                            <p>请尝试以下解决方案:</p>
                            <ul>
                                <li>检查网络连接</li>
                                <li>访问 <a href="/redoc">/redoc</a> (ReDoc 文档)</li>
                                <li>访问 <a href="/docs-debug">/docs-debug</a> (调试页面)</li>
                                <li>直接访问 <a href="/openapi.json">/openapi.json</a> (原始 API 规范)</li>
                            </ul>
                        </div>
                    `;
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# 自定义文档调试端点
@app.get("/docs-debug", include_in_schema=False)
async def docs_debug():
    """文档调试页面"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API 文档调试</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .success { background-color: #d4edda; color: #155724; }
            .error { background-color: #f8d7da; color: #721c24; }
            .info { background-color: #d1ecf1; color: #0c5460; }
        </style>
    </head>
    <body>
        <h1>API 文档调试信息</h1>
        
        <div class="status info">
            <h3>服务状态</h3>
            <p>API 服务正在运行</p>
            <p>OpenAPI JSON: <a href="/openapi.json" target="_blank">/openapi.json</a></p>
            <p>标准文档: <a href="/docs" target="_blank">/docs</a></p>
            <p>ReDoc 文档: <a href="/redoc" target="_blank">/redoc</a></p>
        </div>
        
        <div class="status info">
            <h3>常见问题解决方案</h3>
            <ul>
                <li>如果 Swagger UI 无法加载，请检查网络连接</li>
                <li>尝试清除浏览器缓存后重新访问</li>
                <li>检查浏览器控制台是否有 JavaScript 错误</li>
                <li>确认 CDN 资源可以正常访问</li>
            </ul>
        </div>
        
        <div class="status success">
            <h3>测试链接</h3>
            <p><a href="/health">健康检查</a></p>
            <p><a href="/info">系统信息</a></p>
            <p><a href="/config">配置信息</a></p>
        </div>
        
        <script>
            // 测试 OpenAPI JSON 可访问性
            fetch('/openapi.json')
                .then(response => {
                    if (response.ok) {
                        console.log('OpenAPI JSON 可以正常访问');
                        document.body.innerHTML += '<div class="status success">✓ OpenAPI JSON 可以正常访问</div>';
                    } else {
                        console.error('OpenAPI JSON 访问失败:', response.status);
                        document.body.innerHTML += '<div class="status error">✗ OpenAPI JSON 访问失败: ' + response.status + '</div>';
                    }
                })
                .catch(error => {
                    console.error('OpenAPI JSON 请求错误:', error);
                    document.body.innerHTML += '<div class="status error">✗ OpenAPI JSON 请求错误: ' + error.message + '</div>';
                });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# 根路径重定向到文档
@app.get("/", include_in_schema=False)
async def root():
    """根路径重定向到API文档"""
    return {
        "message": "容器生命周期管理API服务",
        "version": "1.0.0",
        "docs": "/docs",
        "docs_offline": "/docs-offline",
        "redoc": "/redoc",
        "docs_debug": "/docs-debug",
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