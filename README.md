# Docker & Kubernetes 容器生命周期管理系统

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-20.10+-blue.svg)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.20+-blue.svg)](https://kubernetes.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个功能完整的容器生命周期管理系统，提供Docker容器和Kubernetes集群的统一管理界面。支持REST API、CLI工具和Web界面，集成监控、日志和链路追踪功能。

## ✨ 主要特性

### 🐳 Docker管理
- **容器生命周期管理**: 创建、启动、停止、删除、重启容器
- **镜像管理**: 拉取、构建、删除、标签管理
- **网络管理**: 创建、删除、连接网络
- **卷管理**: 创建、删除、挂载数据卷
- **实时监控**: 容器状态、资源使用、日志查看

### ☸️ Kubernetes管理
- **集群管理**: 多集群支持、节点管理
- **工作负载管理**: Pod、Deployment、Service管理
- **命名空间管理**: 资源隔离、配额管理
- **扩缩容**: 自动和手动扩缩容
- **日志和监控**: 实时日志、性能监控

### 🚀 系统特性
- **统一API**: RESTful API设计，支持OpenAPI文档
- **CLI工具**: 命令行界面，支持批量操作
- **Web界面**: 直观的管理界面（通过Grafana）
- **监控告警**: Prometheus + Grafana监控栈
- **链路追踪**: Jaeger分布式追踪
- **高可用**: 支持集群部署和负载均衡
- **安全性**: JWT认证、RBAC权限控制

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web UI        │    │   CLI Tool      │    │   REST API      │
│   (Grafana)     │    │   (Python)      │    │   (FastAPI)     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │    Core Manager Layer     │
                    │  ┌─────────┐ ┌─────────┐  │
                    │  │ Docker  │ │   K8s   │  │
                    │  │Manager  │ │Manager  │  │
                    │  └─────────┘ └─────────┘  │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
    ┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
    │   Docker Engine   │ │  Kubernetes   │ │   Monitoring      │
    │                   │ │   Cluster     │ │   Stack           │
    │ ┌───────────────┐ │ │ ┌───────────┐ │ │ ┌───────────────┐ │
    │ │  Containers   │ │ │ │   Pods    │ │ │ │  Prometheus   │ │
    │ │  Images       │ │ │ │ Services  │ │ │ │  Grafana      │ │
    │ │  Networks     │ │ │ │Deployments│ │ │ │  Jaeger       │ │
    │ │  Volumes      │ │ │ │Namespaces │ │ │ │  AlertManager │ │
    │ └───────────────┘ │ │ └───────────┘ │ │ └───────────────┘ │
    └───────────────────┘ └───────────────┘ └───────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 1.29+
- Python 3.9+ (开发环境)
- Git

### 一键部署

```bash
# 1. 克隆项目
git clone <repository-url>
cd DockerManager

# 2. 启动所有服务
./start.sh

# 或使用Make命令
make run
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| API服务 | http://localhost:8000 | 主要API接口 |
| API文档 | http://localhost:8000/docs | Swagger UI文档 |
| Grafana | http://localhost:3000 | 监控面板 (admin/admin) |
| Prometheus | http://localhost:9090 | 指标收集 |
| Jaeger | http://localhost:16686 | 链路追踪 |

## 📖 使用指南

### REST API

```bash
# 获取Docker系统信息
curl http://localhost:8000/api/v1/docker/info

# 列出所有容器
curl http://localhost:8000/api/v1/docker/containers

# 创建容器
curl -X POST http://localhost:8000/api/v1/docker/containers \
  -H "Content-Type: application/json" \
  -d '{
    "image": "nginx:latest",
    "name": "my-nginx",
    "ports": {"80/tcp": 8080}
  }'

# 获取K8s集群信息
curl http://localhost:8000/api/v1/k8s/cluster/info

# 列出Pods
curl http://localhost:8000/api/v1/k8s/pods?namespace=default
```

### CLI工具

```bash
# 使用CLI工具
python main.py cli --help

# Docker操作
python main.py cli docker info
python main.py cli docker containers list
python main.py cli docker containers run nginx:latest --name my-nginx

# Kubernetes操作
python main.py cli k8s cluster info
python main.py cli k8s pods list --namespace default
python main.py cli k8s deployments scale my-app --replicas 3
```

### Python SDK

```python
from src.docker_manager import DockerManager
from src.k8s_manager import K8sManager

# Docker管理
docker_mgr = DockerManager()
containers = docker_mgr.container_manager.list_containers()
print(f"运行中的容器: {len(containers)}")

