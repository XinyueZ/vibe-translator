# Vibe Translator

[English](#english) | [中文](#中文)

---

## English

A macOS menu bar translation application powered by Google VertexAI.

### Features

- 🌍 **Menu Bar Integration** - Lives in your macOS menu bar
- 🎈 **Floating Widget** - Persistent, draggable desktop widget that expands to show translations instantly without spawning new windows
- 👻 **Omnipresent** - Strictly stays above all other apps and follows you across all macOS Spaces/Desktops automatically
- 🔄 **Multi-Language Support** - Translate between Chinese, English, and German
- 🎨 **Style Options** - Choose translation tones (informal/formal German, regional Chinese dialects, etc.)
- 🎯 **Text Selection** - Select text anywhere and translate instantly
- 💬 **Elegant UI** - Clean, theme-aware dialog with resizable windows
- ⚡ **Fast Translation** - Powered by Gemini 3.1 Flash Lite Preview
- 🌓 **Theme Support** - Automatically adapts to macOS dark/light mode

### Installation

1. **Clone the repository**
```bash
git clone git@github.com:XinyueZ/vibe-translator.git
cd vibe-translator
```

2. **Create virtual environment and install dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure environment variables**

Create a `.env` file with your Google Cloud credentials:
```bash
cp .env.example .env
```

Edit `.env` and add your VertexAI configuration:
```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=True

# Model Configuration
GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

> **Note**: To ensure your Google Cloud authentication remains active, it is recommended to run `gcloud auth application-default login` in your terminal every 24 hours to refresh your credentials. Or use the "Auth 刷新授权" button from the menu bar.

4. **Grant macOS Accessibility Permission**
   - Open **System Settings** → **Privacy & Security** → **Accessibility**
   - Click **+** and add **Terminal** (or your Python executable)
   - Enable the checkbox

### Usage

**Option 1: Double-click launcher (Recommended)**
```bash
# Double-click one of these files in Finder:
run_app.command           # English launcher
启动翻译器.command         # Chinese launcher
```

**Option 2: Terminal**
```bash
source venv/bin/activate
python main.py
```

Keep the Terminal window open (you can minimize it).

**Translation Steps:**

1. You'll see a 🌍 icon in your menu bar (top-right corner) AND a persistent floating 🌍 widget on your desktop
2. You can drag the floating widget anywhere on your screen
3. Select text anywhere in macOS
4. Click the menu bar 🌍 icon and choose translation direction
5. The app automatically captures selected text, translates, and instantly expands the floating widget into a beautiful result dialog
6. Press `Esc` or `Cmd+W` to close the dialog and collapse it back to a floating widget

### Translation Styles

- **German**: Choose between duzen (informal "you", default) or formal Sie
- **Chinese**: Regional accents including Shanghai, Northern/Southern Mainland, Taiwan, Hong Kong
- **English**: American standard, American cowboy style, British standard, British gentleman

### Technology Stack

- **UI Framework**: rumps (menu bar), tkinter (dialogs)
- **Clipboard**: pyperclip
- **AI Model**: Google GenAI SDK with VertexAI
- **Model**: Gemini 3.1 Flash Lite Preview
- **Platform**: macOS

### Requirements

- macOS (tested on macOS 12+)
- Python 3.8+
- Google Cloud account with VertexAI API enabled
- Accessibility permissions

### License

MIT

---

## 中文

一个基于 Google VertexAI 的 macOS 菜单栏翻译工具。

### 功能特性

- 🌍 **菜单栏集成** - 常驻在 macOS 菜单栏
- 🎈 **悬浮组件** - 常驻桌面、可随意拖拽的悬浮球，瞬间展开显示翻译结果，告别反复弹窗
- 👻 **无处不在** - 拥有最高系统层级置顶，且会像“幽灵”一样跨越所有 macOS 桌面空间 (Spaces) 跟随你
- 🔄 **多语言支持** - 中文、英文、德文互译
- 🎨 **风格选项** - 选择翻译风格（德语 duzen/Sie、中文地域口音等）
- 🎯 **文本选择** - 在任何地方选中文本即可翻译
- 💬 **优雅界面** - 简洁、跟随系统主题、可调整大小的对话框
- ⚡ **快速翻译** - 使用 Gemini 3.1 Flash Lite Preview 模型
- 🌓 **主题支持** - 自动适配 macOS 深色/浅色模式

### 安装步骤

1. **克隆仓库**
```bash
git clone git@github.com:XinyueZ/vibe-translator.git
cd vibe-translator
```

2. **创建虚拟环境并安装依赖**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **配置环境变量**

创建 `.env` 文件并填入你的 Google Cloud 凭证：
```bash
cp .env.example .env
```

编辑 `.env` 文件，添加你的 VertexAI 配置：
```
GOOGLE_CLOUD_PROJECT=你的项目ID
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=True

# 模型配置
GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

> **注意**：为了确保您的 Google Cloud 身份验证保持有效，建议每 24 小时在终端中运行一次 `gcloud auth application-default login` 以刷新您的凭证。或者使用菜单栏中的 "Auth 刷新授权" 按钮。

4. **授予 macOS 辅助功能权限**
   - 打开 **系统设置** → **隐私与安全性** → **辅助功能**
   - 点击 **+** 添加 **Terminal**（或你的 Python 可执行文件）
   - 勾选启用

### 使用方法

**方式一：双击启动器（推荐）**
```bash
# 在访达中双击以下文件之一：
run_app.command           # 英文启动器
启动翻译器.command         # 中文启动器
```

**方式二：终端**
```bash
source venv/bin/activate
python main.py
```

保持终端窗口打开（可以最小化）。

**翻译步骤：**

1. 你会在菜单栏右上角看到 🌍 图标，并且在桌面上会看到一个常驻的 🌍 悬浮球
2. 你可以用鼠标拖拽悬浮球到屏幕的任意位置
3. 在 macOS 任何地方选中文本
4. 点击菜单栏的 🌍 图标并选择翻译方向
5. 应用会自动获取选中的文本并翻译，悬浮球会瞬间展开成一个优雅的翻译结果窗口
6. 按 `Esc` 或 `Cmd+W` 关闭结果窗口，它会自动缩回变成悬浮球

### 翻译风格

- **德文**：可选 duzen（非正式"你"，默认）或正式 Sie 口吻
- **中文**：地域口音包括上海海派、大陆北方/南方、台湾腔、港台腔
- **英文**：美国普通式、美国牛仔式、英国普通式、英国绅士口吻

### 技术栈

- **UI 框架**: rumps（菜单栏）、tkinter（对话框）
- **剪贴板**: pyperclip
- **AI 模型**: Google GenAI SDK with VertexAI
- **模型**: Gemini 3.1 Flash Lite Preview
- **平台**: macOS

### 系统要求

- macOS（在 macOS 12+ 测试）
- Python 3.8+
- 开通 VertexAI API 的 Google Cloud 账号
- 辅助功能权限

### 许可证

MIT

---

## Stats

![GitHub stars](https://img.shields.io/github/stars/XinyueZ/vibe-translator?style=social)
![GitHub forks](https://img.shields.io/github/forks/XinyueZ/vibe-translator?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/XinyueZ/vibe-translator?style=social)
![GitHub repo size](https://img.shields.io/github/repo-size/XinyueZ/vibe-translator)
![GitHub language count](https://img.shields.io/github/languages/count/XinyueZ/vibe-translator)
![GitHub top language](https://img.shields.io/github/languages/top/XinyueZ/vibe-translator)
![GitHub last commit](https://img.shields.io/github/last-commit/XinyueZ/vibe-translator)
![Visitors](https://api.visitorbadge.io/api/visitors?path=XinyueZ%2Fvibe-translator&countColor=%23263759&style=flat)
