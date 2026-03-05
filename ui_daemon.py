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
    styles = {
        "中文 → 德文": ["默认（duzen口吻）", "轻松（duzen口吻）", "官方（敬语口吻）", "随和（duzen口吻）", "非正式（duzen口吻）", "一般（duzen口吻）"],
        "德文 → 中文": ["默认", "上海海派腔调", "大陆北方腔调", "大陆南方腔调", "台湾腔", "港台腔"],
        "中文 → 英文": ["默认", "美国普通式", "美国牛仔式", "英国普通式", "英国绅士口吻"],
        "英文 → 中文": ["默认", "上海海派腔调", "大陆北方腔调", "大陆南方腔调", "台湾腔", "港台腔"]
    }
    return styles.get(direction, ["默认"])

class TranslatorUI:
    def __init__(self):
        self.config = load_config()
        self.colors = get_theme_colors()
        
        try:
            self.client = genai.Client(vertexai=True, project=os.getenv('GOOGLE_CLOUD_PROJECT'), location=os.getenv('GOOGLE_CLOUD_LOCATION'))
        except Exception as e:
            print(f"Failed to init VertexAI: {e}")
            self.client = None

        # Base invisible root
        self.root = tk.Tk()
        self.root.withdraw()
        
        # ---------------- WIDGET WINDOW (Floating Icon) ----------------
        self.widget = tk.Toplevel(self.root)
        self.widget.attributes('-topmost', True)
        self.widget.overrideredirect(True) # No window decorations
        self.widget.configure(bg=self.colors['button_bg'])
        
        # Place in saved position or bottom right corner
        self.widget_x = self.config.get('widget_x', self.root.winfo_screenwidth() - 80)
        self.widget_y = self.config.get('widget_y', self.root.winfo_screenheight() - 100)
        self.widget.geometry(f"50x50+{self.widget_x}+{self.widget_y}")
        
        self.widget_lbl = tk.Label(self.widget, text="🌍", font=("Arial", 24), bg=self.colors['button_bg'], fg='white', cursor="hand2")
        self.widget_lbl.pack(expand=True, fill='both')
        
        # Dragging logic variables
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False

        def on_drag_start(event):
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            self._is_dragging = False

        def on_drag_motion(event):
            # Calculate new position
            x = self.widget.winfo_x() - self._drag_start_x + event.x
            y = self.widget.winfo_y() - self._drag_start_y + event.y
            self.widget.geometry(f"+{x}+{y}")
            self._is_dragging = True

        def on_drag_release(event):
            if not self._is_dragging:
                # It was just a click, so expand
                self.expand_to_main()
            else:
                # It was a drag, save new position
                self.config['widget_x'] = self.widget.winfo_x()
                self.config['widget_y'] = self.widget.winfo_y()
                save_config(self.config)

        self.widget_lbl.bind("<ButtonPress-1>", on_drag_start)
        self.widget_lbl.bind("<B1-Motion>", on_drag_motion)
        self.widget_lbl.bind("<ButtonRelease-1>", on_drag_release)

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

    def _force_strict_topmost(self):
        """Use macOS native APIs to ensure windows stay above absolutely everything and cross spaces"""
        try:
            from AppKit import NSApp
            for window in NSApp.windows():
                # 101 is NSPopUpMenuWindowLevel
                window.setLevel_(101)
                
                # Collection Behavior:
                # 1 = NSWindowCollectionBehaviorCanJoinAllSpaces (Appears on all spaces)
                # 16 = NSWindowCollectionBehaviorStationary (Unaffected by Expose/Mission Control)
                # 17 = 1 | 16
                window.setCollectionBehavior_(17) 
        except Exception as e:
            print(f"Notice: Could not set strict macOS topmost/spaces level: {e}")

    def _build_main_ui(self):
        main_frame = tk.Frame(self.main_win, padx=20, pady=20, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = tk.Label(title_frame, text="等待翻译...", font=("Arial", 14, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'])
        self.title_label.pack(side=tk.LEFT)

        # Style selector variables
        self.style_var = tk.StringVar(value="默认")
        self.style_options = ["默认"] # Will be updated dynamically
        
        style_label = tk.Label(title_frame, text="风格:", font=("Arial", 11), bg=self.colors['bg'], fg=self.colors['label_fg'])
        style_label.pack(side=tk.LEFT, padx=(20, 5))

        self.style_button = tk.Label(title_frame, textvariable=self.style_var, font=("Arial", 10), bg=self.colors['textbox_bg'], fg=self.colors['fg'], relief=tk.SOLID, borderwidth=1, padx=8, pady=4, cursor='hand2')
        self.style_button.pack(side=tk.LEFT)

        style_arrow = tk.Label(title_frame, text=" ▼", font=("Arial", 8), bg=self.colors['bg'], fg=self.colors['label_fg'])
        style_arrow.pack(side=tk.LEFT)

        # Font size selector
        font_sizes = [10, 12, 14, 16, 18, 20, 24]
        self.font_size_var = tk.IntVar(value=self.config['font_size'])

        font_size_label = tk.Label(title_frame, text="字体:", font=("Arial", 11), bg=self.colors['bg'], fg=self.colors['label_fg'])
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

        orig_label = tk.Label(main_frame, text="原文:", font=("Arial", 11, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'], anchor='w')
        orig_label.pack(fill=tk.X, pady=(0, 5))

        initial_spacing = round(self.config['font_size'] * 0.309)
        self.orig_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Arial", self.config['font_size']), height=5, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'], spacing1=initial_spacing, spacing3=initial_spacing)
        self.orig_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        trans_label = tk.Label(main_frame, text="译文:", font=("Arial", 11, "bold"), bg=self.colors['bg'], fg=self.colors['label_fg'], anchor='w')
        trans_label.pack(fill=tk.X, pady=(0, 5))

        self.trans_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, font=("Arial", self.config['font_size']), height=5, bg=self.colors['textbox_bg'], fg=self.colors['fg'], insertbackground=self.colors['fg'], spacing1=initial_spacing, spacing3=initial_spacing)
        self.trans_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        self.status_label = tk.Label(main_frame, text="✓ 译文已复制 (按 Esc 收起)", font=("Arial", 10), fg=self.colors['status_fg'], bg=self.colors['bg'])
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
        self.style_options = get_style_options(self.current_source_lang, self.current_target_lang)
        self.style_var.set(self.style_options[0])
        
        for option in self.style_options:
            self.style_menu.add_command(label=option, command=lambda s=option: self.select_style(s))

    def select_style(self, style):
        self.style_var.set(style)
        self.on_style_change()

    def on_style_change(self):
        selected_style = self.style_var.get()
        if "默认" in selected_style:
            return

        self.progress_label.config(text="🔄 正在重新翻译...")
        self.style_button.config(cursor='watch')
        self.main_win.update()

        def translate_with_style():
            try:
                style_instruction = f"请使用{selected_style}风格进行翻译。"
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
                    self.status_label.config(text="✓ 译文已更新并复制到剪贴板 (按 Esc 收起)")
                    self.style_button.config(cursor='hand2')

                self.main_win.after(0, update_ui)
            except Exception as e:
                def show_error():
                    self.progress_label.config(text="❌ 翻译失败")
                    self.style_button.config(cursor='hand2')
                self.main_win.after(0, show_error)

        if self.client:
            threading.Thread(target=translate_with_style, daemon=True).start()
        else:
            self.progress_label.config(text="❌ VertexAI 未初始化")
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
        self.root.after(50, self._force_strict_topmost)
        
        # Simple macOS focus push without aggressive loops
        try:
            import subprocess
            subprocess.run(['osascript', '-e', 'tell application "System Events" to set frontmost of the first process whose unix id is ' + str(os.getpid()) + ' to true'], capture_output=True)
        except:
            pass

    def update_content(self, payload):
        """Update UI with new translation payload"""
        self.current_original = payload.get('original', '')
        translation = payload.get('translation', '')
        self.current_source_lang = payload.get('source_lang', '')
        self.current_target_lang = payload.get('target_lang', '')

        self.title_label.config(text=f"翻译完成: {self.current_source_lang} → {self.current_target_lang}")
        
        # Update style options for the new translation direction
        self.update_style_menu()
        
        self.orig_text.config(state=tk.NORMAL)
        self.orig_text.delete(1.0, tk.END)
        self.orig_text.insert(tk.END, self.current_original)
        self.orig_text.config(state=tk.DISABLED)

        self.trans_text.config(state=tk.NORMAL)
        self.trans_text.delete(1.0, tk.END)
        self.trans_text.insert(tk.END, translation)
        self.trans_text.config(state=tk.DISABLED)

        pyperclip.copy(translation)
        
        # Expand automatically when new translation arrives
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
                            self.root.after(0, self.root.quit)
                            break
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
