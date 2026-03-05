#!/usr/bin/env python3
"""
Persistent UI Daemon for Vibe Translator
Acts as a floating widget that expands to show translations.
Listens on a local socket for incoming translations from main.py.
"""

import sys
import os
import json
import tkinter as tk
from tkinter import scrolledtext
import threading
import socket
import pyperclip
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CONFIG_FILE = os.path.expanduser('~/.vibe_translator_config.json')
PORT = 50051  # Local port for IPC

def load_config():
    default_config = {
        'window_width': 680,
        'window_height': 400,
        'font_size': 14
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return {**default_config, **config}
    except Exception:
        pass
    return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_theme_colors():
    # Detect dark mode roughly by checking dark appearance (simple fallback)
    try:
        import subprocess
        result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], capture_output=True, text=True)
        is_dark = result.returncode == 0 and 'Dark' in result.stdout
    except:
        is_dark = False

    if is_dark:
        return {'bg': '#2C2C2C', 'textbox_bg': '#3C3C3C', 'fg': '#FFFFFF', 'label_fg': '#E0E0E0', 'status_fg': '#00DD00', 'button_bg': '#0A84FF'}
    else:
        return {'bg': '#F0F0F0', 'textbox_bg': '#FFFFFF', 'fg': '#000000', 'label_fg': '#000000', 'status_fg': '#00AA00', 'button_bg': '#007AFF'}

def get_style_options(source_lang, target_lang):
    direction = f"{source_lang} → {target_lang}"
    
    # Common Chinese styles
    chinese_styles = ["默认", "上海海派腔调", "大陆北方腔调", "大陆南方腔调", "台湾腔", "港台腔"]
    
    styles = {
        "中文 → 德文": ["默认（duzen口吻）", "轻松（duzen口吻）", "官方（敬语口吻）", "随和（duzen口吻）", "非正式（duzen口吻）", "一般（duzen口吻）"],
        "德文 → 中文": chinese_styles,
        "中文 → 英文": ["默认", "美国普通式", "美国牛仔式", "英国普通式", "英国绅士口吻"],
        "英文 → 中文": chinese_styles,
        "自动检测 → 中文": chinese_styles
    }
    return styles.get(direction, ["默认"])

