# lavis.py (GPT-4 improved session controller with HUD integration)
import os
import sys
import re
import time
import logging
import threading
from playsound import playsound
from fuzzywuzzy import fuzz

from jarvis.voice.speaker import speak
from jarvis.commands.commands import handle_command
from jarvis.apps.chatbot import chatbot, train_chatbot
from jarvis.memory.learning_mode import learning_mode
from jarvis.commands.apps import open_windows_app
from jarvis.voice.recognizer import start_background_listening, stop_background_listening, command_queue
from jarvis.nlp.intent_detector import detect_intent
from jarvis.web.fallback import handle_fallback

# === HUD Integration ===
sys.path.append(r"C:\Users\baish\Downloads\jarvis_hud\jarvis_hud")
from main import SciFiApp, update_hud_text
# === CONFIG ===
WAKE_WORD = "jarvis"
WAKE_UP_PHRASE = "jarvis wake up"
SLEEP_PHRASE = "jarvis sleep"
AUDIO_STARTUP = "lavis start.mp3"

session_state = "sleep"  # States: sleep, normal, conversation, learning


def start_hud():
    """Start Kivy HUD in a separate thread"""
    app = SciFiApp()
    app.run()


def welcome():
    if os.path.exists(AUDIO_STARTUP):
        playsound(AUDIO_STARTUP)
    msg = "Jarvis is online. Say 'Jarvis wake up' to activate me."
    update_hud_text(msg, category="reply")
    speak(msg)


def extract_app_name(command: str) -> str:
    match = re.search(r"open (.+)", command)
    return match.group(1).strip() if match else ""


def check_wake_phrase(text):
    global session_state
    text = text.lower()
    if WAKE_UP_PHRASE in text:
        session_state = "normal"
        msg = "Yes sir, I am ready."
        update_hud_text(msg, category="reply")
        speak(msg)
        return True
    elif SLEEP_PHRASE in text:
        session_state = "sleep"
        msg = "Okay sir, I’m going to sleep."
        update_hud_text(msg, category="reply")
        speak(msg)
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
                update_hud_text(input_text, category="command")

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
                        update_hud_text("Executed system command.", category="reply")
                        continue
                    app_name = extract_app_name(command)
                    if app_name and open_windows_app(app_name):
                        update_hud_text(f"Opening {app_name}", category="reply")
                        continue
                    msg = f"Sorry sir, I couldn't process the command: {command}"
                    update_hud_text(msg, category="error")
                    speak(msg)

                elif intent == "explorer":
                    from jarvis.commands.explorer import handle_explorer
                    if handle_explorer(command):
                        update_hud_text("Handled file explorer command.", category="reply")
                        continue

                elif intent == "input_control":
                    from jarvis.commands.input_control import handle_input_control
                    if handle_input_control(command):
                        update_hud_text("Handled input control.", category="reply")
                        continue

                elif intent == "learning":
                    session_state = "learning"
                    update_hud_text("Entering learning mode...", category="reply")
                    learning_mode(command)
                    update_hud_text("Exiting learning mode.", category="reply")
                    session_state = "normal"

                elif intent == "conversation":
                    session_state = "conversation"
                    update_hud_text("Responding to conversation...", category="reply")
                    handle_fallback(command)
                    update_hud_text("Conversation done.", category="reply")
                    session_state = "normal"

                else:
                    update_hud_text("Fallback handler responding...", category="reply")
                    handle_fallback(command)

            else:
                time.sleep(0.1)

        except KeyboardInterrupt:
            stop_background_listening()
            msg = "Jarvis shutting down."
            update_hud_text(msg, category="reply")
            speak(msg)
            break

        except Exception as e:
            logging.exception("❌ Error:")
            update_hud_text(str(e), category="error")
            speak("Something went wrong.")


if __name__ == "__main__":
    try:
        # ✅ Start the HUD thread
        hud_thread = threading.Thread(target=start_hud, daemon=True)
        hud_thread.start()

        # ✅ Start the voice assistant loop
        main()

    except Exception as e:
        logging.exception("🔥 Startup error:")
        update_hud_text(str(e), category="error")
        speak("There was a problem starting up.")
