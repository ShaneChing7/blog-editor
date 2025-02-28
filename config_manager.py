import os
import json
from typing import Dict, Any, Optional

class ConfigManager:
    """配置管理类，处理应用程序的配置保存和加载"""
    
    def __init__(self, config_file: str):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件的路径
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """
        从文件加载配置
        
        Returns:
            包含配置信息的字典
        """
        default_config = {
            'save_path': '',
            'auto_save_interval': 60,  # 自动保存间隔（秒）
            'max_recent_files': 10,    # 最近打开文件数量
            'editor_font_size': 12,    # 编辑器字体大小
            'editor_font_family': 'Consolas',  # 编辑器字体
            'preview_font_size': 14,   # 预览字体大小
            'image_max_width': 800,    # 图片最大宽度
            'image_quality': 85,       # 图片压缩质量
            'recent_files': [],        # 最近打开的文件列表
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    default_config.update(loaded_config)
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
        
        return default_config
    
    def save_config(self) -> bool:
        """
        保存配置到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        self.config[key] = value
        
    def add_recent_file(self, file_path: str) -> None:
        """
        添加最近打开的文件
        
        Args:
            file_path: 文件路径
        """
        recent_files = self.get('recent_files', [])
        
        # 如果文件已在列表中，先移除
        if file_path in recent_files:
            recent_files.remove(file_path)
            
        # 添加到列表开头
        recent_files.insert(0, file_path)
        
        # 保持列表长度在限制内
        max_recent = self.get('max_recent_files', 10)
        self.set('recent_files', recent_files[:max_recent])
        
    def clear_recent_files(self) -> None:
        """清空最近打开的文件列表"""
        self.set('recent_files', []) 