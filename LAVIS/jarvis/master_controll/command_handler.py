# LAVIS/voice_control/command_handler.py

import pyautogui
import pytesseract
from PIL import ImageGrab
import re
from LAVIS.jarvis.commands.apps import open_windows_app  # From your existing system

from LAVIS.hud_display import show_hud_reply


def click_text_on_screen(text):
    try:
        screenshot = ImageGrab.grab()
        ocr_data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)

        for i, word in enumerate(ocr_data["text"]):
            if text.lower() in word.lower():
                x = ocr_data["left"][i]
                y = ocr_data["top"][i]
                w = ocr_data["width"][i]
                h = ocr_data["height"][i]
                center_x = x + w // 2
                center_y = y + h // 2
                pyautogui.click(center_x, center_y)
                show_hud_reply(f"Clicked on '{word}'")
                return True

        show_hud_reply(f"❌ Could not find '{text}' on screen.")
        return False
    except Exception as e:
        show_hud_reply(f"❌ Error clicking text: {e}")
        return False


def scroll_screen(direction):
    amount = -800 if direction == "down" else 800
    pyautogui.scroll(amount)
    show_hud_reply(f"Scrolled {direction}")
    return True


def type_text_on_screen(text):
    try:
        pyautogui.write(text)
        show_hud_reply(f"Typed: {text}")
        return True
    except Exception as e:
        show_hud_reply(f"❌ Error typing: {e}")
        return False


def handle_voice_command(command: str) -> bool:
    command = command.lower().strip()

    # ✅ Click <text>
    if command.startswith("click "):
        text = command[6:].strip()
        return click_text_on_screen(text)

    # ✅ Scroll
    elif "scroll down" in command:
        return scroll_screen("down")
    elif "scroll up" in command:
        return scroll_screen("up")

    # ✅ Type <text>
    elif command.startswith("type "):
        match = re.search(r'type (.+)', command)
        if match:
            return type_text_on_screen(match.group(1))

    # ✅ Open App
    elif command.startswith("open "):
        app_name = command[5:].strip()
        if app_name and open_windows_app(app_name):
            show_hud_reply(f"Opening {app_name}")
            return True

    return False
