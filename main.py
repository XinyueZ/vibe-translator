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

# Load environment variables
load_dotenv()


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
                'auto_zh': '自动检测 → 中文',
                'zh_de': '中文 → 德文',
                'de_zh': '德文 → 中文',
                'zh_en': '中文 → 英文',
                'en_zh': '英文 → 中文',
                'auth': 'Auth 刷新授权',
                'ui_zh': '界面中文',
                'ui_en': '界面英文',
                'quit': '退出'
            },
            'en': {
                'auto_zh': 'Auto → ZH',
                'zh_de': 'ZH → DE',
                'de_zh': 'DE → ZH',
                'zh_en': 'ZH → EN',
                'en_zh': 'EN → ZH',
                'auth': 'Auth Refresh',
                'ui_zh': 'UI: Chinese',
                'ui_en': 'UI: English',
                'quit': 'Quit'
            }
        }
        t = self.i18n[self.ui_lang]

        # Initialize VertexAI client
        self.init_vertexai()

        # Start background listener for widget commands
        self.start_command_listener()

        # Translation options in menu
        self.menu = [
            rumps.MenuItem(t['auto_zh'], callback=self.translate_auto_to_zh),
            None,  # Separator
            rumps.MenuItem(t['zh_de'], callback=self.translate_zh_to_de),
            rumps.MenuItem(t['de_zh'], callback=self.translate_de_to_zh),
            rumps.MenuItem(t['zh_en'], callback=self.translate_zh_to_en),
            rumps.MenuItem(t['en_zh'], callback=self.translate_en_to_zh),
            None,  # Separator
            rumps.MenuItem(t['auth'], callback=self.refresh_auth),
            rumps.MenuItem(t['ui_zh'], callback=lambda _: self.change_lang('zh')),
            rumps.MenuItem(t['ui_en'], callback=lambda _: self.change_lang('en')),
            None,  # Separator
            rumps.MenuItem(t['quit'], callback=self.quit_app)
        ]

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
                        if cmd == 'auto_zh': self.translate_auto_to_zh(None)
                        elif cmd == 'zh_de': self.translate_zh_to_de(None)
                        elif cmd == 'de_zh': self.translate_de_to_zh(None)
                        elif cmd == 'zh_en': self.translate_zh_to_en(None)
                        elif cmd == 'en_zh': self.translate_en_to_zh(None)
                        elif cmd == 'auth': self.refresh_auth(None)
                        elif cmd == 'ui_zh': self.change_lang('zh')
                        elif cmd == 'ui_en': self.change_lang('en')
                        elif cmd == 'quit': self.quit_app(None)
                    conn.close()
            except Exception as e:
                print(f"Command listener error: {e}")
        
        threading.Thread(target=listener, daemon=True).start()

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
        """Get currently selected text by simulating Cmd+C"""
        try:
            import time
            import subprocess

            # Save current clipboard content
            original_clipboard = pyperclip.paste()
            
            # --- FOCUS FIX for Floating Widget ---
            # When the user clicks the floating widget, Python (Tkinter) steals focus.
            # We must aggressively hide our own app to force macOS to return focus
            # to the previous application (e.g. Browser/Editor) BEFORE simulating Cmd+C.
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to set visible of first process whose unix id is ' + str(os.getpid()) + ' to false'],
                capture_output=True
            )
            # Give macOS a tiny fraction of a second to switch the active window back
            time.sleep(0.1)
            # -------------------------------------

            # Simulate Cmd+C to copy selected text using osascript
            result = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to keystroke "c" using {command down}'],
                capture_output=True,
                text=True,
                timeout=2
            )

            # Check if osascript failed (permission denied)
            if result.returncode != 0:
                error_msg = result.stderr.strip()
                if "not allowed" in error_msg or "1002" in error_msg:
                    # Permission issue
                    from AppKit import NSAlert, NSCriticalAlertStyle
                    alert = NSAlert.alloc().init()
                    alert.setMessageText_("需要辅助功能权限")
                    alert.setInformativeText_(
                        "请按以下步骤授权：\n\n"
                        "1. 打开 系统设置\n"
                        "2. 进入 隐私与安全性 → 辅助功能\n"
                        "3. 点击 + 添加 Terminal\n"
                        "4. 勾选启用\n\n"
                        "授权后立即生效，无需重启程序。"
                    )
                    alert.addButtonWithTitle_("确定")
                    alert.setAlertStyle_(NSCriticalAlertStyle)
                    alert.window().setLevel_(101)
                    alert.runModal()
                    return None
                else:
                    print(f"osascript error: {error_msg}")
                    return None

            time.sleep(0.3)  # Wait for copy to complete

            # Get new clipboard content
            selected_text = pyperclip.paste()

            # Check if we got new text
            if not selected_text or not selected_text.strip():
                from AppKit import NSAlert, NSInformationalAlertStyle
                alert = NSAlert.alloc().init()
                alert.setMessageText_("提示")
                alert.setInformativeText_("请先选择要翻译的文本，然后再点击菜单选项。")
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

    def translate_text(self, text, source_lang, target_lang, target_lang_en):
        """Translate text using VertexAI"""
        try:
            rumps.notification(
                title=f"翻译中: {source_lang} → {target_lang}",
                subtitle=f"原文: {text[:50]}{'...' if len(text) > 50 else ''}",
                message="正在使用 AI 翻译，请稍候..."
            )
        except Exception as e:
            print(f"Notification error: {e}")

        # Send initial "loading" state to UI Daemon so it pops up immediately
        self._send_to_daemon({
            'status': 'loading',
            'original': text,
            'source_lang': source_lang,
            'target_lang': target_lang
        })

        # Perform translation in background thread
        threading.Thread(
            target=self._perform_translation,
            args=(text, source_lang, target_lang, target_lang_en),
            daemon=True
        ).start()

    def _perform_translation(self, text, source_lang, target_lang, target_lang_en):
        """Perform translation in background thread"""
        try:
            if target_lang == "德文":
                style_instruction = "Use duzen (informal 'you') for the German translation. "
            else:
                style_instruction = ""

            prompt = f"Translate the following text from {source_lang} to {target_lang}. {style_instruction}Only return the translation, no explanations:\n\n{text}"

            response = self.client.models.generate_content(
                model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite-preview'),
                contents=prompt
            )

            translation = response.text.strip()
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
