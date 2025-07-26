import time
import wikipedia
import requests
import json
import threading
from kivy.clock import Clock

from LAVIS.jarvis.llm.ollama_client import ask_ollama
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.voice.speaker import human_speak, speak
from LAVIS.jarvis.apps.chatbot import chatbot
from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import resume_listening, set_session_mode
from LAVIS.hud_display import show_fallback_in_hud
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, answer_about_user

last_fallback_response = None

# ✅ Helper for UI thread-safe call
def safe_ui(func, *args):
    Clock.schedule_once(lambda dt: func(*args), 0)

def detect_emotion(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["sad", "lonely", "depressed", "upset", "tired", "angry", "cry"]):
        return "negative"
    elif any(w in text for w in ["happy", "excited", "love", "awesome", "great", "thank you", "grateful"]):
        return "positive"
    elif "?" in text:
        return "curious"
    return "neutral"

def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load config.json: {e}")
        return {
            "fallback_priority": ["groq", "ollama", "wikipedia", "duckduckgo", "chatbot"],
            "fallback_auto_converse": False
        }

def search_wikipedia(query):
    try:
        return wikipedia.summary(query, sentences=2)
    except Exception as e:
        print(f"[Wikipedia Error] {e}")
        return None

def search_duckduckgo(query):
    try:
        res = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json")
        data = res.json()
        return data.get("AbstractText") or data.get("Answer")
    except Exception as e:
        print(f"[DuckDuckGo Error] {e}")
        return None

# ✅ MAIN FUNCTION (Thread-safe)
def handle_fallback(command: str) -> str:
    # Start fallback in background to avoid GUI freezing
    def background_fallback():
        global last_fallback_response
        try:
            profile = load_user_profile()
            if not command.strip():
                speak("Please say something for me to help.")
                return

            # STEP 1: Personal profile lookup
            from LAVIS.jarvis.nlp.intent_detector import is_personal_query
            if hasattr(profile, "get") and is_personal_query(command):
                print("🔁 Routing to: Profile")
                answer = answer_about_user(command, profile)
                if answer:
                    last_fallback_response = answer
                    safe_ui(show_fallback_in_hud, answer)
                    human_speak(answer)
                    resume_listening()
                    set_session_mode(False)
                    return
                else:
                    print("⚠️ No profile match. Proceeding to fallback sources.")

            # STEP 2: LLM or web fallback
            intent = detect_intent(command)
            emotion = detect_emotion(command)
            print(f"[🧠 Intent] {intent}, [Emotion] {emotion}")

            if len(command.strip().split()) < 2 and "?" not in command:
                speak("Please say a full sentence.")
                return

            config = load_config()
            fallback_order = config.get("fallback_priority", [])
            auto_converse = config.get("fallback_auto_converse", False)
            auto_read = emotion == "negative"

            set_session_mode(True)
            print("🧠 Session mode: ON")

            BAD_RESPONSES = [
                "i apologize", "i'm not sure", "please provide", "no text", "i don’t know",
                "i'm sorry", "as an ai", "not found", "i cannot", "i can't", "i don’t"
            ]

            for method in fallback_order:
                try:
                    print(f"🔍 Trying: {method}")
                    response = None

                    if method == "ollama":
                        response = ask_ollama(f"User asked: {command}\nRespond clearly.")
                    elif method == "groq":
                        response = ask_groq(f"The user said:\n{command}\nRespond as a helpful assistant.")
                    elif method == "wikipedia" and is_connected():
                        response = search_wikipedia(command)
                    elif method == "duckduckgo" and is_connected():
                        response = search_duckduckgo(command)
                    elif method == "chatbot":
                        response = str(chatbot.get_response(command))

                    if response:
                        cleaned = response.lower().strip()
                        if any(bad in cleaned for bad in BAD_RESPONSES):
                            print(f"⚠️ Rejected weak response from {method}")
                            continue

                        last_fallback_response = response
                        safe_ui(show_fallback_in_hud, response)

                        if auto_read or auto_converse:
                            human_speak(response)

                        if auto_converse:
                            resume_listening()
                            set_session_mode(False)

                        return

                except Exception as e:
                    print(f"❌ {method} failed: {e}")
                    continue

            # Final fallback failure
            speak("Sorry, I couldn’t find anything useful.")
            resume_listening()
            set_session_mode(False)

        except Exception as e:
            print(f"[Fallback Error] Critical failure: {e}")
            speak("Something went wrong while handling your request.")
            resume_listening()
            set_session_mode(False)

    # 🔄 Launch in background
    threading.Thread(target=background_fallback, daemon=True).start()
    return "Trying to find an answer..."
