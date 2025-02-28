import sys
import os
import json
import shutil
import tempfile
import hashlib
from datetime import datetime
import markdown
from PIL import Image
import io
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QDateEdit,
    QComboBox, QFileDialog, QColorDialog, QListWidget, QTabWidget,
    QTextBrowser, QFrame, QSplitter, QScrollArea, QToolBar, QMenu,
    QFontComboBox, QSpinBox, QProgressDialog, QMessageBox
)
from PySide6.QtCore import Qt, QDate, QLocale, QPropertyAnimation, QEasingCurve, QSize, QMimeData, QUrl, QTimer, QBuffer
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPalette, QDragEnterEvent, QDropEvent,
    QTextCharFormat, QSyntaxHighlighter, QTextCursor, QKeySequence,
    QAction
)

from config_manager import ConfigManager
from error_handler import ErrorHandler, handle_errors
from image_processor import ImageProcessor
from file_manager import FileManager

class ImageCompressor:
    def __init__(self):
        self.max_size = (1920, 1080)  # 最大分辨率
        self.quality = 85  # JPEG压缩质量
        self.max_file_size = 500 * 1024  # 最大文件大小（500KB）

    def compress_image(self, input_path, output_path):
        """压缩图片，返回是否进行了压缩"""
        try:
            # 如果文件小于最大大小，不进行压缩
            if os.path.getsize(input_path) <= self.max_file_size:
                if input_path != output_path:
                    shutil.copy2(input_path, output_path)
                return False

            img = Image.open(input_path)
            
            # 转换为RGB模式（处理PNG等格式）
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # 调整大小
            if img.size[0] > self.max_size[0] or img.size[1] > self.max_size[1]:
                img.thumbnail(self.max_size, Image.Resampling.LANCZOS)
            
            # 保存压缩后的图片
            img.save(output_path, 'JPEG', quality=self.quality, optimize=True)
            
            # 如果文件仍然太大，继续降低质量
            while os.path.getsize(output_path) > self.max_file_size and self.quality > 30:
                self.quality -= 5
                img.save(output_path, 'JPEG', quality=self.quality, optimize=True)
            
            return True
        except Exception as e:
            print(f"图片压缩失败: {str(e)}")
            if input_path != output_path:
                shutil.copy2(input_path, output_path)
            return False

class DragDropTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)   
        self.temp_dir = tempfile.mkdtemp()  # 创建临时目录
        self.image_paths = []  # 存储所有使用的图片路径
        self.image_compressor = ImageCompressor()  # 创建图片压缩器实例
        self.word_count = 0
        self.read_time = 0
        self.textChanged.connect(self.update_statistics)

    def dragEnterEvent(self, event: QDragEnterEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls() and any(url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.gif')) for url in mime_data.urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            progress = QProgressDialog("正在处理图片...", "取消", 0, len(mime_data.urls()), self)
            progress.setWindowTitle("处理中")
            progress.setWindowModality(Qt.WindowModal)
            
            for i, url in enumerate(mime_data.urls()):
                if progress.wasCanceled():
                    break
                    
                progress.setValue(i)
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    self.process_image(file_path)
                        
            progress.setValue(len(mime_data.urls()))
            event.acceptProposedAction()

    def process_image(self, image_path, image_data=None):
        """处理图片，支持文件路径或图片数据"""
        try:
            # 生成唯一的临时文件名
            temp_filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
            temp_image_path = os.path.join(self.temp_dir, temp_filename)
            
            if image_data:  # 处理剪贴板图片数据
                with open(temp_image_path, 'wb') as f:
                    f.write(image_data)
            else:  # 处理文件路径
                shutil.copy2(image_path, temp_image_path)
            
            # 压缩图片
            was_compressed = self.image_compressor.compress_image(temp_image_path, temp_image_path)
            self.image_paths.append(temp_image_path)
            
            # 插入 Markdown 图片语法
            cursor = self.textCursor()
            cursor.insertText(f"\n![{os.path.basename(temp_image_path)}]({temp_image_path})")
            if was_compressed:
                cursor.insertText(" *(已优化)*\n")
            else:
                cursor.insertText("\n")
                
            return True
        except Exception as e:
            print(f"处理图片失败: {str(e)}")
            return False

    def keyPressEvent(self, event):
        # 处理粘贴操作
        if event.key() == Qt.Key_V and event.modifiers() == Qt.ControlModifier:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            
            if mime_data.hasImage():
                # 从剪贴板获取图片
                image = clipboard.image()
                if not image.isNull():
                    # 将 QImage 转换为字节数据
                    buffer = QBuffer()
                    buffer.open(QBuffer.ReadWrite)
                    image.save(buffer, "PNG")
                    image_data = buffer.data().data()
                    
                    # 处理图片
                    if self.process_image(None, image_data):
                        return
            
            # 如果不是图片或处理失败，执行默认的粘贴操作
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def cleanup(self):
        """清理临时目录"""
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass

    def update_statistics(self):
        """更新字数统计和阅读时间"""
        text = self.toPlainText()
        
        # 计算字数（中英文分别计算）
        chinese_count = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_words = len([w for w in text.split() if any(c.isalpha() for c in w)])
        
        self.word_count = chinese_count + english_words
        
        # 估算阅读时间（假设中文每分钟300字，英文每分钟200词）
        chinese_time = chinese_count / 300
        english_time = english_words / 200
        self.read_time = chinese_time + english_time
        
        # 更新状态栏标签
        if hasattr(self, 'word_count_label'):
            self.word_count_label.setText(f"字数：{self.word_count}")
            
            if self.read_time < 1:
                time_text = "< 1 分钟"
            else:
                minutes = int(self.read_time)
                if minutes == 0:
                    time_text = "< 1 分钟"
                elif minutes < 60:
                    time_text = f"{minutes} 分钟"
                else:
                    hours = minutes // 60
                    remaining_minutes = minutes % 60
                    if remaining_minutes == 0:
                        time_text = f"{hours} 小时"
                    else:
                        time_text = f"{hours} 小时 {remaining_minutes} 分钟"
            
            self.read_time_label.setText(f"预计阅读时间：{time_text}")

class StyledFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            StyledFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
        """)

class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.formats = {}
        
        # 标题格式
        header_format = QTextCharFormat()
        header_format.setFontWeight(QFont.Bold)
        header_format.setForeground(QColor("#2c3e50"))
        self.formats["header"] = header_format
        
        # 强调格式（粗体）
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Bold)
        bold_format.setForeground(QColor("#e83e8c"))
        self.formats["bold"] = bold_format
        
        # 斜体格式
        italic_format = QTextCharFormat()
        italic_format.setFontItalic(True)
        italic_format.setForeground(QColor("#e83e8c"))
        self.formats["italic"] = italic_format
        
        # 代码格式
        code_format = QTextCharFormat()
        code_font = QFont("Consolas")  # 创建字体对象
        code_format.setFont(code_font)  # 使用 setFont 替代 setFontFamily
        code_format.setBackground(QColor("#f8f9fa"))
        code_format.setForeground(QColor("#e83e8c"))
        self.formats["code"] = code_format
        
        # 链接格式
        link_format = QTextCharFormat()
        link_format.setForeground(QColor("#0366d6"))
        link_format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        self.formats["link"] = link_format

    def highlightBlock(self, text):
        # 标题
        for i in range(6, 0, -1):
            pattern = f"^{'#' * i}\\s.*$"
            self.highlight_pattern(text, pattern, self.formats["header"])
        
        # 粗体
        self.highlight_pattern(text, r"\*\*.*?\*\*", self.formats["bold"])
        self.highlight_pattern(text, r"__.*?__", self.formats["bold"])
        
        # 斜体
        self.highlight_pattern(text, r"\*.*?\*", self.formats["italic"])
        self.highlight_pattern(text, r"_.*?_", self.formats["italic"])
        
        # 行内代码
        self.highlight_pattern(text, r"`.*?`", self.formats["code"])
        
        # 链接
        self.highlight_pattern(text, r"\[.*?\]\(.*?\)", self.formats["link"])

    def highlight_pattern(self, text, pattern, format):
        import re
        for match in re.finditer(pattern, text):
            start, end = match.span()
            self.setFormat(start, end - start, format)

class TextCache:
    def __init__(self):
        self.cache_dir = os.path.join(tempfile.gettempdir(), "blog_editor_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_size = 10  # 最大缓存文件数
        self.chunk_size = 50000  # 每个分块的字符数
        
    def get_cache_key(self, text):
        """生成缓存键"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
        
    def save_to_cache(self, text):
        """将文本保存到缓存"""
        try:
            cache_key = self.get_cache_key(text)
            cache_file = os.path.join(self.cache_dir, cache_key)
            
            # 分块保存
            chunks = [text[i:i + self.chunk_size] 
                     for i in range(0, len(text), self.chunk_size)]
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'chunks': chunks,
                    'timestamp': datetime.now().timestamp()
                }, f)
                
            # 清理旧缓存
            self._cleanup_old_cache()
            
            return cache_key
        except Exception as e:
            print(f"保存缓存失败: {str(e)}")
            return None
            
    def load_from_cache(self, cache_key):
        """从缓存加载文本"""
        try:
            cache_file = os.path.join(self.cache_dir, cache_key)
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return ''.join(data['chunks'])
        except Exception as e:
            print(f"加载缓存失败: {str(e)}")
        return None
        
    def _cleanup_old_cache(self):
        """清理旧的缓存文件"""
        try:
            files = []
            for f in os.listdir(self.cache_dir):
                path = os.path.join(self.cache_dir, f)
                if os.path.isfile(path):
                    files.append((path, os.path.getmtime(path)))
            
            # 按修改时间排序
            files.sort(key=lambda x: x[1], reverse=True)
            
            # 删除旧文件
            for path, _ in files[self.cache_size:]:
                os.remove(path)
        except Exception as e:
            print(f"清理缓存失败: {str(e)}")
            
    def cleanup(self):
        """清理所有缓存"""
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
        except Exception as e:
            print(f"清理缓存失败: {str(e)}")

