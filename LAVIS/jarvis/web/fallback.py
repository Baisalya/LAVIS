import time
import wikipedia
import requests
import json

from  LAVIS.jarvis.llm.ollama_client import ask_ollama
from  LAVIS.jarvis.llm.groq_client import ask_groq
from  LAVIS.jarvis.voice.speaker import human_speak, speak, stop_speaking
from  LAVIS.jarvis.apps.chatbot import chatbot
from  LAVIS.jarvis.network import is_connected
from  LAVIS.jarvis.voice.recognizer import command_queue, resume_listening, set_session_mode
from  LAVIS.hud_display import show_fallback_in_hud

last_fallback_response = None

def load_config():
        try:
            with open("config.json", "r") as f:
                return json.load(f)
        except:
            return {
                "fallback_priority": ["groq", "ollama", "wikipedia", "duckduckgo", "chatbot"],
                "fallback_auto_converse": False
            }

def search_wikipedia(query):
        try:
            return wikipedia.summary(query, sentences=2)
        except:
            return None

def search_duckduckgo(query):
        try:
            res = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json")
            data = res.json()
            return data.get("AbstractText") or data.get("Answer")
        except:
            return None

def handle_fallback(command: str) -> bool:
        global last_fallback_response
        from  LAVIS.jarvis.commands.commands import handle_command  # Prevent circular import

        config = load_config()
        priority_list = config.get("fallback_priority")
        auto_converse = config.get("fallback_auto_converse", False)

        set_session_mode(True)
        print("\n🔁 Session mode ON (fallback)")

        BAD_RESPONSES = [
            "i apologize", "i'm not sure", "please provide", 
            "no text for me to read", "i don’t know", "i don't have", 
            "i'm sorry", "as an ai", "i am not able", "not found"
        ]

        response = None

        for method in priority_list:
            try:
                if method == "ollama":
                    response = ask_ollama(command)
                elif method == "groq":
                    response = ask_groq(command)
                elif method == "wikipedia" and is_connected():
                    response = search_wikipedia(command)
                elif method == "duckduckgo" and is_connected():
                    response = search_duckduckgo(command)
                elif method == "chatbot":
                    response = str(chatbot.get_response(command))

                if response and len(response.strip()) > 5:
                    cleaned = response.strip().lower()
                    if any(bad in cleaned for bad in BAD_RESPONSES):
                        print(f"⚠️ Skipping bad fallback response from {method}: {response}")
                        continue  # Try next fallback source

                    # ✅ Valid response found
                    last_fallback_response = response
                    print("🧠 Answer stored. Say 'read it' to hear it.")
                    print("\n📄 Here's what I found:\n" + last_fallback_response)

                    show_fallback_in_hud(last_fallback_response)

                    if auto_converse:
                        human_speak(last_fallback_response)
                        resume_listening()
                        set_session_mode(False)
                        return True

                    break

            except Exception as e:
                print(f"⚠️ {method} failed: {e}")

        if not last_fallback_response:
            speak("Sorry, I couldn't find an answer.")
            resume_listening()
            set_session_mode(False)
            return False

        #speak("I found something useful. Say 'read it' to hear it.")

        start_time = time.time()
        is_reading = False

        while time.time() - start_time < 60:
            if not command_queue.empty():
                follow_up = command_queue.get().strip().lower()
                print("🎧 Follow-up heard:", follow_up)

                if is_reading:
                    if follow_up in ["stop", "pause", "ok stop", "don't read", "enough"]:
                        stop_speaking()
                        speak("Okay, I’ve paused the answer. You can ask more.")
                        is_reading = False
                    else:
                        print("⚠️ Ignoring non-stop input during reading.")
                    continue

                if follow_up in ["read it", "read the answer", "speak it", "tell me"]:
                    if not is_reading:
                        is_reading = True
                        human_speak(last_fallback_response)
                    continue

                elif follow_up in ["exit", "close", "thank you"]:
                    speak("Okay, closing the session.")
                    resume_listening()
                    set_session_mode(False)
                    return True

                elif handle_command(follow_up):
                    continue

                elif len(follow_up.split()) < 3:
                    speak("Could you please clarify?")
                    continue

                # Treat as a new fallback query
                return handle_fallback(follow_up)

            time.sleep(0.2)

        # Timeout fallback
       # speak("No response received. Resuming listening.")
        resume_listening()
        set_session_mode(False)
        return True
