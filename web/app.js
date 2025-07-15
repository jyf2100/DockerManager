/**
 * 容器生命周期管理平台 - 前端应用
 * 提供Docker和Kubernetes资源的Web界面管理
 */

class ContainerManager {
    constructor() {
        this.apiBase = '/api/v1';
        this.currentNamespace = '';
        this.autoRefreshInterval = null;
        this.init();
    }

    /**
     * 初始化应用
     */
    init() {
        this.setupEventListeners();
        this.checkApiStatus();
        
        // 获取当前激活的标签并加载对应数据
        const activeTab = document.querySelector('.nav-item.active')?.dataset.tab || 'dashboard';
        this.loadTabData(activeTab);
        
        this.startAutoRefresh();
    }

    /**
     * 设置事件监听器
     */
    setupEventListeners() {
        // 导航切换
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                this.switchTab(tab);
            });
        });

        // 子导航切换
        document.querySelectorAll('.sub-nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const subtab = e.currentTarget.dataset.subtab;
                this.switchSubTab(subtab);
            });
        });

        // 刷新按钮
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshCurrentView();
        });

        // 模态框关闭
        document.getElementById('modalClose').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('modalCancel').addEventListener('click', () => {
            this.closeModal();
        });

        // 点击模态框外部关闭
        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') {
                this.closeModal();
            }
        });

        // 命名空间选择器
        document.getElementById('namespaceSelector').addEventListener('change', (e) => {
            this.currentNamespace = e.target.value;
            this.refreshKubernetesData();
        });

        // 创建按钮
        document.getElementById('createContainerBtn')?.addEventListener('click', () => {
            this.showCreateContainerModal();
        });

        document.getElementById('pullImageBtn')?.addEventListener('click', () => {
            this.showPullImageModal();
        });

        document.getElementById('createPodBtn')?.addEventListener('click', () => {
            this.showCreatePodModal();
        });
    }

    /**
     * 切换主导航标签
     */
    switchTab(tab) {
        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        // 更新内容显示
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tab).classList.add('active');

        // 加载对应数据
        this.loadTabData(tab);
    }

    /**
     * 切换子导航标签
     */
    switchSubTab(subtab) {
        const parentTab = document.querySelector('.tab-content.active').id;
        
        // 更新子导航状态
        document.querySelectorAll(`#${parentTab} .sub-nav-item`).forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`#${parentTab} [data-subtab="${subtab}"]`).classList.add('active');

        // 更新子内容显示
        document.querySelectorAll(`#${parentTab} .sub-content`).forEach(content => {
            content.classList.remove('active');
        });
        document.querySelector(`#${parentTab} #${subtab}`).classList.add('active');

        // 加载对应数据
        this.loadSubTabData(parentTab, subtab);
    }

    /**
     * 检查API状态
     */
    async checkApiStatus() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            const statusElement = document.getElementById('apiStatus');
            const dot = statusElement.querySelector('.status-dot');
            const text = statusElement.querySelector('.status-text');
            
            if (data.status === 'healthy') {
                dot.className = 'status-dot';
                text.textContent = '服务正常';
            } else {
                dot.className = 'status-dot warning';
                text.textContent = '服务异常';
            }
        } catch (error) {
            const statusElement = document.getElementById('apiStatus');
            const dot = statusElement.querySelector('.status-dot');
            const text = statusElement.querySelector('.status-text');
            
            dot.className = 'status-dot error';
            text.textContent = '连接失败';
            
            this.showNotification('API连接失败', 'error');
        }
    }

    /**
     * 加载标签页数据
     */
    async loadTabData(tab) {
        switch (tab) {
            case 'dashboard':
                await this.loadDashboard();
                break;
            case 'docker':
                await this.loadDockerData();
                break;
            case 'kubernetes':
                await this.loadKubernetesData();
                break;
            case 'monitoring':
                // 监控页面是静态的，不需要加载数据
                break;
        }
    }

    /**
     * 加载子标签页数据
     */
    async loadSubTabData(parentTab, subtab) {
        if (parentTab === 'docker') {
            switch (subtab) {
                case 'containers':
                    await this.loadContainers();
                    break;
                case 'images':
                    await this.loadImages();
                    break;
                case 'networks':
                    await this.loadNetworks();
                    break;
                case 'volumes':
                    await this.loadVolumes();
                    break;
            }
        } else if (parentTab === 'kubernetes') {
            switch (subtab) {
                case 'pods':
                    await this.loadPods();
                    break;
                case 'deployments':
                    await this.loadDeployments();
                    break;
                case 'services':
                    await this.loadServices();
                    break;
                case 'namespaces':
                    await this.loadNamespaces();
                    break;
            }
        }
    }

    /**
     * 加载仪表板数据
     */
    async loadDashboard() {
        try {
            // 加载Docker统计
            const dockerStats = await this.fetchDockerStats();
            this.updateDashboardStats(dockerStats);

            // 加载系统信息
            const systemInfo = await this.fetchSystemInfo();
            this.updateSystemInfo(systemInfo);
        } catch (error) {
            console.error('加载仪表板数据失败:', error);
            this.showNotification('加载仪表板数据失败', 'error');
        }
    }

    /**
     * 获取Docker统计信息
     */
    async fetchDockerStats() {
        const fetchWithCheck = async (url) => {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        };

        const [containers, images, networks, volumes] = await Promise.all([
            fetchWithCheck(`${this.apiBase}/docker/containers?all=true`),
            fetchWithCheck(`${this.apiBase}/docker/images`),
            fetchWithCheck(`${this.apiBase}/docker/networks`),
            fetchWithCheck(`${this.apiBase}/docker/volumes`)
        ]);

        return {
            containers: {
                total: containers.length,
                running: containers.filter(c => c.status === 'running').length
            },
            images: {
                total: images.length,
                size: this.formatBytes(images.reduce((sum, img) => sum + (img.Size || 0), 0))
            },
            networks: networks.length,
            volumes: {
                total: volumes.Volumes?.length || 0,
                size: 'N/A' // Docker API不直接提供卷大小信息
            }
        };
    }

    /**
     * 获取系统信息
     */
    async fetchSystemInfo() {
        const response = await fetch('/info');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    }

    /**
     * 更新仪表板统计
     */
    updateDashboardStats(stats) {
        document.getElementById('dockerContainers').textContent = stats.containers.total;
        document.getElementById('dockerRunning').textContent = `运行中: ${stats.containers.running}`;
        
        document.getElementById('dockerImages').textContent = stats.images.total;
        document.getElementById('imageSize').textContent = `总大小: ${stats.images.size}`;
        
        document.getElementById('dockerVolumes').textContent = stats.volumes.total;
        document.getElementById('volumeSize').textContent = `使用空间: ${stats.volumes.size}`;
    }

    /**
     * 更新系统信息
     */
    updateSystemInfo(info) {
        // 更新Docker信息
        const dockerInfo = document.getElementById('dockerInfo');
        if (info.services?.docker) {
            const docker = info.services.docker;
            dockerInfo.innerHTML = `
                <div class="info-item">
                    <strong>状态:</strong> <span class="status-badge ${docker.status === 'connected' ? 'running' : 'stopped'}">${docker.status}</span>
                </div>
                <div class="info-item">
                    <strong>版本:</strong> ${docker.version || 'N/A'}
                </div>
                <div class="info-item">
                    <strong>API版本:</strong> ${docker.api_version || 'N/A'}
                </div>
            `;
        } else {
            dockerInfo.innerHTML = '<div class="error">无法获取Docker信息</div>';
        }

        // 更新Kubernetes信息
        const k8sInfo = document.getElementById('k8sInfo');
        if (info.services?.kubernetes) {
            const k8s = info.services.kubernetes;
            k8sInfo.innerHTML = `
                <div class="info-item">
                    <strong>状态:</strong> <span class="status-badge ${k8s.status === 'connected' ? 'running' : 'stopped'}">${k8s.status}</span>
                </div>
                <div class="info-item">
                    <strong>版本:</strong> ${k8s.version || 'N/A'}
                </div>
                <div class="info-item">
                    <strong>当前命名空间:</strong> ${k8s.current_namespace || 'default'}
                </div>
            `;
        } else {
            k8sInfo.innerHTML = '<div class="error">无法获取Kubernetes信息</div>';
        }
    }

    /**
     * 加载Docker数据
     */
    async loadDockerData() {
        const activeSubTab = document.querySelector('#docker .sub-nav-item.active')?.dataset.subtab || 'containers';
        await this.loadSubTabData('docker', activeSubTab);
    }

    /**
     * 加载容器列表
     */
    async loadContainers() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('containersTable');
            tbody.innerHTML = '<tr><td colspan="6" class="loading">正在加载容器列表...</td></tr>';
            
            const response = await fetch(`${this.apiBase}/docker/containers?all=true`);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const containers = await response.json();
            
            // 检查返回数据格式
            if (!Array.isArray(containers)) {
                throw new Error('API返回的数据格式不正确');
            }
            
            if (containers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">暂无容器</td></tr>';
                return;
            }

            tbody.innerHTML = containers.map(container => {
                // 验证容器对象
                if (!container || typeof container !== 'object') {
                    console.warn('无效的容器对象:', container);
                    return '';
                }
                
                // 安全地获取容器名称
                const containerName = container.name || (container.id && typeof container.id === 'string' && container.id.length > 12 ? container.id.substring(0, 12) : container.id) || '未知';
                const containerId = container.id || '';
                const containerImage = container.image || '未知';
                const containerState = container.status || 'unknown';
                
                return `
                    <tr>
                        <td>
                            <strong>${containerName}</strong>
                        </td>
                        <td>${containerImage}</td>
                        <td>
                            <span class="status-badge ${containerState === 'running' ? 'running' : 'stopped'}">
                                ${containerState}
                            </span>
                        </td>
                        <td>${this.formatPorts(container.ports)}</td>
                        <td>${this.formatDate(container.created)}</td>
                        <td>
                            <div class="action-buttons">
                                ${containerState === 'running' ? 
                                    `<button class="action-btn stop" onclick="containerManager.stopContainer('${containerId}')" title="停止">
                                        <i class="fas fa-stop"></i>
                                    </button>
                                    <button class="action-btn restart" onclick="containerManager.restartContainer('${containerId}')" title="重启">
                                        <i class="fas fa-redo"></i>
                                    </button>` :
                                    `<button class="action-btn start" onclick="containerManager.startContainer('${containerId}')" title="启动">
                                        <i class="fas fa-play"></i>
                                    </button>`
                                }
                                <button class="action-btn logs" onclick="containerManager.showContainerLogs('${containerId}')" title="日志">
                                    <i class="fas fa-file-alt"></i>
                                </button>
                                <button class="action-btn exec" onclick="containerManager.showContainerExec('${containerId}')" title="执行命令">
                                    <i class="fas fa-terminal"></i>
                                </button>
                                <button class="action-btn delete" onclick="containerManager.removeContainer('${containerId}')" title="删除">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载容器列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('containersTable');
            tbody.innerHTML = `<tr><td colspan="6" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载容器列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 加载镜像列表
     */
    async loadImages() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('imagesTable');
            tbody.innerHTML = '<tr><td colspan="6" class="loading">正在加载镜像列表...</td></tr>';
            
            const response = await fetch(`${this.apiBase}/docker/images`);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const images = await response.json();
            
            // 检查返回数据格式
            if (!Array.isArray(images)) {
                throw new Error('API返回的数据格式不正确');
            }
            
            if (images.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">暂无镜像</td></tr>';
                return;
            }

            tbody.innerHTML = images.map(image => {
                // 验证镜像对象
                if (!image || typeof image !== 'object') {
                    console.warn('无效的镜像对象:', image);
                    return '';
                }
                
                const repoTags = image.tags || ['<none>:<none>'];
                // 安全地处理标签分割
                const firstTag = repoTags[0] || '<none>:<none>';
                const tagParts = firstTag.split(':');
                const repository = tagParts[0] || '<none>';
                const tag = tagParts[1] || '<none>';
                const imageId = image.id || '';
                const imageSize = image.size || 0;
                const imageCreated = image.created || null;
                
                return `
                    <tr>
                        <td><strong>${repository || '未知'}</strong></td>
                        <td>${tag || '未知'}</td>
                        <td><code>${imageId && imageId.length > 19 ? imageId.substring(7, 19) : (imageId || '未知')}</code></td>
                        <td>${this.formatBytes(imageSize)}</td>
                        <td>${this.formatDate(imageCreated)}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="action-btn delete" onclick="containerManager.removeImage('${imageId}')" title="删除">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载镜像列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('imagesTable');
            tbody.innerHTML = `<tr><td colspan="6" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载镜像列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 加载网络列表
     */
    async loadNetworks() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('networksTable');
            tbody.innerHTML = '<tr><td colspan="6" class="loading">正在加载网络列表...</td></tr>';
            
            const response = await fetch(`${this.apiBase}/docker/networks`);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const networks = await response.json();
            
            // 检查返回数据格式
            if (!Array.isArray(networks)) {
                throw new Error('API返回的数据格式不正确');
            }
            
            if (networks.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">暂无网络</td></tr>';
                return;
            }

            tbody.innerHTML = networks.map(network => {
                const ipam = network.ipam?.Config?.[0] || {};
                const networkName = network.name || '未知';
                const networkId = network.id || '';
                const networkDriver = network.driver || '未知';
                const networkScope = network.scope || '未知';
                
                return `
                    <tr>
                        <td><strong>${networkName}</strong></td>
                        <td>${networkDriver}</td>
                        <td>${networkScope}</td>
                        <td>${ipam.Subnet || 'N/A'}</td>
                        <td>${ipam.Gateway || 'N/A'}</td>
                        <td>
                            <div class="action-buttons">
                                ${!['bridge', 'host', 'none'].includes(networkName) ? 
                                    `<button class="action-btn delete" onclick="containerManager.removeNetwork('${networkId}')" title="删除">
                                        <i class="fas fa-trash"></i>
                                    </button>` : ''
                                }
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载网络列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('networksTable');
            tbody.innerHTML = `<tr><td colspan="6" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载网络列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 加载存储卷列表
     */
    async loadVolumes() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('volumesTable');
            tbody.innerHTML = '<tr><td colspan="5" class="loading">正在加载存储卷列表...</td></tr>';
            
            const response = await fetch(`${this.apiBase}/docker/volumes`);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // 检查返回数据格式
            if (!data || typeof data !== 'object') {
                throw new Error('API返回的数据格式不正确');
            }
            
            const volumes = Array.isArray(data) ? data : [];
            
            if (volumes.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="loading">暂无存储卷</td></tr>';
                return;
            }

            tbody.innerHTML = volumes.map(volume => {
                const volumeName = volume.name || '未知';
                const volumeDriver = volume.driver || '未知';
                const volumeMountpoint = volume.mountpoint || '未知';
                const volumeCreated = volume.created || null;
                
                return `
                    <tr>
                        <td><strong>${volumeName}</strong></td>
                        <td>${volumeDriver}</td>
                        <td><code>${volumeMountpoint}</code></td>
                        <td>${this.formatDate(volumeCreated)}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="action-btn delete" onclick="containerManager.removeVolume('${volumeName}')" title="删除">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载存储卷列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('volumesTable');
            tbody.innerHTML = `<tr><td colspan="5" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载存储卷列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 加载Kubernetes数据
     */
    async loadKubernetesData() {
        await this.loadNamespaces();
        const activeSubTab = document.querySelector('#kubernetes .sub-nav-item.active')?.dataset.subtab || 'pods';
        await this.loadSubTabData('kubernetes', activeSubTab);
    }

    /**
     * 加载命名空间列表
     */
    async loadNamespaces() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('namespacesTable');
            tbody.innerHTML = '<tr><td colspan="4" class="loading">正在加载命名空间列表...</td></tr>';
            
            const response = await fetch(`${this.apiBase}/k8s/namespaces`);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // 检查返回数据格式
            if (!data || typeof data !== 'object') {
                throw new Error('API返回的数据格式不正确');
            }
            
            const namespaces = Array.isArray(data) ? data : (data.items || []);
            
            // 更新命名空间选择器
            const selector = document.getElementById('namespaceSelector');
            selector.innerHTML = '<option value="">所有命名空间</option>' + 
                namespaces.map(ns => 
                    `<option value="${ns.name || ''}" ${(ns.name || '') === this.currentNamespace ? 'selected' : ''}>
                        ${ns.name || '未知'}
                    </option>`
                ).join('');

            // 更新命名空间表格
            if (namespaces.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="loading">暂无命名空间</td></tr>';
                return;
            }

            tbody.innerHTML = namespaces.map(ns => {
                const nsName = ns.name || '未知';
                const nsPhase = ns.status || '未知';
                const nsCreated = ns.age || null;
                
                return `
                    <tr>
                        <td><strong>${nsName}</strong></td>
                        <td>
                            <span class="status-badge ${nsPhase === 'Active' ? 'running' : 'stopped'}">
                                ${nsPhase}
                            </span>
                        </td>
                        <td>${this.formatDate(nsCreated)}</td>
                        <td>
                            <div class="action-buttons">
                                ${!['default', 'kube-system', 'kube-public'].includes(nsName) ? 
                                    `<button class="action-btn delete" onclick="containerManager.removeNamespace('${nsName}')" title="删除">
                                        <i class="fas fa-trash"></i>
                                    </button>` : ''
                                }
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载命名空间列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('namespacesTable');
            tbody.innerHTML = `<tr><td colspan="4" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载命名空间列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 加载Pod列表
     */
    async loadPods() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('podsTable');
            tbody.innerHTML = '<tr><td colspan="7" class="loading">正在加载Pod列表...</td></tr>';
            
            const url = this.currentNamespace ? 
                `${this.apiBase}/k8s/pods?namespace=${this.currentNamespace}` : 
                `${this.apiBase}/k8s/pods`;
            
            const response = await fetch(url);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // 检查返回数据格式
            if (!data || typeof data !== 'object') {
                throw new Error('API返回的数据格式不正确');
            }
            
            const pods = Array.isArray(data) ? data : (data.items || []);
            
            if (pods.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">暂无Pod</td></tr>';
                return;
            }

            tbody.innerHTML = pods.map(pod => {
                const podName = pod.name || '未知';
                const podNamespace = pod.namespace || '未知';
                const status = pod.status || '未知';
                const restartCount = pod.restarts || 0;
                const nodeName = pod.node || 'N/A';
                const createdTime = pod.age || null;
                
                return `
                    <tr>
                        <td><strong>${podName}</strong></td>
                        <td>${podNamespace}</td>
                        <td>
                            <span class="status-badge ${status === 'Running' ? 'running' : status === 'Pending' ? 'pending' : 'stopped'}">
                                ${status}
                            </span>
                        </td>
                        <td>${restartCount}</td>
                        <td>${nodeName}</td>
                        <td>${this.formatDate(createdTime)}</td>
                        <td>
                            <div class="action-buttons">
                                <button class="action-btn logs" onclick="containerManager.showPodLogs('${podName}', '${podNamespace}')" title="日志">
                                    <i class="fas fa-file-alt"></i>
                                </button>
                                <button class="action-btn delete" onclick="containerManager.removePod('${podName}', '${podNamespace}')" title="删除">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('加载Pod列表失败:', error);
            
            // 显示错误信息
            const tbody = document.getElementById('podsTable');
            tbody.innerHTML = `<tr><td colspan="7" class="error">加载失败: ${error.message}</td></tr>`;
            
            this.showNotification(`加载Pod列表失败: ${error.message}`, 'error');
        }
    }

    /**
     * 容器操作方法
     */
    async startContainer(containerId) {
        try {
            await fetch(`${this.apiBase}/docker/containers/${containerId}/start`, {
                method: 'POST'
            });
            this.showNotification('容器启动成功', 'success');
            await this.loadContainers();
        } catch (error) {
            this.showNotification('容器启动失败', 'error');
        }
    }

    async stopContainer(containerId) {
        try {
            await fetch(`${this.apiBase}/docker/containers/${containerId}/stop`, {
                method: 'POST'
            });
            this.showNotification('容器停止成功', 'success');
            await this.loadContainers();
        } catch (error) {
            this.showNotification('容器停止失败', 'error');
        }
    }

    async restartContainer(containerId) {
        try {
            await fetch(`${this.apiBase}/docker/containers/${containerId}/restart`, {
                method: 'POST'
            });
            this.showNotification('容器重启成功', 'success');
            await this.loadContainers();
        } catch (error) {
            this.showNotification('容器重启失败', 'error');
        }
    }

    async removeContainer(containerId) {
        if (!confirm('确定要删除这个容器吗？')) return;
        
        try {
            await fetch(`${this.apiBase}/docker/containers/${containerId}`, {
                method: 'DELETE'
            });
            this.showNotification('容器删除成功', 'success');
            await this.loadContainers();
        } catch (error) {
            this.showNotification('容器删除失败', 'error');
        }
    }

    /**
     * 显示容器日志
     */
    async showContainerLogs(containerId) {
        try {
            const response = await fetch(`${this.apiBase}/docker/containers/${containerId}/logs?tail=100`);
            const data = await response.json();
            
            this.showModal('容器日志', `
                <div style="background: #1a1a1a; color: #fff; padding: 1rem; border-radius: 8px; font-family: monospace; max-height: 400px; overflow-y: auto;">
                    <pre>${data.logs || '暂无日志'}</pre>
                </div>
            `, false);
        } catch (error) {
            this.showNotification('获取容器日志失败', 'error');
        }
    }

    /**
     * 工具方法
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString * 1000 || dateString);
        return date.toLocaleString('zh-CN');
    }

    formatPorts(ports) {
        if (!ports || typeof ports !== 'object' || Object.keys(ports).length === 0) return 'N/A';
        
        const portList = [];
        for (const [containerPort, hostBindings] of Object.entries(ports)) {
            if (hostBindings && hostBindings.length > 0) {
                hostBindings.forEach(binding => {
                    portList.push(`${binding.HostPort}:${containerPort}`);
                });
            } else {
                portList.push(containerPort);
            }
        }
        
        return portList.length > 0 ? portList.join(', ') : 'N/A';
    }

    /**
     * 显示模态框
     */
    showModal(title, content, showFooter = true) {
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalBody').innerHTML = content;
        document.getElementById('modalFooter').style.display = showFooter ? 'flex' : 'none';
        document.getElementById('modal').classList.add('active');
    }

    /**
     * 关闭模态框
     */
    closeModal() {
        document.getElementById('modal').classList.remove('active');
    }

    /**
     * 显示通知
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        document.getElementById('notifications').appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    /**
     * 刷新当前视图
     */
    refreshCurrentView() {
        const activeTab = document.querySelector('.nav-item.active')?.dataset.tab;
        if (activeTab) {
            this.loadTabData(activeTab);
        }
    }

    /**
     * 开始自动刷新
     */
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.checkApiStatus();
            // 只在仪表板页面自动刷新数据
            const activeTab = document.querySelector('.nav-item.active')?.dataset.tab;
            if (activeTab === 'dashboard') {
                this.loadDashboard();
            }
        }, 30000); // 30秒刷新一次
    }

    /**
     * 停止自动刷新
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * 刷新Kubernetes数据
     */
    async refreshKubernetesData() {
        const activeSubTab = document.querySelector('#kubernetes .sub-nav-item.active')?.dataset.subtab;
        if (activeSubTab) {
            await this.loadSubTabData('kubernetes', activeSubTab);
        }
    }

    // 占位方法，用于未来扩展
    showCreateContainerModal() {
        this.showNotification('创建容器功能开发中...', 'info');
    }

    showPullImageModal() {
        this.showNotification('拉取镜像功能开发中...', 'info');
    }

    showCreatePodModal() {
        this.showNotification('创建Pod功能开发中...', 'info');
    }

    async removeImage(imageId) {
        if (!confirm('确定要删除这个镜像吗？')) return;
        this.showNotification('删除镜像功能开发中...', 'info');
    }

    async removeNetwork(networkId) {
        if (!confirm('确定要删除这个网络吗？')) return;
        this.showNotification('删除网络功能开发中...', 'info');
    }

    async removeVolume(volumeName) {
        if (!confirm('确定要删除这个存储卷吗？')) return;
        this.showNotification('删除存储卷功能开发中...', 'info');
    }

    async removeNamespace(namespaceName) {
        if (!confirm('确定要删除这个命名空间吗？')) return;
        this.showNotification('删除命名空间功能开发中...', 'info');
    }

    async removePod(podName, namespace) {
        if (!confirm('确定要删除这个Pod吗？')) return;
        this.showNotification('删除Pod功能开发中...', 'info');
    }

    async showPodLogs(podName, namespace) {
        this.showNotification('查看Pod日志功能开发中...', 'info');
    }

    async showContainerExec(containerId) {
        this.showNotification('容器命令执行功能开发中...', 'info');
    }

    async showDeploymentDetails(deploymentName, namespace) {
        this.showNotification('查看Deployment详情功能开发中...', 'info');
    }

    async scaleDeployment(deploymentName, namespace) {
        this.showNotification('Deployment扩缩容功能开发中...', 'info');
    }

    async removeDeployment(deploymentName, namespace) {
        if (!confirm('确定要删除这个Deployment吗？')) return;
        this.showNotification('删除Deployment功能开发中...', 'info');
    }

    async showServiceDetails(serviceName, namespace) {
        this.showNotification('查看Service详情功能开发中...', 'info');
    }

    async removeService(serviceName, namespace) {
        if (!confirm('确定要删除这个Service吗？')) return;
        this.showNotification('删除Service功能开发中...', 'info');
    }

    async loadDeployments() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('deploymentsTable');
            tbody.innerHTML = '<tr><td colspan="7" class="loading">正在加载Deployment列表...</td></tr>';
            
            const url = this.currentNamespace ? 
                `${this.apiBase}/k8s/deployments?namespace=${this.currentNamespace}` : 
                `${this.apiBase}/k8s/deployments`;
            
            const response = await fetch(url);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // 检查返回数据格式
            if (!Array.isArray(data)) {
                throw new Error('API返回的数据格式不正确');
            }
            
            // 清空表格
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="no-data">暂无Deployment</td></tr>';
                return;
            }
            
            // 填充表格数据
            data.forEach(deployment => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${deployment.name || 'N/A'}</td>
                    <td>${deployment.namespace || 'N/A'}</td>
                    <td>${deployment.ready_replicas || 0}/${deployment.replicas || 0}</td>
                    <td>${deployment.updated_replicas || 0}</td>
                    <td>${deployment.available_replicas || 0}</td>
                    <td>${this.formatDate(deployment.age)}</td>
                    <td>
                        <button class="btn btn-sm" onclick="containerManager.showDeploymentDetails('${deployment.name}', '${deployment.namespace}')" title="查看详情">
                            <i class="fas fa-info-circle"></i>
                        </button>
                        <button class="btn btn-sm btn-warning" onclick="containerManager.scaleDeployment('${deployment.name}', '${deployment.namespace}')" title="扩缩容">
                            <i class="fas fa-expand-arrows-alt"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="containerManager.removeDeployment('${deployment.name}', '${deployment.namespace}')" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
            
        } catch (error) {
            console.error('加载Deployment列表失败:', error);
            const tbody = document.getElementById('deploymentsTable');
            tbody.innerHTML = '<tr><td colspan="7" class="error">加载失败: ' + error.message + '</td></tr>';
            this.showNotification('加载Deployment列表失败', 'error');
        }
    }

    async loadServices() {
        try {
            // 显示加载状态
            const tbody = document.getElementById('servicesTable');
            tbody.innerHTML = '<tr><td colspan="7" class="loading">正在加载Service列表...</td></tr>';
            
            const url = this.currentNamespace ? 
                `${this.apiBase}/k8s/services?namespace=${this.currentNamespace}` : 
                `${this.apiBase}/k8s/services`;
            
            const response = await fetch(url);
            
            // 检查响应状态
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // 检查返回数据格式
            if (!Array.isArray(data)) {
                throw new Error('API返回的数据格式不正确');
            }
            
            // 清空表格
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="no-data">暂无Service</td></tr>';
                return;
            }
            
            // 填充表格数据
            data.forEach(service => {
                const row = document.createElement('tr');
                
                // 格式化端口信息
                const ports = service.ports && Array.isArray(service.ports) 
                    ? service.ports.map(p => `${p.port}:${p.target_port}/${p.protocol}`).join(', ')
                    : 'N/A';
                
                // 格式化外部IP
                const externalIPs = service.external_ips && Array.isArray(service.external_ips) && service.external_ips.length > 0
                    ? service.external_ips.join(', ')
                    : 'N/A';
                
                row.innerHTML = `
                    <td>${service.name || 'N/A'}</td>
                    <td>${service.namespace || 'N/A'}</td>
                    <td>${service.type || 'N/A'}</td>
                    <td>${service.cluster_ip || 'N/A'}</td>
                    <td>${externalIPs}</td>
                    <td>${ports}</td>
                    <td>${this.formatDate(service.age)}</td>
                    <td>
                        <button class="btn btn-sm" onclick="containerManager.showServiceDetails('${service.name}', '${service.namespace}')" title="查看详情">
                            <i class="fas fa-info-circle"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="containerManager.removeService('${service.name}', '${service.namespace}')" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(row);
            });
            
        } catch (error) {
            console.error('加载Service列表失败:', error);
            const tbody = document.getElementById('servicesTable');
            tbody.innerHTML = '<tr><td colspan="7" class="error">加载失败: ' + error.message + '</td></tr>';
            this.showNotification('加载Service列表失败', 'error');
        }
    }
}

// 初始化应用
const containerManager = new ContainerManager();

// 全局错误处理
window.addEventListener('error', (event) => {
    console.error('全局错误:', event.error);
    containerManager.showNotification('发生未知错误', 'error');
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    containerManager.stopAutoRefresh();
});