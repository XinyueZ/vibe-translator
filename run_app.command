#!/bin/bash
# Vibe Translator 启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查是否已经在运行
if pgrep -f "python.*main.py" > /dev/null; then
    echo "翻译器已经在运行中！"
    sleep 2
    exit 0
fi

# 激活虚拟环境并在后台启动应用
source venv/bin/activate
nohup python main.py > /tmp/vibe-translator.log 2>&1 &

echo "翻译器已启动！托盘图标：🌍"
echo "日志文件：/tmp/vibe-translator.log"
sleep 2
