# === intent_detector.py (Bundled Upgrade) ===

import os
import json
import re
from LAVIS.jarvis.nlp.fallback_corrector import correct_command
from LAVIS.jarvis.llm.ollama_client import ask_ollama
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.commands.apps import open_windows_app

INTENT_LABELS = [
    "command", "conversation", "input_control", "explorer", "learning", "network", "unknown"
]

BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, "json")
CACHE_FILE = os.path.join(CACHE_DIR, "intent_cache.json")
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

    conversation = ["what is", "who is", "tell me about", "explain", "define", "do you think", "opinion", "difference between", "give me info", "should i"]
    if any(kw in text for kw in conversation): return "conversation"

    input_control = ["move mouse", "scroll", "click", "press", "switch tab", "snap window"]
    if any(kw in text for kw in input_control): return "input_control"

    explorer = ["open folder", "list files", "explorer", "my computer", "file manager"]
    if any(kw in text for kw in explorer): return "explorer"

    command = ["open", "launch", "start", "close", "play", "stop", "run"]
    if any(kw in text for kw in command): return "command"

    learning = ["remember", "teach you", "learn this", "save this"]
    if any(kw in text for kw in learning): return "learning"

    network = ["wifi", "bluetooth", "connect", "disconnect", "scan network"]
    if any(kw in text for kw in network): return "network"

    return "unknown"

def detect_intent(raw_text: str) -> str:
    corrected_text = correct_command(raw_text).strip().lower()
    cache = load_cache()

    fast_result = fast_rule_intent(corrected_text)
    if fast_result != "unknown":
        return fast_result

    if corrected_text in cache:
        return cache[corrected_text]

    prompt = (
        f"You are an intent classifier for a voice assistant.\n"
        f"Classify the intent into one of these labels: {', '.join(INTENT_LABELS)}\n"
        f"User input: \"{corrected_text}\"\nRespond ONLY with the label."
    )

    response = ask_ollama(prompt)
    if not response or response.strip().lower() not in INTENT_LABELS:
        print("⚠️ Ollama failed, trying Groq...")
        response = ask_groq(prompt)

    intent = (response or "unknown").strip().lower()
    if intent not in INTENT_LABELS:
        intent = "unknown"

    if intent != "unknown":
        cache[corrected_text] = intent
        save_cache(cache)

    return intent

def is_personal_query(text: str) -> bool:
    personal_keywords = ["my name", "nickname", "birthday", "creator", "color", "favorite", "where do you live", "goal", "quirk"]
    return any(k in text.lower() for k in personal_keywords)

# === enhanced command matcher ===
COMMAND_SYNONYMS = {
    "notepad": ["text editor", "write something"],
    "calculator": ["calc", "math", "do math"],
    "chrome": ["browser", "internet", "web"],
}

def resolve_app_name(raw_command):
    command = raw_command.lower()
    for app, synonyms in COMMAND_SYNONYMS.items():
        if app in command or any(word in command for word in synonyms):
            return app
    return ""

def match_hardcoded_command(command: str):
    command = command.lower().strip()

    if "open notepad" in command:
        return lambda: open_windows_app("notepad")

    if "launch calculator" in command or "open calculator" in command:
        return lambda: open_windows_app("calculator")

    if re.match(r"open (.+)", command):
        app_name = command.split("open ")[1]
        return lambda: open_windows_app(app_name)

    return None
