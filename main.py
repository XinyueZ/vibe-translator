#!/usr/bin/env python3
"""
Vibe Translator - macOS Menu Bar Translation App
Uses Google VertexAI for translations
"""

import os
import rumps
import pyperclip
import threading
import subprocess
import json
import tempfile
from google import genai
from dotenv import load_dotenv

# Load environment variables (override existing ones to ensure .env takes precedence)
load_dotenv(override=True)


def load_config():
    config_path = os.path.expanduser('~/.vibe_translator_config.json')
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_config(config):
    config_path = os.path.expanduser('~/.vibe_translator_config.json')
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except:
        pass

class TranslatorApp(rumps.App):
    """macOS Menu Bar Translation Application"""

    def __init__(self):
        super(TranslatorApp, self).__init__(
            "🌍",  # Menu bar icon
            quit_button=None
        )
        
        self.config = load_config()
        self.ui_lang = self.config.get('ui_lang', 'zh')
        
        self.i18n = {
            'zh': {
                'rescue_widget': '找回悬浮',
                'hover_tr': '右上悬停',
                'hover_br': '右下悬停',
                'hover_tl': '左上悬停',
                'hover_bl': '左下悬停',
                'ocr_translate': '📸 截图翻译',
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
                'quit': '退出'
            },
            'en': {
                'rescue_widget': 'Show Widget',
                'hover_tr': 'Hover Top Right',
                'hover_br': 'Hover Bottom Right',
                'hover_tl': 'Hover Top Left',
                'hover_bl': 'Hover Bottom Left',
                'ocr_translate': '📸 OCR Translate',
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
                'quit': 'Quit'
            }
        }
        t = self.i18n[self.ui_lang]

        # Initialize VertexAI client
        self.init_vertexai()

        # Start background listener for widget commands
        self.start_command_listener()

        self.use_local_ai = self.config.get('use_local_ai', False)
        self.local_ai_item = rumps.MenuItem(t['local_ai'], callback=self.toggle_local_ai)
        self.local_ai_item.state = self.use_local_ai

        self.mouse_follow = self.config.get('mouse_follow', True)
        self.mouse_follow_item = rumps.MenuItem(t['mouse_follow'], callback=self.toggle_mouse_follow)
        self.mouse_follow_item.state = self.mouse_follow

        self.hover_pos = self.config.get('hover_position', 'top_right')
        self.hover_tr_item = rumps.MenuItem(t['hover_tr'], callback=lambda _: self.set_hover_position('top_right'))
        self.hover_br_item = rumps.MenuItem(t['hover_br'], callback=lambda _: self.set_hover_position('bottom_right'))
        self.hover_tl_item = rumps.MenuItem(t['hover_tl'], callback=lambda _: self.set_hover_position('top_left'))
        self.hover_bl_item = rumps.MenuItem(t['hover_bl'], callback=lambda _: self.set_hover_position('bottom_left'))
        self._update_hover_checks()

        # Translation options in menu
        menu_items = [
            rumps.MenuItem(t['rescue_widget'], callback=self.rescue_widget),
            self.hover_tr_item,
            self.hover_br_item,
            self.hover_tl_item,
            self.hover_bl_item,
            None,
            rumps.MenuItem(t['ocr_translate'], callback=self.ocr_translate),
            rumps.MenuItem(t['auto_zh'], callback=self.translate_auto_to_zh),
            rumps.MenuItem(t['auto_de'], callback=self.translate_auto_to_de),
            rumps.MenuItem(t['auto_en'], callback=self.translate_auto_to_en),
            rumps.MenuItem(t['zh_de'], callback=self.translate_zh_to_de),
            rumps.MenuItem(t['de_zh'], callback=self.translate_de_to_zh),
            rumps.MenuItem(t['zh_en'], callback=self.translate_zh_to_en),
            rumps.MenuItem(t['en_zh'], callback=self.translate_en_to_zh),
            None,  # Separator
            rumps.MenuItem(t['add_lang'], callback=self.add_translation_language),
        ]
        
        if 'custom_langs' in self.config and len(self.config['custom_langs']) > 0:
            menu_items.append(rumps.MenuItem(t['remove_lang'], callback=self.remove_translation_language))
        
        # Add custom languages
        if 'custom_langs' in self.config:
            for cl in self.config['custom_langs']:
                label_text = f"• {cl['source']} → {cl['target']}"
                item = rumps.MenuItem(label_text, callback=lambda _, cid=cl['id']: self.translate_custom(cid))
                menu_items.append(item)
                
        menu_items.append(None) # Separator for the group
                
        menu_items.extend([
            self.local_ai_item,
            self.mouse_follow_item,
            rumps.MenuItem(t['how_to_use'], callback=self.show_how_to_use),
            rumps.MenuItem(t['ui_zh'], callback=lambda _: self.change_lang('zh')),
            rumps.MenuItem(t['ui_en'], callback=lambda _: self.change_lang('en')),
            None,  # Separator
            rumps.MenuItem(t['auth'], callback=self.refresh_auth),
            rumps.MenuItem(t['restart'], callback=self.restart_app),
            rumps.MenuItem(t['quit'], callback=self.quit_app)
        ])
        
        self.menu = menu_items

    def rescue_widget(self, _):
        self._send_to_daemon({'action': 'rescue_widget'})

    def toggle_local_ai(self, sender):
        self.use_local_ai = not self.use_local_ai
        sender.state = self.use_local_ai
        self.config['use_local_ai'] = self.use_local_ai
        save_config(self.config)
        self._send_to_daemon({'action': 'toggle_local_ai', 'state': self.use_local_ai})

    def show_how_to_use(self, _):
        self._send_to_daemon({'action': 'show_how_to_use'})

    def toggle_mouse_follow(self, sender):
        self.mouse_follow = not self.mouse_follow
        sender.state = self.mouse_follow
        self.config['mouse_follow'] = self.mouse_follow
        save_config(self.config)
        self._send_to_daemon({'action': 'toggle_mouse_follow', 'state': self.mouse_follow})

    def set_hover_position(self, pos):
        self.hover_pos = pos
        self.config['hover_position'] = pos
        save_config(self.config)
        self._update_hover_checks()
        self._send_to_daemon({'action': 'set_hover_position', 'pos': pos})
        
    def _update_hover_checks(self):
        self.hover_tr_item.state = (self.hover_pos == 'top_right')
        self.hover_br_item.state = (self.hover_pos == 'bottom_right')
        self.hover_tl_item.state = (self.hover_pos == 'top_left')
        self.hover_bl_item.state = (self.hover_pos == 'bottom_left')

    def change_lang(self, lang):
        if self.ui_lang == lang: return
        self.config['ui_lang'] = lang
        save_config(self.config)
        print(f">>> Changing UI language to {lang}, restarting...")
        
        # Kill daemon gracefully
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(('127.0.0.1', 50051))
            s.sendall(json.dumps({'action': 'quit'}).encode('utf-8'))
            s.close()
        except: pass
        
        import sys, subprocess
        subprocess.Popen(
            [sys.executable, sys.argv[0]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        rumps.quit_application()

    def start_command_listener(self):
        """Listen for commands triggered from the floating widget"""
        def listener():
            import socket
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                server.bind(('127.0.0.1', 50052))
                server.listen(5)
                print(">>> Main app listening for widget commands on port 50052")
                while True:
                    conn, addr = server.accept()
                    data = conn.recv(1024).decode('utf-8')
                    if data:
                        cmd = data.strip()
                        print(f">>> Received command from widget: {cmd}")
                        if cmd.startswith('custom_translate_'):
                            cid = cmd.replace('custom_translate_', '')
                            self.translate_custom(cid)
                        elif cmd == 'reload_config':
                            print(">>> Reloading config dynamically")
                            self.config = load_config()
                            self._rebuild_main_menu()
                            self._send_to_daemon({'action': 'reload_ui_config'})
                        elif cmd == 'ocr_translate': self.ocr_translate(None)
                        elif cmd == 'auto_zh': self.translate_auto_to_zh(None)
                        elif cmd == 'auto_de': self.translate_auto_to_de(None)
                        elif cmd == 'auto_en': self.translate_auto_to_en(None)
                        elif cmd == 'add_lang': self.add_translation_language(None)
                        elif cmd == 'remove_lang': self.remove_translation_language(None)
                        elif cmd == 'zh_de': self.translate_zh_to_de(None)
                        elif cmd == 'de_zh': self.translate_de_to_zh(None)
                        elif cmd == 'zh_en': self.translate_zh_to_en(None)
                        elif cmd == 'en_zh': self.translate_en_to_zh(None)
                        elif cmd == 'auth': self.refresh_auth(None)
                        elif cmd == 'ui_zh': self.change_lang('zh')
                        elif cmd == 'ui_en': self.change_lang('en')
                        elif cmd == 'toggle_local_ai': self.toggle_local_ai(self.local_ai_item)
                        elif cmd == 'toggle_mouse_follow': self.toggle_mouse_follow(self.mouse_follow_item)
                        elif cmd == 'restart': self.restart_app(None)
                        elif cmd == 'quit': self.quit_app(None)
                    conn.close()
            except Exception as e:
                print(f"Command listener error: {e}")
        
        threading.Thread(target=listener, daemon=True).start()


    def _rebuild_main_menu(self):
        t = self.i18n[self.ui_lang]
        
        # We need to clear the existing menu
        self.menu.clear()
        
        menu_items = [
            rumps.MenuItem(t['rescue_widget'], callback=self.rescue_widget),
            self.hover_tr_item,
            self.hover_br_item,
            self.hover_tl_item,
            self.hover_bl_item,
            None,
            rumps.MenuItem(t['ocr_translate'], callback=self.ocr_translate),
            rumps.MenuItem(t['auto_zh'], callback=self.translate_auto_to_zh),
            rumps.MenuItem(t['auto_de'], callback=self.translate_auto_to_de),
            rumps.MenuItem(t['auto_en'], callback=self.translate_auto_to_en),
            rumps.MenuItem(t['zh_de'], callback=self.translate_zh_to_de),
            rumps.MenuItem(t['de_zh'], callback=self.translate_de_to_zh),
            rumps.MenuItem(t['zh_en'], callback=self.translate_zh_to_en),
            rumps.MenuItem(t['en_zh'], callback=self.translate_en_to_zh),
            None,  # Separator
            rumps.MenuItem(t['add_lang'], callback=self.add_translation_language),
        ]
        
        if 'custom_langs' in self.config and len(self.config['custom_langs']) > 0:
            menu_items.append(rumps.MenuItem(t['remove_lang'], callback=self.remove_translation_language))
        
        # Add custom languages
        if 'custom_langs' in self.config:
            for cl in self.config['custom_langs']:
                label_text = f"• {cl['source']} → {cl['target']}"
                item = rumps.MenuItem(label_text, callback=lambda _, cid=cl['id']: self.translate_custom(cid))
                menu_items.append(item)
                
        menu_items.append(None) # Separator
                
        menu_items.extend([
            self.local_ai_item,
            self.mouse_follow_item,
            rumps.MenuItem(t['how_to_use'], callback=self.show_how_to_use),
            rumps.MenuItem(t['ui_zh'], callback=lambda _: self.change_lang('zh')),
            rumps.MenuItem(t['ui_en'], callback=lambda _: self.change_lang('en')),
            None,  # Separator
            rumps.MenuItem(t['auth'], callback=self.refresh_auth),
            rumps.MenuItem(t['restart'], callback=self.restart_app),
            rumps.MenuItem(t['quit'], callback=self.quit_app)
        ])
        
        # In rumps, if we assign to self.menu it creates a new menu, 
        # or we can update the existing one. We cleared it, now we update it.
        self.menu.update(menu_items)

    def init_vertexai(self):
        """Initialize Google GenAI client (VertexAI or AI Studio)"""
        try:
            use_vertex = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'False').lower() in ('true', '1', 't', 'yes')

            if use_vertex:
                # Configure VertexAI
                project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
                location = os.getenv('GOOGLE_CLOUD_LOCATION')
                model_name = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')
                
                # Auto-override location for preview models
                if "-preview" in model_name.lower():
                    print(f">>> Preview model detected ({model_name}), forcing location to 'global'")
                    location = "global" # Forced to global as per requirement
                    
                if not project_id or not location:
                    raise ValueError("Missing GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION for VertexAI.")
                    
                # Initialize client
                self.client = genai.Client(
                    vertexai=True,
                    project=project_id,
                    location=location
                )
                print(f"✓ VertexAI initialized: {project_id} @ {location} (Model: {model_name})")
            else:
                # Configure AI Studio
                api_key = os.getenv('GOOGLE_AI_STUDIO_API_KEY')
                if not api_key:
                    raise ValueError("Illegal State: GOOGLE_GENAI_USE_VERTEXAI is False, but GOOGLE_AI_STUDIO_API_KEY is missing.")
                
                # Initialize client
                self.client = genai.Client(api_key=api_key)
                print(f"✓ Google AI Studio initialized with API Key")
                
        except Exception as e:
            print(f"✗ Failed to initialize AI Client: {e}")
            rumps.alert("AI 初始化失败", f"配置错误或缺失:\n{e}\n\n请检查 .env 文件。")
            self.client = None
            
        # Start UI Daemon automatically
        self.start_ui_daemon()

    def start_ui_daemon(self):
        """Ensure UI Daemon is running"""
        import socket
        # Check if it's already running by trying to connect
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('127.0.0.1', 50051))
            s.close()
            print("✓ UI Daemon is already running.")
            return
        except ConnectionRefusedError:
            pass # Not running, we will start it
            
        try:
            print(">>> Starting UI Daemon...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(script_dir, "ui_daemon.py")
            venv_python = os.path.join(script_dir, "venv", "bin", "python")
            if not os.path.exists(venv_python):
                venv_python = "python3"
                
            self.daemon_process = subprocess.Popen(
                [venv_python, daemon_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            import atexit
            def cleanup_daemon():
                if hasattr(self, 'daemon_process') and self.daemon_process:
                    try:
                        self.daemon_process.terminate()
                    except:
                        pass
            atexit.register(cleanup_daemon)
        except Exception as e:
            print(f"Error starting UI Daemon: {e}")


    def remove_translation_language(self, _):
        self._send_to_daemon({'action': 'show_remove_lang_dialog'})

    def add_translation_language(self, _):
        self._send_to_daemon({'action': 'show_add_lang_dialog'})


    def translate_custom(self, cid):
        print(f">>> Menu clicked: Custom translate {cid}")
        # Reload config to ensure we have latest
        self.config = load_config()
        custom_lang = next((c for c in self.config.get('custom_langs', []) if c['id'] == cid), None)
        
        if not custom_lang:
            print("Custom lang not found.")
            return
            
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, custom_lang['source'], custom_lang['target'], custom_lang['target'], custom_lang_id=cid)

    def ocr_translate(self, _):
        """截图翻译"""
        print(">>> Menu clicked: 截图翻译")
        pass

    def translate_auto_to_zh(self, _):
        """自动检测 → 中文"""
        print(">>> Menu clicked: 自动检测 → 中文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "自动检测", "中文", "Chinese")

    def translate_auto_to_de(self, _):
        """自动检测 → 德文"""
        print(">>> Menu clicked: 自动检测 → 德文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "自动检测", "德文", "German")

    def translate_auto_to_en(self, _):
        """自动检测 → 英文"""
        print(">>> Menu clicked: 自动检测 → 英文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "自动检测", "英文", "English")

    def translate_zh_to_de(self, _):
        """中文 → 德文"""
        print(">>> Menu clicked: 中文 → 德文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "中文", "德文", "German")

    def translate_de_to_zh(self, _):
        """德文 → 中文"""
        print(">>> Menu clicked: 德文 → 中文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "德文", "中文", "Chinese")

    def translate_zh_to_en(self, _):
        """中文 → 英文"""
        print(">>> Menu clicked: 中文 → 英文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "中文", "英文", "English")

    def translate_en_to_zh(self, _):
        """英文 → 中文"""
        print(">>> Menu clicked: 英文 → 中文")
        import sys
        sys.stdout.flush()
        text = self.get_selected_text()
        if text:
            print(f">>> Got text, starting translation: {text[:50]}...")
            sys.stdout.flush()
            self.translate_text(text, "英文", "中文", "Chinese")

    def get_selected_text(self):
        """Get currently selected text by using the clipboard."""
        try:
            import pyperclip

            # Get clipboard content directly
            selected_text = pyperclip.paste()

            # Check if we got text
            if not selected_text or not selected_text.strip():
                from AppKit import NSAlert, NSInformationalAlertStyle
                alert = NSAlert.alloc().init()
                alert.setMessageText_("提示")
                alert.setInformativeText_("剪贴板为空。\n\n请先使用 Cmd+C 复制要翻译的文本，然后再点击翻译选项。")
                alert.addButtonWithTitle_("确定")
                alert.setAlertStyle_(NSInformationalAlertStyle)
                alert.window().setLevel_(101)
                alert.runModal()
                return None

            print(f"Selected text: {selected_text[:100]}...")
            return selected_text.strip()

        except Exception as e:
            print(f"Error getting selected text: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _send_to_daemon(self, payload_dict):
        """Helper to send data to UI Daemon"""
        import socket
        import json
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            try:
                s.connect(('127.0.0.1', 50051))
                s.sendall(json.dumps(payload_dict).encode('utf-8'))
            except ConnectionRefusedError:
                print(">>> UI Daemon not running. Restarting it...")
                self.start_ui_daemon()
                import time
                time.sleep(1)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(('127.0.0.1', 50051))
                s.sendall(json.dumps(payload_dict).encode('utf-8'))
            finally:
                s.close()
        except Exception as e:
            print(f"Error sending to UI Daemon: {e}")

    def translate_text(self, text, source_lang, target_lang, target_lang_en, custom_lang_id=None):
        """Translate text using VertexAI/LocalAI"""
        try:
            rumps.notification(
                title=f"翻译中: {source_lang} → {target_lang}",
                subtitle=f"原文: {text[:50]}{'...' if len(text) > 50 else ''}",
                message="正在使用 AI 翻译，请稍候..."
            )
        except Exception as e:
            print(f"Notification error: {e}")

        # Determine model name for UI
        if self.use_local_ai:
            self.config = load_config()
            model = self.config.get('ollama_model') or os.getenv('OLLAMA_MODEL', 'qwen2.5:1.5b')
            model_str = f"Ollama ({model})"
        else:
            gemini_model = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview')
            use_vertex = os.getenv('GOOGLE_GENAI_USE_VERTEXAI', 'False').lower() in ('true', '1', 't', 'yes')
            if use_vertex:
                model_str = f"VertexAI ({gemini_model})"
            else:
                model_str = f"Google GenAI ({gemini_model})"

        # Send initial "loading" state to UI Daemon so it pops up immediately
        self._send_to_daemon({
            'status': 'loading',
            'original': text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'model_name': model_str
        })

        # Perform translation in background thread
        threading.Thread(
            target=self._perform_translation,
            args=(text, source_lang, target_lang, target_lang_en, custom_lang_id),
            daemon=True
        ).start()

    def _perform_translation(self, text, source_lang, target_lang, target_lang_en, custom_lang_id=None):
        """Perform translation in background thread"""
        try:
            style_instruction = ""
            if custom_lang_id:
                # Need to get style instruction from config
                self.config = load_config()
                custom_lang = next((c for c in self.config.get('custom_langs', []) if c['id'] == custom_lang_id), None)
                if custom_lang:
                    style_instruction = custom_lang.get('default_style', '') + " "
                    
            elif target_lang == "德文":
                style_instruction = "Use duzen (informal 'you') for the German translation. "

            prompt = f"Translate the following text from {source_lang} to {target_lang}. {style_instruction}Only return the translation, no explanations:\n\n{text}"

            translation = ""
            is_first = True

            if self.use_local_ai:
                import requests
                self.config = load_config()
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
                            translation += chunk
                            self._send_to_daemon({
                                'status': 'streaming',
                                'chunk': chunk,
                                'is_first': is_first
                            })
                            is_first = False
            else:
                response_stream = self.client.models.generate_content_stream(
                    model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
                    contents=prompt
                )

                for chunk in response_stream:
                    if chunk.text:
                        translation += chunk.text
                        self._send_to_daemon({
                            'status': 'streaming',
                            'chunk': chunk.text,
                            'is_first': is_first
                        })
                        is_first = False

            translation = translation.strip()
            pyperclip.copy(translation)

            # Send final result to UI Daemon
            self._send_to_daemon({
                'status': 'complete',
                'original': text,
                'translation': translation,
                'source_lang': source_lang,
                'target_lang': target_lang
            })

        except Exception as e:
            print(f"Translation error: {e}")
            import traceback
            traceback.print_exc()
            
            # Send error state to UI Daemon
            self._send_to_daemon({
                'status': 'error',
                'error_msg': str(e)
            })

            # Show error dialog
            self._show_error_dialog(str(e))

    # _show_result_dialog is no longer needed but we can leave it or remove it.
    # I will remove it to clean up the code.
    def _show_result_dialog(self, original, translation, source_lang, target_lang):
        pass # Deprecated, replaced by _send_to_daemon

    def _show_error_dialog(self, error_msg):
        """Show error dialog"""
        try:
            # Use rumps notification for errors
            rumps.notification(
                title="翻译失败",
                subtitle="",
                message=f"错误: {error_msg}"
            )
        except Exception as e:
            print(f"Error showing error dialog: {e}")

    def refresh_auth(self, _):
        """刷新 Google Cloud 授权并重启应用"""
        import os
        import sys
        import subprocess
        
        try:
            rumps.notification(
                title="刷新授权",
                subtitle="正在打开终端...",
                message="请在浏览器中完成登录，应用正在重启..."
            )
        except Exception as e:
            print(f"Notification error: {e}")
            
        print(">>> 正在运行 gcloud auth application-default login...")
        subprocess.Popen([
            "osascript", "-e",
            'tell application "Terminal" to do script "gcloud auth application-default login"'
        ])
        
        print(">>> 准备重启应用...")
        
        # 发送退出信号给旧的 UI Daemon
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(('127.0.0.1', 50051))
            s.sendall(json.dumps({'action': 'quit'}).encode('utf-8'))
            s.close()
        except: pass

        # 启动一个新的独立进程来运行这个脚本
        subprocess.Popen(
            [sys.executable, sys.argv[0]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True # 脱离当前进程组
        )
        
        # 优雅地退出当前应用实例
        rumps.quit_application()

    def restart_app(self, _):
        """重启应用"""
        import sys
        import subprocess
        import socket
        
        print(">>> 准备重启应用...")
        
        # 发送退出信号给旧的 UI Daemon
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(('127.0.0.1', 50051))
            s.sendall(json.dumps({'action': 'quit'}).encode('utf-8'))
            s.close()
        except: pass

        # 启动一个新的独立进程来运行这个脚本
        subprocess.Popen(
            [sys.executable, sys.argv[0]],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True # 脱离当前进程组
        )
        
        # 优雅地退出当前应用实例
        rumps.quit_application()

    def quit_app(self, _):
        """Quit the application and the UI Daemon"""
        import socket
        try:
            # Send quit signal to UI Daemon
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(('127.0.0.1', 50051))
            s.sendall(json.dumps({'action': 'quit'}).encode('utf-8'))
            s.close()
            print(">>> Sent quit signal to UI Daemon.")
        except:
            pass # Daemon might already be dead
            
        rumps.quit_application()


if __name__ == "__main__":
    print("=" * 50)
    print("Starting Vibe Translator...")
    print("=" * 50)
    import sys
    sys.stdout.flush()

    app = TranslatorApp()
    print("App initialized, starting main loop...")
    sys.stdout.flush()

    app.run()
