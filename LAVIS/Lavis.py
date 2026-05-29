# Lavis.py (Polished)

import os, sys, re, time, logging, threading, datetime

# Mute Kivy's verbose debug logs
os.environ["KIVY_LOG_LEVEL"] = "warning"

# Add the parent directory to sys.path to allow absolute imports starting with 'LAVIS.'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import LLM fallback first to avoid SpeechBrain lazy-import conflict with torch/transformers
from LAVIS.jarvis.llm.llm_ask import LLMFallback

from fuzzywuzzy import fuzz
import random
from playsound import playsound
from kivy.clock import Clock

from LAVIS.jarvis.voice.speaker import speak
from LAVIS.jarvis.commands.commands import handle_command
from LAVIS.jarvis.apps.chatbot import chatbot, train_chatbot
from LAVIS.jarvis.commands.apps import open_windows_app, get_start_menu_apps
from LAVIS.jarvis.voice.recognizer import (
    start_background_listening,
    stop_background_listening,
    command_queue,
    resume_listening,
)
from LAVIS.jarvis.nlp.intent_detector import detect_intent, match_hardcoded_command, resolve_app_name
from LAVIS.jarvis.web.fallback import handle_fallback
from LAVIS.jarvis.commands.explorer import handle_explorer
from LAVIS.jarvis.commands.input_control import handle_input_control
from LAVIS.jarvis.apps.userai.lavish_messages import AssistantCrushMessages
from LAVIS.utils.hud_utils import get_hud_controller
from LAVIS.jarvis.network import start_network_watcher

try:
    from jarvis_hud.main import update_hud_text, update_hud_status, hud_interface
except ImportError:
    def update_hud_text(text, category="info", typing=True): print(f"[{category.upper()}] {text}")
    def update_hud_status(status): print(f"[HUD STATUS] {status}")
    hud_interface = None

try:
    from LAVIS.hud_display import show_fallback_in_hud, show_hud_reply, show_hud_command
except ImportError:
    def show_hud_reply(text, typing=True): print(f"[REPLY] {text}")
    def show_hud_command(text, typing=True): print(f"[COMMAND] {text}")
    def show_fallback_in_hud(text): print(f"[FALLBACK] {text}")

WAKE_WORD = "Lavish"
WAKE_WORD_PATTERN = r"\b(lavis|lavish|levies|lobbies|ladies|labs)\b"
WAKE_UP_PHRASE = "hello Lavish"
SLEEP_PHRASE = "Lavish sleep"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_STARTUP_CANDIDATES = [
    os.path.join(BASE_DIR, "lavis_start.mp3"),
    os.path.join(BASE_DIR, "lavis start.mp3"),
]
USER_NAME = "Lala"


