# === lavis.py (Fixed & Aligned) ===
import os
import sys
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
from LAVIS.jarvis.commands.apps import open_windows_app
from LAVIS.jarvis.voice.recognizer import start_background_listening, stop_background_listening, command_queue
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.web.fallback import handle_fallback

# === HUD Integration ===
from jarvis_hud.main import SciFiApp, update_hud_text

from LAVIS.hud_display import show_fallback_in_hud, show_hud_reply, show_hud_command
from LAVIS.jarvis.commands.apps import get_start_menu_apps

# === CONFIG ===
WAKE_WORD = "jarvis"
WAKE_UP_PHRASE = "jarvis wake up"
SLEEP_PHRASE = "jarvis sleep"
AUDIO_STARTUP = "lavis start.mp3"

session_state = "sleep"  # States: sleep, normal, conversation, learning
get_start_menu_apps()  # 🔁 Preload app list into cache
start_background_listening()
def start_hud():
    app = SciFiApp()
    app.run()

def hud_speak(message: str):
    show_hud_reply(message)
    speak(message)

def welcome():
    if os.path.exists(AUDIO_STARTUP):
        playsound(AUDIO_STARTUP)
    msg = "Presence confirmed. Let’s make things happen when you're ready."
    hud_speak(msg)

def extract_app_name(command: str) -> str:
    match = re.search(r"open (.+)", command)
    return match.group(1).strip() if match else ""

def check_wake_phrase(text):
    global session_state
    text = text.lower()
    if WAKE_UP_PHRASE in text:
        session_state = "normal"
        hud_speak("systems operational. Awaiting your instructions.")
        return True
    elif SLEEP_PHRASE in text:
        session_state = "sleep"
        hud_speak("Okay sir, I’m going to sleep.")
        return True
    return False

def main():
    global session_state

    if not os.path.exists("jarvis.sqlite3"):
        train_chatbot()

    welcome()
    session_state = "sleep"
    start_background_listening()

    while True:
        try:
            if not command_queue.empty():
                input_text = command_queue.get()
                print("🎤 Heard:", input_text)
                show_hud_command(input_text, typing=False)
                time.sleep(0.05)

                if check_wake_phrase(input_text):
                    continue

                if session_state == "sleep":
                    continue

                command = re.sub(rf"\b{WAKE_WORD}\b", "", input_text, flags=re.IGNORECASE).strip()
                if not command:
                    command = input_text

                print("📝 Command:", command)
                intent = detect_intent(command)

                if intent == "command":
                    if handle_command(command):
                        show_hud_reply("Executed system command.")
                        continue
                    app_name = extract_app_name(command)
                    if app_name and open_windows_app(app_name):
                        show_hud_reply(f"Opening {app_name}")
                        continue
                    hud_speak(f"Sorry sir, I couldn't process the command: {command}")

                elif intent == "explorer":
                    from jarvis.commands.explorer import handle_explorer
                    if handle_explorer(command):
                        show_hud_reply("Handled file explorer command.")
                        continue

                elif intent == "input_control":
                    from jarvis.commands.input_control import handle_input_control
                    if handle_input_control(command):
                        show_hud_reply("Handled input control.")
                        continue

                elif intent == "learning":
                    session_state = "learning"
                    show_hud_reply("Entering learning mode...")
                    learning_mode(command)
                    show_hud_reply("Exiting learning mode.")
                    session_state = "normal"

                elif intent == "conversation":
                    if len(command.strip().split()) < 3:
                        print("🛑 Too short to trigger conversation mode.")
                        show_hud_reply("I didn't catch a full sentence. Please repeat.")
                        continue
                    session_state = "conversation"
                    show_hud_reply("Responding to conversation...")
                    # You can insert chatbot logic here if desired
                    continue

                elif handle_fallback(command):
                    from jarvis.web.fallback import last_fallback_response
                    show_fallback_in_hud(last_fallback_response)
                    show_hud_reply("Conversation done.")
                    session_state = "normal"
                    continue

                else:
                    show_hud_reply("Fallback handler responding...")
                    if handle_fallback(command):
                        from jarvis.web.fallback import last_fallback_response
                        show_fallback_in_hud(last_fallback_response)
                        session_state = "normal"
                        continue

            else:
                time.sleep(0.1)

        except KeyboardInterrupt:
            stop_background_listening()
            hud_speak("Jarvis shutting down.")
            break

        except Exception as e:
            logging.exception("❌ Error:")
            update_hud_text(str(e), category="error")
            speak("Something went wrong.")

if __name__ == "__main__":
    try:
        hud_thread = threading.Thread(target=start_hud, daemon=True)
        hud_thread.start()
        main()
    except Exception as e:
        logging.exception("🔥 Startup error:")
        update_hud_text(str(e), category="error")
        speak("There was a problem starting up.")
