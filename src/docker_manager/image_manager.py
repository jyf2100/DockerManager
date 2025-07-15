"""Docker镜像管理器"""

import io
from typing import List, Dict, Any, Optional, Iterator
from docker.models.images import Image
from docker.errors import APIError, NotFound, ImageNotFound

from ..common.logger import LoggerMixin
from ..common.exceptions import DockerImageError
from .docker_client import DockerManager


class ImageManager(LoggerMixin):
    """Docker镜像管理器
    
    负责镜像的拉取、构建、删除等操作
    """
    
    def __init__(self, docker_manager: DockerManager):
        """初始化镜像管理器
        
        Args:
            docker_manager: Docker管理器实例
        """
        super().__init__()
        self.docker_manager = docker_manager
    
    def list_images(self, all_images: bool = False) -> List[Dict[str, Any]]:
        """列出镜像
        
        Args:
            all_images: 是否包含中间镜像
            
        Returns:
            镜像信息列表
        """
        try:
            images = self.docker_manager.client.images.list(all=all_images)
            
            result = []
            for image in images:
                image_info = {
                    'id': image.id,
                    'short_id': image.short_id,
                    'tags': image.tags,
                    'size': image.attrs.get('Size', 0),
                    'created': image.attrs.get('Created'),
                    'labels': image.attrs.get('Config', {}).get('Labels') or {},
                    'architecture': image.attrs.get('Architecture'),
                    'os': image.attrs.get('Os'),
                    'parent': image.attrs.get('Parent', ''),
                    'repo_digests': image.attrs.get('RepoDigests', [])
                }
                result.append(image_info)
            
            self.log_info(f"获取镜像列表成功，共 {len(result)} 个镜像")
            return result
            
        except APIError as e:
            error_msg = f"获取镜像列表失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def get_image(self, image_id: str) -> Dict[str, Any]:
        """获取镜像详细信息
        
        Args:
            image_id: 镜像ID或标签
            
        Returns:
            镜像详细信息
        """
        try:
            image = self.docker_manager.client.images.get(image_id)
            
            # 获取镜像历史
            history = []
            try:
                history = image.history()
            except Exception:
                pass
            
            image_info = {
                'id': image.id,
                'short_id': image.short_id,
                'tags': image.tags,
                'size': image.attrs.get('Size', 0),
                'created': image.attrs.get('Created'),
                'author': image.attrs.get('Author', ''),
                'comment': image.attrs.get('Comment', ''),
                'config': image.attrs.get('Config', {}),
                'container_config': image.attrs.get('ContainerConfig', {}),
                'architecture': image.attrs.get('Architecture'),
                'os': image.attrs.get('Os'),
                'parent': image.attrs.get('Parent', ''),
                'repo_digests': image.attrs.get('RepoDigests', []),
                'root_fs': image.attrs.get('RootFS', {}),
                'history': history
            }
            
            return image_info
            
        except ImageNotFound:
            error_msg = f"镜像 {image_id} 不存在"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
        except APIError as e:
            error_msg = f"获取镜像 {image_id} 信息失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def pull_image(self, repository: str, tag: str = 'latest', 
                   auth_config: Optional[Dict[str, str]] = None) -> Iterator[Dict[str, Any]]:
        """拉取镜像
        
        Args:
            repository: 镜像仓库名
            tag: 镜像标签
            auth_config: 认证配置 {'username': 'user', 'password': 'pass'}
            
        Yields:
            拉取进度信息
        """
        try:
            image_name = f"{repository}:{tag}"
            self.log_info(f"开始拉取镜像: {image_name}")
            
            pull_kwargs = {'repository': repository, 'tag': tag, 'stream': True, 'decode': True}
            if auth_config:
                pull_kwargs['auth_config'] = auth_config
            
            for line in self.docker_manager.client.api.pull(**pull_kwargs):
                yield line
            
            self.log_info(f"镜像拉取完成: {image_name}")
            
        except APIError as e:
            error_msg = f"拉取镜像 {repository}:{tag} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def build_image(self, path: str, tag: Optional[str] = None, 
                   dockerfile: str = 'Dockerfile',
                   buildargs: Optional[Dict[str, str]] = None,
                   nocache: bool = False) -> Iterator[Dict[str, Any]]:
        """构建镜像
        
        Args:
            path: 构建上下文路径
            tag: 镜像标签
            dockerfile: Dockerfile文件名
            buildargs: 构建参数
            nocache: 是否禁用缓存
            
        Yields:
            构建进度信息
        """
        try:
            self.log_info(f"开始构建镜像: {tag or 'unnamed'} from {path}")
            
            build_kwargs = {
                'path': path,
                'dockerfile': dockerfile,
                'rm': True,
                'stream': True,
                'decode': True,
                'nocache': nocache
            }
            
            if tag:
                build_kwargs['tag'] = tag
            if buildargs:
                build_kwargs['buildargs'] = buildargs
            
            for line in self.docker_manager.client.api.build(**build_kwargs):
                yield line
            
            self.log_info(f"镜像构建完成: {tag or 'unnamed'}")
            
        except APIError as e:
            error_msg = f"构建镜像失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def push_image(self, repository: str, tag: str = 'latest',
                   auth_config: Optional[Dict[str, str]] = None) -> Iterator[Dict[str, Any]]:
        """推送镜像
        
        Args:
            repository: 镜像仓库名
            tag: 镜像标签
            auth_config: 认证配置
            
        Yields:
            推送进度信息
        """
        try:
            image_name = f"{repository}:{tag}"
            self.log_info(f"开始推送镜像: {image_name}")
            
            push_kwargs = {'repository': repository, 'tag': tag, 'stream': True, 'decode': True}
            if auth_config:
                push_kwargs['auth_config'] = auth_config
            
            for line in self.docker_manager.client.api.push(**push_kwargs):
                yield line
            
            self.log_info(f"镜像推送完成: {image_name}")
            
        except APIError as e:
            error_msg = f"推送镜像 {repository}:{tag} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def remove_image(self, image_id: str, force: bool = False, 
                    noprune: bool = False) -> List[Dict[str, str]]:
        """删除镜像
        
        Args:
            image_id: 镜像ID或标签
            force: 是否强制删除
            noprune: 是否不删除未标记的父镜像
            
        Returns:
            删除结果列表
        """
        try:
            result = self.docker_manager.client.api.remove_image(
                image_id, force=force, noprune=noprune
            )
            
            self.log_info(f"镜像删除成功: {image_id}")
            return result
            
        except ImageNotFound:
            error_msg = f"镜像 {image_id} 不存在"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
        except APIError as e:
            error_msg = f"删除镜像 {image_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def tag_image(self, image_id: str, repository: str, tag: str = 'latest') -> bool:
        """为镜像添加标签
        
        Args:
            image_id: 镜像ID或现有标签
            repository: 新的仓库名
            tag: 新的标签
            
        Returns:
            是否成功
        """
        try:
            image = self.docker_manager.client.images.get(image_id)
            result = image.tag(repository, tag)
            
            if result:
                self.log_info(f"镜像标签添加成功: {image_id} -> {repository}:{tag}")
            else:
                self.log_warning(f"镜像标签添加失败: {image_id} -> {repository}:{tag}")
            
            return result
            
        except ImageNotFound:
            error_msg = f"镜像 {image_id} 不存在"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
        except APIError as e:
            error_msg = f"为镜像 {image_id} 添加标签失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def search_images(self, term: str, limit: int = 25) -> List[Dict[str, Any]]:
        """搜索镜像
        
        Args:
            term: 搜索关键词
            limit: 结果数量限制
            
        Returns:
            搜索结果列表
        """
        try:
            results = self.docker_manager.client.api.search(term, limit=limit)
            
            self.log_info(f"镜像搜索完成: {term}，找到 {len(results)} 个结果")
            return results
            
        except APIError as e:
            error_msg = f"搜索镜像失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def export_image(self, image_id: str, output_path: str) -> bool:
        """导出镜像
        
        Args:
            image_id: 镜像ID或标签
            output_path: 输出文件路径
            
        Returns:
            是否成功
        """
        try:
            image = self.docker_manager.client.images.get(image_id)
            
            with open(output_path, 'wb') as f:
                for chunk in image.save():
                    f.write(chunk)
            
            self.log_info(f"镜像导出成功: {image_id} -> {output_path}")
            return True
            
        except ImageNotFound:
            error_msg = f"镜像 {image_id} 不存在"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
        except Exception as e:
            error_msg = f"导出镜像 {image_id} 失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def import_image(self, input_path: str, repository: Optional[str] = None, 
                    tag: str = 'latest') -> str:
        """导入镜像
        
        Args:
            input_path: 输入文件路径
            repository: 仓库名
            tag: 标签
            
        Returns:
            导入的镜像ID
        """
        try:
            with open(input_path, 'rb') as f:
                result = self.docker_manager.client.api.import_image_from_data(
                    f.read(), repository=repository, tag=tag
                )
            
            # 解析返回的镜像ID
            import json
            lines = result.decode('utf-8').strip().split('\n')
            last_line = json.loads(lines[-1])
            image_id = last_line.get('aux', {}).get('ID', '')
            
            self.log_info(f"镜像导入成功: {input_path} -> {image_id}")
            return image_id
            
        except Exception as e:
            error_msg = f"导入镜像失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)
    
    def prune_images(self, dangling_only: bool = True) -> Dict[str, Any]:
        """清理未使用的镜像
        
        Args:
            dangling_only: 是否只清理悬空镜像
            
        Returns:
            清理结果
        """
        try:
            filters = {}
            if dangling_only:
                filters['dangling'] = True
            
            result = self.docker_manager.client.images.prune(filters=filters)
            
            deleted_count = len(result.get('ImagesDeleted', []))
            space_reclaimed = result.get('SpaceReclaimed', 0)
            
            self.log_info(f"镜像清理完成，删除 {deleted_count} 个镜像，回收空间 {space_reclaimed} 字节")
            return result
            
        except APIError as e:
            error_msg = f"清理镜像失败: {str(e)}"
            self.log_error(error_msg)
            raise DockerImageError(error_msg)