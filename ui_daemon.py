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

def get_style_options(source_lang, target_lang, config=None):
    direction = f"{source_lang} → {target_lang}"
    
    # Check custom langs first
    if config and 'custom_langs' in config:
        for cl in config['custom_langs']:
            if f"{cl['source']} → {cl['target']}" == direction:
                styles = ["默认"]
                if 'styles' in cl and cl['styles']:
                    styles.extend(list(cl['styles'].keys()))
                return styles
                
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
                'rescue_widget': '找回悬浮',
                'auto_zh': '自动检测 → 中文',
                'auto_de': '自动检测 → 德文',
                'auto_en': '自动检测 → 英文',
                'add_lang': '➕ 添加翻译语言',
                'remove_lang': '➖ 移除翻译语言',
                'zh_de': '中文 → 德文',
                'de_zh': '德文 → 中文',
                'zh_en': '中文 → 英文',
                'en_zh': '英文 → 中文',
                'auth': 'Auth 刷新授权',
                'ui_zh': '界面中文',
                'ui_en': '界面英文',
                'local_ai': '本地 AI',
                'mouse_follow': '鼠标跟随',
                'how_to_use': '使用方法',
                'restart': '重启',
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
                'rescue_widget': 'Show Widget',
                'auto_zh': 'Auto → ZH',
                'auto_de': 'Auto → DE',
                'auto_en': 'Auto → EN',
                'add_lang': '➕ Add Language',
                'remove_lang': '➖ Remove Language',
                'zh_de': 'ZH → DE',
                'de_zh': 'DE → ZH',
                'zh_en': 'ZH → EN',
                'en_zh': 'EN → ZH',
                'auth': 'Auth Refresh',
                'ui_zh': 'UI: Chinese',
                'ui_en': 'UI: English',
                'local_ai': 'Local AI',
                'mouse_follow': 'Mouse Follow',
                'how_to_use': 'How to Use',
                'restart': 'Restart',
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
        self._rebuild_context_menu()
        self._context_menu_open = False

        def show_context_menu(event):
            self._context_menu_open = True
            try:
                self.context_menu.post(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()
                # Use a slight delay to allow menu clicks to process before unsetting the flag
                self.root.after(200, lambda: setattr(self, '_context_menu_open', False))

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
            from pynput import keyboard, mouse
            def on_press(key):
                if key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = True
            def on_release(key):
                if key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    self.ctrl_pressed = False
            self.kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.kb_listener.start()
            
            def on_click(x, y, button, pressed):
                if pressed and getattr(self, 'mouse_follow', True) and not getattr(self.main_win, 'winfo_viewable', lambda: False)():
                    # 强行解除可能的拖拽卡死状态
                    self._is_dragging = False
                    
                    # 只有在没有打开右键菜单的时候，才执行全局吸附，防止点击菜单项被中断
                    if getattr(self, '_context_menu_open', False):
                        return
                    
                    # 当用户在任意地方点击时，立刻强制悬浮圆吸附过来
                    def snap_to_cursor():
                        if self.main_win.winfo_viewable() or getattr(self, '_context_menu_open', False): return
                        new_x = int(x) + 10
                        new_y = int(y) + 10
                        screen_w = self.root.winfo_screenwidth()
                        screen_h = self.root.winfo_screenheight()
                        if new_x + 60 > screen_w: new_x = int(x) - 70
                        if new_y + 65 > screen_h: new_y = int(y) - 75
                        self.widget.geometry(f"+{new_x}+{new_y}")
                        
                    self.root.after(0, snap_to_cursor)

            self.mouse_listener = mouse.Listener(on_click=on_click)
            self.mouse_listener.start()
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
                # Forcefully ensure it's not withdrawn or iconified
                if self.widget.state() != 'normal':
                    self.widget.deiconify()
                
                # Re-apply topmost attribute
                self.widget.attributes('-topmost', 1)
                self.widget.lift()
                
                # Check if it's accidentally off-screen and rescue it
                screen_w = self.root.winfo_screenwidth()
                screen_h = self.root.winfo_screenheight()
                wx = self.widget.winfo_x()
                wy = self.widget.winfo_y()
                
                # If it's completely out of bounds (more than 100px off screen), reset to center
                if wx < -100 or wy < -100 or wx > screen_w or wy > screen_h:
                    print(">>> Watchdog: Widget went off-screen, rescuing to center.")
                    self.widget.geometry(f"+{screen_w//2}+{screen_h//2}")
                    
                # Re-assert native macOS topmost level gently
                self._force_strict_topmost()
            except Exception as e:
                print(f"Watchdog error: {e}")
        
        # Run this check every 1000ms (1 second) for more aggressive recovery
        self.root.after(1000, self._start_visibility_watchdog)

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
            

        if self.ui_lang == 'zh':
            title_text = "添加翻译语言"
            def_style_text = "默认风格:"
            tone_text = "语气风格:"
            name_placeholder = "名称"
            prompt_placeholder = "Prompt要求"
            hint_text = "(输入名称和Prompt后按回车键添加风格)"
            err_empty = "源语言和目标语言不能为空！"
            err_style_empty = "默认风格不能为空！必须提供一个基础翻译指令。"
            err_name_prompt = "风格名称和Prompt不能为空！"
            success_msg = "自定义语言已保存！"
            default_text = "默认"
        else:
            title_text = "Add Language"
            def_style_text = "Default Prompt:"
            tone_text = "Style:"
            name_placeholder = "Name"
            prompt_placeholder = "Prompt"
            hint_text = "(Press Enter after inputting Name and Prompt to add)"
            err_empty = "Source and Target languages cannot be empty!"
            err_style_empty = "Default style cannot be empty!"
            err_name_prompt = "Style name and Prompt cannot be empty!"
            success_msg = "Custom language saved!"
            default_text = "Default"
        self.add_lang_win = tk.Toplevel(self.root)
        self.add_lang_win.title(title_text)
        self.add_lang_win.configure(bg=self.colors['bg'], padx=30, pady=30)
        # On macOS, setting background of Toplevel directly might not cover everything perfectly without a main frame
        main_frame = tk.Frame(self.add_lang_win, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.add_lang_win.attributes('-topmost', True)
        
        # Center window
        w = self.config.get('add_lang_w', 400)
        h = self.config.get('add_lang_h', 300)
        sw = self.add_lang_win.winfo_screenwidth()
        sh = self.add_lang_win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.add_lang_win.geometry(f"{w}x{h}+{x}+{y}")
        
        def save_dialog_size(e):
            if hasattr(self, 'add_lang_win') and self.add_lang_win.winfo_exists():
                try:
                    self.config['add_lang_w'] = self.add_lang_win.winfo_width()
                    self.config['add_lang_h'] = self.add_lang_win.winfo_height()
                except: pass
        self.add_lang_win.bind("<Configure>", save_dialog_size)

        
        # Variables
        def on_close():
            try:
                self.config['add_lang_w'] = self.add_lang_win.winfo_width()
                self.config['add_lang_h'] = self.add_lang_win.winfo_height()
                save_config(self.config)
            except: pass
            self.add_lang_win.destroy()
            
        self.add_lang_win.protocol("WM_DELETE_WINDOW", on_close)

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
        tk.Label(frame2, text=def_style_text, font=("Arial", 12), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT)
        default_style_entry = tk.Entry(frame2, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        default_style_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Row 3: Styles
        frame3 = tk.Frame(main_frame, bg=self.colors['bg'])
        frame3.pack(fill=tk.X, pady=(0, 15))
        
        self.style_combo_var = tk.StringVar(value=default_text)
        style_combo = tk.OptionMenu(frame3, self.style_combo_var, default_text)
        style_combo.config(bg=self.colors['button_bg'], fg='white', activebackground=self.colors.get('button_hover', self.colors['button_bg']), activeforeground='white', borderwidth=0, highlightthickness=0, width=8)
        style_combo.pack(side=tk.LEFT)
        
        tk.Label(frame3, text=tone_text, font=("Arial", 12), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT, padx=(15, 5))
        
        style_name_entry = tk.Entry(frame3, width=8, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        style_name_entry.pack(side=tk.LEFT)
        style_name_entry.insert(0, name_placeholder)
        
        style_prompt_entry = tk.Entry(frame3, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'])
        style_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        style_prompt_entry.insert(0, prompt_placeholder)
        
        tk.Label(frame3, text="↵", font=("Arial", 16), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(side=tk.LEFT)
        
        def clear_placeholder(e, entry, text):
            if entry.get() == text:
                entry.delete(0, tk.END)
                
        style_name_entry.bind("<FocusIn>", lambda e: clear_placeholder(e, style_name_entry, name_placeholder))
        style_prompt_entry.bind("<FocusIn>", lambda e: clear_placeholder(e, style_prompt_entry, prompt_placeholder))
        
        
        
        def add_style():
            name = style_name_entry.get().strip()
            prompt = style_prompt_entry.get().strip()
            if not name or name == name_placeholder or not prompt or prompt == prompt_placeholder:
                self.show_error_dialog(err_name_prompt)
                return
            
            self.custom_styles_dict[name] = prompt
            
            # Update menu
            menu = style_combo["menu"]
            menu.delete(0, "end")
            menu.add_command(label=default_text, command=lambda value=default_text: self.style_combo_var.set(value))
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
                self.show_error_dialog(err_empty)
                return
            if not def_style:
                self.show_error_dialog(err_style_empty)
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
            
            self.show_error_dialog(success_msg, title="Success" if self.ui_lang == "en" else "成功")

        # Use Label for custom button styling on macOS with floppy disk emoji
        save_btn = tk.Label(frame4, text="💾", font=("Arial", 36), bg=self.colors['bg'], cursor="hand2")
        save_btn.pack(side=tk.RIGHT)
        save_btn.bind("<Button-1>", lambda e: save_lang())
        

    def show_remove_lang_dialog(self):
        if 'custom_langs' not in self.config or not self.config['custom_langs']:
            self.show_error_dialog("当前没有自定义语言可移除。" if self.ui_lang == 'zh' else "No custom languages to remove.", title="提示" if self.ui_lang == 'zh' else "Info")
            return
            
        rem_win = tk.Toplevel(self.root)
        rem_win.title("移除翻译语言 / Remove Language")
        rem_win.configure(bg=self.colors['bg'], padx=30, pady=30)
        rem_win.attributes('-topmost', True)
        
        w = 350
        h = 200
        sw = rem_win.winfo_screenwidth()
        sh = rem_win.winfo_screenheight()
        rem_win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        
        tk.Label(rem_win, text="选择要移除的语言组:" if self.ui_lang == 'zh' else "Select language pair to remove:", font=("Arial", 12), bg=self.colors['bg'], fg=self.colors['label_fg']).pack(pady=(0, 15))
        
        combo_var = tk.StringVar()
        options = {}
        for cl in self.config['custom_langs']:
            label = f"{cl['source']} → {cl['target']}"
            options[label] = cl['id']
            
        first_label = list(options.keys())[0]
        combo_var.set(first_label)
        
        combo = tk.OptionMenu(rem_win, combo_var, *options.keys())
        combo.config(bg=self.colors['button_bg'], fg='white', borderwidth=0, highlightthickness=0)
        combo.pack(pady=(0, 20))
        
        def do_remove():
            selected_label = combo_var.get()
            selected_id = options[selected_label]
            self.config['custom_langs'] = [cl for cl in self.config['custom_langs'] if cl['id'] != selected_id]
            save_config(self.config)
            self.send_command_to_main('reload_config')
            rem_win.destroy()
            self.show_error_dialog(f"已移除: {selected_label}" if self.ui_lang == 'zh' else f"Removed: {selected_label}", title="成功" if self.ui_lang == 'zh' else "Success")
            
        btn = tk.Label(rem_win, text="🗑️", font=("Arial", 28), bg=self.colors['bg'], cursor="hand2")
        btn.pack()
        btn.bind("<Button-1>", lambda e: do_remove())

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

    def rescue_widget(self):
        """强制显示并居中悬浮窗"""
        try:
            widget_size = 60
            x = (self.root.winfo_screenwidth() - widget_size) // 2
            y = (self.root.winfo_screenheight() - widget_size) // 2
            
            self.widget.geometry(f"{widget_size}x{widget_size}+{x}+{y}")
            self.widget.deiconify()
            self.widget.lift()
            self.widget.attributes('-topmost', True)
            self._force_strict_topmost()
            
            # Save the new position
            self.config['widget_x'] = x
            self.config['widget_y'] = y
            save_config(self.config)
            
            print(">>> Widget rescued and centered.")
        except Exception as e:
            print(f"Failed to rescue widget: {e}")

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


    def _rebuild_context_menu(self):
        if hasattr(self, 'context_menu'):
            self.context_menu.destroy()
            
        self.context_menu = tk.Menu(self.widget, tearoff=0)
        self.context_menu.add_command(label=self.t['auto_zh'], command=lambda: self.send_command_to_main('auto_zh'))
        self.context_menu.add_command(label=self.t['auto_de'], command=lambda: self.send_command_to_main('auto_de'))
        self.context_menu.add_command(label=self.t['auto_en'], command=lambda: self.send_command_to_main('auto_en'))
        self.context_menu.add_command(label=self.t['zh_de'], command=lambda: self.send_command_to_main('zh_de'))
        self.context_menu.add_command(label=self.t['de_zh'], command=lambda: self.send_command_to_main('de_zh'))
        self.context_menu.add_command(label=self.t['zh_en'], command=lambda: self.send_command_to_main('zh_en'))
        self.context_menu.add_command(label=self.t['en_zh'], command=lambda: self.send_command_to_main('en_zh'))
        
        if 'custom_langs' in self.config and len(self.config['custom_langs']) > 0:
            self.context_menu.add_separator()
            for cl in self.config['custom_langs']:
                label_text = f"• {cl['source']} → {cl['target']}"
                self.context_menu.add_command(label=label_text, command=lambda cid=cl['id']: self.send_command_to_main(f'custom_translate_{cid}'))

    def _change_ollama_model(self, name):
        self.ollama_model_var.set(name)
        self.config['ollama_model'] = name
        save_config(self.config)
        self.retranslate(trigger='model')

    def _update_backend_label(self):
        if not hasattr(self, 'backend_frame'): return
        
        for widget in self.backend_frame.winfo_children():
            widget.destroy()

        use_local = self.config.get('use_local_ai', False)
        if use_local:
            import urllib.request
            host = os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
            model_list = []
            try:
                req = urllib.request.Request(f"{host}/api/tags")
                with urllib.request.urlopen(req, timeout=1) as response:
                    data = json.loads(response.read().decode())
                    model_list = [m['name'] for m in data.get('models', [])]
            except Exception:
                pass
                
            current_model = self.config.get('ollama_model', os.getenv('OLLAMA_MODEL', 'qwen2.5:0.5b'))
            if not model_list:
                model_list = [current_model]
                
            lbl = tk.Label(self.backend_frame, text="ollama", font=("Arial", 10, "bold"), bg=self.colors['bg'], fg=self.colors['button_bg'])
            lbl.pack(side=tk.LEFT, padx=(0, 5))
            
            self.ollama_model_var = tk.StringVar(value=current_model)
            model_btn = tk.Label(self.backend_frame, textvariable=self.ollama_model_var, font=("Arial", 10), bg=self.colors['textbox_bg'], fg=self.colors['fg'], relief=tk.SOLID, borderwidth=1, padx=8, pady=2, cursor='hand2')
            model_btn.pack(side=tk.LEFT)
            
            model_arrow = tk.Label(self.backend_frame, text=" ▼", font=("Arial", 8), bg=self.colors['bg'], fg=self.colors['label_fg'])
            model_arrow.pack(side=tk.LEFT)
            
            model_menu = tk.Menu(self.main_win, tearoff=0)
            for m in model_list:
                model_menu.add_command(label=m, command=lambda name=m: self._change_ollama_model(name))
                
            def show_model_menu(e):
                try:
                    model_menu.post(e.x_root, e.y_root)
                finally:
                    model_menu.grab_release()
                    
            model_btn.bind('<Button-1>', show_model_menu)
            model_arrow.bind('<Button-1>', show_model_menu)
        else:
            model = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')
            use_vertex = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'False').lower() in ('true', '1', 't', 'yes')
            if use_vertex:
                backend = f"vertexai ({model})"
            else:
                backend = f"genai ({model})"
            lbl = tk.Label(self.backend_frame, text=backend, font=("Arial", 10, "bold"), bg=self.colors['bg'], fg=self.colors['button_bg'])
            lbl.pack(side=tk.RIGHT)

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
        
        self.backend_frame = tk.Frame(title_frame, bg=self.colors['bg'])
        self.backend_frame.pack(side=tk.RIGHT)
        self._update_backend_label()

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
        self.retranslate(trigger='style')

    def retranslate(self, trigger='style'):
        if not hasattr(self, 'current_original') or not self.current_original:
            return

        selected_style = self.style_var.get()
        if trigger == 'style' and ("默认" in selected_style or "Default" in selected_style):
            return

        self.progress_label.config(text=self.t['re_trans'])
        self.style_button.config(cursor='watch')
        self.main_win.update()

        def translate_with_style():
            try:
                style_instruction = ""
                if "默认" not in selected_style and "Default" not in selected_style:
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

                new_translation = ""
                is_first = True

                if self.config.get('use_local_ai', False):
                    import requests
                    host = os.getenv('OLLAMA_HOST', 'http://localhost:11434').rstrip('/')
                    model = self.config.get('ollama_model') or os.getenv('OLLAMA_MODEL', 'qwen2.5:1.5b')

                    payload = {
                        "model": model,
                        "prompt": prompt,
                        "stream": True
                    }

                    try:
                        response = requests.post(f"{host}/api/generate", json=payload, stream=True)
                    except requests.exceptions.ConnectionError:
                        raise Exception("无法连接到 Ollama 服务，请在 terminal 里运行 `ollama serve` 来启动服务。")

                    if response.status_code != 200:
                        error_msg = f"Ollama Error (HTTP {response.status_code})"
                        try:
                            error_json = response.json()
                            if 'error' in error_json:
                                error_msg += f": {error_json['error']}"
                        except:
                            error_msg += f": {response.text}"
                        raise Exception(error_msg)

                    for line in response.iter_lines():
                        if line:
                            data = json.loads(line)
                            if "response" in data:
                                chunk = data["response"]
                                new_translation += chunk

                                def update_chunk(c=chunk, first=is_first):
                                    self.trans_text.config(state=tk.NORMAL)
                                    if first:
                                        self.trans_text.delete(1.0, tk.END)
                                    self.trans_text.insert(tk.END, c)
                                    self.trans_text.see(tk.END)
                                    self.trans_text.config(state=tk.DISABLED)

                                self.main_win.after(0, update_chunk)
                                is_first = False
                else:
                    response_stream = self.client.models.generate_content_stream(
                        model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
                        contents=prompt
                    )

                    for chunk in response_stream:
                        if chunk.text:
                            new_translation += chunk.text

                            def update_chunk(c=chunk.text, first=is_first):
                                self.trans_text.config(state=tk.NORMAL)
                                if first:
                                    self.trans_text.delete(1.0, tk.END)
                                self.trans_text.insert(tk.END, c)
                                self.trans_text.see(tk.END)
                                self.trans_text.config(state=tk.DISABLED)

                            self.main_win.after(0, update_chunk)
                            is_first = False

                new_translation = new_translation.strip()

                def update_ui():
                    self.trans_text.config(state=tk.NORMAL)
                    # We already appended everything, but replace it cleanly at the end
                    self.trans_text.delete(1.0, tk.END)
                    self.trans_text.insert(tk.END, new_translation)
                    self.trans_text.config(state=tk.DISABLED)
                    pyperclip.copy(new_translation)
                    self.progress_label.config(text="")
                    self.status_label.config(text=self.t['copied'])
                    self.style_button.config(cursor='hand2')

                self.main_win.after(0, update_ui)
            except Exception as e:
                def show_error(err=str(e)):
                    self.progress_label.config(text=f"{self.t['trans_fail']}: {err[:30]}...")
                    self.style_button.config(cursor='hand2')
                self.main_win.after(0, show_error)

        if self.client or self.config.get('use_local_ai', False):
            threading.Thread(target=translate_with_style, daemon=True).start()
        else:
            self.progress_label.config(text="❌ AI Client Error")
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
        self.widget.attributes('-topmost', 1)
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
            
            model_name = payload.get('model_name')
            if model_name:
                if self.ui_lang == 'zh':
                    api_msg = f"⏳ {model_name} 正在为您翻译，请稍候..."
                else:
                    api_msg = f"⏳ {model_name} is translating for you, please wait..."
            else:
                api_msg = self.t['call_api']
                
            self.trans_text.insert(tk.END, api_msg)
            self.trans_text.config(state=tk.DISABLED)
            
            self.progress_label.config(text="")
            self.status_label.config(text=self.t['wait'], fg=self.colors['label_fg'])
            
            self.expand_to_main()
            
        elif status == 'streaming':
            chunk = payload.get('chunk', '')
            is_first = payload.get('is_first', False)
            
            self.trans_text.config(state=tk.NORMAL)
            if is_first:
                self.trans_text.delete(1.0, tk.END)
            self.trans_text.insert(tk.END, chunk)
            self.trans_text.see(tk.END)
            self.trans_text.config(state=tk.DISABLED)
            
            self.status_label.config(text=self.t['wait'], fg=self.colors['label_fg'])
            
            if not self.main_win.winfo_viewable():
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
                        elif payload.get('action') == 'show_remove_lang_dialog':
                            self.root.after(0, self.show_remove_lang_dialog)
                        elif payload.get('action') == 'reload_ui_config':
                            self.config = load_config()
                            self._rebuild_context_menu()
                        elif payload.get('action') == 'rescue_widget':
                            self.root.after(0, self.rescue_widget)
                        elif payload.get('action') == 'toggle_mouse_follow':
                            self.mouse_follow = payload.get('state', False)
                            self.config['mouse_follow'] = self.mouse_follow
                            try:
                                self.mouse_follow_var.set(self.mouse_follow)
                            except AttributeError:
                                pass
                        elif payload.get('action') == 'toggle_local_ai':
                            self.config['use_local_ai'] = payload.get('state', False)
                            try:
                                self.local_ai_var.set(self.config['use_local_ai'])
                            except AttributeError:
                                pass
                            self.root.after(0, self._update_backend_label)
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
