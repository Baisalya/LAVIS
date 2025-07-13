# LAVIS/voice_control/command_handler.py

import re
from LAVIS.hud_display import show_hud_reply
from LAVIS.jarvis.master_controll.advanced_controller import (
    WindowManager,
    MouseController,
    KeyboardController,
    FileExplorer,
    VolumeController,
    MediaControl,
    ScreenControl,
    ScreenshotController,
    ClipboardController,
    WebControl,
    AppCloser,
    Scheduler,
    SmartOCRHandler,
    SmartAutocomplete,
    Authentication
)
from LAVIS.jarvis.nlp.fallback_corrector import correct_command
from LAVIS.jarvis.commands.apps import open_windows_app


def handle_voice_command(raw_command: str) -> bool:
    corrected_text = correct_command(raw_command).strip().lower()
    print(f"🛠️ Corrected Voice Command: {corrected_text}")

    try:
        if corrected_text.startswith("click "):
            SmartOCRHandler.click_text(corrected_text[6:].strip())

        elif corrected_text.startswith("move mouse to"):
            coords = re.findall(r"\d+", corrected_text)
            if len(coords) == 2:
                MouseController.move_mouse(coords[0], coords[1])

        elif corrected_text == "right click":
            MouseController.right_click()

        elif corrected_text == "double click":
            MouseController.double_click()

        elif corrected_text.startswith("drag from"):
            coords = re.findall(r"\d+", corrected_text)
            if len(coords) == 4:
                MouseController.drag_mouse(*coords)

        elif corrected_text.startswith("type "):
            KeyboardController.press_hotkey('ctrl', 'v')

        elif corrected_text.startswith("press "):
            keys = corrected_text.replace("press ", "").split()
            KeyboardController.press_hotkey(*keys)

        elif corrected_text.startswith("open "):
            app = corrected_text.replace("open ", "").strip()
            if open_windows_app(app):
                show_hud_reply(f"Launching {app}")
            elif FileExplorer.open_path(app):
                return True
            else:
                show_hud_reply(f"❌ Could not open {app}")
                return False

        elif corrected_text.startswith("scroll down"):
            from pyautogui import scroll
            scroll(-800)
            show_hud_reply("Scrolled down")

        elif corrected_text.startswith("scroll up"):
            from pyautogui import scroll
            scroll(800)
            show_hud_reply("Scrolled up")

        elif corrected_text == "mute":
            VolumeController.mute()

        elif corrected_text == "increase volume":
            VolumeController.volume_up()

        elif corrected_text == "decrease volume":
            VolumeController.volume_down()

        elif corrected_text in ["play music", "pause video"]:
            MediaControl.play_pause()

        elif corrected_text == "lock screen":
            ScreenControl.lock_screen()

        elif corrected_text == "take screenshot":
            ScreenshotController.take_screenshot()

        elif corrected_text == "copy this":
            ClipboardController.copy()

        elif corrected_text == "paste here":
            ClipboardController.paste()

        elif corrected_text == "read clipboard":
            ClipboardController.read_clipboard()

        elif corrected_text.startswith("search for"):
            WebControl.search_google(corrected_text.replace("search for", "").strip())

        elif corrected_text.startswith("open ") and ".com" in corrected_text:
            WebControl.open_url(corrected_text.replace("open ", "").strip())

        elif corrected_text.startswith("close "):
            AppCloser.close_app(corrected_text.replace("close ", "").strip())

        elif corrected_text.startswith("remind me in"):
            minutes = int(re.findall(r"\d+", corrected_text)[0])
            message = corrected_text.split("to")[-1].strip() if "to" in corrected_text else "Reminder"
            Scheduler.remind_in(minutes, message)

        elif corrected_text in ["switch window", "next window"]:
            WindowManager.switch_window()

        elif corrected_text.startswith("enter password"):
            pwd = corrected_text.replace("enter password", "").strip()
            Authentication.autofill_password(pwd)

        else:
            show_hud_reply(f"❓ Unrecognized command: {corrected_text}")
            return False

        return True

    except Exception as e:
        show_hud_reply(f"❌ Command Error: {e}")
        return False
