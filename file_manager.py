import os
import shutil
import yaml
from typing import Dict, Any, Tuple, Optional
from error_handler import FileOperationError, handle_errors

class FileManager:
    """文件管理类，处理所有文件相关操作"""
    
    def __init__(self, config_manager):
        """
        初始化文件管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config = config_manager
        
    @handle_errors()
    def save_blog(self, folder_name: str, content: str, metadata: Dict[str, Any],
                  images: Dict[str, str]) -> str:
        """
        保存博客文件
        
        Args:
            folder_name: 文件夹名称
            content: 博客内容
            metadata: 元数据
            images: 图片路径字典 {原始路径: 目标路径}
            
        Returns:
            str: 保存的文件夹路径
            
        Raises:
            FileOperationError: 文件操作失败时抛出
        """
        try:
            # 获取保存路径
            save_path = self.config.get('save_path', '')
            if not save_path:
                raise FileOperationError("未设置保存路径")
                
            # 创建文章文件夹
            article_folder = os.path.join(save_path, folder_name)
            os.makedirs(article_folder, exist_ok=True)
            
            # 处理图片
            for src_path, dest_name in images.items():
                if os.path.exists(src_path):
                    dest_path = os.path.join(article_folder, dest_name)
                    shutil.copy2(src_path, dest_path)
                    # 更新内容中的图片路径
                    content = content.replace(src_path, f"./{dest_name}")
            
            # 生成frontmatter
            frontmatter = self._generate_frontmatter(metadata)
            
            # 保存markdown文件
            file_path = os.path.join(article_folder, "index.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("---\n")
                f.write(frontmatter)
                f.write("---\n\n")
                f.write(content)
                
            return article_folder
            
        except Exception as e:
            raise FileOperationError(f"保存博客失败: {str(e)}")
            
    @handle_errors()
    def import_markdown(self, file_path: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        导入Markdown文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Tuple[str, Optional[Dict]]: (文件内容, 元数据)
            
        Raises:
            FileOperationError: 文件操作失败时抛出
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查是否包含frontmatter
            if content.startswith('---'):
                # 提取frontmatter
                _, frontmatter, content = content.split('---', 2)
                try:
                    metadata = yaml.safe_load(frontmatter)
                    return content.strip(), metadata
                except:
                    # 如果解析frontmatter失败，返回完整内容
                    return (frontmatter + '---' + content).strip(), None
            else:
                return content.strip(), None
                
        except Exception as e:
            raise FileOperationError(f"导入Markdown文件失败: {str(e)}")
            
    def _generate_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """
        生成frontmatter
        
        Args:
            metadata: 元数据字典
            
        Returns:
            str: YAML格式的frontmatter
        """
        try:
            return yaml.dump(metadata, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            raise FileOperationError(f"生成frontmatter失败: {str(e)}")
            
    @handle_errors()
    def ensure_unique_filename(self, folder_path: str, filename: str) -> str:
        """
        确保文件名唯一
        
        Args:
            folder_path: 文件夹路径
            filename: 原始文件名
            
        Returns:
            str: 唯一的文件名
        """
        name, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename
        
        while os.path.exists(os.path.join(folder_path, new_filename)):
            new_filename = f"{name}_{counter}{ext}"
            counter += 1
            
        return new_filename 