#!/bin/bash
# 容器生命周期管理项目启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    # 检查Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    # 检查Docker服务状态
    if ! docker info &> /dev/null; then
        log_error "Docker服务未运行，请启动Docker服务"
        exit 1
    fi
    
    log_success "依赖检查通过"
}

# 初始化配置
init_config() {
    log_info "初始化配置..."
    
    # 创建必要的目录
    mkdir -p logs data backups
    
    # 复制配置文件
    if [ ! -f "config/config.yaml" ] && [ -f "config/config.example.yaml" ]; then
        cp config/config.example.yaml config/config.yaml
        log_success "已创建配置文件: config/config.yaml"
    fi
    
    # 设置权限
    chmod +x main.py
    
    log_success "配置初始化完成"
}

# 构建镜像
build_images() {
    log_info "构建Docker镜像..."
    docker-compose build
    log_success "镜像构建完成"
}

# 启动服务
start_services() {
    log_info "启动服务..."
    docker-compose up -d
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 10
    
    # 检查服务状态
    check_services
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    
    # 检查API服务
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "API服务运行正常: http://localhost:8000"
    else
        log_warning "API服务可能未完全启动，请稍后检查"
    fi
    
    # 检查Grafana
    if curl -f http://localhost:3000/api/health &> /dev/null; then
        log_success "Grafana运行正常: http://localhost:3000"
    else
        log_warning "Grafana可能未完全启动，请稍后检查"
    fi
    
    # 检查Prometheus
    if curl -f http://localhost:9090/-/healthy &> /dev/null; then
        log_success "Prometheus运行正常: http://localhost:9090"
    else
        log_warning "Prometheus可能未完全启动，请稍后检查"
    fi
    
    # 显示容器状态
    echo ""
    log_info "容器状态:"
    docker-compose ps
}

# 显示访问信息
show_access_info() {
    echo ""
    log_success "=== 服务访问信息 ==="
    echo -e "${GREEN}API服务:${NC} http://localhost:8000"
    echo -e "${GREEN}API文档:${NC} http://localhost:8000/docs"
    echo -e "${GREEN}Grafana:${NC} http://localhost:3000 (admin/admin)"
    echo -e "${GREEN}Prometheus:${NC} http://localhost:9090"
    echo -e "${GREEN}Jaeger:${NC} http://localhost:16686"
    echo ""
    log_info "使用 'docker-compose logs -f' 查看日志"
    log_info "使用 'docker-compose down' 停止服务"
    log_info "使用 'make help' 查看更多命令"
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    docker-compose down
    log_success "服务已停止"
}

# 重启服务
restart_services() {
    log_info "重启服务..."
    docker-compose restart
    sleep 5
    check_services
    log_success "服务重启完成"
}

# 查看日志
view_logs() {
    local service=${1:-"docker-manager"}
    log_info "查看 $service 服务日志..."
    docker-compose logs -f "$service"
}

# 清理资源
cleanup() {
    log_info "清理资源..."
    docker-compose down -v --remove-orphans
    docker system prune -f
    log_success "清理完成"
}

# 备份数据
backup_data() {
    log_info "备份数据..."
    
    local backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$backup_dir"
    
    # 备份PostgreSQL
    if docker-compose ps postgres | grep -q "Up"; then
        docker-compose exec -T postgres pg_dump -U docker_manager docker_manager > "$backup_dir/postgres.sql"
        log_success "PostgreSQL数据已备份到: $backup_dir/postgres.sql"
    fi
    
    # 备份Redis
    if docker-compose ps redis | grep -q "Up"; then
        docker-compose exec redis redis-cli --rdb - > "$backup_dir/redis.rdb"
        log_success "Redis数据已备份到: $backup_dir/redis.rdb"
    fi
    
    # 备份配置文件
    cp -r config "$backup_dir/"
    log_success "配置文件已备份到: $backup_dir/config/"
    
    log_success "数据备份完成: $backup_dir"
}

# 显示帮助信息
show_help() {
    echo "容器生命周期管理项目启动脚本"
    echo ""
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     - 启动所有服务（默认）"
    echo "  stop      - 停止所有服务"
    echo "  restart   - 重启所有服务"
    echo "  status    - 检查服务状态"
    echo "  logs      - 查看日志 [服务名]"
    echo "  build     - 构建镜像"
    echo "  backup    - 备份数据"
    echo "  cleanup   - 清理资源"
    echo "  help      - 显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start          # 启动所有服务"
    echo "  $0 logs api       # 查看API服务日志"
    echo "  $0 backup         # 备份数据"
}

# 主函数
main() {
    local command=${1:-"start"}
    
    case $command in
        "start")
            check_dependencies
            init_config
            build_images
            start_services
            show_access_info
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services
            ;;
        "status")
            check_services
            ;;
        "logs")
            view_logs "$2"
            ;;
        "build")
            check_dependencies
            build_images
            ;;
        "backup")
            backup_data
            ;;
        "cleanup")
            cleanup
            ;;
        "help")
            show_help
            ;;
        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"