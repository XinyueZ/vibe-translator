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


class TranslatorApp(rumps.App):
    """macOS Menu Bar Translation Application"""

    def __init__(self):
        super(TranslatorApp, self).__init__(
            "🌍",  # Menu bar icon
            quit_button=None
        )

        # Initialize VertexAI client
        self.init_vertexai()

        # Translation options in menu
        self.menu = [
            rumps.MenuItem("中文 → 德文", callback=self.translate_zh_to_de),
            rumps.MenuItem("德文 → 中文", callback=self.translate_de_to_zh),
            rumps.MenuItem("中文 → 英文", callback=self.translate_zh_to_en),
            rumps.MenuItem("英文 → 中文", callback=self.translate_en_to_zh),
            None,  # Separator
            rumps.MenuItem("退出", callback=self.quit_app)
        ]

    def init_vertexai(self):
        """Initialize Google VertexAI client"""
        try:
            # Configure VertexAI
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            location = os.getenv('GOOGLE_CLOUD_LOCATION')

            # Initialize client
            self.client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location
            )
            print(f"✓ VertexAI initialized: {project_id} @ {location}")
        except Exception as e:
            print(f"✗ Failed to initialize VertexAI: {e}")
            rumps.alert("初始化失败", f"无法连接到 VertexAI:\n{e}")

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

    def translate_text(self, text, source_lang, target_lang, target_lang_en):
        """Translate text using VertexAI"""
        # Show notification that translation is starting
        try:
            rumps.notification(
                title=f"翻译中: {source_lang} → {target_lang}",
                subtitle=f"原文: {text[:50]}{'...' if len(text) > 50 else ''}",
                message="正在使用 AI 翻译，请稍候..."
            )
        except Exception as e:
            print(f"Notification error: {e}")

        # Perform translation in background thread
        threading.Thread(
            target=self._perform_translation,
            args=(text, source_lang, target_lang, target_lang_en),
            daemon=True
        ).start()

    def _perform_translation(self, text, source_lang, target_lang, target_lang_en):
        """Perform translation in background thread"""
        try:
            # Create prompt with default style
            # For German, default to duzen (informal "you")
            if target_lang == "德文":
                style_instruction = "Use duzen (informal 'you') for the German translation. "
            else:
                style_instruction = ""

            prompt = f"Translate the following text from {source_lang} to {target_lang}. {style_instruction}Only return the translation, no explanations:\n\n{text}"

            print(f">>> Translating from {source_lang} to {target_lang}...")
            import sys
            sys.stdout.flush()

            # Call VertexAI with Gemini 2.5 Flash Lite
            print(">>> Calling VertexAI...")
            sys.stdout.flush()

            response = self.client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt
            )

            print(">>> Got response from VertexAI")
            sys.stdout.flush()

            # Extract translation
            translation = response.text.strip()
            print(f">>> Translation completed: {translation[:100]}...")
            sys.stdout.flush()

            # Copy translation to clipboard
            pyperclip.copy(translation)

            print(f">>> Showing result dialog...")
            sys.stdout.flush()

            # Show result dialog
            self._show_result_dialog(text, translation, source_lang, target_lang)

            print(f">>> Translation complete!")
            sys.stdout.flush()

        except Exception as e:
            print(f"Translation error: {e}")
            import traceback
            traceback.print_exc()

            # Show error dialog
            self._show_error_dialog(str(e))


    def _show_result_dialog(self, original, translation, source_lang, target_lang):
        """Show translation result using separate Python process"""
        try:
            # Get script path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            show_result_script = os.path.join(script_dir, "show_result.py")

            # Get python from venv
            venv_python = os.path.join(script_dir, "venv", "bin", "python")
            if not os.path.exists(venv_python):
                venv_python = "python3"

            # Create temporary JSON file with data
            data = {
                'original': original,
                'translation': translation,
                'source_lang': source_lang,
                'target_lang': target_lang
            }

            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(data, f)
                temp_file = f.name

            print(f">>> Created temp file: {temp_file}")

            # Use 'open' command to run Python script - this ensures proper foreground window
            cmd = f"open -a Terminal {venv_python} {show_result_script} {temp_file}"

            # Actually, let's try using pythonw or direct execution
            subprocess.Popen(
                [venv_python, show_result_script, temp_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )

            print(f">>> Window launched")

        except Exception as e:
            print(f"Error showing result dialog: {e}")
            import traceback
            traceback.print_exc()

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

    def quit_app(self, _):
        """Quit the application"""
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
