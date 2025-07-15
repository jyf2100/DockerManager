# 容器生命周期管理项目部署指南

## 项目概述

本项目是一个全功能的容器生命周期管理系统，支持Docker容器和Kubernetes集群的统一管理。提供了REST API、CLI工具和Web界面，集成了监控、日志和链路追踪功能。

## 系统要求

### 最低要求
- **操作系统**: Linux (Ubuntu 18.04+, CentOS 7+) / macOS / Windows 10+
- **内存**: 4GB RAM
- **存储**: 20GB 可用空间
- **CPU**: 2核心

### 推荐配置
- **操作系统**: Linux (Ubuntu 20.04+)
- **内存**: 8GB+ RAM
- **存储**: 50GB+ SSD
- **CPU**: 4核心+

### 依赖软件
- Docker 20.10+
- Docker Compose 1.29+
- Python 3.9+ (开发环境)
- Git

## 快速开始

### 1. 克隆项目
```bash
git clone <repository-url>
cd DockerManager
```

### 2. 一键启动
```bash
# 使用启动脚本（推荐）
./start.sh

# 或使用Make命令
make run

# 或直接使用Docker Compose
docker-compose up -d
```

### 3. 访问服务
- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Grafana监控**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger链路追踪**: http://localhost:16686

## 详细部署步骤

### 1. 环境准备

#### 安装Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# CentOS/RHEL
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
```

#### 安装Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 配置文件设置

#### 复制配置模板
```bash
cp config/config.example.yaml config/config.yaml
```

#### 编辑配置文件
```yaml
# config/config.yaml
api:
  host: "0.0.0.0"
  port: 8000
  debug: false

docker:
  host: "unix:///var/run/docker.sock"
  timeout: 60

kubernetes:
  config_type: "kube_config"  # in_cluster, kube_config, service_account
  config_path: "~/.kube/config"
  namespace: "default"

logging:
  level: "INFO"
  file: "logs/app.log"
  max_size: "100MB"
  backup_count: 5
```

### 3. 数据库配置

项目使用PostgreSQL作为主数据库，Redis作为缓存。配置已在docker-compose.yml中预设，默认配置：

- **PostgreSQL**:
  - 数据库: docker_manager
  - 用户: docker_manager
  - 密码: docker_manager_password
  - 端口: 5432

- **Redis**:
  - 端口: 6379
  - 无密码（开发环境）

### 4. 网络配置

#### 端口映射
| 服务 | 内部端口 | 外部端口 | 说明 |
|------|----------|----------|------|
| API服务 | 8000 | 8000 | 主要API接口 |
| Nginx | 80/443 | 80/443 | 反向代理 |
| PostgreSQL | 5432 | 5432 | 数据库 |
| Redis | 6379 | 6379 | 缓存 |
| Grafana | 3000 | 3000 | 监控面板 |
| Prometheus | 9090 | 9090 | 指标收集 |
| Jaeger | 16686 | 16686 | 链路追踪 |

#### 防火墙设置
```bash
# Ubuntu/Debian
sudo ufw allow 8000
sudo ufw allow 3000
sudo ufw allow 9090

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp
sudo firewall-cmd --reload
```

## 生产环境部署

### 1. 安全配置

#### SSL/TLS证书
```bash
# 创建SSL目录
mkdir -p nginx/ssl

# 生成自签名证书（测试用）
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem

# 或使用Let's Encrypt（生产环境）
certbot certonly --standalone -d your-domain.com
```

#### 环境变量
```bash
# 创建.env文件
cat > .env << EOF
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
API_SECRET_KEY=your_secret_key
JWT_SECRET=your_jwt_secret
EOF
```

### 2. 性能优化

#### 资源限制
```yaml
# docker-compose.override.yml
version: '3.8'
services:
  docker-manager:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### 数据库优化
```yaml
# PostgreSQL配置优化
postgres:
  environment:
    - POSTGRES_SHARED_PRELOAD_LIBRARIES=pg_stat_statements
    - POSTGRES_MAX_CONNECTIONS=200
    - POSTGRES_SHARED_BUFFERS=256MB
    - POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
```

### 3. 监控配置

