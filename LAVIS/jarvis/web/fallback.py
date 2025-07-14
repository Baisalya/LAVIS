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


def handle_fallback(command: str) -> bool:
    global last_fallback_response
    from LAVIS.jarvis.commands.commands import handle_command  # Prevent circular import

    config = load_config()
    priority_list = config.get("fallback_priority")
    auto_converse = config.get("fallback_auto_converse", False)

    # 🧠 Detect intent + emotion
    intent = detect_intent(command)
    emotion = detect_emotion(command)
    print(f"[🧠] Intent: {intent}, Emotion: {emotion}")

    auto_read = (emotion == "negative")  # 🚀 Auto-read aloud if sad/angry/etc

    if len(command.split()) < 2 and "?" not in command:
        print("🧠 Too short. Skipping.")
        return False

    if intent not in ["conversation", "unknown"] and emotion == "neutral" and "?" not in command:
        print("🧠 Skipping fallback: No reason to respond.")
        return False

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
                prompt = (
                    f"You are a warm, supportive assistant. Always respond if the user shows emotion or speaks like a friend.\n\n"
                    f"User said: \"{command}\"\n\n"
                    f"Give an empathetic, comforting, or friendly response."
                )
                response = ask_ollama(prompt)

            elif method == "groq":
                prompt = (
                    f"You're a caring AI companion. The user just said:\n\n"
                    f"\"{command}\"\n\n"
                    f"Respond warmly like a friend would. Comfort them or offer something thoughtful."
                )
                response = ask_groq(prompt)

            elif method == "wikipedia" and is_connected():
                response = search_wikipedia(command)

            elif method == "duckduckgo" and is_connected():
                response = search_duckduckgo(command)

            elif method == "chatbot":
                response = str(chatbot.get_response(command))

            if response and response.strip().lower() == "skip":
                print(f"🤖 {method} chose not to reply (SKIP).")
                continue

            if response and len(response.strip()) > 5:
                cleaned = response.strip().lower()
                if any(bad in cleaned for bad in BAD_RESPONSES):
                    print(f"⚠️ Skipping bad fallback response from {method}: {response}")
                    continue

                last_fallback_response = response
                show_fallback_in_hud(last_fallback_response)

                if auto_read:
                    human_speak(last_fallback_response)  # 🗣️ auto speak
                elif auto_converse:
                    human_speak(last_fallback_response)
                    resume_listening()
                    set_session_mode(False)
                    return True

                break

        except Exception as e:
            print(f"⚠️ {method} failed: {e}")

    if not last_fallback_response:
        speak("Sorry, I couldn’t find anything helpful.")
        resume_listening()
        set_session_mode(False)
        return False

    start_time = time.time()
    is_reading = auto_read

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
                    print("🔇 Ignored input during reading.")
                continue

            if follow_up in ["read it", "read the answer", "speak it", "tell me"]:
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

            # Treat as a new query
            return handle_fallback(follow_up)

        time.sleep(0.2)

    resume_listening()
    set_session_mode(False)
    return True