# Kubernetes管理
k8s_mgr = K8sManager()
pods = k8s_mgr.pod_manager.list_pods(namespace="default")
print(f"默认命名空间的Pods: {len(pods)}")
```

## 🛠️ 开发环境

### 本地开发

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制配置文件
cp config/config.example.yaml config/config.yaml

# 4. 启动开发服务器
python main.py api --reload
```

### 运行测试

```bash
# 运行所有测试
make test

# 运行特定测试
pytest tests/test_docker_manager.py -v
pytest tests/test_k8s_manager.py -v

# 生成覆盖率报告
make test-coverage
```

### 代码质量

```bash
# 代码格式化
make format

# 代码检查
make lint

# 类型检查
make type-check
```

## 📊 监控和告警

### Grafana仪表板

系统提供了预配置的Grafana仪表板：

- **系统概览**: 整体系统状态和性能指标
- **Docker监控**: 容器状态、资源使用、操作统计
- **Kubernetes监控**: 集群状态、Pod性能、服务健康
- **API监控**: 请求量、响应时间、错误率
- **基础设施监控**: 主机资源、网络、存储

### 告警规则

```yaml
# 示例告警规则
groups:
  - name: docker_manager_alerts
    rules:
      - alert: APIHighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API错误率过高"
          description: "API错误率超过10%，持续5分钟"
      
      - alert: ContainerDown
        expr: docker_container_running == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "容器停止运行"
          description: "容器 {{ $labels.name }} 已停止运行"
```

## 🔧 配置说明

### 主配置文件 (config/config.yaml)

```yaml
# API服务配置
api:
  host: "0.0.0.0"
  port: 8000
  debug: false
  workers: 4
  reload: false

# Docker配置
docker:
  host: "unix:///var/run/docker.sock"
  timeout: 60
  api_version: "auto"

# Kubernetes配置
kubernetes:
  config_type: "kube_config"  # in_cluster, kube_config, service_account
  config_path: "~/.kube/config"
  namespace: "default"
  timeout: 60

# 数据库配置
database:
  url: "postgresql://docker_manager:password@localhost:5432/docker_manager"
  pool_size: 10
  max_overflow: 20

# Redis配置
redis:
  url: "redis://localhost:6379/0"
  timeout: 5

# 日志配置
logging:
  level: "INFO"
  file: "logs/app.log"
  max_size: "100MB"
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 监控配置
monitoring:
  prometheus:
    enabled: true
    port: 9090
  jaeger:
    enabled: true
    endpoint: "http://localhost:14268/api/traces"
```

## 🚀 部署选项

### Docker Compose (推荐)

```bash
# 开发环境
docker-compose up -d

# 生产环境
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Kubernetes部署

```bash
# 生成K8s配置
kompose convert

# 部署到集群
kubectl apply -f k8s/
```

### Docker Swarm

```bash
# 初始化Swarm
docker swarm init

# 部署Stack
docker stack deploy -c docker-compose.yml docker-manager
```

## 🔒 安全考虑

### 认证和授权

- JWT Token认证
- RBAC权限控制
- API密钥管理
- 会话管理

### 网络安全

- HTTPS/TLS加密
- 防火墙配置
- 网络隔离
- 访问控制列表

### 数据安全

- 敏感数据加密
- 定期备份
- 访问日志审计
- 数据脱敏

## 📈 性能优化

### 缓存策略

- Redis缓存热点数据
- API响应缓存
- 数据库查询优化
- 连接池管理

### 扩展性

- 水平扩展支持
- 负载均衡
- 数据库分片
- 微服务架构

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 开发规范

- 遵循PEP 8代码风格
- 编写单元测试
- 更新文档
- 提交信息规范

## 📝 更新日志

### v1.0.0 (2024-01-01)

- ✨ 初始版本发布
- 🐳 Docker容器管理功能
- ☸️ Kubernetes集群管理功能
- 🚀 REST API和CLI工具
- 📊 监控和告警系统
- 🔒 安全认证和授权

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 支持和帮助

- 📖 [详细文档](DEPLOYMENT.md)
- 🐛 [问题报告](https://github.com/your-repo/issues)
- 💬 [讨论区](https://github.com/your-repo/discussions)
- 📧 [邮件支持](mailto:support@example.com)

## 🙏 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的Web框架
- [Docker SDK](https://docker-py.readthedocs.io/) - Docker Python SDK
- [Kubernetes Python Client](https://github.com/kubernetes-client/python) - K8s Python客户端
- [Prometheus](https://prometheus.io/) - 监控和告警系统
- [Grafana](https://grafana.com/) - 可视化和监控平台
- [Jaeger](https://www.jaegertracing.io/) - 分布式追踪系统

---

**⭐ 如果这个项目对你有帮助，请给我们一个Star！**