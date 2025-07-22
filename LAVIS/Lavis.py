import os, re, time, logging, threading, datetime
from fuzzywuzzy import fuzz
import random
from playsound import playsound

from LAVIS.jarvis.voice.speaker import speak
from LAVIS.jarvis.commands.commands import handle_command
from LAVIS.jarvis.apps.chatbot import chatbot, train_chatbot
from LAVIS.jarvis.commands.apps import open_windows_app, get_start_menu_apps
from LAVIS.jarvis.voice.recognizer import start_background_listening, stop_background_listening, command_queue
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.web.fallback import handle_fallback, load_config, detect_emotion

from jarvis_hud.main import update_hud_text, update_hud_status, hud_interface
from LAVIS.hud_display import show_fallback_in_hud, show_hud_reply, show_hud_command
from jarvis_hud.components.hud_controller import HUDController
from LAVIS.utils.hud_utils import get_hud_controller

from LAVIS.jarvis.commands.explorer import handle_explorer
from LAVIS.jarvis.commands.input_control import handle_input_control
from LAVIS.jarvis.apps.userai.lavish_messages import AssistantCrushMessages

WAKE_WORD = "Lavish"
WAKE_UP_PHRASE = "hello Lavish"
SLEEP_PHRASE = "Lavish sleep"
AUDIO_STARTUP = os.path.abspath("LAVIS/lavis_start.mp3")
USER_NAME = "Lala"

class LavisCore:
    def __init__(self):
        self.session_state = "sleep"
        self.control_mode = "normal"
        try:
            self.hud_controller = HUDController(hud_interface) if hud_interface else self.get_fallback_console_hud()
        except Exception:
            self.hud_controller = self.get_fallback_console_hud()
        self.crush = AssistantCrushMessages(USER_NAME)
        update_hud_status("Sleep")

    def get_fallback_console_hud(self):
        try:
            from LAVIS.utils.console_hud import ConsoleHUDController
            return ConsoleHUDController()
        except Exception as e:
            print(f"❌ Console HUD failed: {e}")
            return None

    def hud_speak(self, message: str):
        try:
            show_hud_reply("...", typing=True)
            time.sleep(0.3)
            show_hud_reply(message)
            speak(message)
        except Exception as e:
            print(f"[HUD Speak Error] {e}")

    def welcome(self):
        try:
            if os.path.exists(AUDIO_STARTUP):
                playsound(AUDIO_STARTUP)
            self.hud_speak("Presence confirmed. Let's make things happen when you're ready.")
        except Exception as e:
            print(f"[Welcome Error] {e}")

    def check_wake_phrase(self, text):
        try:
            text = text.lower().strip()

            if re.search(r"\b(hello|hi)\s+(Lavis|Lavish|levies|lobbies|ladies|labs)\b", text) or fuzz.ratio(text, WAKE_UP_PHRASE) > 85:
                if self.session_state == "sleep":
                    self.session_state = "normal"
                    update_hud_status("Online")
                    current_hour = datetime.datetime.now().hour
                    if 5 <= current_hour < 12:
                        greeting = f"Good morning, {USER_NAME} "
                    elif 12 <= current_hour < 17:
                        greeting = f"Good afternoon, {USER_NAME} "
                    elif 17 <= current_hour < 21:
                        greeting = f"Good evening, {USER_NAME} "
                    else:
                        greeting = self.crush.random_late_night_greeting()
                    self.hud_speak(f"{greeting} Welcome back!")
                else:
                    self.hud_speak(random.choice([
                        "Yes? I'm right here.",
                        "You called me?",
                        "Standing by!",
                        f"How can I help, {USER_NAME}?",
                        "Reporting for duty!"
                    ]))
                return True

            elif re.search(r"\b(jarvis\s+)?(sleep|go to sleep|shutdown|rest)\b", text):
                self.session_state = "sleep"
                self.hud_speak(f"Okay {USER_NAME}, I'm going to sleep now 🛌")
                update_hud_status("Sleep")
                return True

            return False
        except Exception as e:
            print(f"[Wake Phrase Error] {e}")
            return False

    def extract_app_name(self, command: str) -> str:
        match = re.search(r"\b(open|start|launch|run)\b\s+(.+)", command.lower())
        return match.group(2).strip() if match else ""

   # === handle_input() Upgrade in LavisCore ===

    def handle_input(self, input_text):
        try:
            if self.check_wake_phrase(input_text):
                return

            if self.session_state == "sleep":
                return

            if len(input_text.strip().split()) < 2 and "?" not in input_text:
                show_hud_reply("Please say a full sentence.")
                return

            command = re.sub(rf"\b{WAKE_WORD}\b", "", input_text, flags=re.IGNORECASE).strip() or input_text
            self.hud_controller.update(command, category="command", typing=True)
            command_lower = command.lower().strip()

            # === Mode controls ===
            if "activate hand control" in command_lower:
                self.hud_speak("Activating hand control mode. Use your hand to control the system.")
                try:
                    from LAVIS.jarvis.master_controll.hand_controller import HandControl
                    threading.Thread(target=HandControl().run, daemon=True).start()
                except Exception as e:
                    self.hud_speak("Error activating hand control.")
                    print(f"[Hand Control Error] {e}")
                return

            if "activate master control" in command_lower:
                self.control_mode = "master_control"
                self.hud_speak("Master control activated. You can now control screen and apps only.")
                update_hud_status("Master Control")
                return

            if "deactivate master control" in command_lower:
                self.control_mode = "normal"
                self.hud_speak("Master control deactivated. Full assistant is back online.")
                update_hud_status("Online")
                return

            if "activate restricted mode" in command_lower:
                self.control_mode = "restricted"
                self.hud_speak("Restricted mode activated. Only apps and file explorer are allowed.")
                update_hud_status("Restricted")
                return

            if "deactivate restricted mode" in command_lower:
                self.control_mode = "normal"
                self.hud_speak("Restricted mode deactivated.")
                update_hud_status("Online")
                return

            # === Offline hardcoded command match ===
            from LAVIS.jarvis.nlp.intent_detector import match_hardcoded_command, resolve_app_name
            offline_handler = match_hardcoded_command(command_lower)
            if offline_handler:
                offline_handler()
                show_hud_reply("Offline command matched.")
                return

            # === Control mode limits ===
            if self.control_mode == "master_control":
                from LAVIS.jarvis.master_controll.command_handler import handle_voice_command
                if handle_voice_command(command): return
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
                    else:
                        self.hud_speak(f"Restricted: Failed to open {app_name}")
                    return
                elif handle_explorer(command):
                    show_hud_reply("Handled file explorer command.")
                    return
                self.hud_speak("Command not allowed in restricted mode.")
                return

            # === Intent classification ===
            from LAVIS.jarvis.nlp.intent_detector import detect_intent
            intent = detect_intent(command)
            print(f"🧠 Intent Detected: {intent}")

            if intent == "command":
                from LAVIS.jarvis.commands.commands import handle_command
                handled = handle_command(command)
                app_name = self.extract_app_name(command) or resolve_app_name(command)
                if app_name and open_windows_app(app_name):
                    show_hud_reply(f"Opening {app_name}")
                    return
                if handled:
                    show_hud_reply("Executed system command.")
                    return
                self.hud_speak(f"Sorry sir, I couldn't process the command: {command}")
                return

            if intent == "input_control" and handle_input_control(command):
                show_hud_reply("Handled input control.")
                return

            if intent == "explorer" and handle_explorer(command):
                show_hud_reply("Handled file explorer command.")
                return

            if intent == "network":
                from LAVIS.jarvis.commands.network_bluetooth import handle_network_bluetooth
                if handle_network_bluetooth(command):
                    show_hud_reply("Network/Bluetooth command handled.")
                    return

            if intent == "conversation":
                show_hud_reply("Let me think about that...")
                def run_fallback():
                    try:
                        from LAVIS.jarvis.web.fallback import handle_fallback
                        response = handle_fallback(command)
                        self.session_state = "normal"
                        if isinstance(response, str) and response.strip():
                            self.hud_controller.update(response, category="reply", typing=True)
                    except Exception as e:
                        print(f"[Fallback Error] {e}")
                threading.Thread(target=run_fallback, daemon=True).start()
                return

            # Default fallback
            show_hud_reply("Trying to find an answer...")
            def run_final_fallback():
                try:
                    from LAVIS.jarvis.web.fallback import handle_fallback
                    response = handle_fallback(command)
                    self.session_state = "normal"
                    self.hud_controller.update(response or "Sorry, I couldn't find a response.", category="reply", typing=True)
                except Exception as e:
                    print(f"[Fallback Error] {e}")
            threading.Thread(target=run_final_fallback, daemon=True).start()

        except Exception as e:
            print(f"[Handle Input Error] {e}")

