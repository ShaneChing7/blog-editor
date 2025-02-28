import os
from datetime import datetime
from typing import Tuple, Optional
from PIL import Image
import io
from PySide6.QtGui import QImage
from error_handler import ImageProcessingError, handle_errors

class ImageProcessor:
    """图片处理类，处理所有图片相关操作"""
    
    def __init__(self, config_manager):
        """
        初始化图片处理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config = config_manager
        self.temp_dir = None
        
    def setup_temp_dir(self, temp_dir: str) -> None:
        """
        设置临时目录
        
        Args:
            temp_dir: 临时目录路径
        """
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        
    @handle_errors()
    def process_image(self, image_path: str, image_data: Optional[bytes] = None) -> str:
        """
        处理图片（压缩、优化）
        
        Args:
            image_path: 图片路径（对于文件）
            image_data: 图片数据（对于剪贴板图片）
            
        Returns:
            str: 处理后的图片路径
            
        Raises:
            ImageProcessingError: 图片处理失败时抛出
        """
        if not self.temp_dir:
            raise ImageProcessingError("临时目录未设置")
            
        try:
            # 生成唯一的临时文件名
            temp_filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            temp_image_path = os.path.join(self.temp_dir, temp_filename)
            
            # 处理图片数据或文件
            if image_data:
                with open(temp_image_path, 'wb') as f:
                    f.write(image_data)
            else:
                if not os.path.exists(image_path):
                    raise ImageProcessingError(f"图片文件不存在: {image_path}")
                Image.open(image_path).save(temp_image_path)
            
            # 压缩和优化图片
            self._optimize_image(temp_image_path)
            
            return temp_image_path
            
        except Exception as e:
            raise ImageProcessingError(f"图片处理失败: {str(e)}")
            
    @handle_errors()
    def _optimize_image(self, image_path: str) -> None:
        """
        优化图片（调整大小、压缩）
        
        Args:
            image_path: 图片路径
            
        Raises:
            ImageProcessingError: 图片优化失败时抛出
        """
        try:
            # 从配置获取参数
            max_width = self.config.get('image_max_width', 800)
            quality = self.config.get('image_quality', 85)
            
            img = Image.open(image_path)
            
            # 转换为RGB模式（处理PNG等格式）
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # 调整大小
            if img.size[0] > max_width:
                ratio = max_width / img.size[0]
                new_size = (max_width, int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 保存优化后的图片
            img.save(image_path, 'JPEG', quality=quality, optimize=True)
            
        except Exception as e:
            raise ImageProcessingError(f"图片优化失败: {str(e)}")
            
    @handle_errors()
    def qimage_to_bytes(self, qimage: QImage) -> bytes:
        """
        将QImage转换为字节数据
        
        Args:
            qimage: QImage对象
            
        Returns:
            bytes: 图片字节数据
            
        Raises:
            ImageProcessingError: 转换失败时抛出
        """
        try:
            buffer = io.BytesIO()
            qimage.save(buffer, "PNG")
            return buffer.getvalue()
        except Exception as e:
            raise ImageProcessingError(f"图片转换失败: {str(e)}")
            
    def cleanup(self) -> None:
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"清理临时文件失败: {str(e)}") 