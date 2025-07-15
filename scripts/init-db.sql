-- 容器生命周期管理项目数据库初始化脚本

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS docker_manager;

-- 使用数据库
\c docker_manager;

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建Docker主机表
CREATE TABLE IF NOT EXISTS docker_hosts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    host_url VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建Kubernetes集群表
CREATE TABLE IF NOT EXISTS k8s_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    config_type VARCHAR(20) NOT NULL CHECK (config_type IN ('in_cluster', 'kube_config', 'service_account')),
    config_path VARCHAR(255),
    namespace_default VARCHAR(100) DEFAULT 'default',
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建容器操作日志表
CREATE TABLE IF NOT EXISTS container_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(50) NOT NULL,
    container_id VARCHAR(255),
    container_name VARCHAR(255),
    image_name VARCHAR(255),
    docker_host_id UUID REFERENCES docker_hosts(id),
    operation_data JSONB,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'pending')),
    error_message TEXT,
    executed_by UUID REFERENCES users(id),
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建Kubernetes操作日志表
CREATE TABLE IF NOT EXISTS k8s_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    operation_type VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_name VARCHAR(255),
    namespace VARCHAR(100),
    cluster_id UUID REFERENCES k8s_clusters(id),
    operation_data JSONB,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'pending')),
    error_message TEXT,
    executed_by UUID REFERENCES users(id),
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建API访问日志表
CREATE TABLE IF NOT EXISTS api_access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    method VARCHAR(10) NOT NULL,
    path VARCHAR(255) NOT NULL,
    query_params JSONB,
    request_body JSONB,
    response_status INTEGER NOT NULL,
    response_time_ms INTEGER,
    user_id UUID REFERENCES users(id),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_docker_hosts_name ON docker_hosts(name);
CREATE INDEX IF NOT EXISTS idx_k8s_clusters_name ON k8s_clusters(name);
CREATE INDEX IF NOT EXISTS idx_container_operations_type ON container_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_container_operations_status ON container_operations(status);
CREATE INDEX IF NOT EXISTS idx_container_operations_executed_at ON container_operations(executed_at);
CREATE INDEX IF NOT EXISTS idx_k8s_operations_type ON k8s_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_k8s_operations_status ON k8s_operations(status);
CREATE INDEX IF NOT EXISTS idx_k8s_operations_executed_at ON k8s_operations(executed_at);
CREATE INDEX IF NOT EXISTS idx_api_access_logs_path ON api_access_logs(path);
CREATE INDEX IF NOT EXISTS idx_api_access_logs_created_at ON api_access_logs(created_at);

-- 创建更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建更新时间触发器
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_docker_hosts_updated_at BEFORE UPDATE ON docker_hosts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_k8s_clusters_updated_at BEFORE UPDATE ON k8s_clusters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_system_configs_updated_at BEFORE UPDATE ON system_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入默认管理员用户（密码: admin123）
INSERT INTO users (username, email, password_hash, is_admin) 
VALUES (
    'admin', 
    'admin@dockermanager.local', 
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq5S/kS', 
    true
) ON CONFLICT (username) DO NOTHING;

-- 插入默认系统配置
INSERT INTO system_configs (config_key, config_value, description) VALUES
('api_rate_limit', '{"requests_per_minute": 100, "burst_size": 20}', 'API访问频率限制'),
('docker_timeout', '{"default": 60, "build": 300, "pull": 600}', 'Docker操作超时设置'),
('k8s_timeout', '{"default": 30, "deploy": 300, "scale": 120}', 'Kubernetes操作超时设置'),
('log_retention', '{"api_logs_days": 30, "operation_logs_days": 90}', '日志保留策略'),
('monitoring', '{"enabled": true, "metrics_interval": 30}', '监控配置')
ON CONFLICT (config_key) DO NOTHING;

-- 创建视图：操作统计
CREATE OR REPLACE VIEW operation_stats AS
SELECT 
    'docker' as platform,
    operation_type,
    status,
    COUNT(*) as count,
    DATE_TRUNC('day', executed_at) as date
FROM container_operations
GROUP BY operation_type, status, DATE_TRUNC('day', executed_at)
UNION ALL
SELECT 
    'kubernetes' as platform,
    operation_type,
    status,
    COUNT(*) as count,
    DATE_TRUNC('day', executed_at) as date
FROM k8s_operations
GROUP BY operation_type, status, DATE_TRUNC('day', executed_at);

-- 创建视图：用户活动统计
CREATE OR REPLACE VIEW user_activity_stats AS
SELECT 
    u.username,
    u.email,
    COUNT(DISTINCT co.id) as docker_operations,
    COUNT(DISTINCT ko.id) as k8s_operations,
    COUNT(DISTINCT al.id) as api_calls,
    MAX(GREATEST(co.executed_at, ko.executed_at, al.created_at)) as last_activity
FROM users u
LEFT JOIN container_operations co ON u.id = co.executed_by
LEFT JOIN k8s_operations ko ON u.id = ko.executed_by
LEFT JOIN api_access_logs al ON u.id = al.user_id
GROUP BY u.id, u.username, u.email;

-- 授权
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO docker_manager;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO docker_manager;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO docker_manager;

-- 完成初始化
SELECT 'Database initialization completed successfully!' as status;