class MarkdownEditor(DragDropTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_editor()
        self.setup_toolbar()
        self.setup_status_bar()
        self.highlighter = MarkdownHighlighter(self.document())
        self.text_cache = TextCache()
        self.current_cache_key = None
        self.word_count = 0
        self.read_time = 0

    def setup_editor(self):
        # 设置字体和行高
        font = QFont("Consolas", 12)
        self.setFont(font)
        
        # 启用行号显示的样式，添加底部padding以防止状态栏遮挡
        self.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #2c3e50;
                border: none;
                line-height: 1.6;
                padding: 10px;
                padding-bottom: 40px;  /* 为状态栏预留空间 */
            }
        """)
        
        # 设置制表符宽度
        self.setTabStopDistance(40)

    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QWidget(self)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        # 添加弹性空间，将标签推到右侧
        status_layout.addStretch()
        
        # 字数统计标签
        self.word_count_label = QLabel("字数：0")
        self.word_count_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 2px 8px;
                background: #f5f5f5;
                border-radius: 4px;
            }
        """)
        
        # 阅读时间标签
        self.read_time_label = QLabel("预计阅读时间：< 1 分钟")
        self.read_time_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 2px 8px;
                background: #f5f5f5;
                border-radius: 4px;
                margin-left: 10px;
            }
        """)
        
        status_layout.addWidget(self.word_count_label)
        status_layout.addWidget(self.read_time_label)
        
        # 设置状态栏的固定高度和背景
        self.status_bar.setFixedHeight(30)
        self.status_bar.setStyleSheet("""
            QWidget {
                background: rgba(255, 255, 255, 0.95);
            }
        """)
        self.status_bar.show()

    def update_statistics(self):
        """更新字数统计和阅读时间"""
        text = self.toPlainText()
        
        # 计算字数（中英文分别计算）
        chinese_count = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_words = len([w for w in text.split() if any(c.isalpha() for c in w)])
        
        self.word_count = chinese_count + english_words
        
        # 估算阅读时间（假设中文每分钟300字，英文每分钟200词）
        chinese_time = chinese_count / 300
        english_time = english_words / 200
        self.read_time = chinese_time + english_time
        
        # 更新状态栏标签
        if hasattr(self, 'word_count_label'):
            self.word_count_label.setText(f"字数：{self.word_count}")
            
            if self.read_time < 1:
                time_text = "< 1 分钟"
            else:
                minutes = int(self.read_time)
                if minutes == 0:
                    time_text = "< 1 分钟"
                elif minutes < 60:
                    time_text = f"{minutes} 分钟"
                else:
                    hours = minutes // 60
                    remaining_minutes = minutes % 60
                    if remaining_minutes == 0:
                        time_text = f"{hours} 小时"
                    else:
                        time_text = f"{hours} 小时 {remaining_minutes} 分钟"
            
            self.read_time_label.setText(f"预计阅读时间：{time_text}")

    def setup_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setStyleSheet("""
            QToolBar {
                spacing: 4px;
                background: #ffffff;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                padding: 8px;
            }
            QToolButton {
                border: 1px solid transparent;
                padding: 6px 12px;
                border-radius: 4px;
                min-width: 80px;
                color: #333333;
                font-size: 13px;
            }
            QToolButton:hover {
                background: #f0f0f0;
                border: 1px solid #e0e0e0;
            }
            QToolButton:pressed {
                background: #e8e8e8;
                border: 1px solid #d0d0d0;
            }
            QToolButton::menu-indicator {
                image: url(none);
                width: 0;
            }
            QMenu {
                background-color: white;
                border: 1px solid #d0d0d0;
                padding: 8px 0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #333333;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #f0f0f0;
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background: #e0e0e0;
                margin: 4px 0;
            }
        """)

        # 添加导入按钮
        import_action = QAction("📄 导入", self.toolbar)
        import_action.setShortcut(QKeySequence("Ctrl+O"))
        import_action.triggered.connect(self.import_markdown)
        self.toolbar.addAction(import_action)

        # 添加分隔线
        self.toolbar.addSeparator()

        # 创建标题菜单
        header_menu = QMenu("标题", self)
        header_icons = ["H1", "H2", "H3", "H4", "H5", "H6"]
        for i, icon in enumerate(header_icons, 1):
            action = QAction(f"{icon} 标题 {i}", self)
            action.setData(i)
            action.triggered.connect(self.on_header_action_triggered)
            header_menu.addAction(action)
        
        # 将标题菜单添加到工具栏
        header_action = QAction("📝 标题", self.toolbar)
        header_action.setMenu(header_menu)
        self.toolbar.addAction(header_action)

        # 创建格式菜单
        format_menu = QMenu("格式(O)", self)
        
        # 添加文本格式选项
        bold_action = QAction("🅱️ 加粗", self)
        bold_action.setShortcut(QKeySequence("Ctrl+B"))
        bold_action.triggered.connect(lambda: self.insert_bold("**"))
        format_menu.addAction(bold_action)
        
        italic_action = QAction("📐 斜体", self)
        italic_action.setShortcut(QKeySequence("Ctrl+I"))
        italic_action.triggered.connect(lambda: self.insert_italic("*"))
        format_menu.addAction(italic_action)
        
        format_menu.addSeparator()
        
        # 添加其他格式选项
        code_action = QAction("💻 代码", self)
        code_action.setShortcut(QKeySequence("Ctrl+K"))
        code_action.triggered.connect(lambda: self.insert_code("`"))
        format_menu.addAction(code_action)
        
        code_block_action = QAction("📟 代码块", self)
        code_block_action.setShortcut(QKeySequence("Ctrl+Shift+K"))
        code_block_action.triggered.connect(lambda: self.insert_code_block("```"))
        format_menu.addAction(code_block_action)
        
        format_menu.addSeparator()
        
        # 添加列表和引用选项
        list_action = QAction("📋 列表", self)
        list_action.setShortcut(QKeySequence("Ctrl+U"))
        list_action.triggered.connect(lambda: self.insert_list("-"))
        format_menu.addAction(list_action)
        
        quote_action = QAction("💬 引用", self)
        quote_action.setShortcut(QKeySequence("Ctrl+Q"))
        quote_action.triggered.connect(lambda: self.insert_quote(">"))
        format_menu.addAction(quote_action)
        
        format_menu.addSeparator()
        
        # 添加链接和图片选项
        link_action = QAction("🔗 链接", self)
        link_action.setShortcut(QKeySequence("Ctrl+L"))
        link_action.triggered.connect(lambda: self.insert_link("[链接](url)"))
        format_menu.addAction(link_action)
        
        image_action = QAction("🖼️ 图片", self)
        image_action.setShortcut(QKeySequence("Ctrl+P"))
        image_action.triggered.connect(lambda: self.insert_image("![描述](图片url)"))
        format_menu.addAction(image_action)

        # 将格式菜单添加到工具栏
        format_action = QAction("🎨 格式", self.toolbar)
        format_action.setMenu(format_menu)
        self.toolbar.addAction(format_action)

    def on_header_action_triggered(self):
        action = self.sender()
        if action:
            level = action.data()
            self.insert_header("#" * level + " ")

    def insert_format(self, prefix, suffix=""):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            # 记住选择的起始位置
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            
            # 插入带格式的文本
            cursor.insertText(f"{prefix}{selected_text}{suffix}")
            
            # 重新选中文本（不包括格式标记）
            new_cursor = self.textCursor()
            new_cursor.setPosition(start + len(prefix))
            new_cursor.setPosition(start + len(prefix) + len(selected_text), QTextCursor.KeepAnchor)
            self.setTextCursor(new_cursor)
        else:
            cursor.insertText(prefix + suffix)
            # 如果有后缀，将光标移动到中间
            if suffix:
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, len(suffix))
            self.setTextCursor(cursor)
        
        self.setFocus()

    def insert_header(self, prefix):
        cursor = self.textCursor()
        selected_text = cursor.selectedText()
        
        if selected_text:
            # 记住选择的起始位置
            start = cursor.selectionStart()
            
            # 插入带标题标记的文本
            cursor.insertText(f"{prefix}{selected_text}")
            
            # 重新选中文本（不包括标题标记）
            new_cursor = self.textCursor()
            new_cursor.setPosition(start + len(prefix))
            new_cursor.setPosition(start + len(prefix) + len(selected_text), QTextCursor.KeepAnchor)
            self.setTextCursor(new_cursor)
        else:
            # 如果没有选中文本，处理当前行
            cursor.movePosition(QTextCursor.StartOfLine)
            line_start_pos = cursor.position()
            cursor.movePosition(QTextCursor.EndOfLine)
            line_text = cursor.selectedText()
            
            # 删除现有的标题标记（如果有）
            line_text = line_text.lstrip('#').lstrip()
            
            # 插入新的标题
            cursor.movePosition(QTextCursor.StartOfLine)
            cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
            
            # 记住当前行文本的长度
            text_length = len(line_text)
            
            cursor.insertText(f"{prefix}{line_text}")
            
            # 选中新插入的文本（不包括标题标记）
            new_cursor = self.textCursor()
            new_cursor.movePosition(QTextCursor.StartOfLine)
            new_cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, len(prefix))
            new_cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, text_length)
            self.setTextCursor(new_cursor)
        
        self.setFocus()

    def insert_bold(self, prefix):
        self.insert_format("**", "**")

    def insert_italic(self, prefix):
        self.insert_format("*", "*")

    def insert_code(self, prefix):
        self.insert_format("`", "`")

    def insert_link(self, prefix):
        self.insert_format("[", "](url)")

    def insert_image(self, prefix):
        self.insert_format("![描述](", ")")

    def insert_list(self, prefix):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("- ")
        self.setFocus()

    def insert_quote(self, prefix):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.insertText("> ")
        self.setFocus()

    def insert_code_block(self, prefix):
        self.insert_format("```\n", "\n```")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            self.textCursor().insertText("    ")
        else:
            super().keyPressEvent(event)

    def import_markdown(self):
        """导入 Markdown 文件"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "导入 Markdown 文件",
            "",
            "Markdown 文件 (*.md)"
        )
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 检查是否包含 frontmatter
                if content.startswith('---'):
                    # 提取 frontmatter
                    _, frontmatter, content = content.split('---', 2)
                    import yaml
                    try:
                        metadata = yaml.safe_load(frontmatter)
                        # 发送信号给父窗口更新元数据
                        if hasattr(self.parent(), 'update_metadata'):
                            self.parent().update_metadata(metadata)
                    except:
                        # 如果解析 frontmatter 失败，就把整个内容当作正文
                        content = frontmatter + '---' + content
                
                # 设置文章内容
                self.setPlainText(content.strip())
                
                # 确保统计更新被触发
                self.update_statistics()
                
                # 更新预览
                if hasattr(self.parent(), 'update_preview'):
                    self.parent().update_preview()
                
            except Exception as e:
                print(f"导入失败: {str(e)}")

    def setPlainText(self, text):
        """重写setPlainText方法，添加缓存支持"""
        # 保存到缓存
        self.current_cache_key = self.text_cache.save_to_cache(text)
        super().setPlainText(text)
        # 手动触发统计更新
        self.update_statistics()

    def toPlainText(self):
        """重写toPlainText方法，优先从缓存读取"""
        if self.current_cache_key:
            cached_text = self.text_cache.load_from_cache(self.current_cache_key)
            if cached_text is not None:
                return cached_text
        return super().toPlainText()

    def resizeEvent(self, event):
        """处理窗口大小调整事件"""
        super().resizeEvent(event)
        # 更新状态栏位置
        self.status_bar.move(
            self.width() - self.status_bar.width() - 20,
            self.height() - self.status_bar.height() - 10
        )

