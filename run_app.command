#!/bin/bash
# 在前台运行翻译器（保持Terminal窗口打开）

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查是否已经在运行
if pgrep -f "python.*main.py" > /dev/null; then
    echo "翻译器已经在运行中！"
    echo "如果看不到托盘图标，请关闭此窗口并重新打开。"
    read -p "按Enter键退出..."
    exit 0
fi

# 激活虚拟环境并运行
source venv/bin/activate
echo "正在启动翻译器..."
echo "托盘图标应该出现在屏幕顶部菜单栏右侧：🌍"
echo ""
echo "注意：请保持此Terminal窗口打开！"
echo "关闭此窗口会终止翻译器。"
echo ""
python main.py