class LavisCore:
    def __init__(self):
        self.session_state = "sleep"
        self.control_mode = "normal"
        self.last_wake_time = 0
        self.in_conversation = False  # ✅ tracks if user is mid-chat

        # LLM fallback handler
        self.llm = LLMFallback()

        try:
            from jarvis_hud.components.hud_controller import HUDController
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
        def speak_thread():
            try:
                Clock.schedule_once(lambda dt: show_hud_reply("...", typing=True), 0)
                time.sleep(0.3)
                Clock.schedule_once(lambda dt: show_hud_reply(message), 0)
                speak(message)
            except Exception as e:
                # ✅ show HUD error if speech fails
                print(f"[HUD Speak Error] {e}")
                Clock.schedule_once(lambda dt: show_hud_reply("⚠️ Speech failed."), 0)
        threading.Thread(target=speak_thread, daemon=True).start()

    def welcome(self):
        try:
            startup_audio = next((p for p in AUDIO_STARTUP_CANDIDATES if os.path.exists(p)), None)
            if startup_audio:
                playsound(startup_audio)

            welcome_msg = random.choice([
                f"I'm here, {USER_NAME}. Say hello Lavis when you need me.",
                f"Lavis is online, {USER_NAME}. I'll stay quiet until you call.",
                "Presence confirmed. I'm ready when you are.",
            ])

            self.hud_speak(welcome_msg)

        except Exception as e:
            print(f"[Welcome Error] {e}")

    def generate_greeting(self):
        current_hour = datetime.datetime.now().hour
        if 5 <= current_hour < 12:
            choices = [f"Good morning, {USER_NAME}. I'm listening.", f"Morning, {USER_NAME}. What are we doing first?"]
        elif 12 <= current_hour < 17:
            choices = [f"Good afternoon, {USER_NAME}. I'm with you.", f"Afternoon, {USER_NAME}. Tell me what you need."]
        elif 17 <= current_hour < 21:
            choices = [f"Good evening, {USER_NAME}. I'm listening.", f"Evening, {USER_NAME}. What's on your mind?"]
        else:
            choices = [self.crush.random_late_night_greeting(), f"I'm here, {USER_NAME}. Go ahead."]
        return random.choice(choices)

    def check_wake_phrase(self, text):
        try:
            text = text.lower().strip()
            if re.search(r"\b(hello|hi)\s+(lavis|lavish|levies|lobbies|ladies|labs)\b", text) or fuzz.ratio(text, WAKE_UP_PHRASE) > 85:
                if self.session_state == "sleep":
                    self.session_state = "normal"
                    self.last_wake_time = time.time()
                    Clock.schedule_once(lambda dt: update_hud_status("Online"), 0)
                    greeting = self.generate_greeting()
                    self.hud_speak(greeting)
                else:
                    reply = random.choice([
                        "Yes? I'm right here.",
                        "You called me?",
                        "Standing by.",
                        f"How can I help, {USER_NAME}?",
                        "I'm listening."
                    ])
                    self.hud_speak(reply)
                return True

            elif re.search(r"\b(jarvis\s+)?(sleep|go to sleep|shutdown|rest)\b", text):
                self.session_state = "sleep"
                self.in_conversation = False
                self.hud_speak(f"Okay {USER_NAME}, I'm going to sleep now 🛌")
                Clock.schedule_once(lambda dt: update_hud_status("Sleep"), 0)
                return True

            return False
        except Exception as e:
            print(f"[Wake Phrase Error] {e}")
            return False

    def extract_app_name(self, command: str) -> str:
        match = re.search(r"\b(open|start|launch|run)\b\s+(.+)", command.lower())
        return match.group(2).strip() if match else ""

    def handle_input(self, input_text, skip_echo=False):  # ✅ skip_echo from recognizer barge-in
        try:
            if self.check_wake_phrase(input_text):
                return

            if self.session_state == "sleep":
                return

            if self.session_state == "normal" and time.time() - self.last_wake_time < 1.2:
                print("⏳ Delaying command due to wake-up buffer")
                return

            if not input_text or not input_text.strip():
                return

            command = re.sub(WAKE_WORD_PATTERN, "", input_text, flags=re.IGNORECASE).strip() or input_text
            if not skip_echo:  # ✅ avoid double-echo if recognizer already displayed
                if self.hud_controller and hasattr(self.hud_controller, "update"):
                    Clock.schedule_once(lambda dt: self.hud_controller.update(command, category="command", typing=True), 0)
                else:
                    Clock.schedule_once(lambda dt: show_hud_command(command), 0)

            command_lower = command.lower().strip()

            # Conversation flagging
            self.in_conversation = True

            # (control mode logic unchanged…)
            # [ ... same as before ... ]
            
            # Control modes
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
                Clock.schedule_once(lambda dt: update_hud_status("Master Control"), 0)
                return

            if "deactivate master control" in command_lower:
                self.control_mode = "normal"
                self.hud_speak("Master control deactivated. Full assistant is back online.")
                Clock.schedule_once(lambda dt: update_hud_status("Online"), 0)
                return

            if "activate restricted mode" in command_lower:
                self.control_mode = "restricted"
                self.hud_speak("Restricted mode activated. Only apps and file explorer are allowed.")
                Clock.schedule_once(lambda dt: update_hud_status("Restricted"), 0)
                return

            if "deactivate restricted mode" in command_lower:
                self.control_mode = "normal"
                self.hud_speak("Restricted mode deactivated.")
                Clock.schedule_once(lambda dt: update_hud_status("Online"), 0)
                return

            offline_handler = match_hardcoded_command(command_lower)
            if offline_handler:
                offline_handler()
                Clock.schedule_once(lambda dt: show_hud_reply("Offline command matched."), 0)
                return

            if self.control_mode == "master_control":
                from LAVIS.jarvis.master_controll.command_handler import handle_voice_command
                if handle_voice_command(command): return
                if handle_explorer(command):
                    Clock.schedule_once(lambda dt: show_hud_reply("Handled file explorer command."), 0)
                    return
                self.hud_speak("Command not allowed in master control mode.")
                return

            if self.control_mode == "restricted":
                if command.startswith("open "):
                    app_name = self.extract_app_name(command)
                    if self.session_state != "normal":
                        self.hud_speak("Assistant is not awake yet.")
                        return
                    if app_name and open_windows_app(app_name):
                        Clock.schedule_once(lambda dt: show_hud_reply(f"Opening {app_name}"), 0)
                    else:
                        self.hud_speak(f"Restricted: Failed to open {app_name}")
                    return
                elif handle_explorer(command):
                    Clock.schedule_once(lambda dt: show_hud_reply("Handled file explorer command."), 0)
                    return
                self.hud_speak("Command not allowed in restricted mode.")
                return

            if self.session_state != "normal":
                self.hud_speak("Assistant is not awake yet.")
                return

            # NLP and fallback
            intent = detect_intent(command)
            print(f"🧠 Intent Detected: {intent}")

            if intent == "command":
                handled = handle_command(command)
                app_name = self.extract_app_name(command) or resolve_app_name(command)
                if app_name and open_windows_app(app_name):
                    Clock.schedule_once(lambda dt: show_hud_reply(f"Opening {app_name}"), 0)
                    return
                if handled:
                    Clock.schedule_once(lambda dt: show_hud_reply("Executed system command."), 0)
                    return
                self.hud_speak(f"Sorry, I couldn't process the command: {command}")
                return

            if intent == "input_control" and handle_input_control(command):
                Clock.schedule_once(lambda dt: show_hud_reply("Handled input control."), 0)
                return

            if intent == "explorer" and handle_explorer(command):
                Clock.schedule_once(lambda dt: show_hud_reply("Handled file explorer command."), 0)
                return
            if intent == "network":
                from LAVIS.jarvis.commands.network_bluetooth import handle_network_bluetooth
                if handle_network_bluetooth(command):
                    Clock.schedule_once(lambda dt: show_hud_reply("Network/Bluetooth command handled."), 0)
                    return

            # Conversational fallback
            try:
                Clock.schedule_once(lambda dt: show_hud_reply("Let me think about that..."), 0)
                threading.Thread(
                    target=lambda: self.hud_speak(self.llm.ask(command)),
                    daemon=True
                ).start()
            except Exception:
                threading.Thread(target=lambda: handle_fallback(command), daemon=True).start()

        except Exception as e:
            logging.exception("⚠️ Runtime error in main loop:")
            Clock.schedule_once(lambda dt: update_hud_text(str(e), category="error"), 0)
            speak("Something went wrong during input processing.")

