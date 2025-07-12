# Lavis.py (Final Full Version with Fixed Module Import)

import os
import re
import time
import logging
import threading
from playsound import playsound
from fuzzywuzzy import fuzz

from LAVIS.jarvis.voice.speaker import speak
from LAVIS.jarvis.commands.commands import handle_command
from LAVIS.jarvis.apps.chatbot import chatbot, train_chatbot
from LAVIS.jarvis.memory.learning_mode import learning_mode
from LAVIS.jarvis.commands.apps import open_windows_app, get_start_menu_apps
from LAVIS.jarvis.voice.recognizer import start_background_listening, stop_background_listening, command_queue
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.web.fallback import handle_fallback

from jarvis_hud.main import update_hud_text, update_hud_status, hud_interface
from LAVIS.hud_display import show_fallback_in_hud, show_hud_reply, show_hud_command
from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller

# ✅ FIX: Update these two lines
from LAVIS.jarvis.commands.explorer import handle_explorer
from LAVIS.jarvis.commands.input_control import handle_input_control

WAKE_WORD = "jarvis"
WAKE_UP_PHRASE = "jarvis wake up"
SLEEP_PHRASE = "jarvis sleep"
AUDIO_STARTUP = r"\LAVIS\lavis start.mp3"

class LavisCore:
    def __init__(self):
        self.session_state = "sleep"
        self.control_mode = "normal"

        if hud_interface:
            from jarvis_hud.components.hud_controller import HUDController
            self.hud_controller = HUDController(hud_interface)
        else:
            from LAVIS.utils.console_hud import ConsoleHUDController
            self.hud_controller = ConsoleHUDController()

        update_hud_status("sleep")

    def hud_speak(self, message: str):
        show_hud_reply("...", typing=True)
        time.sleep(0.3)
        show_hud_reply(message)
        speak(message)

    def welcome(self):
        if os.path.exists(AUDIO_STARTUP):
            playsound(AUDIO_STARTUP)
        self.hud_speak("Presence confirmed. Let's make things happen when you're ready.")

    def check_wake_phrase(self, text):
        text = text.lower()
        if WAKE_UP_PHRASE in text:
            self.session_state = "normal"
            update_hud_status("Online")
            self.hud_speak("Systems operational. Awaiting your instructions.")
            return True
        elif SLEEP_PHRASE in text:
            self.session_state = "sleep"
            self.hud_speak("Okay sir, I'm going to sleep.")
            return True
        return False

    def extract_app_name(self, command: str) -> str:
        match = re.search(r"open (.+)", command)
        return match.group(1).strip() if match else ""

    def handle_input(self, input_text):
        if self.check_wake_phrase(input_text):
            return

        if self.session_state == "sleep":
            return

        command = re.sub(rf"\b{WAKE_WORD}\b", "", input_text, flags=re.IGNORECASE).strip() or input_text
        self.hud_controller.update(command, category="command", typing=True)

        command_lower = command.lower().strip()

        if "activate master control" in command_lower:
            self.control_mode = "master_control"
            self.hud_speak("Master control activated. You can now control screen and apps only.")
            update_hud_status("Master Control")
            return

        elif "deactivate master control" in command_lower:
            self.control_mode = "normal"
            self.hud_speak("Master control deactivated. Full assistant is back online.")
            update_hud_status("Online")
            return

        elif "activate restricted mode" in command_lower:
            self.control_mode = "restricted"
            self.hud_speak("Restricted mode activated. Only apps and file explorer are allowed.")
            update_hud_status("Restricted")
            return

        elif "deactivate restricted mode" in command_lower:
            self.control_mode = "normal"
            self.hud_speak("Restricted mode deactivated.")
            update_hud_status("Online")
            return

        if self.control_mode == "master_control":
            from LAVIS.jarvis.master_controll.command_handler import handle_voice_command
            if handle_voice_command(command):
                return
            if handle_explorer(command):
                show_hud_reply("Handled file explorer command.")
                return
            self.hud_speak("Command not allowed in master control mode.")
            return

        if self.control_mode == "restricted":
            if command.startswith("open "):
                app_name = self.extract_app_name(command)
                if app_name and open_windows_app(app_name):
                    show_hud_reply(f"Opening {app_name}")
                    return
            elif handle_explorer(command):
                show_hud_reply("Handled file explorer command.")
                return
            self.hud_speak("Command not allowed in restricted mode.")
            return

        intent = detect_intent(command)

        if intent == "command":
            if handle_command(command):
                show_hud_reply("Executed system command.")
                return
            app_name = self.extract_app_name(command)
            if app_name and open_windows_app(app_name):
                show_hud_reply(f"Opening {app_name}")
                return
            self.hud_speak(f"Sorry sir, I couldn't process the command: {command}")

      

        elif intent == "input_control":
            if handle_input_control(command):
                show_hud_reply("Handled input control.")

        elif intent == "learning":
            self.session_state = "learning"
            show_hud_reply("Entering learning mode...")
            learning_mode(command)
            update_hud_status("Learning")
            show_hud_reply("Exiting learning mode.")
            self.session_state = "normal"

        elif intent == "conversation":
            if len(command.strip().split()) < 3:
                show_hud_reply("I didn't catch a full sentence. Please repeat.")
                return
            self.session_state = "conversation"
            update_hud_status("normal")
            show_hud_reply("Responding to conversation...")

        else:
            show_hud_reply("Trying to find an answer...")

            def run_fallback():
                response = handle_fallback(command)
                if response:
                    self.session_state = "normal"
                self.hud_controller.update(response or "Sorry, I couldn't find a response.", category="reply", typing=True)

            threading.Thread(target=run_fallback, daemon=True).start()

class LavisRunner:
    def __init__(self):
        self.core = LavisCore()

    def run(self):
        try:
            if not os.path.exists("jarvis.sqlite3"):
                train_chatbot()

            get_start_menu_apps()
            self.core.welcome()
            start_background_listening()

            while True:
                if not command_queue.empty():
                    input_text = command_queue.get()
                    self.core.hud_controller.type_live_text(input_text)
                    print("\U0001f3a4 Heard:", input_text)
                    self.core.handle_input(input_text)
                else:
                    time.sleep(0.1)

        except KeyboardInterrupt:
            stop_background_listening()
            self.core.hud_speak("Jarvis shutting down.")

        except Exception as e:
            logging.exception("\u274c Error in main loop:")
            update_hud_text(str(e), category="error")
            speak("Something went wrong.")


def main():
    LavisRunner().run()

if __name__ == "__main__":
    print("\U0001f9ea Running Lavis in console-only mode (no HUD)")

    def show_hud_command(text, typing=True): print(f"\U0001f9ea [COMMAND] {text}")
    def show_hud_reply(text, typing=True): print(f"\U0001f9ea [REPLY] {text}")
    def show_fallback_in_hud(text): print(f"\U0001f9ea [FALLBACK] {text}")
    def update_hud_text(text, category="info", typing=True): print(f"\U0001f9ea [{category.upper()}] {text}")

    main()
