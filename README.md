# Blog Editor

一个功能强大的 Markdown 博客编辑器，支持实时预览、图片处理、自动保存等功能。

## 功能特点

- 📝 Markdown 实时编辑与预览
- 🖼️ 支持图片拖放和粘贴
- 📊 实时字数统计（中英文分开统计）
- ⏱️ 预计阅读时间计算
- 💾 自动保存功能
- 🎨 Markdown 语法高亮
- 📋 支持 frontmatter 元数据
- 🗂️ 文章分类和标签管理
- 🎯 一键导出博客文章

## 系统要求

- Python 3.8 或更高版本
- Windows/Linux/MacOS

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/ShaneChing7/blog-editor.git
cd blog-editor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

运行程序：
```bash
python blog_editor.py
```

### 主要功能

1. **编辑器功能**
   - 使用工具栏快速插入 Markdown 语法
   - 支持快捷键操作
   - 实时预览编辑效果

2. **图片处理**
   - 支持拖放图片
   - 支持剪贴板粘贴图片
   - 自动压缩和优化图片
   - 自动生成唯一的图片文件名

3. **文章管理**
   - 支持设置文章标题、描述、标签等元数据
   - 自动生成 frontmatter
   - 支持导入已有的 Markdown 文件

4. **自动保存**
   - 定期自动保存内容
   - 程序意外关闭时可恢复编辑内容

## 项目结构

```
blog-editor/
├── blog_editor.py      # 主程序
├── config_manager.py   # 配置管理模块
├── error_handler.py    # 错误处理模块
├── file_manager.py     # 文件管理模块
├── image_processor.py  # 图片处理模块
├── requirements.txt    # 项目依赖
└── README.md          # 项目文档
```

## 配置说明

配置文件位于用户目录下的 `.blog_editor_config.json`，包含以下配置项：

- `save_path`: 博客文章保存路径
- `auto_save_interval`: 自动保存间隔（秒）
- `editor_font_size`: 编辑器字体大小
- `editor_font_family`: 编辑器字体
- `image_max_width`: 图片最大宽度
- `image_quality`: 图片压缩质量

## 开发说明

### 模块说明

1. **ConfigManager**
   - 处理程序配置的加载和保存
   - 提供配置项的读写接口

2. **ErrorHandler**
   - 统一的错误处理机制
   - 错误日志记录
   - 用户友好的错误提示

3. **ImageProcessor**
   - 图片压缩和优化
   - 临时文件管理
   - 图片格式转换

4. **FileManager**
   - 文件保存和导入
   - frontmatter 处理
   - 文件命名和组织

### 扩展开发

1. 添加新功能：
   - 在相应的模块中添加新的类或方法
   - 使用 `@handle_errors()` 装饰器进行错误处理
   - 遵循现有的代码风格和文档规范

2. 修改配置：
   - 在 `ConfigManager` 的 `_load_config` 方法中添加新的配置项
   - 更新配置文件结构

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

[MIT License](LICENSE)

## 作者

[ShaneQin]

## 更新日志

### v1.0.0
- 初始版本发布
- 基本编辑功能
- 图片处理功能
- 自动保存功能 