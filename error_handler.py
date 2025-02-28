from typing import Optional, Callable
from PySide6.QtWidgets import QMessageBox
import logging
import os
import sys
import traceback
from datetime import datetime

class BlogEditorError(Exception):
    """博客编辑器基础异常类"""
    def __init__(self, message: str, details: Optional[str] = None):
        super().__init__(message)
        self.details = details

class ConfigError(BlogEditorError):
    """配置相关错误"""
    pass

class FileOperationError(BlogEditorError):
    """文件操作错误"""
    pass

class ImageProcessingError(BlogEditorError):
    """图片处理错误"""
    pass

class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, log_file: str):
        """
        初始化错误处理器
        
        Args:
            log_file: 日志文件路径
        """
        self.log_file = log_file
        self._setup_logging()
        
    def _setup_logging(self) -> None:
        """配置日志系统"""
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            filename=self.log_file,
            level=logging.ERROR,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
    def handle_error(self, error: Exception, show_dialog: bool = True,
                    callback: Optional[Callable] = None) -> None:
        """
        处理异常
        
        Args:
            error: 异常对象
            show_dialog: 是否显示错误对话框
            callback: 错误处理后的回调函数
        """
        # 获取错误详情
        error_type = type(error).__name__
        error_msg = str(error)
        error_details = getattr(error, 'details', None) or traceback.format_exc()
        
        # 记录错误日志
        logging.error(f"{error_type}: {error_msg}\n{error_details}")
        
        if show_dialog:
            self.show_error_dialog(error_type, error_msg, error_details)
            
        if callback:
            try:
                callback(error)
            except Exception as e:
                logging.error(f"Error in callback: {str(e)}")
                
    def show_error_dialog(self, error_type: str, error_msg: str,
                         error_details: Optional[str] = None) -> None:
        """
        显示错误对话框
        
        Args:
            error_type: 错误类型
            error_msg: 错误消息
            error_details: 错误详情
        """
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("错误")
        msg_box.setText(f"{error_type}: {error_msg}")
        
        if error_details:
            msg_box.setDetailedText(error_details)
            
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
        
    def get_error_log(self) -> str:
        """
        获取错误日志内容
        
        Returns:
            str: 日志内容
        """
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"无法读取日志文件: {str(e)}"
            
    def clear_error_log(self) -> None:
        """清空错误日志"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception as e:
            logging.error(f"清空日志文件失败: {str(e)}")

# 全局错误处理装饰器
def handle_errors(show_dialog: bool = True):
    """
    错误处理装饰器
    
    Args:
        show_dialog: 是否显示错误对话框
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 获取第一个参数（self）的error_handler属性
                if args and hasattr(args[0], 'error_handler'):
                    args[0].error_handler.handle_error(e, show_dialog)
                else:
                    raise e
        return wrapper
    return decorator 