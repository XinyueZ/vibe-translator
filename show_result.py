#!/usr/bin/env python3
"""
Standalone script to show translation result
This runs in a separate process to avoid threading issues
"""

import sys
import os
import json
import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import pyperclip
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration file path
CONFIG_FILE = os.path.expanduser('~/.vibe_translator_config.json')


def load_config():
    """Load saved configuration"""
    default_config = {
        'window_width': 680,
        'window_height': 400,
        'font_size': 12
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge with defaults to handle missing keys
                return {**default_config, **config}
    except Exception as e:
        print(f"Error loading config: {e}")
    return default_config


def save_config(config):
    """Save configuration"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


def is_dark_mode():
    """Detect if macOS is in dark mode"""
    try:
        result = subprocess.run(
            ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and 'Dark' in result.stdout
    except Exception:
        return False


def get_theme_colors():
    """Get colors based on system theme"""
    if is_dark_mode():
        # Dark mode colors
        return {
            'bg': '#2C2C2C',           # Dark background
            'textbox_bg': '#3C3C3C',   # Lighter textbox background
            'fg': '#FFFFFF',           # White text
            'label_fg': '#E0E0E0',     # Slightly dimmed labels
            'status_fg': '#00DD00',    # Bright green for status
            'button_bg': '#0A84FF',    # macOS blue (dark mode)
            'button_fg': '#FFFFFF'     # White button text
        }
    else:
        # Light mode colors
        return {
            'bg': '#F0F0F0',           # Light gray background
            'textbox_bg': '#FFFFFF',   # White textbox
            'fg': '#000000',           # Black text
            'label_fg': '#000000',     # Black labels
            'status_fg': '#00AA00',    # Green for status
            'button_bg': '#007AFF',    # macOS blue (light mode)
            'button_fg': '#FFFFFF'     # White button text
        }


def get_style_options(source_lang, target_lang):
    """Get style options based on translation direction"""
    direction = f"{source_lang} → {target_lang}"

    styles = {
        "中文 → 德文": [
            "默认（duzen口吻）",
            "轻松（duzen口吻）",
            "官方（敬语口吻）",
            "随和（duzen口吻）",
            "非正式（duzen口吻）",
            "一般（duzen口吻）"
        ],
        "德文 → 中文": [
            "默认",
            "上海海派腔调",
            "大陆北方腔调",
            "大陆南方腔调",
            "台湾腔",
            "港台腔"
        ],
        "中文 → 英文": [
            "默认",
            "美国普通式",
            "美国牛仔式",
            "英国普通式",
            "英国绅士口吻"
        ],
        "英文 → 中文": [
            "默认",
            "上海海派腔调",
            "大陆北方腔调",
            "大陆南方腔调",
            "台湾腔",
            "港台腔"
        ]
    }

    return styles.get(direction, ["默认"])


def show_result(original, translation, source_lang, target_lang):
    """Show translation result in a window"""
    root = tk.Tk()
    root.title(f"翻译完成: {source_lang} → {target_lang}")

    # Load saved configuration
    config = load_config()

    # Initialize VertexAI client
    try:
        client = genai.Client(
            vertexai=True,
            project=os.getenv('GOOGLE_CLOUD_PROJECT'),
            location=os.getenv('GOOGLE_CLOUD_LOCATION')
        )
    except Exception as e:
        print(f"Failed to initialize VertexAI: {e}")
        client = None

    # Window size from config
    window_width = config['window_width']
    window_height = config['window_height']

    # Center window on screen
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Stay on top and focus
    root.attributes('-topmost', True)
    root.focus_force()
    root.lift()

    # Allow resizing with minimum size
    root.resizable(True, True)
    root.minsize(500, 300)  # Minimum size to keep UI usable

    # CRITICAL: Set window to appear above fullscreen apps
    # This must be done BEFORE setting geometry
    root.attributes('-topmost', True)

    # Don't use utility type - it prevents dropdown menus from working
    # We'll rely on window level instead

    # Get theme colors
    colors = get_theme_colors()

    # Set window background
    root.configure(bg=colors['bg'])

    # Main frame
    main_frame = tk.Frame(root, padx=20, pady=20, bg=colors['bg'])
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title and style selector frame
    title_frame = tk.Frame(main_frame, bg=colors['bg'])
    title_frame.pack(fill=tk.X, pady=(0, 10))

    # Title
    title_label = tk.Label(
        title_frame,
        text=f"翻译完成: {source_lang} → {target_lang}",
        font=("Arial", 14, "bold"),
        bg=colors['bg'],
        fg=colors['label_fg']
    )
    title_label.pack(side=tk.LEFT)

    # Style selector - custom dropdown to avoid modal issue with high window level
    style_options = get_style_options(source_lang, target_lang)
    style_var = tk.StringVar(value=style_options[0])  # Default to first option

    style_label = tk.Label(
        title_frame,
        text="风格:",
        font=("Arial", 11),
        bg=colors['bg'],
        fg=colors['label_fg']
    )
    style_label.pack(side=tk.LEFT, padx=(20, 5))

    # Custom dropdown button
    style_button = tk.Label(
        title_frame,
        textvariable=style_var,
        font=("Arial", 10),
        bg=colors['textbox_bg'],
        fg=colors['fg'],
        relief=tk.SOLID,
        borderwidth=1,
        padx=8,
        pady=4,
        cursor='hand2'
    )
    style_button.pack(side=tk.LEFT)

    # Dropdown arrow indicator
    arrow_label = tk.Label(
        title_frame,
        text=" ▼",
        font=("Arial", 8),
        bg=colors['bg'],
        fg=colors['label_fg']
    )
    arrow_label.pack(side=tk.LEFT)

    # Font size selector
    font_sizes = [10, 12, 14, 16, 18, 20, 24]
    font_size_var = tk.IntVar(value=config['font_size'])  # Load from config

    font_size_label = tk.Label(
        title_frame,
        text="字体:",
        font=("Arial", 11),
        bg=colors['bg'],
        fg=colors['label_fg']
    )
    font_size_label.pack(side=tk.LEFT, padx=(20, 5))

    # Font size button
    font_size_button = tk.Label(
        title_frame,
        text=str(font_size_var.get()),
        font=("Arial", 10),
        bg=colors['textbox_bg'],
        fg=colors['fg'],
        relief=tk.SOLID,
        borderwidth=1,
        padx=8,
        pady=4,
        cursor='hand2'
    )
    font_size_button.pack(side=tk.LEFT)

    # Font size dropdown arrow
    font_size_arrow = tk.Label(
        title_frame,
        text=" ▼",
        font=("Arial", 8),
        bg=colors['bg'],
        fg=colors['label_fg']
    )
    font_size_arrow.pack(side=tk.LEFT)

    # Create popup menu for style selection
    style_menu = tk.Menu(root, tearoff=0)

    def select_style(style):
        style_var.set(style)
        on_style_change()

    for option in style_options:
        style_menu.add_command(label=option, command=lambda s=option: select_style(s))

    # Show menu on click
    def show_style_menu(event):
        try:
            style_menu.post(event.x_root, event.y_root)
        finally:
            style_menu.grab_release()

    style_button.bind('<Button-1>', show_style_menu)
    arrow_label.bind('<Button-1>', show_style_menu)

    # Progress label (hidden by default)
    progress_label = tk.Label(
        main_frame,
        text="",
        font=("Arial", 10),
        bg=colors['bg'],
        fg=colors['button_bg']
    )
    progress_label.pack(pady=(0, 5))

    # Original text frame
    orig_label = tk.Label(
        main_frame,
        text="原文:",
        font=("Arial", 11, "bold"),
        bg=colors['bg'],
        fg=colors['label_fg'],
        anchor='w'
    )
    orig_label.pack(fill=tk.X, pady=(0, 5))

    # Calculate initial spacing based on saved font size
    initial_spacing = round(config['font_size'] * 0.309)

    orig_text = scrolledtext.ScrolledText(
        main_frame,
        wrap=tk.WORD,
        font=("Arial", config['font_size']),
        height=5,  # Initial 5 lines
        width=60,
        relief=tk.SOLID,
        borderwidth=1,
        bg=colors['textbox_bg'],
        fg=colors['fg'],
        insertbackground=colors['fg'],  # Cursor color
        spacing1=initial_spacing,  # Space before each line (Golden ratio)
        spacing2=0,  # Space between wrapped lines
        spacing3=initial_spacing   # Space after each line
    )
    # Allow textbox to expand proportionally (takes 1 part of available space)
    orig_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    orig_text.insert(tk.END, original)
    orig_text.config(state=tk.DISABLED)

    # Translation frame
    trans_label = tk.Label(
        main_frame,
        text="译文:",
        font=("Arial", 11, "bold"),
        bg=colors['bg'],
        fg=colors['label_fg'],
        anchor='w'
    )
    trans_label.pack(fill=tk.X, pady=(0, 5))

    trans_text = scrolledtext.ScrolledText(
        main_frame,
        wrap=tk.WORD,
        font=("Arial", config['font_size']),
        height=5,  # Initial 5 lines
        width=60,
        relief=tk.SOLID,
        borderwidth=1,
        bg=colors['textbox_bg'],
        fg=colors['fg'],
        insertbackground=colors['fg'],  # Cursor color
        spacing1=initial_spacing,  # Space before each line (Golden ratio)
        spacing2=0,  # Space between wrapped lines
        spacing3=initial_spacing   # Space after each line
    )
    # Allow textbox to expand proportionally (takes 1 part of available space)
    trans_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    trans_text.insert(tk.END, translation)
    trans_text.config(state=tk.DISABLED)

    # Font size selection logic (after text boxes are created)
    font_size_menu = tk.Menu(root, tearoff=0)

    def select_font_size(size):
        font_size_var.set(size)
        font_size_button.config(text=str(size))
        # Calculate line spacing based on golden ratio
        # Line height = font_size * φ (≈ 1.618)
        # Leading = line_height - font_size = font_size * 0.618
        # Spacing (top + bottom) = leading / 2
        spacing = round(size * 0.309)  # ≈ size * 0.618 / 2
        # Update font size and spacing for both text boxes
        orig_text.config(font=("Arial", size), spacing1=spacing, spacing3=spacing)
        trans_text.config(font=("Arial", size), spacing1=spacing, spacing3=spacing)
        # Save font size to config
        config['font_size'] = size
        save_config(config)

    for size in font_sizes:
        font_size_menu.add_command(label=str(size), command=lambda s=size: select_font_size(s))

    # Show font size menu on click
    def show_font_size_menu(event):
        try:
            font_size_menu.post(event.x_root, event.y_root)
        finally:
            font_size_menu.grab_release()

    font_size_button.bind('<Button-1>', show_font_size_menu)
    font_size_arrow.bind('<Button-1>', show_font_size_menu)

    # Status label
    status_label = tk.Label(
        main_frame,
        text="✓ 译文已复制到剪贴板 (按 Esc 关闭)",
        font=("Arial", 10),
        fg=colors['status_fg'],
        bg=colors['bg']
    )
    status_label.pack(pady=(5, 0))

    # Function to retranslate with selected style
    def on_style_change():
        selected_style = style_var.get()

        # Skip if default style (any variant)
        if "默认" in selected_style:
            return

        # Show progress
        progress_label.config(text="🔄 正在重新翻译...")
        style_button.config(cursor='watch')
        root.update()

        # Perform translation in background thread
        def translate_with_style():
            try:
                # Create style-specific prompt
                if "默认" in selected_style:
                    # Check if translating to German - use duzen by default
                    if target_lang == "德文":
                        style_instruction = "请使用 duzen 口吻（非正式的\"你\"）进行翻译。"
                    else:
                        style_instruction = ""
                else:
                    style_instruction = f"请使用{selected_style}风格进行翻译。"

                # Build comprehensive prompt
                prompt = f"""请将以下完整文本从{source_lang}翻译成{target_lang}。

{style_instruction}

重要要求：
1. 翻译所有内容，包括所有行和段落
2. 保持原文的换行和格式
3. 只返回翻译结果，不要添加任何解释或说明

原文：
{original}

译文："""

                print(f"Style translation prompt:\n{prompt}\n")

                # Call VertexAI
                response = client.models.generate_content(
                    model='gemini-3.1-flash-lite-preview',
                    contents=prompt
                )

                new_translation = response.text.strip()
                print(f"Style translation result: {new_translation}")

                # Update UI in main thread
                def update_ui():
                    trans_text.config(state=tk.NORMAL)
                    trans_text.delete(1.0, tk.END)
                    trans_text.insert(tk.END, new_translation)
                    trans_text.config(state=tk.DISABLED)

                    # Copy to clipboard
                    import pyperclip
                    pyperclip.copy(new_translation)

                    progress_label.config(text="")
                    status_label.config(text="✓ 译文已更新并复制到剪贴板 (按 Esc 关闭)")
                    style_button.config(cursor='hand2')

                root.after(0, update_ui)

            except Exception as e:
                print(f"Translation error: {e}")
                def show_error():
                    progress_label.config(text="❌ 翻译失败")
                    style_button.config(cursor='hand2')
                root.after(0, show_error)

        # Start translation thread
        if client:
            threading.Thread(target=translate_with_style, daemon=True).start()
        else:
            progress_label.config(text="❌ VertexAI 未初始化")
            style_button.config(cursor='hand2')

    # Function to save window size on close
    def on_window_close():
        # Get current window geometry
        geometry = root.geometry()
        # Parse width and height from geometry string (format: WIDTHxHEIGHT+X+Y)
        size_part = geometry.split('+')[0]
        width, height = map(int, size_part.split('x'))
        # Save to config
        config['window_width'] = width
        config['window_height'] = height
        save_config(config)
        # Destroy window
        root.destroy()

    # Bind Escape key to close
    root.bind('<Escape>', lambda e: on_window_close())

    # Also bind Cmd+W to close (macOS standard)
    root.bind('<Command-w>', lambda e: on_window_close())

    # Bind window close button (X button)
    root.protocol("WM_DELETE_WINDOW", on_window_close)

    # Force window to highest level to appear above fullscreen apps
    # This needs to be done after the window is created
    root.update_idletasks()

    # Use PyObjC to set window level and force focus
    try:
        from AppKit import NSApp, NSWindow, NSApplicationActivationPolicyRegular
        from Foundation import NSArray

        # CRITICAL: Set activation policy to regular app
        # This allows the app to be activated and take focus
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        # Force the application to activate and take focus
        # This makes the window visible and switches to its desktop
        NSApp.activateIgnoringOtherApps_(True)

        # Get the Tk window
        for window in NSApp.windows():
            if window.title() == root.title():
                # Use NSPopUpMenuWindowLevel (101) to appear above fullscreen apps
                window.setLevel_(101)  # NSPopUpMenuWindowLevel

                # REMOVE collection behavior that prevents desktop switching
                # We WANT to switch to the window's desktop
                # Don't use Stationary or CanJoinAllSpaces
                window.setCollectionBehavior_(0)

                # Make window key and bring to front
                window.makeKeyAndOrderFront_(None)

                # Force window to become the key window (get focus)
                window.makeKeyWindow()

                # Order front again to ensure visibility
                window.orderFrontRegardless()

                print(f"Window activated with focus on its desktop")
                break

        # Give the window manager time to process
        root.update()

    except Exception as e:
        print(f"Warning: Could not set window level: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: just bring to front
        root.lift()
        root.focus_force()

    # Run
    root.mainloop()


if __name__ == "__main__":
    import json

    # Check if data file is provided
    if len(sys.argv) >= 2 and sys.argv[1].endswith('.json'):
        # Load from JSON file
        try:
            with open(sys.argv[1], 'r', encoding='utf-8') as f:
                data = json.load(f)
            original = data['original']
            translation = data['translation']
            source_lang = data['source_lang']
            target_lang = data['target_lang']
        except Exception as e:
            print(f"Error loading data file: {e}")
            sys.exit(1)
    elif len(sys.argv) >= 5:
        # Load from command line arguments
        original = sys.argv[1]
        translation = sys.argv[2]
        source_lang = sys.argv[3]
        target_lang = sys.argv[4]
    else:
        print("Usage: show_result.py <data.json> OR <original> <translation> <source_lang> <target_lang>")
        sys.exit(1)

    show_result(original, translation, source_lang, target_lang)
