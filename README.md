# Vibe Translator

一个基于 Google VertexAI 的 macOS 菜单栏翻译工具。

## 功能

- 🌍 系统菜单栏常驻应用
- ⌨️ 全局快捷键 `Ctrl+Cmd+T` 快速翻译
- 🔄 支持中文、英文、德文互译
- 🎯 选中文本即可翻译
- 💬 优雅的翻译结果对话框

## 安装

1. 安装依赖：
```bash
cd /Users/xinyue.zhao/Desktop/dev/AI/vibe-translator
pip install -r requirements.txt
```

2. 配置环境变量：
确保 `.env` 文件包含正确的 Google Cloud 配置

3. 授予权限：
   - 系统设置 → 隐私与安全性 → 辅助功能
   - 添加 Terminal 或你的 Python 应用

## 使用方法

1. 启动应用：
```bash
python main.py
```

2. 你会在菜单栏看到 🌍 图标

3. 在任何应用中**选中文本**（不需要复制）

4. 点击菜单栏 🌍 图标，选择翻译方向：
   - 中文 → 德文
   - 德文 → 中文
   - 中文 → 英文
   - 英文 → 中文

5. 程序会自动获取选中的文本并翻译

6. 在屏幕中央的对话框查看翻译结果

## 技术栈

- **UI**: rumps (macOS 状态栏), tkinter (对话框)
- **剪贴板**: pyperclip
- **AI**: Google GenAI SDK (VertexAI)
- **模型**: Gemini 2.5 Flash Lite

## 注意事项

- 需要 Google Cloud VertexAI 访问权限
- macOS 需要**辅助功能权限**（用于自动复制选中文本）
- 确保已正确配置 Google Cloud 认证

### 授予辅助功能权限

1. 打开 **系统设置** → **隐私与安全性** → **辅助功能**
2. 点击 **+** 按钮添加 **Terminal** 或 **Python**
3. 重启程序

## 开发

使用 Gemini 2.5 Flash Lite 模型进行翻译，速度快且成本低。

## License

MIT
