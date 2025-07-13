# LAVIS/voice_control/advanced_controller.py

import os
import re
import pyautogui
import pyperclip
import webbrowser
import subprocess
from PIL import ImageGrab
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from LAVIS.hud_display import show_hud_reply


class WindowManager:
    @staticmethod
    def switch_window():
        pyautogui.hotkey('alt', 'tab')
        show_hud_reply("Switched window")


class MouseController:
    @staticmethod
    def move_mouse(x, y):
        pyautogui.moveTo(int(x), int(y))
        show_hud_reply(f"Moved mouse to {x}, {y}")

    @staticmethod
    def right_click():
        pyautogui.rightClick()
        show_hud_reply("Right click")

    @staticmethod
    def double_click():
        pyautogui.doubleClick()
        show_hud_reply("Double click")

    @staticmethod
    def drag_mouse(x1, y1, x2, y2):
        pyautogui.moveTo(int(x1), int(y1))
        pyautogui.mouseDown()
        pyautogui.moveTo(int(x2), int(y2), duration=0.5)
        pyautogui.mouseUp()
        show_hud_reply("Dragged mouse")


class KeyboardController:
    @staticmethod
    def press_hotkey(*keys):
        pyautogui.hotkey(*keys)
        show_hud_reply(f"Pressed {' + '.join(keys)}")


class FileExplorer:
    @staticmethod
    def open_path(path_name):
        try:
            os.startfile(path_name)
            show_hud_reply(f"Opened {path_name}")
        except:
            show_hud_reply(f"❌ Could not open {path_name}")


class VolumeController:
    @staticmethod
    def mute():
        pyautogui.press('volumemute')
        show_hud_reply("Muted volume")

    @staticmethod
    def volume_up():
        pyautogui.press('volumeup')
        show_hud_reply("Increased volume")

    @staticmethod
    def volume_down():
        pyautogui.press('volumedown')
        show_hud_reply("Decreased volume")


class MediaControl:
    @staticmethod
    def play_pause():
        pyautogui.press('playpause')
        show_hud_reply("Toggled play/pause")


class ScreenControl:
    @staticmethod
    def lock_screen():
        subprocess.run("rundll32.exe user32.dll,LockWorkStation")
        show_hud_reply("Locked screen")


class ScreenshotController:
    @staticmethod
    def take_screenshot():
        image = ImageGrab.grab()
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        image.save(filename)
        show_hud_reply(f"📸 Screenshot saved as {filename}")


class ClipboardController:
    @staticmethod
    def copy():
        pyautogui.hotkey('ctrl', 'c')
        show_hud_reply("Copied to clipboard")

    @staticmethod
    def paste():
        pyautogui.hotkey('ctrl', 'v')
        show_hud_reply("Pasted from clipboard")

    @staticmethod
    def read_clipboard():
        try:
            content = pyperclip.paste()
            show_hud_reply(f"Clipboard: {content}")
        except:
            show_hud_reply("❌ Failed to read clipboard")


class WebControl:
    @staticmethod
    def open_url(url):
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
        show_hud_reply(f"Opened {url}")

    @staticmethod
    def search_google(query):
        webbrowser.open(f"https://www.google.com/search?q={query}")
        show_hud_reply(f"Searching Google for: {query}")


class AppCloser:
    @staticmethod
    def close_app(name):
        try:
            os.system(f"taskkill /f /im {name}.exe")
            show_hud_reply(f"Closed {name}")
        except:
            show_hud_reply(f"❌ Could not close {name}")


class Scheduler:
    scheduler = BackgroundScheduler()
    scheduler.start()

    @staticmethod
    def remind_in(minutes, message):
        remind_time = datetime.now() + timedelta(minutes=minutes)
        Scheduler.scheduler.add_job(
            lambda: show_hud_reply(f"🔔 Reminder: {message}"),
            'date', run_date=remind_time
        )
        show_hud_reply(f"Reminder set for {minutes} minutes from now")


class SmartOCRHandler:
    @staticmethod
    def click_text(text):
        try:
            from pytesseract import image_to_data, Output
            screenshot = ImageGrab.grab()
            data = image_to_data(screenshot, output_type=Output.DICT)
            for i, word in enumerate(data['text']):
                if text.lower() in word.lower():
                    x = data['left'][i] + data['width'][i] // 2
                    y = data['top'][i] + data['height'][i] // 2
                    pyautogui.click(x, y)
                    show_hud_reply(f"Clicked on '{word}'")
                    return
            show_hud_reply(f"❌ '{text}' not found")
        except Exception as e:
            show_hud_reply(f"❌ OCR Error: {e}")


class LiveScreenAnalyzer:
    @staticmethod
    def detect_color_region(color_name):
        show_hud_reply(f"🧠 Detecting regions with color: {color_name} (not implemented)")


class SmartAutocomplete:
    @staticmethod
    def predict_intent(command):
        if "send email" in command:
            return "email_module.send_email()"
        elif "remind me" in command:
            return "Scheduler.remind_in()"
        return "unknown"


class Authentication:
    @staticmethod
    def autofill_password(password):
        pyautogui.write(password)
        show_hud_reply("Autofilled password (⚠️ security risk)")
