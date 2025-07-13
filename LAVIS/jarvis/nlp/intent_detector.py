# LAVIS/jarvis/nlp/intent_detector.py

import os
import json
from LAVIS.jarvis.nlp.fallback_corrector import correct_command
from LAVIS.jarvis.llm.ollama_client import ask_ollama
from LAVIS.jarvis.llm.groq_client import ask_groq

INTENT_LABELS = [
    "command", "conversation", "input_control", "explorer", "learning", "network", "unknown"
]

# === Save cache to LAVIS/jarvis/nlp/json/intent_cache.json ===
BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, "json")
CACHE_FILE = os.path.join(CACHE_DIR, "intent_cache.json")

# Ensure directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

if not os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "w") as f:
        json.dump({}, f)


def load_cache():
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fast_rule_intent(text: str) -> str:
    text = text.lower()

    if any(kw in text for kw in [
        "what is", "tell me about", "do you think", "why", "how does", "opinion", "should i", "explain",
        "give me information", "define", "difference between", "summarize", "who is"
    ]):
        return "conversation"

    if any(kw in text for kw in [
        "move mouse", "click", "scroll", "type", "press", "drag", "drop",
        "switch window", "alt tab", "show desktop", "close window",
        "minimize window", "maximize window", "snap left", "snap right"
    ]):
        return "input_control"

    if any(kw in text for kw in [
        "open folder", "open file", "this pc", "list drives",
        "shutdown", "restart", "log out", "sign out"
    ]):
        return "explorer"

    if any(kw in text for kw in [
        "open", "close", "launch", "play", "start", "stop"
    ]):
        return "command"

    if any(kw in text for kw in [
        "remember this", "learn this", "save this", "teach you"
    ]):
        return "learning"

    if any(kw in text for kw in [
        "scan bluetooth", "scan network", "connect network", "connect to",
        "bluetooth", "wifi", "wi-fi"
    ]):
        return "network"

    return "unknown"


def detect_intent(raw_text: str) -> str:
    corrected_text = correct_command(raw_text).strip().lower()
    cache = load_cache()

    # === Step 1: Try fast heuristic rules ===
    fast_result = fast_rule_intent(corrected_text)
    if fast_result != "unknown":
        return fast_result

    # === Step 2: Check cache ===
    if corrected_text in cache:
        return cache[corrected_text]

    # === Step 3: LLM Fallback ===
    prompt = (
        f"You are an intent classifier for a voice assistant.\n"
        f"Classify the intent of this user input into one of the following labels:\n"
        f"{', '.join(INTENT_LABELS)}\n\n"
        f"User input: \"{corrected_text}\"\n"
        f"Respond ONLY with the label."
    )

    response = ask_ollama(prompt)
    if not response or response.strip().lower() not in INTENT_LABELS:
        print("⚠️ Ollama failed or gave invalid response. Falling back to Groq...")
        response = ask_groq(prompt)

    intent = (response or "unknown").strip().lower()
    if intent not in INTENT_LABELS:
        intent = "unknown"

    # === Save to cache ===
    cache[corrected_text] = intent
    save_cache(cache)

    return intent
