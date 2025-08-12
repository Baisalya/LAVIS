from LAVIS.jarvis.llm.llm_ask import LLMFallback
from LAVIS.jarvis.voice.speaker import human_speak, speak
from LAVIS.jarvis.apps.chatbot import chatbot
from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import resume_listening, set_session_mode
from LAVIS.hud_display import show_fallback_in_hud
from LAVIS.jarvis.nlp.intent_detector import detect_intent
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, answer_about_user, build_system_prompt
import wikipedia
import requests
import json

last_fallback_response = None
llm_fallback = LLMFallback()

def detect_emotion(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["sad", "lonely", "depressed", "upset", "tired", "angry", "cry"]):
        return "negative"
    elif any(w in text for w in ["happy", "excited", "love", "awesome", "great", "thank you", "grateful"]):
        return "positive"
    elif "?" in text:
        return "curious"
    return "neutral"

def is_question_like(text: str) -> bool:
    question_words = ["what", "why", "how", "who", "when", "where", "do you", "can you"]
    return "?" in text or any(text.lower().startswith(w) for w in question_words)

def is_conversational(text: str) -> bool:
    return is_question_like(text) or detect_emotion(text) in ["positive", "negative"]

def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Failed to load config.json: {e}")
        return {
            "fallback_priority": ["llm", "wikipedia", "duckduckgo", "chatbot"],
            "fallback_auto_converse": True
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

        from LAVIS.jarvis.nlp.intent_detector import is_personal_query
        if hasattr(profile, "get") and is_personal_query(command):
            print("🔁 Routing to: Profile Answer")
            profile_answer = answer_about_user(command, profile)
            if profile_answer:
                system_prompt = build_system_prompt(profile)
                combined_prompt = f"{system_prompt}\n\nUser asked: {command}\nHere is the known fact: {profile_answer}\nRespond naturally as Jarvis."

                jarvis_reply = llm_fallback.ask(combined_prompt)
                last_fallback_response = jarvis_reply
                show_fallback_in_hud(jarvis_reply)
                print("🗣️ Speaking (profile):", jarvis_reply)
                human_speak(jarvis_reply)
                return jarvis_reply

        intent = detect_intent(command)
        emotion = detect_emotion(command)
        mood = profile.get("personality_traits", {}).get("mood", "neutral")
        print(f"[🧠 Intent] {intent}, [Emotion] {emotion}, [Mood] {mood}")

        if len(command.strip().split()) < 2 and "?" not in command:
            return "I need a bit more detail to help you out."

        config = load_config()
        fallback_order = config.get("fallback_priority", [])
        auto_converse = config.get("fallback_auto_converse", False)

        set_session_mode(True)
        print("🧠 Session mode: ON")

        BAD_RESPONSES = [
            "i apologize", "i'm not sure", "please provide", "no text", "i don’t know",
            "i'm sorry", "as an ai", "not found", "i cannot", "i can't", "i don’t"
        ]

        for method in fallback_order:
            try:
                print(f"🔍 Trying: {method}")
                show_fallback_in_hud(f"Trying: {method}")
                response = None

                if method == "llm":
                    response = llm_fallback.ask(f"The user said:\n{command}\nRespond as a helpful assistant.")
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
                        profile_response = answer_about_user(command, profile)
                        if profile_response:
                            show_fallback_in_hud(profile_response)
                            print("🗣️ Speaking (fallback profile):", profile_response)
                            human_speak(profile_response)
                            resume_listening()
                            set_session_mode(False)
                            return profile_response
                        continue

                    last_fallback_response = response
                    show_fallback_in_hud(response)
                    print("🗣️ Speaking:", response)
                    human_speak(response)
                    # ✅ Smart Session Control

                    if auto_converse and is_conversational(command):
                        print("🔁 Keeping session open for further conversation...")
                                                # Do not resume listening yet

                    else:
                        print("🔕 Ending session after one-shot reply...")
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
