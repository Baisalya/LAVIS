# LAVIS/utils/emotion_utils.py

import re
from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.llm.ollama_client import ask_ollama

def detect_emotion(text: str) -> str:
    """
    Hybrid emotion detector: hardcoded first, then fallback to LLM if still neutral.
    Returns: 'positive', 'negative', 'curious', or 'neutral'
    """

    text = text.lower().strip()

    negative_keywords = [
        "sad", "lonely", "depressed", "upset", "tired", "angry", "cry", "hate", "worried", "stressed", "bad"
    ]
    positive_keywords = [
        "happy", "excited", "love", "awesome", "great", "thank you", "grateful", "good", "joy", "nice", "amazing"
    ]

    if any(word in text for word in negative_keywords):
        return "negative"
    elif any(word in text for word in positive_keywords):
        return "positive"
    elif "?" in text:
        return "curious"

    # 🧠 Use LLM if still uncertain (neutral)
    if is_connected():
        try:
            prompt = (
                "Classify the user's emotional tone based on what they said.\n\n"
                "Respond with only one word: positive, negative, curious, or neutral.\n\n"
                f"User: {text}"
            )

            # 🔁 Try Groq first, then Ollama
            response = ask_groq(prompt).strip().lower()
            if response not in ["positive", "negative", "curious", "neutral"]:
                response = ask_ollama(prompt).strip().lower()

            if response in ["positive", "negative", "curious", "neutral"]:
                return response

        except Exception as e:
            print("⚠️ LLM emotion fallback failed:", e)

    return "neutral"
