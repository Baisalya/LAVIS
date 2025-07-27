import time
import wikipedia
import requests
import json

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

def handle_fallback(command: str) -> str:
    global last_fallback_response
    try:
        profile = load_user_profile()
        if not command.strip():
            return "Please say something for me to help."

        # STEP 1: Check for profile-based personal answer
        from LAVIS.jarvis.nlp.intent_detector import is_personal_query
        if hasattr(profile, "get") and is_personal_query(command):
            print("🔁 Routing to: Profile Answer")
            answer = answer_about_user(command, profile)
            if answer:
                last_fallback_response = answer
                show_fallback_in_hud(answer)
                human_speak(answer)
                resume_listening()
                set_session_mode(False)
                return answer

        # STEP 2: LLM/Web/Chatbot fallback
        intent = detect_intent(command)
        emotion = detect_emotion(command)
        mood = profile.get("personality_traits", {}).get("mood", "neutral")
        print(f"[🧠 Intent] {intent}, [Emotion] {emotion}, [Mood] {mood}")

        if len(command.strip().split()) < 2 and "?" not in command:
            return "I need a bit more detail to help you out."

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

                        # 🔁 Try user profile
                        print("🧠 Attempting profile-based answer fallback...")
                        profile_response = answer_about_user(command, profile)
                        if profile_response:
                            show_fallback_in_hud(profile_response)
                            human_speak(profile_response)
                            resume_listening()
                            set_session_mode(False)
                            return profile_response
                        continue

                    last_fallback_response = response
                    show_fallback_in_hud(response)
                    if auto_read or auto_converse:
                        human_speak(response)
                    if auto_converse:
                        resume_listening()
                        set_session_mode(False)
                    return response

            except Exception as e:
                print(f"❌ {method} failed: {e}")
                continue

        speak("Sorry, I couldn’t find anything useful.")
        resume_listening()
        set_session_mode(False)
        return "Sorry, I couldn’t find anything useful."

    except Exception as e:
        print(f"[Fallback Error] Critical failure: {e}")
        resume_listening()
        set_session_mode(False)
        return "An error occurred while processing your request."

def get_hardcoded_response(text: str) -> str:
    text = text.lower().strip()
    simple_responses = {
        "who are you": "I'm Lavis, your assistant. I'm here to help anytime you need.",
        "what is your name": "My name is Lavis. You gave me that, remember?",
        "how are you": "I'm doing great! And you?",
        "tell me a joke": "Why don’t robots get scared? Because they have nerves of steel!",
        "are you alive": "Not quite, but I do enjoy our conversations.",
        "what can you do": "I can help with tasks, answer questions, control apps, and more. Just ask!",
    }

    for key, val in simple_responses.items():
        if key in text:
            return val

    return None
