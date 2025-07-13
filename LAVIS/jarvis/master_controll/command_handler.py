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


def handle_voice_command(command: str) -> bool:
    command = command.lower().strip()

    try:
        if command.startswith("click "):
            SmartOCRHandler.click_text(command[6:].strip())

        elif command.startswith("move mouse to"):
            coords = re.findall(r"\d+", command)
            if len(coords) == 2:
                MouseController.move_mouse(coords[0], coords[1])

        elif command == "right click":
            MouseController.right_click()

        elif command == "double click":
            MouseController.double_click()

        elif command.startswith("drag from"):
            coords = re.findall(r"\d+", command)
            if len(coords) == 4:
                MouseController.drag_mouse(*coords)

        elif command.startswith("type "):
            KeyboardController.press_hotkey('ctrl', 'v')

        elif command.startswith("press "):
            keys = command.replace("press ", "").split()
            KeyboardController.press_hotkey(*keys)

        elif command.startswith("open "):
            app = command.replace("open ", "").strip()
            FileExplorer.open_path(app)

        elif command.startswith("scroll down"):
            from pyautogui import scroll
            scroll(-800)
            show_hud_reply("Scrolled down")

        elif command.startswith("scroll up"):
            from pyautogui import scroll
            scroll(800)
            show_hud_reply("Scrolled up")

        elif command == "mute":
            VolumeController.mute()

        elif command == "increase volume":
            VolumeController.volume_up()

        elif command == "decrease volume":
            VolumeController.volume_down()

        elif command == "play music" or command == "pause video":
            MediaControl.play_pause()

        elif command == "lock screen":
            ScreenControl.lock_screen()

        elif command == "take screenshot":
            ScreenshotController.take_screenshot()

        elif command == "copy this":
            ClipboardController.copy()

        elif command == "paste here":
            ClipboardController.paste()

        elif command == "read clipboard":
            ClipboardController.read_clipboard()

        elif command.startswith("search for"):
            WebControl.search_google(command.replace("search for", "").strip())

        elif command.startswith("open ") and ".com" in command:
            WebControl.open_url(command.replace("open ", "").strip())

        elif command.startswith("close "):
            AppCloser.close_app(command.replace("close ", "").strip())

        elif command.startswith("remind me in"):
            minutes = int(re.findall(r"\d+", command)[0])
            message = command.split("to")[-1].strip() if "to" in command else "Reminder"
            Scheduler.remind_in(minutes, message)

        elif command == "switch window" or command == "next window":
            WindowManager.switch_window()

        elif command.startswith("enter password"):
            pwd = command.replace("enter password", "").strip()
            Authentication.autofill_password(pwd)

        else:
            show_hud_reply(f"❓ Unrecognized command: {command}")
            return False

        return True

    except Exception as e:
        show_hud_reply(f"❌ Command Error: {e}")
        return False