#### Grafana仪表板
1. 访问 http://localhost:3000
2. 使用 admin/admin 登录
3. 添加Prometheus数据源: http://prometheus:9090
4. 导入预设仪表板

#### 告警配置
```yaml
# prometheus/alert_rules.yml
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
```

## 运维管理

### 1. 日常维护

#### 查看服务状态
```bash
# 检查所有服务
./start.sh status

# 查看特定服务日志
./start.sh logs docker-manager

# 查看资源使用
docker stats
```

#### 数据备份
```bash
# 自动备份
./start.sh backup

# 手动备份数据库
make backup

# 定时备份（添加到crontab）
0 2 * * * /path/to/project/start.sh backup
```

#### 日志管理
```bash
# 清理旧日志
docker system prune -f

# 限制日志大小
docker-compose.yml中添加:
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 2. 故障排除

#### 常见问题

**API服务无法启动**
```bash
# 检查端口占用
sudo netstat -tlnp | grep 8000

# 检查Docker socket权限
sudo chmod 666 /var/run/docker.sock

# 查看详细错误
docker-compose logs docker-manager
```

**数据库连接失败**
```bash
# 检查数据库状态
docker-compose exec postgres pg_isready

# 重置数据库
docker-compose down postgres
docker volume rm dockermanager_postgres_data
docker-compose up -d postgres
```

**Kubernetes连接问题**
```bash
# 检查kubeconfig
kubectl cluster-info

# 验证权限
kubectl auth can-i get pods

# 更新配置
cp ~/.kube/config config/kubeconfig
```

### 3. 性能监控

#### 关键指标
- API响应时间
- 错误率
- 内存使用率
- CPU使用率
- 数据库连接数
- 容器操作成功率

#### 监控查询
```promql
# API请求率
rate(http_requests_total[5m])

# 错误率
rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])

# 响应时间
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

## 扩展部署

### 1. 集群部署

#### Docker Swarm
```bash
# 初始化Swarm
docker swarm init

# 部署Stack
docker stack deploy -c docker-compose.yml docker-manager
```

#### Kubernetes部署
```bash
# 生成Kubernetes配置
kompose convert

# 部署到K8s
kubectl apply -f .
```

### 2. 负载均衡

#### Nginx负载均衡
```nginx
upstream docker_manager_api {
    least_conn;
    server docker-manager-1:8000;
    server docker-manager-2:8000;
    server docker-manager-3:8000;
}
```

### 3. 高可用配置

#### 数据库主从
```yaml
# PostgreSQL主从配置
postgres-master:
  image: postgres:15-alpine
  environment:
    - POSTGRES_REPLICATION_MODE=master
    - POSTGRES_REPLICATION_USER=replicator
    - POSTGRES_REPLICATION_PASSWORD=replicator_password

postgres-slave:
  image: postgres:15-alpine
  environment:
    - POSTGRES_REPLICATION_MODE=slave
    - POSTGRES_MASTER_HOST=postgres-master
```

## 安全最佳实践

### 1. 网络安全
- 使用防火墙限制端口访问
- 配置SSL/TLS加密
- 使用VPN或专用网络
- 定期更新证书

### 2. 访问控制
- 实施强密码策略
- 启用多因素认证
- 定期轮换密钥
- 最小权限原则

### 3. 数据安全
- 加密敏感数据
- 定期备份
- 访问日志审计
- 数据脱敏

## 故障恢复

### 1. 数据恢复
```bash
# 恢复PostgreSQL
docker-compose exec -T postgres psql -U docker_manager docker_manager < backup.sql

# 恢复Redis
docker-compose exec redis redis-cli --pipe < backup.rdb
```

### 2. 服务恢复
```bash
# 重启所有服务
./start.sh restart

# 重建损坏的容器
docker-compose up -d --force-recreate
```

### 3. 灾难恢复
```bash
# 完全重新部署
./start.sh cleanup
./start.sh start
```

## 联系支持

如果遇到问题，请：
1. 查看日志文件
2. 检查GitHub Issues
3. 提交详细的错误报告
4. 联系技术支持团队

---

**注意**: 本文档会随着项目更新而更新，请定期查看最新版本。