class TranslatorUI:
    def __init__(self):
        self.config = load_config()
        self.colors = get_theme_colors()
        self.ui_lang = self.config.get('ui_lang', 'zh')
        
        self.i18n = {
            'zh': {
                'auto_zh': '自动检测 → 中文',
                'add_lang': '➕ 添加翻译语言',
                'zh_de': '中文 → 德文',
                'de_zh': '德文 → 中文',
                'zh_en': '中文 → 英文',
                'en_zh': '英文 → 中文',
                'auth': 'Auth 刷新授权',
                'ui_zh': '界面中文',
                'ui_en': '界面英文',
                'mouse_follow': '鼠标跟随',
                'how_to_use': '使用方法',
                'quit': '退出',
                'ctrl_click': 'ctrl+鼠标',
                'wait': '等待翻译...',
                'orig': '原文:',
                'trans': '译文:',
                'style': '风格:',
                'font': '字体:',
                'copied': '✓ 译文已复制 (按 Esc 收起)',
                'translating': '正在翻译:',
                'call_api': '⏳ 正在为您翻译，请稍候...',
                'trans_done': '翻译完成:',
                'trans_fail': '❌ 翻译失败',
                'err_net': '请检查网络或配置',
                're_trans': '🔄 正在重新翻译...'
            },
            'en': {
                'auto_zh': 'Auto → ZH',
                'add_lang': '➕ Add Language',
                'zh_de': 'ZH → DE',
                'de_zh': 'DE → ZH',
                'zh_en': 'ZH → EN',
                'en_zh': 'EN → ZH',
                'auth': 'Auth Refresh',
                'ui_zh': 'UI: Chinese',
                'ui_en': 'UI: English',
                'mouse_follow': 'Mouse Follow',
                'how_to_use': 'How to Use',
                'quit': 'Quit',
                'ctrl_click': 'ctrl+click',
                'wait': 'Waiting for translation...',
                'orig': 'Original:',
                'trans': 'Translation:',
                'style': 'Style:',
                'font': 'Font:',
                'copied': '✓ Copied to clipboard (Esc to hide)',
                'translating': 'Translating:',
                'call_api': '⏳ Translating for you, please wait...',
                'trans_done': 'Done:',
                'trans_fail': '❌ Translation Failed',
                'err_net': 'Check network or config',
                're_trans': '🔄 Retranslating...'
            }
        }
        self.t = self.i18n[self.ui_lang]
        
        try:
            use_vertex = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'False').lower() in ('true', '1', 't', 'yes')
            
            if use_vertex:
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
                location = os.getenv('GOOGLE_CLOUD_LOCATION')
                model_name = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')
                
                # Auto-override location for preview models
                if "-preview" in model_name.lower():
                    location = "global"
                    
                if not project_id or not location:
                    raise ValueError("Missing GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION")
                self.client = genai.Client(vertexai=True, project=project_id, location=location)
            else:
                api_key = os.getenv('GOOGLE_AI_STUDIO_API_KEY')
                if not api_key:
                    raise ValueError("Illegal State: GOOGLE_AI_STUDIO_API_KEY is missing when VertexAI is disabled")
                self.client = genai.Client(api_key=api_key)
        except Exception as e:
            print(f"Failed to init GenAI Client: {e}")
            self.client = None

        # Base invisible root
        self.root = tk.Tk()
        self.root.withdraw()
        
        # ---------------- WIDGET WINDOW (Floating Icon) ----------------
        self.widget = tk.Toplevel(self.root)
        self.widget.attributes('-topmost', True)
        self.widget.overrideredirect(True) # No window decorations
        
        # Make the window background transparent
        self.widget.configure(bg='systemTransparent')
        self.widget.attributes('-transparent', True) # Important for macOS
        
        # Place in saved position or bottom right corner
        self.widget_x = self.config.get('widget_x', self.root.winfo_screenwidth() - 80)
        self.widget_y = self.config.get('widget_y', self.root.winfo_screenheight() - 100)
        
        # Make the window square for a perfect circle (e.g., 60x60)
        widget_size = 60
        self.widget.geometry(f"{widget_size}x{widget_size}+{self.widget_x}+{self.widget_y}")
        
        # Create a Canvas to draw the circle
        self.widget_canvas = tk.Canvas(self.widget, width=widget_size, height=widget_size, bg='systemTransparent', highlightthickness=0)
        self.widget_canvas.pack(expand=True, fill='both')
        
        # Draw the circle (margin of 2 pixels to avoid clipping)
        margin = 2
        self.circle_id = self.widget_canvas.create_oval(
            margin, margin, widget_size-margin, widget_size-margin, 
            fill=self.colors['button_bg'], outline=""
        )
        
        # Add the icon text in the center
        self.widget_icon = self.widget_canvas.create_text(
            widget_size/2, widget_size/2 - 5, 
            text="🌍", font=("Arial", 22), fill="white"
        )
        
        # Add the hint text below the icon
        self.widget_hint = self.widget_canvas.create_text(
            widget_size/2, widget_size/2 + 15, 
            text=self.t['ctrl_click'], font=("Arial", 8), fill="white"
        )
        
        # Bind events to the canvas instead of labels
        self.widget_target = self.widget_canvas
        
        # Dragging logic variables
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._win_start_x = 0
        self._win_start_y = 0
        self._is_dragging = False

        def on_drag_start(event):
            self._drag_start_x = event.x_root
            self._drag_start_y = event.y_root
            self._win_start_x = self.widget.winfo_x()
            self._win_start_y = self.widget.winfo_y()
            self._is_dragging = False

        def on_drag_motion(event):
            dx = event.x_root - self._drag_start_x
            dy = event.y_root - self._drag_start_y
            if not self._is_dragging and (abs(dx) > 3 or abs(dy) > 3):
                self._is_dragging = True
            if self._is_dragging:
                new_x = self._win_start_x + dx
                new_y = self._win_start_y + dy
                self.widget.geometry(f"+{new_x}+{new_y}")

        def on_drag_release(event):
            if self._is_dragging:
                self.config['widget_x'] = self.widget.winfo_x()
                self.config['widget_y'] = self.widget.winfo_y()
                save_config(self.config)
            # We explicitly removed self.expand_to_main() here
            # so the main window only opens when an actual translation is triggered.

        for ui_element in (self.widget_canvas,):
            ui_element.bind("<ButtonPress-1>", on_drag_start)
            ui_element.bind("<B1-Motion>", on_drag_motion)
            ui_element.bind("<ButtonRelease-1>", on_drag_release)

        # Context Menu for the widget
        self.context_menu = tk.Menu(self.widget, tearoff=0)
        self.context_menu.add_command(label=self.t['auto_zh'], command=lambda: self.send_command_to_main('auto_zh'))
        self.context_menu.add_separator()
        self.context_menu.add_command(label=self.t['add_lang'], command=lambda: self.send_command_to_main('add_lang'))
        
        # Add custom languages
        if 'custom_langs' in self.config:
            for cl in self.config['custom_langs']:
                label_text = f"{cl['source']} → {cl['target']}"
                self.context_menu.add_command(label=label_text, command=lambda cid=cl['id']: self.send_command_to_main(f'custom_translate_{cid}'))
                
        self.context_menu.add_command(label=self.t['zh_de'], command=lambda: self.send_command_to_main('zh_de'))
        self.context_menu.add_command(label=self.t['de_zh'], command=lambda: self.send_command_to_main('de_zh'))
        self.context_menu.add_command(label=self.t['zh_en'], command=lambda: self.send_command_to_main('zh_en'))
        self.context_menu.add_command(label=self.t['en_zh'], command=lambda: self.send_command_to_main('en_zh'))
        self.context_menu.add_separator()
        
        self.mouse_follow_var = tk.BooleanVar(value=self.config.get('mouse_follow', True))
        def on_widget_toggle_mouse_follow():
            # Send command to main which will broadcast state back
            self.send_command_to_main('toggle_mouse_follow')
        
        self.context_menu.add_checkbutton(label=self.t['mouse_follow'], variable=self.mouse_follow_var, command=on_widget_toggle_mouse_follow)
        self.context_menu.add_command(label=self.t['how_to_use'], command=self.show_toast)
        
        self.context_menu.add_command(label=self.t['ui_zh'], command=lambda: self.send_command_to_main('ui_zh'))
        self.context_menu.add_command(label=self.t['ui_en'], command=lambda: self.send_command_to_main('ui_en'))
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label=self.t['auth'], command=lambda: self.send_command_to_main('auth'))
        self.context_menu.add_command(label=self.t['quit'], command=lambda: self.send_command_to_main('quit'))

        def show_context_menu(event):
            try:
                self.context_menu.post(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

        for ui_element in (self.widget_canvas,):
            ui_element.bind("<Button-2>", show_context_menu)
            ui_element.bind("<Button-3>", show_context_menu)
            ui_element.bind("<Control-Button-1>", show_context_menu)

        # ---------------- MAIN WINDOW ----------------
        self.main_win = tk.Toplevel(self.root)
        self.main_win.title("Vibe Translator")
        self.main_win.attributes('-topmost', True)
        self.main_win.configure(bg=self.colors['bg'])
        self.main_win.protocol("WM_DELETE_WINDOW", self.collapse_to_widget)
        self.main_win.bind('<Escape>', lambda e: self.collapse_to_widget())
        self.main_win.bind('<Command-w>', lambda e: self.collapse_to_widget())
        
        self._build_main_ui()
        
        # Initially hide main window
        self.main_win.withdraw()

        # Start Socket Server
        self.server_thread = threading.Thread(target=self._start_server, daemon=True)
        self.server_thread.start()
        
        # Force strict topmost using PyObjC after windows are mapped
        self.root.after(100, self._force_strict_topmost)
        
        # Start watchdog to prevent macOS from mysteriously hiding the widget
        self._start_visibility_watchdog()

        # Mouse follow logic
        self.mouse_follow = self.config.get('mouse_follow', True)
        self.ctrl_pressed = False
        
        try:
            from pynput import keyboard
            def on_press(key):
                if key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = True
            def on_release(key):
                if key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = False
            self.kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.kb_listener.start()
        except ImportError:
            pass

        self.root.after(20, self._mouse_follow_loop)

    def _mouse_follow_loop(self):
        if self.mouse_follow and not self.ctrl_pressed and not self.main_win.winfo_viewable() and not getattr(self, '_is_dragging', False):
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
            
            # Simple offset
            new_x = x + 10
            new_y = y + 10
            
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            
            # Bound check assuming widget is approx 60x65
            if new_x + 60 > screen_w:
                new_x = x - 70
            if new_y + 65 > screen_h:
                new_y = y - 75
                
            self.widget.geometry(f"+{new_x}+{new_y}")
            
        self.root.after(20, self._mouse_follow_loop)

    def _start_visibility_watchdog(self):
        """Periodically ensure the widget remains visible and on top"""
        # If the main window is NOT visible, the widget SHOULD be visible
        if not self.main_win.winfo_viewable():
            try:
                if self.widget.state() != 'normal':
                    self.widget.deiconify()
                self.widget.lift()
                self.widget.attributes('-topmost', True)
                # Re-assert native macOS topmost level gently
                self._force_strict_topmost()
            except Exception:
                pass
        
        # Run this check every 2000ms (2 seconds)
        self.root.after(2000, self._start_visibility_watchdog)

    def _format_lang(self, lang_str):
        if self.ui_lang == 'en':
            return lang_str.replace("自动检测", "Auto").replace("中文", "ZH").replace("英文", "EN").replace("德文", "DE")
        return lang_str


    def show_toast(self):
        """Show a temporary toast notification"""
        if hasattr(self, 'toast_win') and self.toast_win and self.toast_win.winfo_exists():
            self.toast_win.destroy()
            
        self.toast_win = tk.Toplevel(self.root)
        self.toast_win.overrideredirect(True)
        self.toast_win.attributes('-topmost', True)
        self.toast_win.configure(bg=self.colors['bg'], highlightthickness=1, highlightbackground=self.colors['fg'])
        
        if self.ui_lang == 'zh':
            msg = "💡 使用方法:\n\n1. 在任何地方选中文本\n2. 按 Cmd+C 复制\n3. 选中文本后，按住 Ctrl 键将鼠标移至圆上，并保持 Ctrl+鼠标左键点击以打开翻译选项\n\n(开启「鼠标跟随」后圆会自动靠近鼠标)"
        else:
            msg = "💡 How to Use:\n\n1. Select text anywhere\n2. Press Cmd+C to copy\n3. Hold Ctrl, move mouse to the widget, then Ctrl+Click to select translation options\n\n(Enable 'Mouse Follow' for easier access)"
            
        lbl = tk.Label(
            self.toast_win, 
            text=msg, 
            bg=self.colors['bg'], 
            fg=self.colors['fg'], 
            font=("System", 13), 
            padx=20, 
            pady=20, 
            justify="left"
        )
        lbl.pack()
        
        self.toast_win.update_idletasks()
        w = self.toast_win.winfo_width()
        h = self.toast_win.winfo_height()
        
        sw = self.toast_win.winfo_screenwidth()
        sh = self.toast_win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        
        self.toast_win.geometry(f"{w}x{h}+{x}+{y}")
        
        alpha = 0.0
        self.toast_win.attributes('-alpha', alpha)
        
        def fade_in():
            nonlocal alpha
            if not self.toast_win.winfo_exists(): return
            if alpha < 0.95:
                alpha += 0.05
                self.toast_win.attributes('-alpha', alpha)
                self.root.after(20, fade_in)
            else:
                self.root.after(8000, fade_out)
                
        def fade_out():
            nonlocal alpha
            if not self.toast_win.winfo_exists(): return
            if alpha > 0.0:
                alpha -= 0.05
                self.toast_win.attributes('-alpha', alpha)
                self.root.after(20, fade_out)
            else:
                self.toast_win.destroy()
                
        self.toast_win.bind("<Button-1>", lambda e: fade_out())
        lbl.bind("<Button-1>", lambda e: fade_out())
        
        fade_in()


    def show_add_lang_dialog(self):
        if hasattr(self, 'add_lang_win') and self.add_lang_win.winfo_exists():
            self.add_lang_win.lift()
            self.add_lang_win.focus_force()
            return
            
        self.add_lang_win = tk.Toplevel(self.root)
        self.add_lang_win.title("添加翻译语言 / Add Language")
        self.add_lang_win.configure(bg=self.colors['bg'], padx=30, pady=30)
        # On macOS, setting background of Toplevel directly might not cover everything perfectly without a main frame
        main_frame = tk.Frame(self.add_lang_win, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.add_lang_win.attributes('-topmost', True)
        
        # Center window
        w = 400
        h = 300
        sw = self.add_lang_win.winfo_screenwidth()
        sh = self.add_lang_win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.add_lang_win.geometry(f"{w}x{h}+{x}+{y}")
        
        # Variables
        self.custom_styles_dict = {}
        
        # Row 1: Source -> Target
        frame1 = tk.Frame(main_frame, bg=self.colors['bg'])
        frame1.pack(fill=tk.X, pady=(0, 15))
        
        source_entry = tk.Entry(frame1, width=10, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        source_entry.pack(side=tk.LEFT)
        
        tk.Label(frame1, text=" ➔ ", font=("Arial", 14), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT, padx=10)
        
        target_entry = tk.Entry(frame1, width=10, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        target_entry.pack(side=tk.LEFT)
        
        # Row 2: Default Style
        frame2 = tk.Frame(main_frame, bg=self.colors['bg'])
        frame2.pack(fill=tk.X, pady=(0, 15))
        tk.Label(frame2, text="默认风格 / Default Prompt:", font=("Arial", 12), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT)
        default_style_entry = tk.Entry(frame2, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        default_style_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Row 3: Styles
        frame3 = tk.Frame(main_frame, bg=self.colors['bg'])
        frame3.pack(fill=tk.X, pady=(0, 15))
        
        self.style_combo_var = tk.StringVar(value="默认")
        style_combo = tk.OptionMenu(frame3, self.style_combo_var, "默认")
        style_combo.config(bg=self.colors['button_bg'], fg='white', activebackground=self.colors.get('button_hover', self.colors['button_bg']), activeforeground='white', borderwidth=0, highlightthickness=0, width=8)
        style_combo.pack(side=tk.LEFT)
        
        tk.Label(frame3, text="语气风格:", font=("Arial", 12), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT, padx=(15, 5))
        
        style_name_entry = tk.Entry(frame3, width=8, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        style_name_entry.pack(side=tk.LEFT)
        style_name_entry.insert(0, "名称")
        
        style_prompt_entry = tk.Entry(frame3, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        style_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        style_prompt_entry.insert(0, "Prompt要求")
        
        tk.Label(frame3, text="↵", font=("Arial", 16), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT)
        
        def clear_placeholder(e, entry, text):
            if entry.get() == text:
                entry.delete(0, tk.END)
                
        style_name_entry.bind("<FocusIn>", lambda e: clear_placeholder(e, style_name_entry, "名称"))
        style_prompt_entry.bind("<FocusIn>", lambda e: clear_placeholder(e, style_prompt_entry, "Prompt要求"))
        
        
        
        def add_style():
            name = style_name_entry.get().strip()
            prompt = style_prompt_entry.get().strip()
            if not name or name == "名称" or not prompt or prompt == "Prompt要求":
                self.show_error_dialog("风格名称和Prompt不能为空！")
                return
            
            self.custom_styles_dict[name] = prompt
            
            # Update menu
            menu = style_combo["menu"]
            menu.delete(0, "end")
            menu.add_command(label="默认", command=lambda value="默认": self.style_combo_var.set(value))
            for k in self.custom_styles_dict.keys():
                menu.add_command(label=k, command=lambda value=k: self.style_combo_var.set(value))
                
            self.style_combo_var.set(name)
            style_name_entry.delete(0, tk.END)
            style_prompt_entry.delete(0, tk.END)
            
        # Bind Enter key to add_style instead of a button
        def on_enter_press(e):
            add_style()
        style_prompt_entry.bind("<Return>", on_enter_press)
        style_name_entry.bind("<Return>", on_enter_press)
        

        # Row 4: Save
        frame4 = tk.Frame(main_frame, bg=self.colors['bg'])
        frame4.pack(fill=tk.X, pady=(20, 0))
        
        def save_lang():
            src = source_entry.get().strip()
            tgt = target_entry.get().strip()
            def_style = default_style_entry.get().strip()
            
            if not src or not tgt:
                self.show_error_dialog("源语言和目标语言不能为空！")
                return
            if not def_style:
                self.show_error_dialog("默认风格不能为空！必须提供一个基础翻译指令。")
                return
                
            # Add to config
            if 'custom_langs' not in self.config:
                self.config['custom_langs'] = []
                
            lang_id = f"custom_{len(self.config['custom_langs']) + 1}"
            
            self.config['custom_langs'].append({
                "id": lang_id,
                "source": src,
                "target": tgt,
                "default_style": def_style,
                "styles": self.custom_styles_dict
            })
            
            save_config(self.config)
            
            # Tell main app to reload config and update menu
            self.send_command_to_main('reload_config')
            
            self.add_lang_win.destroy()
            
            rumps_msg = "自定义语言已保存！应用将自动刷新菜单。"
            self.show_error_dialog(rumps_msg, title="成功")

        save_btn = tk.Button(frame4, text="存储 / Save", command=save_lang, bg=self.colors['button_bg'], fg='white', borderwidth=0, font=("Arial", 13), cursor="hand2")
        # On macOS tkinter buttons are tricky to size with padding, so we can use a frame hack or just leave it
        
        save_btn.pack()
        
    def show_error_dialog(self, msg, title="错误"):
        err_win = tk.Toplevel(self.add_lang_win if hasattr(self, 'add_lang_win') and self.add_lang_win.winfo_exists() else self.root)
        err_win.title(title)
        err_win.attributes('-topmost', True)
        err_win.configure(bg=self.colors['bg'], padx=20, pady=20)
        tk.Label(err_win, text=msg, bg=self.colors['bg'], fg=self.colors['fg'], wraplength=250).pack(pady=(0,15))
        tk.Button(err_win, text="OK", command=err_win.destroy).pack()
        
        err_win.update_idletasks()
        w = err_win.winfo_width()
        h = err_win.winfo_height()
        sw = err_win.winfo_screenwidth()
        sh = err_win.winfo_screenheight()
        err_win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def send_command_to_main(self, cmd):
        """Send a menu command to the main.py tray application"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(('127.0.0.1', 50052))
            s.sendall(cmd.encode('utf-8'))
            s.close()
        except Exception as e:
            print(f"Failed to send command to main app: {e}")

    def _force_strict_topmost(self):
        """Use macOS native APIs to ensure windows stay above absolutely everything and cross spaces"""
        try:
            from AppKit import NSApp
            for window in NSApp.windows():
                # 1000 is NSScreenSaverWindowLevel (Highest reliable level)
                # 101 is NSPopUpMenuWindowLevel
                window.setLevel_(1000)
                
                # Collection Behavior Flags:
                # 1   (1 << 0) = NSWindowCollectionBehaviorCanJoinAllSpaces (Appears on all spaces)
                # 16  (1 << 4) = NSWindowCollectionBehaviorStationary (Unaffected by Expose)
                # 256 (1 << 8) = NSWindowCollectionBehaviorFullScreenAuxiliary (Can appear over fullscreen apps!)
                # 273 = 1 | 16 | 256
                window.setCollectionBehavior_(273) 
                
                # If this is the small widget window (not the main window which needs text input),
                # prevent it from becoming the key window so it doesn't steal focus from browsers
                # when right-clicked.
                if window.frame().size.width < 100:
                    # NSWindowStyleMaskNonactivatingPanel = 1 << 7
                    # This prevents the app from activating when the window is clicked
                    window.setStyleMask_(window.styleMask() | 128)
        except Exception as e:
            print(f"Notice: Could not set strict macOS topmost/spaces level: {e}")

    def _build_main_ui(self):
        main_frame = tk.Frame(self.main_win, padx=20, pady=20, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = tk.Label(title_frame, text=self.t['wait'], font=("Arial", 14, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'])
        self.title_label.pack(side=tk.LEFT)

        # Style selector variables
        self.style_var = tk.StringVar(value="默认" if self.ui_lang == 'zh' else "Default")
        self.style_options = ["默认" if self.ui_lang == 'zh' else "Default"]
        
        style_label = tk.Label(title_frame, text=self.t['style'], font=("Arial", 11), bg=self.colors['bg'], fg=self.colors['label_fg'])
        style_label.pack(side=tk.LEFT, padx=(20, 5))

        self.style_button = tk.Label(title_frame, textvariable=self.style_var, font=("Arial", 10), bg=self.colors['textbox_bg'], fg=self.colors['fg'], relief=tk.SOLID, borderwidth=1, padx=8, pady=4, cursor='hand2')
        self.style_button.pack(side=tk.LEFT)

        style_arrow = tk.Label(title_frame, text=" ▼", font=("Arial", 8), bg=self.colors['bg'], fg=self.colors['label_fg'])
        style_arrow.pack(side=tk.LEFT)

        # Font size selector
        font_sizes = [10, 12, 14, 16, 18, 20, 24]
        self.font_size_var = tk.IntVar(value=self.config['font_size'])

        font_size_label = tk.Label(title_frame, text=self.t['font'], font=("Arial", 11), bg=self.colors['bg'], fg=self.colors['label_fg'])
        font_size_label.pack(side=tk.LEFT, padx=(20, 5))

        self.font_size_button = tk.Label(title_frame, text=str(self.font_size_var.get()), font=("Arial", 10), bg=self.colors['textbox_bg'], fg=self.colors['fg'], relief=tk.SOLID, borderwidth=1, padx=8, pady=4, cursor='hand2')
        self.font_size_button.pack(side=tk.LEFT)

        font_size_arrow = tk.Label(title_frame, text=" ▼", font=("Arial", 8), bg=self.colors['bg'], fg=self.colors['label_fg'])
        font_size_arrow.pack(side=tk.LEFT)

        # Progress Label
        self.progress_label = tk.Label(main_frame, text="", font=("Arial", 10), bg=self.colors['bg'], fg=self.colors['button_bg'])
        self.progress_label.pack(pady=(0, 5))

        # Menus
        self.style_menu = tk.Menu(self.main_win, tearoff=0)
        self.font_size_menu = tk.Menu(self.main_win, tearoff=0)

        def show_style_menu(e):
            try:
                self.style_menu.post(e.x_root, e.y_root)
            finally:
                self.style_menu.grab_release()

        def show_font_menu(e):
            try:
                self.font_size_menu.post(e.x_root, e.y_root)
            finally:
                self.font_size_menu.grab_release()

        self.style_button.bind('<Button-1>', show_style_menu)
        style_arrow.bind('<Button-1>', show_style_menu)
        
        self.font_size_button.bind('<Button-1>', show_font_menu)
        font_size_arrow.bind('<Button-1>', show_font_menu)

        for size in font_sizes:
            self.font_size_menu.add_command(label=str(size), command=lambda s=size: self.select_font_size(s))

        orig_label = tk.Label(main_frame, text=self.t['orig'], font=("Arial", 11, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'], anchor='w')
        orig_label.pack(fill=tk.X, pady=(0, 5))

        initial_spacing = round(self.config['font_size'] * 0.309)
        self.orig_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Arial", self.config['font_size']), height=5, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'], spacing1=initial_spacing, spacing3=initial_spacing)
        self.orig_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        trans_label = tk.Label(main_frame, text=self.t['trans'], font=("Arial", 11, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'], anchor='w')
        trans_label.pack(fill=tk.X, pady=(0, 5))

        self.trans_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Arial", self.config['font_size']), height=5, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'], spacing1=initial_spacing, spacing3=initial_spacing)
        self.trans_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.status_label = tk.Label(main_frame, text=self.t['copied'], font=("Arial", 10), fg=self.colors['status_fg'], bg=self.colors['bg'])
        self.status_label.pack(pady=(5, 0))

    def select_font_size(self, size):
        self.font_size_var.set(size)
        self.font_size_button.config(text=str(size))
        spacing = round(size * 0.309)
        self.orig_text.config(font=("Arial", size), spacing1=spacing, spacing3=spacing)
        self.trans_text.config(font=("Arial", size), spacing1=spacing, spacing3=spacing)
        self.config['font_size'] = size
        save_config(self.config)

    def update_style_menu(self):
        self.style_menu.delete(0, tk.END)
        self.style_options = get_style_options(self.current_source_lang, self.current_target_lang, self.config)
        self.style_var.set(self.style_options[0])
        
        for option in self.style_options:
            self.style_menu.add_command(label=option, command=lambda s=option: self.select_style(s))

    def select_style(self, style):
        self.style_var.set(style)
        self.on_style_change()

    def on_style_change(self):
        selected_style = self.style_var.get()
        if "默认" in selected_style or "Default" in selected_style:
            return

        self.progress_label.config(text=self.t['re_trans'])
        self.style_button.config(cursor='watch')
        self.main_win.update()

        def translate_with_style():
            try:
                style_instruction = f"请使用{selected_style}风格进行翻译。"
                
                # Check if it's a custom language style
                direction = f"{self.current_source_lang} → {self.current_target_lang}"
                if 'custom_langs' in self.config:
                    for cl in self.config['custom_langs']:
                        if f"{cl['source']} → {cl['target']}" == direction:
                            if selected_style in cl.get('styles', {}):
                                style_instruction = cl['styles'][selected_style]
                            break

                prompt = f"请将以下完整文本从{self.current_source_lang}翻译成{self.current_target_lang}。\n\n{style_instruction}\n\n重要要求：\n1. 翻译所有内容，包括所有行和段落\n2. 保持原文的换行和格式\n3. 只返回翻译结果，不要添加任何解释或说明\n\n原文：\n{self.current_original}\n\n译文："
                
                response = self.client.models.generate_content(
                    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
                    contents=prompt
                )
                new_translation = response.text.strip()

                def update_ui():
                    self.trans_text.config(state=tk.NORMAL)
                    self.trans_text.delete(1.0, tk.END)
                    self.trans_text.insert(tk.END, new_translation)
                    self.trans_text.config(state=tk.DISABLED)
                    pyperclip.copy(new_translation)
                    self.progress_label.config(text="")
                    self.status_label.config(text=self.t['copied'])
                    self.style_button.config(cursor='hand2')

                self.main_win.after(0, update_ui)
            except Exception as e:
                def show_error():
                    self.progress_label.config(text=self.t['trans_fail'])
                    self.style_button.config(cursor='hand2')
                self.main_win.after(0, show_error)

        if self.client:
            threading.Thread(target=translate_with_style, daemon=True).start()
        else:
            self.progress_label.config(text="❌ VertexAI Error")
            self.style_button.config(cursor='hand2')

    def collapse_to_widget(self):
        """Hide main window, show widget"""
        if self.main_win.winfo_viewable():
            geom = self.main_win.geometry()
            try:
                w, h = map(int, geom.split('+')[0].split('x'))
                self.config['window_width'] = w
                self.config['window_height'] = h
                save_config(self.config)
            except:
                pass
            
        self.main_win.withdraw()
        self.widget.deiconify()
        self.widget.lift()
        self.root.update_idletasks()
        self.root.after(50, self._force_strict_topmost)

    def expand_to_main(self):
        """Hide widget, show main window"""
        self.widget.withdraw()
        
        w = self.config['window_width']
        h = self.config['window_height']
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.main_win.geometry(f"{w}x{h}+{x}+{y}")
        
        self.main_win.deiconify()
        self.main_win.lift()
        self.main_win.focus_force()
        self.root.update_idletasks()
        self.root.after(50, self._force_strict_topmost)
        
        try:
            import subprocess
            subprocess.run(['osascript', '-e', 'tell application "System Events" to set frontmost of the first process whose unix id is ' + str(os.getpid()) + ' to true'], capture_output=True)
        except:
            pass

    def update_content(self, payload):
        """Update UI based on translation status payload"""
        status = payload.get('status', 'complete')
        
        if status == 'loading':
            self.current_original = payload.get('original', '')
            self.current_source_lang = payload.get('source_lang', '')
            self.current_target_lang = payload.get('target_lang', '')

            title = f"{self.t['translating']} {self._format_lang(self.current_source_lang)} → {self._format_lang(self.current_target_lang)}..."
            self.title_label.config(text=title)
            self.update_style_menu()
            
            self.orig_text.config(state=tk.NORMAL)
            self.orig_text.delete(1.0, tk.END)
            self.orig_text.insert(tk.END, self.current_original)
            self.orig_text.config(state=tk.DISABLED)

            self.trans_text.config(state=tk.NORMAL)
            self.trans_text.delete(1.0, tk.END)
            self.trans_text.insert(tk.END, self.t['call_api'])
            self.trans_text.config(state=tk.DISABLED)
            
            self.progress_label.config(text="")
            self.status_label.config(text=self.t['wait'], fg=self.colors['label_fg'])
            
            self.expand_to_main()
            
        elif status == 'complete':
            translation = payload.get('translation', '')
            
            if 'source_lang' in payload:
                self.current_source_lang = payload.get('source_lang', '')
                self.current_target_lang = payload.get('target_lang', '')
                self.current_original = payload.get('original', '')
                self.update_style_menu()

            title = f"{self.t['trans_done']} {self._format_lang(self.current_source_lang)} → {self._format_lang(self.current_target_lang)}"
            self.title_label.config(text=title)
            
            self.orig_text.config(state=tk.NORMAL)
            self.orig_text.delete(1.0, tk.END)
            self.orig_text.insert(tk.END, self.current_original)
            self.orig_text.config(state=tk.DISABLED)

            self.trans_text.config(state=tk.NORMAL)
            self.trans_text.delete(1.0, tk.END)
            self.trans_text.insert(tk.END, translation)
            self.trans_text.config(state=tk.DISABLED)

            self.status_label.config(text=self.t['copied'], fg=self.colors['status_fg'])
            
            if not self.main_win.winfo_viewable():
                self.expand_to_main()
                
        elif status == 'error':
            error_msg = payload.get('error_msg', 'Unknown error')
            self.title_label.config(text=self.t['trans_fail'])
            self.trans_text.config(state=tk.NORMAL)
            self.trans_text.delete(1.0, tk.END)
            self.trans_text.insert(tk.END, f"{self.t['trans_fail']}:\n{error_msg}")
            self.trans_text.config(state=tk.DISABLED)
            self.status_label.config(text=self.t['err_net'], fg='red')
            
            if not self.main_win.winfo_viewable():
                self.expand_to_main()

    def _start_server(self):
        """Socket server to receive payloads from main.py"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('127.0.0.1', PORT))
            server.listen(5)
            print(f"UI Daemon listening on port {PORT}")
            while True:
                conn, addr = server.accept()
                data = conn.recv(65535).decode('utf-8')
                if data:
                    try:
                        payload = json.loads(data)
                        if payload.get('action') == 'quit':
                            def force_quit():
                                self.root.quit()
                                self.root.destroy()
                                import os
                                os._exit(0)
                            self.root.after(0, force_quit)
                            break
                        elif payload.get('action') == 'show_how_to_use':
                            self.show_toast()
                        elif payload.get('action') == 'show_add_lang_dialog':
                            self.root.after(0, self.show_add_lang_dialog)
                        elif payload.get('action') == 'reload_ui_config':
                            self.config = load_config()
                            # NOTE: To fully refresh the context menu dynamically requires a bit more logic,
                            # For simplicity, telling the user to restart or wait for daemon refresh is okay,
                            # but we can just quit and let main restart us if needed, or we just ignore for now and require app restart.
                        elif payload.get('action') == 'toggle_mouse_follow':
                            self.mouse_follow = payload.get('state', False)
                            self.config['mouse_follow'] = self.mouse_follow
                            try:
                                self.mouse_follow_var.set(self.mouse_follow)
                            except AttributeError:
                                pass
                        else:
                            # Important: Schedule update_content on the main Tkinter thread
                            self.root.after(0, lambda p=payload: self.update_content(p))
                    except json.JSONDecodeError as e:
                        print(f"Invalid payload: {e}")
                conn.close()
        except Exception as e:
            print(f"UI Daemon server error: {e}")
        finally:
            server.close()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TranslatorUI()
    app.run()