class AutoSaver:
    def __init__(self, editor):
        self.editor = editor
        self.auto_save_interval = 60000  # 60秒
        self.last_content = ""
        self.last_metadata = {}
        self.auto_save_dir = os.path.join(tempfile.gettempdir(), "blog_editor_autosave")
        os.makedirs(self.auto_save_dir, exist_ok=True)
        
        # 创建自动保存计时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.auto_save)
        self.timer.start(self.auto_save_interval)
        
    def auto_save(self):
        """自动保存当前内容和元数据"""
        try:
            current_content = self.editor.content_input.toPlainText()
            current_metadata = {
                "title": self.editor.title_input.text(),
                "description": self.editor.desc_input.toPlainText(),
                "folder": self.editor.folder_input.text(),
                "date": self.editor.date_input.date().toString("yyyy-MM-dd"),
                "tags": [self.editor.tags_list.item(i).text() 
                        for i in range(self.editor.tags_list.count())],
                "language": self.editor.lang_select.currentText(),
                "color": self.editor.current_color,
                "image_path": self.editor.image_path
            }
            
            # 只在内容或元数据发生变化时保存
            if (current_content != self.last_content or 
                current_metadata != self.last_metadata):
                
                # 保存内容
                content_file = os.path.join(self.auto_save_dir, "content.md")
                with open(content_file, "w", encoding="utf-8") as f:
                    f.write(current_content)
                
                # 保存元数据
                metadata_file = os.path.join(self.auto_save_dir, "metadata.json")
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(current_metadata, f, ensure_ascii=False, indent=2)
                
                self.last_content = current_content
                self.last_metadata = current_metadata
                
                # 更新状态栏
                self.editor.statusBar().showMessage("已自动保存", 2000)
                self.editor.statusBar().setStyleSheet("""
                    QStatusBar {
                        background-color: #2ecc71;
                        color: white;
                        padding: 5px;
                    }
                """)
                
        except Exception as e:
            self.editor.error_handler.handle_error(e, show_dialog=False)
            self.editor.statusBar().showMessage("自动保存失败", 2000)
            self.editor.statusBar().setStyleSheet("""
                QStatusBar {
                    background-color: #e74c3c;
                    color: white;
                    padding: 5px;
                }
            """)
            
    def try_restore(self):
        """尝试恢复上次的自动保存内容"""
        try:
            content_file = os.path.join(self.auto_save_dir, "content.md")
            metadata_file = os.path.join(self.auto_save_dir, "metadata.json")
            
            if os.path.exists(content_file) and os.path.exists(metadata_file):
                # 读取内容
                with open(content_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 读取元数据
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                
                return content, metadata
                
        except Exception as e:
            print(f"恢复自动保存失败: {str(e)}")
        
        return None, None
        
    def cleanup(self):
        """清理自动保存文件"""
        try:
            if os.path.exists(self.auto_save_dir):
                shutil.rmtree(self.auto_save_dir)
        except Exception as e:
            print(f"清理自动保存失败: {str(e)}")

class BlogEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("博客编辑器")
        self.setMinimumSize(1400, 900)
        
        # 初始化各个管理器
        self.config_manager = ConfigManager(
            os.path.join(os.path.expanduser("~"), ".blog_editor_config.json")
        )
        self.error_handler = ErrorHandler(
            os.path.join(os.path.expanduser("~"), ".blog_editor", "error.log")
        )
        self.image_processor = ImageProcessor(self.config_manager)
        self.file_manager = FileManager(self.config_manager)
        
        # 设置临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.image_processor.setup_temp_dir(self.temp_dir)
        
        # 从配置加载保存路径
        self.save_path = self.config_manager.get('save_path', '')
        
        # 设置中文环境
        QLocale.setDefault(QLocale(QLocale.Chinese, QLocale.China))
        
        # 初始化UI
        self._init_ui()
        
        # 初始化自动保存器
        self._setup_auto_save()
        
        # 尝试恢复自动保存的内容
        self._try_restore_auto_save()

    @handle_errors()
    def _init_ui(self):
        """初始化用户界面"""
        # 设置应用样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 13px;
                color: #333;
                margin-bottom: 4px;
            }
            QLineEdit, QTextEdit, QDateEdit, QComboBox {
                padding: 8px 12px;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                min-height: 20px;
                font-size: 13px;
                color: #2c3e50;
            }
            QLineEdit:focus, QTextEdit:focus, QDateEdit:focus, QComboBox:focus {
                border: 2px solid #4a90e2;
                outline: none;
            }
            QLineEdit:hover, QTextEdit:hover, QDateEdit:hover, QComboBox:hover {
                border: 1px solid #4a90e2;
            }
            QDateEdit::drop-down, QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QDateEdit::down-arrow, QComboBox::down-arrow {
                image: none;
                border: solid 5px transparent;
                border-top: solid 5px #666;
                margin-right: 5px;
            }
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                padding: 5px;
                outline: none;  /* 移除焦点轮廓 */
            }
            QListWidget::item {
                padding: 5px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
                border: none;  /* 移除选中边框 */
            }
            QListWidget::item:hover {
                background-color: #f5f5f5;
            }
            QListWidget:focus {
                border: 1px solid #4a90e2;  /* 列表获得焦点时的边框样式 */
                outline: none;  /* 移除默认的焦点轮廓 */
            }
            QPushButton {
                padding: 8px 16px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                min-width: 80px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5d8c;
            }
            QPushButton#deleteButton {
                background-color: #dc3545;
            }
            QPushButton#deleteButton:hover {
                background-color: #c82333;
            }
            QPushButton#addButton {
                background-color: #28a745;
            }
            QPushButton#addButton:hover {
                background-color: #218838;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QSplitter::handle {
                background-color: #ddd;
                margin: 2px;
            }
            StyledFrame {
                background-color: white;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
            QTextEdit#contentEdit {
                font-family: "Consolas", "Microsoft YaHei", monospace;
                font-size: 14px;
                line-height: 1.5;
                background-color: #ffffff;
                color: #2c3e50;
                border: none;
            }
            QTextBrowser#preview {
                font-family: "Microsoft YaHei", Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                background-color: #ffffff;
                padding: 20px;
                border: none;
            }
        """)
        
        # 创建主窗口部件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 创建左侧元数据编辑区域
        left_widget = QWidget()
        left_widget.setFixedWidth(400)  # 固定左侧宽度
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(15)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidget(left_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }")

        # 元数据编辑框架
        metadata_frame = StyledFrame()
        metadata_layout = QVBoxLayout(metadata_frame)
        metadata_layout.setSpacing(15)
        metadata_layout.setContentsMargins(15, 15, 15, 15)

        # 文件夹名称
        self.folder_input = self.create_input_group("文件夹名称:", QLineEdit())
        self.folder_input.setPlaceholderText("输入文件夹名称（将用作文章的唯一标识）")
        metadata_layout.addWidget(self.create_form_group("文件夹名称", self.folder_input))

        # 标题
        self.title_input = self.create_input_group("标题:", QLineEdit())
        self.title_input.setPlaceholderText("输入博客标题")
        metadata_layout.addWidget(self.create_form_group("标题", self.title_input))

        # 发布日期
        self.date_input = QDateEdit()
        self.date_input.setLocale(QLocale(QLocale.Chinese))
        self.date_input.setDisplayFormat("yyyy年MM月dd日")
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        # 设置日期选择框样式
        self.date_input.setStyleSheet("""
            QDateEdit {
                padding: 8px 35px 8px 12px;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                min-height: 20px;
                font-size: 13px;
                color: #2c3e50;
            }
            QDateEdit:focus {
                border: 2px solid #4a90e2;
                outline: none;
            }
            QDateEdit:hover {
                border: 1px solid #4a90e2;
            }
            QDateEdit::drop-down {
                width: 25px;
                border: none;
                border-left: 1px solid #e0e0e0;
                background: transparent;
            }
            QDateEdit::down-arrow {
                width: 16px;
                height: 16px;
                margin-right: 5px;
                background: transparent;
                border: none;
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24'%3E%3Cpath fill='%23666666' d='M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z'/%3E%3C/svg%3E");
            }
            QDateEdit::down-arrow:hover {
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24'%3E%3Cpath fill='%234a90e2' d='M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z'/%3E%3C/svg%3E");
            }
        """)
        
        # 设置日历弹出框样式
        self.date_input.calendarWidget().setStyleSheet("""
            QCalendarWidget {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QCalendarWidget QToolButton {
                color: #333333;
                padding: 6px;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                min-width: 60px;
                min-height: 25px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QCalendarWidget QMenu {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
            }
            QCalendarWidget QMenu::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QCalendarWidget QSpinBox {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 3px;
                margin: 0 2px;
                font-size: 13px;
            }
            QCalendarWidget QSpinBox::up-button, QCalendarWidget QSpinBox::down-button {
                border: none;
                background: #f5f5f5;
                border-radius: 2px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #ffffff;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #e0e0e0;
                padding: 6px;
            }
            QCalendarWidget QWidget { 
                alternate-background-color: #fafafa;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #333333;
                selection-background-color: #e3f2fd;
                selection-color: #1976d2;
                font-size: 13px;
            }
            QCalendarWidget QAbstractItemView:disabled {
                color: #bbbbbb;
            }
            QCalendarWidget QTableView {
                outline: 0;
                selection-background-color: #e3f2fd;
            }
            QCalendarWidget QTableView QHeaderView {
                background-color: white;
            }
            QCalendarWidget QTableView QHeaderView::section {
                color: #666666;
                padding: 6px;
                border: none;
                font-size: 12px;
                font-weight: bold;
                background-color: transparent;
            }
            QCalendarWidget QTableView QAbstractItemView:enabled #qt_calendar_daywidget[today="true"] {
                color: #1976d2;
                font-weight: bold;
                background-color: #e3f2fd;
                border-radius: 4px;
            }
            QCalendarWidget QTableView QAbstractItemView:enabled #qt_calendar_daywidget[selected="true"] {
                color: white;
                font-weight: bold;
                background-color: #1976d2;
                border-radius: 4px;
            }
            QCalendarWidget QTableView QAbstractItemView:enabled #qt_calendar_daywidget[weekend="true"] {
                color: #e57373;
            }
        """)
        metadata_layout.addWidget(self.create_form_group("发布日期", self.date_input))

        # 描述
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("输入博客描述")
        self.desc_input.setMaximumHeight(250)
        metadata_layout.addWidget(self.create_form_group("描述", self.desc_input))

        # 标签
        tags_widget = QWidget()
        tags_layout = QVBoxLayout(tags_widget)
        tags_layout.setSpacing(8)
        tags_layout.setContentsMargins(0, 0, 0, 0)

        self.tags_list = QListWidget()
        self.tags_list.setMaximumHeight(100)
        
        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("输入标签名称")
        add_tag_btn = QPushButton("添加")
        add_tag_btn.setObjectName("addButton")
        remove_tag_btn = QPushButton("删除")
        remove_tag_btn.setObjectName("deleteButton")
        add_tag_btn.clicked.connect(self.add_tag)
        remove_tag_btn.clicked.connect(self.remove_tag)
        
        tag_input_layout.addWidget(self.tag_input)
        tag_input_layout.addWidget(add_tag_btn)
        tag_input_layout.addWidget(remove_tag_btn)
        
        tags_layout.addWidget(self.tags_list)
        tags_layout.addLayout(tag_input_layout)
        metadata_layout.addWidget(self.create_form_group("标签", tags_widget))

        # 语言选择
        self.lang_select = QComboBox()
        self.lang_select.addItems(["中文", "English"])
        metadata_layout.addWidget(self.create_form_group("语言", self.lang_select))

        # 封面图片
        image_widget = QWidget()
        image_layout = QVBoxLayout(image_widget)
        image_layout.setSpacing(8)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self.image_path_label = QLabel("未选择图片")
        self.image_path_label.setStyleSheet("color: #666;")
        select_image_btn = QPushButton("选择图片")
        select_image_btn.clicked.connect(self.select_image)
        
        image_layout.addWidget(self.image_path_label)
        image_layout.addWidget(select_image_btn)
        metadata_layout.addWidget(self.create_form_group("封面图片", image_widget))

        # 背景颜色
        color_widget = QWidget()
        color_layout = QVBoxLayout(color_widget)
        color_layout.setSpacing(8)
        color_layout.setContentsMargins(0, 0, 0, 0)

        color_preview_layout = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.setStyleSheet("background-color: #FFFFFF; border: 1px solid #ddd; border-radius: 4px;")
        color_preview_layout.addWidget(self.color_preview)
        color_preview_layout.addStretch()

        select_color_btn = QPushButton("选择颜色")
        select_color_btn.clicked.connect(self.select_color)
        
        color_layout.addLayout(color_preview_layout)
        color_layout.addWidget(select_color_btn)
        metadata_layout.addWidget(self.create_form_group("背景颜色", color_widget))

        # 保存路径
        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setSpacing(8)
        path_layout.setContentsMargins(0, 0, 0, 0)

        self.path_input = QLineEdit()
        self.path_input.setText(self.save_path)
        self.path_input.setReadOnly(True)
        select_path_btn = QPushButton("选择")
        select_path_btn.clicked.connect(self.select_save_path)
        
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(select_path_btn)
        metadata_layout.addWidget(self.create_form_group("保存路径", path_widget))

        # 保存按钮
        save_btn = QPushButton("保存博客")
        save_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
                min-width: 120px;
                margin-top: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            QPushButton:hover {
                background-color: #27ae60;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            QPushButton:pressed {
                background-color: #219a52;
                box-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }
        """)
        save_btn.clicked.connect(self.save_blog)
        metadata_layout.addWidget(save_btn)

        # 添加弹性空间
        metadata_layout.addStretch()

        # 将元数据框架添加到左侧布局
        left_layout.addWidget(metadata_frame)
        
        # 创建右侧内容编辑区域
        content_frame = StyledFrame()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 编辑器
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        editor_layout.setContentsMargins(15, 15, 15, 15)
        
        editor_label = QLabel("Markdown 编辑")
        editor_label.setStyleSheet("font-weight: bold;")
        self.content_input = MarkdownEditor()
        self.content_input.setObjectName("contentEdit")
        self.content_input.setPlaceholderText("在这里输入 Markdown 格式的博客内容...\n支持拖放图片")
        self.content_input.textChanged.connect(self.update_preview)
        
        # 修复工具栏显示
        editor_layout.addWidget(editor_label)
        editor_layout.addWidget(self.content_input.toolbar)  # 先添加工具栏
        editor_layout.addWidget(self.content_input)  # 再添加编辑器
        
        # 预览
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(15, 15, 15, 15)
        
        preview_label = QLabel("预览")
        preview_label.setStyleSheet("font-weight: bold;")
        self.preview_widget = QTextBrowser()
        self.preview_widget.setObjectName("preview")
        self.preview_widget.setOpenExternalLinks(True)
        
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview_widget)
        
        # 添加到分割器
        splitter.addWidget(editor_widget)
        splitter.addWidget(preview_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        content_layout.addWidget(splitter)

        # 添加左侧和右侧区域到主布局
        main_layout.addWidget(scroll)
        main_layout.addWidget(content_frame, stretch=1)
        
        # 初始化数据
        self.current_color = "#FFFFFF"
        self.image_path = ""
        
        # 初始化自动保存器
        self.auto_saver = AutoSaver(self)
        
        # 尝试恢复自动保存的内容
        content, metadata = self.auto_saver.try_restore()
        if content and metadata:
            reply = QMessageBox.question(
                self,
                "恢复自动保存",
                "检测到上次未保存的内容，是否恢复？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.content_input.setPlainText(content)
                self.title_input.setText(metadata.get("title", ""))
                self.desc_input.setText(metadata.get("description", ""))
                self.folder_input.setText(metadata.get("folder", ""))
                
                if metadata.get("date"):
                    self.date_input.setDate(QDate.fromString(metadata["date"], "yyyy-MM-dd"))
                
                self.tags_list.clear()
                for tag in metadata.get("tags", []):
                    self.tags_list.addItem(tag)
                
                if metadata.get("language"):
                    index = 0 if metadata["language"] == "中文" else 1
                    self.lang_select.setCurrentIndex(index)
                
                if metadata.get("color"):
                    self.current_color = metadata["color"]
                    self.color_preview.setStyleSheet(
                        f"background-color: {self.current_color}; border: 1px solid #ddd; border-radius: 4px;"
                    )
                
                if metadata.get("image_path"):
                    self.image_path = metadata["image_path"]
                    self.image_path_label.setText(os.path.basename(self.image_path))
                    self.image_path_label.setStyleSheet("color: #2ecc71;")

    def create_form_group(self, label_text, widget):
        """创建表单组"""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold;")
        
        layout.addWidget(label)
        layout.addWidget(widget)
        
        return group

    def create_input_group(self, label_text, widget):
        """创建输入组"""
        return widget

    def add_tag(self):
        tag = self.tag_input.text().strip()
        if tag and not self.tags_list.findItems(tag, Qt.MatchFlag.MatchExactly):
            self.tags_list.addItem(tag)
            self.tag_input.clear()
            
    def remove_tag(self):
        current_item = self.tags_list.currentItem()
        if current_item:
            self.tags_list.takeItem(self.tags_list.row(current_item))
            
    def select_image(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择封面图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg)"
        )
        if file_name:
            self.image_path = file_name
            self.image_path_label.setText(os.path.basename(file_name))
            self.image_path_label.setStyleSheet("color: #2ecc71;")
            # 预览封面图片
            preview_html = f'<img src="file:///{file_name.replace(os.sep, "/")}" style="max-width: 200px; height: auto; margin-top: 10px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">'
            self.image_path_label.setText(f"{os.path.basename(file_name)}\n")
            self.image_path_label.setTextFormat(Qt.RichText)
            self.image_path_label.setText(self.image_path_label.text() + preview_html)
            
    def select_color(self):
        color_dialog = QColorDialog(QColor(self.current_color))
        # 设置颜色对话框的标题
        color_dialog.setWindowTitle("选择背景颜色")
        # 设置颜色对话框的样式
        color_dialog.setStyleSheet("""
            QColorDialog {
                background-color: #ffffff;
            }
            QColorDialog QLabel {
                font-size: 13px;
                color: #333333;
                padding: 5px;
            }
            QColorDialog QPushButton {
                min-width: 80px;
                min-height: 30px;
                padding: 5px 15px;
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
            }
            QColorDialog QPushButton:hover {
                background-color: #357abd;
            }
            QColorDialog QPushButton:pressed {
                background-color: #2a5d8c;
            }
            QColorDialog QLineEdit {
                padding: 5px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
                selection-background-color: #4a90e2;
            }
            QColorDialog QLineEdit:focus {
                border: 2px solid #4a90e2;
            }
            QColorDialog QSpinBox {
                padding: 5px;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
            }
            QColorDialog QSpinBox:focus {
                border: 2px solid #4a90e2;
            }
            QColorDialog QSpinBox::up-button, QColorDialog QSpinBox::down-button {
                border: none;
                background: #f5f5f5;
                border-radius: 2px;
            }
            QColorDialog QSpinBox::up-button:hover, QColorDialog QSpinBox::down-button:hover {
                background: #e0e0e0;
            }
            /* 自定义颜色部分的样式 */
            QColorDialog QWidget#qt_pick_button {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 5px;
            }
            QColorDialog QWidget#qt_pick_button:hover {
                border: 1px solid #4a90e2;
            }
            /* 基本颜色和自定义颜色的标签样式 */
            QColorDialog QLabel#qt_basic_colors_label, QColorDialog QLabel#qt_custom_colors_label {
                font-weight: bold;
                color: #333333;
                margin-top: 10px;
            }
            /* 颜色选择区域的样式 */
            QColorDialog QWidget#qt_color_picker {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
            }
            /* 颜色预览区域的样式 */
            QColorDialog QWidget#qt_color_preview {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        if color_dialog.exec() == QColorDialog.Accepted:
            self.current_color = color_dialog.selectedColor().name()
            self.color_preview.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #ddd; border-radius: 4px;")
            
    def select_save_path(self):
        """选择博客保存路径"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择博客保存路径",
            self.save_path or os.path.expanduser("~"),  # 如果没有保存路径，默认打开用户目录
            QFileDialog.ShowDirsOnly
        )
        if directory:
            self.save_path = directory
            self.path_input.setText(directory)
            # 保存新的路径到配置文件
            self.config_manager.save_config()
            
    def save_blog(self):
        # 检查文件夹名称
        folder_name = self.folder_input.text().strip()
        if not folder_name:
            self.statusBar().showMessage("请输入文件夹名称！", 3000)
            self.statusBar().setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")
            self.folder_input.setFocus()
            return
            
        # 收集所有标签
        tags = []
        for i in range(self.tags_list.count()):
            tags.append(self.tags_list.item(i).text())
            
        # 构建frontmatter
        frontmatter = {
            "title": self.title_input.text(),
            "publishDate": self.date_input.date().toString("yyyy-MM-dd"),
            "description": self.desc_input.toPlainText(),
            "tags": tags,
            "language": "中文" if self.lang_select.currentText() == "中文" else "English",
            "heroImage": {
                "src": f"./{os.path.basename(self.image_path)}" if self.image_path else "",
                "color": self.current_color
            }
        }
        
        try:
            # 创建文章专属文件夹
            article_folder = os.path.join(self.save_path, folder_name)
            os.makedirs(article_folder, exist_ok=True)
            
            # 处理文章中的图片
            content = self.content_input.toPlainText()
            
            # 查找所有图片引用
            import re
            image_pattern = r'!\[.*?\]\((.*?)\)'
            image_paths = re.findall(image_pattern, content)
            
            # 复制所有图片到文章目录并更新引用
            for img_path in image_paths:
                if img_path.startswith(('http://', 'https://')):
                    continue  # 跳过网络图片
                    
                # 获取图片文件名
                img_filename = os.path.basename(img_path)
                # 复制图片到文章目录
                target_path = os.path.join(article_folder, img_filename)
                try:
                    shutil.copy2(img_path, target_path)
                    # 更新内容中的图片路径为相对路径
                    content = content.replace(img_path, f"./{img_filename}")
                except:
                    pass  # 如果复制失败，保持原路径
            
            # 保存markdown文件
            md_content = "---\n"
            md_content += f"title: '{frontmatter['title']}'\n"
            md_content += f"publishDate: {frontmatter['publishDate']}\n"
            md_content += f"description: '{frontmatter['description']}'\n"
            md_content += "tags:\n"
            for tag in frontmatter['tags']:
                md_content += f"  - {tag}\n"
            md_content += f"language: '{frontmatter['language']}'\n"
            
            # 如果有封面图片，更新图片路径为相对路径
            if self.image_path:
                image_filename = os.path.basename(self.image_path)
                frontmatter['heroImage']['src'] = f"./{image_filename}"
                # 复制封面图片到文章文件夹
                target_path = os.path.join(article_folder, image_filename)
                shutil.copy2(self.image_path, target_path)
            
            md_content += f"heroImage: {{ src: '{frontmatter['heroImage']['src']}', color: '{frontmatter['heroImage']['color']}' }}\n"
            md_content += "---\n\n"
            md_content += content
            
            # 保存markdown文件到文章文件夹
            file_path = os.path.join(article_folder, "index.md")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
                
            self.statusBar().showMessage(f"博客保存成功！保存位置：{article_folder}", 3000)
            self.statusBar().setStyleSheet("background-color: #2ecc71; color: white; padding: 8px;")
        except Exception as e:
            self.statusBar().showMessage(f"保存失败: {str(e)}", 5000)
            self.statusBar().setStyleSheet("background-color: #e74c3c; color: white; padding: 8px;")

    def update_preview(self):
        """更新 Markdown 预览"""
        md_text = self.content_input.toPlainText()
        
        # 处理图片路径
        def path_to_url(md):
            import re
            def replace_path(match):
                alt = match.group(1)
                path = match.group(2)
                if path.startswith(('http://', 'https://', 'file:///')):
                    return f'![{alt}]({path})'
                
                # 处理相对路径
                if path.startswith('./') or path.startswith('../'):
                    base_path = os.path.dirname(self.save_path)
                    abs_path = os.path.abspath(os.path.join(base_path, path))
                else:
                    # 处理本地路径
                    abs_path = os.path.abspath(path)
                
                # 转换为 file:/// URL
                url_path = 'file:///' + abs_path.replace(os.sep, '/')
                return f'![{alt}]({url_path})'
            
            # 匹配 Markdown 图片语法
            pattern = r'!\[(.*?)\]\((.*?)\)'
            return re.sub(pattern, replace_path, md)
        
        # 处理图片路径
        md_text = path_to_url(md_text)
        
        # 渲染 Markdown
        html = markdown.markdown(
            md_text,
            extensions=[
                'markdown.extensions.extra',
                'markdown.extensions.codehilite',
                'markdown.extensions.tables',
                'markdown.extensions.toc',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br'
            ]
        )
        
        # 添加基本样式
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: "Microsoft YaHei", Arial, sans-serif;
                line-height: 1.6;
                color: #2c3e50;
                max-width: 100%;
                padding: 20px 40px;
                margin: 0;
                box-sizing: border-box;
            }}
            h1, h2, h3, h4, h5, h6 {{
                color: #34495e;
                margin-top: 24px;
                margin-bottom: 16px;
                line-height: 1.25;
            }}
            h1 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: .3em; }}
            h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: .3em; }}
            p {{ margin: 16px 0; line-height: 1.8; }}
            img {{
                max-width: 600px;  /* 设置固定的最大宽度 */
                max-height: 400px;  /* 设置固定的最大高度 */
                width: auto;  /* 保持宽高比 */
                height: auto;  /* 保持宽高比 */
                object-fit: contain;  /* 确保图片完整显示 */
                border-radius: 4px;
                margin: 20px auto;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: block;
            }}
            code {{
                background-color: #f8f9fa;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: Consolas, monospace;
                font-size: 0.9em;
                color: #e83e8c;
            }}
            pre {{
                background-color: #f8f9fa;
                padding: 16px;
                border-radius: 4px;
                overflow-x: auto;
                line-height: 1.45;
                border: 1px solid #e1e4e8;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
                color: #24292e;
                white-space: pre;
            }}
            blockquote {{
                padding: 0.5em 1em;
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                margin: 16px 0;
                background-color: #f6f8fa;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 16px 0;
                display: block;
                overflow-x: auto;
            }}
            table th, table td {{
                border: 1px solid #dfe2e5;
                padding: 8px 13px;
            }}
            table th {{
                background-color: #f6f8fa;
                font-weight: 600;
            }}
            table tr:nth-child(2n) {{
                background-color: #f8f9fa;
            }}
            a {{
                color: #0366d6;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
                color: #0056b3;
            }}
            ul, ol {{
                padding-left: 2em;
                margin: 16px 0;
            }}
            li {{
                margin: 4px 0;
            }}
            hr {{
                height: 1px;
                background-color: #e1e4e8;
                border: none;
                margin: 24px 0;
            }}
            kbd {{
                background-color: #fafbfc;
                border: 1px solid #d1d5da;
                border-bottom-color: #c6cbd1;
                border-radius: 3px;
                box-shadow: inset 0 -1px 0 #c6cbd1;
                color: #444d56;
                display: inline-block;
                font-size: 0.9em;
                line-height: 1;
                padding: 3px 5px;
            }}
        </style>
        </head>
        <body>
        {html}
        </body>
        </html>
        """
        
        # 设置 QTextBrowser 的基础路径为保存路径
        self.preview_widget.setSearchPaths([self.save_path])
        self.preview_widget.setHtml(styled_html)

    def update_metadata(self, metadata):
        """更新元数据表单"""
        if 'title' in metadata:
            self.title_input.setText(metadata['title'].strip("'\""))
        
        if 'description' in metadata:
            self.desc_input.setText(metadata['description'].strip("'\""))
        
        if 'publishDate' in metadata:
            try:
                date = QDate.fromString(metadata['publishDate'], "yyyy-MM-dd")
                self.date_input.setDate(date)
            except:
                pass
        
        if 'tags' in metadata and isinstance(metadata['tags'], list):
            self.tags_list.clear()
            for tag in metadata['tags']:
                self.tags_list.addItem(str(tag))
        
        if 'language' in metadata:
            lang = metadata['language']
            index = 0 if lang == '中文' else 1
            self.lang_select.setCurrentIndex(index)
        
        if 'heroImage' in metadata:
            if isinstance(metadata['heroImage'], dict):
                if 'color' in metadata['heroImage']:
                    color = metadata['heroImage']['color']
                    self.current_color = color
                    self.color_preview.setStyleSheet(
                        f"background-color: {color}; border: 1px solid #ddd; border-radius: 4px;"
                    )
        
        self.statusBar().showMessage("元数据更新成功！", 3000)
        self.statusBar().setStyleSheet("background-color: #2ecc71; color: white; padding: 8px;")

    def load_save_path(self):
        """从配置文件加载上次的保存路径"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    path = config.get('save_path', '')
                    if os.path.exists(path):
                        return path
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
        return ""  # 如果没有配置文件或路径无效，返回空字符串

    def save_config(self):
        """保存配置到文件"""
        try:
            config = {'save_path': self.save_path}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")

    def closeEvent(self, event):
        """程序关闭时保存配置"""
        self.save_config()  # 保存配置
        self.content_input.cleanup()
        self.auto_saver.cleanup()
        self.content_input.text_cache.cleanup()
        super().closeEvent(event)

    @handle_errors()
    def _setup_auto_save(self):
        """设置自动保存"""
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self._auto_save)
        interval = self.config_manager.get('auto_save_interval', 60) * 1000  # 转换为毫秒
        self.auto_save_timer.start(interval)
        
    @handle_errors()
    def _try_restore_auto_save(self):
        """尝试恢复自动保存的内容"""
        content = self.config_manager.get('auto_save_content', '')
        metadata = self.config_manager.get('auto_save_metadata', {})
        
        if content or metadata:
            reply = QMessageBox.question(
                self,
                "恢复自动保存",
                "检测到上次未保存的内容，是否恢复？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._restore_content(content, metadata)

    @handle_errors()
    def _restore_content(self, content: str, metadata: dict):
        """恢复内容和元数据"""
        if content:
            self.content_input.setPlainText(content)
            
        if metadata:
            self.title_input.setText(metadata.get("title", ""))
            self.desc_input.setText(metadata.get("description", ""))
            self.folder_input.setText(metadata.get("folder", ""))
            
            if metadata.get("date"):
                self.date_input.setDate(QDate.fromString(metadata["date"], "yyyy-MM-dd"))
            
            self.tags_list.clear()
            for tag in metadata.get("tags", []):
                self.tags_list.addItem(tag)
            
            if metadata.get("language"):
                index = 0 if metadata["language"] == "中文" else 1
                self.lang_select.setCurrentIndex(index)
            
            if metadata.get("color"):
                self.current_color = metadata["color"]
                self.color_preview.setStyleSheet(
                    f"background-color: {self.current_color}; border: 1px solid #ddd; border-radius: 4px;"
                )
            
            if metadata.get("image_path"):
                self.image_path = metadata["image_path"]
                self.image_path_label.setText(os.path.basename(self.image_path))
                self.image_path_label.setStyleSheet("color: #2ecc71;")

    @handle_errors()
    def _auto_save(self) -> None:
        """自动保存当前内容和元数据"""
        try:
            # 获取当前内容
            current_content = self.content_input.toPlainText()
            
            # 收集当前元数据
            current_metadata = {
                "title": self.title_input.text(),
                "description": self.desc_input.toPlainText(),
                "folder": self.folder_input.text(),
                "date": self.date_input.date().toString("yyyy-MM-dd"),
                "tags": [self.tags_list.item(i).text() 
                        for i in range(self.tags_list.count())],
                "language": self.lang_select.currentText(),
                "color": self.current_color,
                "image_path": getattr(self, 'image_path', '')
            }
            
            # 保存到配置
            self.config_manager.set('auto_save_content', current_content)
            self.config_manager.set('auto_save_metadata', current_metadata)
            self.config_manager.save_config()
            
            # 更新状态栏
            self.statusBar().showMessage("已自动保存", 2000)
            self.statusBar().setStyleSheet("""
                QStatusBar {
                    background-color: #2ecc71;
                    color: white;
                    padding: 5px;
                }
            """)
            
        except Exception as e:
            self.error_handler.handle_error(e, show_dialog=False)
            self.statusBar().showMessage("自动保存失败", 2000)
            self.statusBar().setStyleSheet("""
                QStatusBar {
                    background-color: #e74c3c;
                    color: white;
                    padding: 5px;
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用字体
    font = QFont("Microsoft YaHei", 10)  # 使用微软雅黑字体
    app.setFont(font)
    
    window = BlogEditor()
    window.show()
    sys.exit(app.exec()) 