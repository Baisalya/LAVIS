import time
import wikipedia
import requests
import json

from LAVIS.jarvis.llm.ollama_client import ask_ollama
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.voice.speaker import human_speak, speak, stop_speaking
from LAVIS.jarvis.apps.chatbot import chatbot
from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import command_queue, resume_listening, set_session_mode
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

def handle_fallback(command: str) -> str:
    global last_fallback_response
    from LAVIS.jarvis.commands.commands import handle_command
    from LAVIS.jarvis.voice.speaker import human_speak, speak, stop_speaking
    from LAVIS.hud_display import show_fallback_in_hud
    from LAVIS.jarvis.voice.recognizer import resume_listening, set_session_mode
    from LAVIS.jarvis.nlp.intent_detector import is_personal_query

    profile = load_user_profile()

    # 🧠 STEP 1: Route Personal Queries to Profile
    if is_personal_query(command):
        print("🔁 Routing to: Profile")
        personal_answer = answer_about_user(command, profile)
        if personal_answer:
            last_fallback_response = personal_answer
            show_fallback_in_hud(personal_answer)
            human_speak(personal_answer)
            resume_listening()
            set_session_mode(False)
            return personal_answer
        else:
            print("⚠️ No matching personal answer found. Will try fallback.")

    # 🧠 STEP 2: External Fallback Sources
    intent = detect_intent(command)
    emotion = detect_emotion(command)
    print(f"[🧠] Intent: {intent}, Emotion: {emotion}")

    if len(command.strip().split()) < 2 and "?" not in command:
        return "I need a bit more detail to help you."

    config = load_config()
    priority_list = config.get("fallback_priority", [])
    auto_converse = config.get("fallback_auto_converse", False)
    auto_read = emotion == "negative"

    set_session_mode(True)
    print("🧠 Session mode: ON")

    BAD_RESPONSES = [
        "i apologize", "i'm not sure", "please provide", "no text", "i don’t know",
        "i'm sorry", "as an ai", "not found", "i cannot", "i can't", "i don’t", "hoBIES"
    ]

    for method in priority_list:
        try:
            print(f"🔎 Trying fallback source: {method}")
            if method == "ollama":
                prompt = f"User asked: {command}\nRespond clearly."
                response = ask_ollama(prompt)

            elif method == "groq":
                prompt = f"The user said:\n{command}\nRespond as a helpful assistant."
                response = ask_groq(prompt)

            elif method == "wikipedia" and is_connected():
                response = search_wikipedia(command)

            elif method == "duckduckgo" and is_connected():
                response = search_duckduckgo(command)

            elif method == "chatbot":
                response = str(chatbot.get_response(command))

            if response:
                cleaned = response.lower().strip()
                if any(bad in cleaned for bad in BAD_RESPONSES):
                    print(f"⚠️ Skipped bad response from {method}: {response}")
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
# Detect if the question should be answered from profile
