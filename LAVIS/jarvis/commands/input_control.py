#input control.py
import pyautogui
import pyperclip
import time
from LAVIS.jarvis.voice.speaker import speak

drag_mode = {"active": False, "start": (0, 0)}  # Keep track of drag state

def handle_input_control(command: str) -> bool:
    global drag_mode
    command = command.lower().strip()

    # 🎯 Mouse Movement
    if "move mouse" in command:
        try:
            parts = command.replace("move mouse", "").strip().split()
            x = int(parts[0])
            y = int(parts[1])
            pyautogui.moveTo(x, y, duration=0.5)
            speak(f"Mouse moved to {x}, {y}")
        except:
            speak("Please say: move mouse 100 200")
        return True

    # 🖱️ Mouse Clicks
    elif "left click" in command:
        pyautogui.click()
        speak("Left click")
        return True

    elif "right click" in command:
        pyautogui.click(button='right')
        speak("Right click")
        return True

    elif "double click" in command:
        pyautogui.doubleClick()
        speak("Double click")
        return True

    # 🔁 Scroll
    elif "scroll up" in command:
        pyautogui.scroll(500)
        speak("Scrolling up")
        return True

    elif "scroll down" in command:
        pyautogui.scroll(-500)
        speak("Scrolling down")
        return True

    # 🧠 Typing
    elif "type" in command:
        text = command.replace("type", "").strip()
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        speak("Typed")
        return True

    elif "press enter" in command:
        pyautogui.press("enter")
        speak("Pressed enter")
        return True

    elif "press tab" in command:
        pyautogui.press("tab")
        speak("Pressed tab")
        return True

    elif "press key" in command:
        key = command.replace("press key", "").strip()
        pyautogui.press(key)
        speak(f"Pressed {key}")
        return True

    # 🖱️ Drag and Drop
    elif "start drag" in command:
        drag_mode["start"] = pyautogui.position()
        pyautogui.mouseDown()
        drag_mode["active"] = True
        speak("Started dragging")
        return True

    elif "end drag" in command:
        pyautogui.mouseUp()
        drag_mode["active"] = False
        speak("Dropped")
        return True

    # 🪟 Window Controls
    elif "switch window" in command or "alt tab" in command:
        pyautogui.keyDown("alt")
        pyautogui.press("tab")
        pyautogui.keyUp("alt")
        speak("Switched window")
        return True

    elif "show desktop" in command or "windows d" in command:
        pyautogui.hotkey("win", "d")
        speak("Showing desktop")
        return True

    elif "close window" in command:
        pyautogui.hotkey("alt", "f4")
        speak("Window closed")
        return True

    elif "minimize window" in command:
        pyautogui.hotkey("win", "down")
        speak("Window minimized")
        return True

    elif "maximize window" in command:
        pyautogui.hotkey("win", "up")
        speak("Window maximized")
        return True

    elif "snap left" in command:
        pyautogui.hotkey("win", "left")
        speak("Snapped window left")
        return True

    elif "snap right" in command:
        pyautogui.hotkey("win", "right")
        speak("Snapped window right")
        return True

    return False