class LavisRunner:
    def __init__(self):
        self.core = LavisCore()

    def run(self):
        try:
            if not os.path.exists("jarvis.sqlite3"):
                train_chatbot()

            get_start_menu_apps(force_reload=True)
            self.core.welcome()
            start_background_listening()

            while True:
                try:
                    if not command_queue.empty():
                        input_text = command_queue.get()
                        self.core.hud_controller.type_live_text(input_text)
                        print("🎤 Heard:", input_text)
                        self.core.handle_input(input_text)
                    else:
                        time.sleep(0.1)
                except Exception as e:
                    logging.exception("⚠️ Runtime error in main loop:")
                    update_hud_text(str(e), category="error")
                    speak("Something went wrong during input processing.")

        except KeyboardInterrupt:
            stop_background_listening()
            self.core.hud_speak("Jarvis shutting down.")
        except Exception as e:
            logging.exception("❌ Error in outer main loop:")
            update_hud_text(str(e), category="error")
            speak("Something went wrong.")

def main():
    LavisRunner().run()

if __name__ == "__main__":
    print("🧠 Running Lavis in console-only mode")
    def show_hud_command(text, typing=True): print(f"🧠 [COMMAND] {text}")
    def show_hud_reply(text, typing=True): print(f"🧠 [REPLY] {text}")
    def show_fallback_in_hud(text): print(f"🧠 [FALLBACK] {text}")
    def update_hud_text(text, category="info", typing=True): print(f"🧠 [{category.upper()}] {text}")
    main()
