# === lavis.py ===
import os
import re
import time
import logging
from playsound import playsound 
from fuzzywuzzy import fuzz
import threading

from LAVIS.jarvis.voice.speaker import speak
from LAVIS.jarvis.commands.commands import handle_command
from LAVIS.jarvis.apps.chatbot import chatbot, train_chatbot
from LAVIS.jarvis.memory.learning_mode import learning_mode
from LAVIS.jarvis.commands.apps import open_windows_app
from LAVIS.jarvis.voice.recognizer import start_background_listening, stop_background_listening, command_queue
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.web.fallback import handle_fallback

from jarvis_hud.main import update_hud_text
from LAVIS.hud_display import show_fallback_in_hud, show_hud_reply, show_hud_command
from LAVIS.jarvis.commands.apps import get_start_menu_apps

WAKE_WORD = "jarvis"
WAKE_UP_PHRASE = "jarvis wake up"
SLEEP_PHRASE = "jarvis sleep"
AUDIO_STARTUP = r"\LAVIS\lavis start.mp3"

session_state = "sleep"

def hud_speak(message: str):
    show_hud_reply("...", typing=True)
    time.sleep(0.3)
    show_hud_reply(message)
    speak(message)

def welcome():
    if os.path.exists(AUDIO_STARTUP):
        playsound(AUDIO_STARTUP)
    hud_speak("Presence confirmed. Let’s make things happen when you're ready.")

def extract_app_name(command: str) -> str:
    match = re.search(r"open (.+)", command)
    return match.group(1).strip() if match else ""

def check_wake_phrase(text):
    global session_state
    text = text.lower()
    if WAKE_UP_PHRASE in text:
        session_state = "normal"
        hud_speak("Systems operational. Awaiting your instructions.")
        return True
    elif SLEEP_PHRASE in text:
        session_state = "sleep"
        hud_speak("Okay sir, I’m going to sleep.")
        return True
    return False
def main():
    global session_state

    try:
        if not os.path.exists("jarvis.sqlite3"):
            train_chatbot()

        get_start_menu_apps()
        welcome()
        start_background_listening()

        while True:
            if not command_queue.empty():
                input_text = command_queue.get()

                # ✅ Instantly show what was said in the HUD
                show_hud_command(input_text, typing=True)
                time.sleep(0.1)

                print("🎤 Heard:", input_text)

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
                        show_hud_reply("I didn't catch a full sentence. Please repeat.")
                        continue
                    session_state = "conversation"
                    show_hud_reply("Responding to conversation...")
                    # You can integrate chatbot reply here if needed
                    continue
                  
                # elif handle_fallback(command):
                #     from LAVIS.jarvis.web.fallback import last_fallback_response
                #     show_fallback_in_hud(last_fallback_response)
                #     show_hud_reply("Conversation done.")
                #     session_state = "normal"
                #     continue

                # else:
                #     show_hud_reply("Fallback handler responding...")
                #     if handle_fallback(command):
                #         from LAVIS.jarvis.web.fallback  import last_fallback_response
                #         show_fallback_in_hud(last_fallback_response)
                #         session_state = "normal"
                #         continue
                else:
                  # Fallback handler manages everything including follow-ups
                   show_hud_reply("Trying to find an answer...")
                if handle_fallback(command):
                    session_state = "normal"
                else:
                    show_hud_reply("Sorry, I couldn't find a response.")
                    continue

            else:
                time.sleep(0.1)

    except KeyboardInterrupt:
        stop_background_listening()
        hud_speak("Jarvis shutting down.")

    except Exception as e:
        logging.exception("❌ Error in main loop:")
        update_hud_text(str(e), category="error")
        speak("Something went wrong.")
if __name__ == "__main__":
    print("🧪 Running Lavis in console-only mode (no HUD)")

    # === HUD function overrides for console testing ===
    def show_hud_command(text, typing=True): print(f"🧪 [COMMAND] {text}")
    def show_hud_reply(text, typing=True): print(f"🧪 [REPLY] {text}")
    def show_fallback_in_hud(text): print(f"🧪 [FALLBACK] {text}")
    def update_hud_text(text, category="info", typing=True): print(f"🧪 [{category.upper()}] {text}")

    main()
