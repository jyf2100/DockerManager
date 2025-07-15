# 容器生命周期管理项目 Makefile

.PHONY: help install dev test lint format clean build run stop logs shell backup restore

# 默认目标
help:
	@echo "容器生命周期管理项目 - 可用命令:"
	@echo ""
	@echo "开发环境:"
	@echo "  install     - 安装依赖包"
	@echo "  dev         - 启动开发环境"
	@echo "  test        - 运行测试"
	@echo "  lint        - 代码检查"
	@echo "  format      - 代码格式化"
	@echo "  clean       - 清理临时文件"
	@echo ""
	@echo "Docker操作:"
	@echo "  build       - 构建Docker镜像"
	@echo "  run         - 启动服务"
	@echo "  stop        - 停止服务"
	@echo "  restart     - 重启服务"
	@echo "  logs        - 查看日志"
	@echo "  shell       - 进入容器shell"
	@echo ""
	@echo "数据管理:"
	@echo "  backup      - 备份数据"
	@echo "  restore     - 恢复数据"
	@echo ""
	@echo "CLI工具:"
	@echo "  cli-help    - 显示CLI帮助"
	@echo "  docker-info - 显示Docker信息"
	@echo "  k8s-info    - 显示K8s信息"

# 安装依赖
install:
	@echo "安装Python依赖..."
	pip install -r requirements.txt
	@echo "依赖安装完成!"

# 开发环境
dev:
	@echo "启动开发环境..."
	python main.py api --reload --host 0.0.0.0 --port 8000

# 运行测试
test:
	@echo "运行测试..."
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "测试完成! 覆盖率报告: htmlcov/index.html"

# 代码检查
lint:
	@echo "运行代码检查..."
	flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503
	@echo "代码检查完成!"

# 代码格式化
format:
	@echo "格式化代码..."
	black src/ tests/ --line-length=100
	@echo "代码格式化完成!"

# 清理临时文件
clean:
	@echo "清理临时文件..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name "*.egg-info" -delete
	rm -rf build/ dist/ .coverage htmlcov/
	@echo "清理完成!"

# 构建Docker镜像
build:
	@echo "构建Docker镜像..."
	docker-compose build
	@echo "镜像构建完成!"

# 启动服务
run:
	@echo "启动服务..."
	docker-compose up -d
	@echo "服务启动完成!"
	@echo "API服务: http://localhost:8000"
	@echo "API文档: http://localhost:8000/docs"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"

# 停止服务
stop:
	@echo "停止服务..."
	docker-compose down
	@echo "服务已停止!"

# 重启服务
restart: stop run

# 查看日志
logs:
	@echo "查看服务日志..."
	docker-compose logs -f docker-manager

# 进入容器shell
shell:
	@echo "进入容器shell..."
	docker-compose exec docker-manager /bin/bash

# 备份数据
backup:
	@echo "备份数据..."
	mkdir -p backups
	docker-compose exec postgres pg_dump -U docker_manager docker_manager > backups/postgres_$(shell date +%Y%m%d_%H%M%S).sql
	docker-compose exec redis redis-cli --rdb backups/redis_$(shell date +%Y%m%d_%H%M%S).rdb
	@echo "数据备份完成!"

# 恢复数据
restore:
	@echo "恢复数据..."
	@echo "请手动指定备份文件进行恢复"
	@echo "PostgreSQL: docker-compose exec -T postgres psql -U docker_manager docker_manager < backup_file.sql"
	@echo "Redis: docker-compose exec redis redis-cli --pipe < backup_file.rdb"

# CLI工具帮助
cli-help:
	@echo "CLI工具帮助:"
	python main.py cli --help

# 显示Docker信息
docker-info:
	@echo "Docker系统信息:"
	python main.py cli docker info

# 显示K8s信息
k8s-info:
	@echo "Kubernetes集群信息:"
	python main.py cli k8s info

# 显示Docker容器
docker-ps:
	@echo "Docker容器列表:"
	python main.py cli docker ps -a

# 显示K8s Pod
k8s-pods:
	@echo "Kubernetes Pod列表:"
	python main.py cli k8s pods -A

# 健康检查
health:
	@echo "服务健康检查..."
	curl -f http://localhost:8000/health || echo "API服务不可用"
	curl -f http://localhost:3000/api/health || echo "Grafana不可用"
	curl -f http://localhost:9090/-/healthy || echo "Prometheus不可用"

# 性能测试
perf-test:
	@echo "运行性能测试..."
	@echo "请确保服务正在运行"
	ab -n 1000 -c 10 http://localhost:8000/health

# 安全扫描
security-scan:
	@echo "运行安全扫描..."
	bandit -r src/ -f json -o security-report.json
	safety check --json --output safety-report.json
	@echo "安全扫描完成! 查看: security-report.json, safety-report.json"

# 生成API文档
docs:
	@echo "生成API文档..."
	mkdir -p docs/api
	curl http://localhost:8000/openapi.json > docs/api/openapi.json
	@echo "API文档已生成: docs/api/openapi.json"

# 数据库迁移
db-migrate:
	@echo "数据库迁移..."
	docker-compose exec postgres psql -U docker_manager docker_manager -f /docker-entrypoint-initdb.d/init-db.sql

# 监控状态
monitor:
	@echo "监控服务状态..."
	docker-compose ps
	@echo ""
	@echo "资源使用情况:"
	docker stats --no-stream

# 更新依赖
update-deps:
	@echo "更新依赖包..."
	pip list --outdated
	pip install --upgrade pip
	pip-review --local --interactive

# 代码质量检查
quality:
	@echo "代码质量检查..."
	pylint src/ --output-format=json > quality-report.json || true
	mccabe src/ --min 10
	@echo "质量检查完成! 查看: quality-report.json"