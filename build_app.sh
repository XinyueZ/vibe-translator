#!/bin/bash
# 激活虚拟环境
source venv/bin/activate

# 安装打包必需的依赖
pip install pyinstaller pyobjc-framework-WebKit

# 检查是否存在 icon.icns，如果没有则生成
if [ ! -f "icon.icns" ]; then
    echo "正在从 splash.png 生成 icon.icns..."
    mkdir -p MyIcon.iconset
    sips -z 16 16     assets/splash.png --out MyIcon.iconset/icon_16x16.png
    sips -z 32 32     assets/splash.png --out MyIcon.iconset/icon_16x16@2x.png
    sips -z 32 32     assets/splash.png --out MyIcon.iconset/icon_32x32.png
    sips -z 64 64     assets/splash.png --out MyIcon.iconset/icon_32x32@2x.png
    sips -z 128 128   assets/splash.png --out MyIcon.iconset/icon_128x128.png
    sips -z 256 256   assets/splash.png --out MyIcon.iconset/icon_128x128@2x.png
    sips -z 256 256   assets/splash.png --out MyIcon.iconset/icon_256x256.png
    sips -z 512 512   assets/splash.png --out MyIcon.iconset/icon_256x256@2x.png
    sips -z 512 512   assets/splash.png --out MyIcon.iconset/icon_512x512.png
    sips -z 1024 1024 assets/splash.png --out MyIcon.iconset/icon_512x512@2x.png
    iconutil -c icns MyIcon.iconset -o icon.icns
    rm -rf MyIcon.iconset
fi

# 使用 PyInstaller 进行打包
echo "开始打包 Vibe Translator.app..."
pyinstaller --noconfirm \
    --name "Vibe Translator" \
    --icon icon.icns \
    --add-data "assets:assets" \
    --add-data "mac_ocr.swift:." \
    --add-data ".env.example:." \
    --hidden-import ui_daemon \
    --hidden-import splash \
    --hidden-import WebKit \
    --hidden-import AppKit \
    --hidden-import Foundation \
    --hidden-import pkg_resources \
    --windowed \
    main.py

echo "打包完成！已在 dist/ 目录下生成 Vibe Translator.app。"