class LavisRunner:
    def __init__(self):
        self.core = LavisCore()

        # 🔗 Give handle_system access to this runner/core
        from LAVIS.jarvis.commands import system
        system.set_core_instance(self)

    def run(self):
        while True:
            try:
                if not os.path.exists("jarvis.sqlite3"):
                    train_chatbot()
                get_start_menu_apps(force_reload=True)
                self.core.welcome()
                resume_listening()
                start_background_listening()
                start_network_watcher()

                while True:
                    try:
                        if not command_queue.empty():
                            input_text = command_queue.get()
                            Clock.schedule_once(
                                lambda dt: self.core.hud_controller.type_live_text(input_text), 
                                0
                            )
                            print("🎤 Heard:", input_text)
                            self.core.handle_input(input_text)
                        else:
                            time.sleep(0.1)
                    except Exception as e:
                        logging.exception("⚠️ Runtime error in inner loop:")
                        Clock.schedule_once(lambda dt: update_hud_text(str(e), category="error"), 0)
                        speak("Something went wrong during input processing.")
            except KeyboardInterrupt:
                stop_background_listening()
                self.core.hud_speak("Jarvis shutting down.")
                break
            except Exception as e:
                logging.exception("❌ Error in outer main loop:")
                Clock.schedule_once(lambda dt: update_hud_text(str(e), category="error"), 0)
                speak("Something went wrong. Restarting...")
                time.sleep(1)

def main():
    LavisRunner().run()

if __name__ == "__main__":
    print("🧠 Running Lavis in console-only mode")
    def show_hud_command(text, typing=True): print(f"🧠 [COMMAND] {text}")
    def show_hud_reply(text, typing=True): print(f"🧠 [REPLY] {text}")
    def show_fallback_in_hud(text): print(f"🧠 [FALLBACK] {text}")
    def update_hud_text(text, category="info", typing=True): print(f"🧠 [{category.upper()}] {text}")
    main()
