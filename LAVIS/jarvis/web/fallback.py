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
import re
import time
from typing import Optional

# ----------------------
# Globals / LLM bridge
# ----------------------
last_fallback_response = None
llm_fallback = LLMFallback()

# runtime buffers for human-like behavior
_last_processed_ts = 0.0
_recent_texts = []  # list of (text, ts)
# ----------------------
# Default ignore config (can be overridden via config.json -> "ignore_settings")
# ----------------------
_DEFAULT_IGNORE_CFG = {
    "ignore_min_words": 3,
    "ignore_min_chars": 10,
    "ignore_max_stopword_ratio": 0.65,
    "ignore_min_avg_word_len": 2.5,
    "ignore_partial_token_min_len": 2,
    "ignore_fillers": ["uh", "um", "hmm", "huh", "ok", "okay", "yeah", "yep", "nope", "mm", "ah", "oh", "hm"],
    "ignore_comma_fragment_len": 40,
    "min_confidence": 0.45,
    "debounce_ms": 650,
    "duplicate_window_s": 2.0,
    "repeat_to_accept": 3,
    "single_word_allowed_keywords": ["weather", "time", "date", "news", "joke", "music", "song", "battery", "volume"],
}

# light stopword set for fragment heuristics
_STOPWORDS = {
    "the","a","an","and","or","but","if","then","so","of","in","on","for","to","is","are","was","were",
    "i","you","he","she","it","we","they","me","him","her","them","this","that","these","those","with",
    "as","at","by","from","about","into","over","after","before","between"
}

# small verbs/keywords list to detect intent in fragments
_VERB_KEYWORDS = {
    "is","are","do","does","did","have","has","will","can","could","would","should",
    "make","take","go","play","show","tell","give","find","search","open","close",
    "turn","set","call","remind","schedule","add","remove","create","start","stop",
    "pause","resume","translate","define","explain","weather","time","date","who","what","when","where","why","how"
}

# ----------------------
# Utility: load config
# ----------------------
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

def _load_ignore_config():
    cfg = load_config()
    ignore_cfg = cfg.get("ignore_settings")
    if isinstance(ignore_cfg, dict):
        merged = _DEFAULT_IGNORE_CFG.copy()
        merged.update(ignore_cfg)
        return merged
    return _DEFAULT_IGNORE_CFG.copy()

_IGNORE_CFG = _load_ignore_config()

# ----------------------
# Heuristics: emotion / question checks
# ----------------------
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

# ----------------------
# Heuristic to ignore short/fragment transcripts
# ----------------------
def should_ignore_transcript(text: str,
                             confidence: Optional[float] = None,
                             is_partial: bool = False) -> bool:
    """
    Return True to IGNORE the transcript (do not call fallback, do not TTS).
    Conservative heuristics: word count, char length, filler-only, stopword ratio,
    partial token detection and punctuation/commas fragments.
    """
    if not text:
        return True

    cfg = _IGNORE_CFG
    t = text.strip()
    # normalize some punctuation but preserve commas/question marks
    t_clean = re.sub(r"[\-—_]+", " ", t)
    t_clean = re.sub(r"[^\w\s'.,?]", "", t_clean)
    if not t_clean:
        return True

    words = [w.strip("',.?").lower() for w in t_clean.split() if w.strip("',.?")]
    word_count = len(words)
    if word_count == 0:
        return True

    # if it ends with question mark -> likely intentional question -> do not ignore
    if t_clean.endswith('?'):
        return False

    # allow single meaningful keywords (e.g., "weather", "time")
    if word_count == 1:
        single = words[0]
        if single in cfg.get("single_word_allowed_keywords", []):
            return False

    # 1) filler exact match (all tokens are fillers)
    fillers = set(cfg.get("ignore_fillers", []))
    if all(w in fillers for w in words):
        return True

    # 2) overall shortness
    if len(t_clean) < cfg.get("ignore_min_chars", 10):
        # if it's extremely short, ignore quickly
        if len(t_clean) < 3:
            return True

    # 3) very few words and small average word length -> fragment
    if word_count < cfg.get("ignore_min_words", 3):
        avg_len = sum(len(w) for w in words) / max(1, word_count)
        # if there's a clear verb/keyword, consider meaningful
        if any(w in _VERB_KEYWORDS for w in words):
            return False
        if avg_len < cfg.get("ignore_min_avg_word_len", 2.5):
            return True

    # 4) stopword-heavy fragments (likely partial)
    stopword_count = sum(1 for w in words if w in _STOPWORDS)
    stopword_ratio = stopword_count / max(1, word_count)
    if stopword_ratio >= cfg.get("ignore_max_stopword_ratio", 0.65) and word_count < 6:
        return True

    # 5) trailing partial token / short last token (recognizer cut mid-word)
    last_token = words[-1]
    if is_partial:
        # be stricter for partial transcripts: ignore most partials
        return True
    if len(last_token) <= cfg.get("ignore_partial_token_min_len", 2):
        # if last token is tiny and likely not a standalone word, treat as fragment
        if not last_token.isalpha() or len(last_token) <= 2:
            return True

    # 6) comma-separated fragment like "lifestyle choices, one day influence the aging"
    if ',' in t and word_count < 10:
        if len(t_clean) < cfg.get("ignore_comma_fragment_len", 40):
            return True

    # 7) low confidence -> ignore
    if confidence is not None and confidence < cfg.get("min_confidence", 0.45):
        return True

    # 8) if there's at least one verb/keyword or a contentful word length -> treat as meaningful
    if any(w in _VERB_KEYWORDS for w in words):
        return False
    content_words = [w for w in words if w not in _STOPWORDS and w not in fillers]
    if len(content_words) >= 1:
        return False

    # passed conservative filters -> treat as meaningful
    return False

# ----------------------
# Hardcoded responses (quick path)
# ----------------------
def get_hardcoded_response(text: str) -> str:
    text = (text or "").lower().strip()
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

# ----------------------
# Knowledge helpers
# ----------------------
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

# ----------------------
# Main fallback handler (refined / more aware)
# ----------------------
def handle_fallback(command: str, confidence: Optional[float] = None, is_partial: bool = False) -> str:
    """
    Main entry. Added parameters confidence and is_partial so recognizer can pass them.
    Returns response string (or empty string if ignored).
    """
    global last_fallback_response, _last_processed_ts, _recent_texts
    try:
        profile = load_user_profile()

        if not command or not command.strip():
            return "Please say something for me to help."

        now = time.time()
        cfg_ignore = _IGNORE_CFG
        # debounce: if events are flooding, ignore small bursts
        debounce_s = cfg_ignore.get("debounce_ms", 650) / 1000.0
        if now - _last_processed_ts < debounce_s:
            print("⏱️ Debounced rapid transcript (ignored):", command)
            show_fallback_in_hud("Debounced input")
            # append to recent for potential repeat acceptance
            _recent_texts.append((command.strip(), now))
            # trim recent list
            _recent_texts = [(t, ts) for (t, ts) in _recent_texts if now - ts <= cfg_ignore.get("duplicate_window_s", 2.0)]
            return ""

        # update recent buffer and compute duplicates
        _recent_texts.append((command.strip(), now))
        # keep only recent window
        _recent_texts = [(t, ts) for (t, ts) in _recent_texts if now - ts <= cfg_ignore.get("duplicate_window_s", 2.0)]
        occurrences = sum(1 for (t, ts) in _recent_texts if t == command.strip())

        # If the same fragment repeated enough times in short window, accept it (user intentionally repeated)
        if occurrences >= cfg_ignore.get("repeat_to_accept", 3):
            force_accept = True
            print(f"🔁 Detected intentional repeat ({occurrences}) — forcing accept: {command}")
        else:
            force_accept = False

        # 0) Ignore obvious partials / fragments early (so we don't call LLM / TTS)
        if not force_accept and should_ignore_transcript(command, confidence=confidence, is_partial=is_partial):
            print("🔇 Ignored fragment/transcript:", command)
            show_fallback_in_hud(f"Ignored: {command}")
            # ensure recognizer resumes and session cleared
            resume_listening()
            set_session_mode(False)
            # update last processed ts so we still respect debounce
            _last_processed_ts = now
            return ""

        # 1) quick hardcoded answers (no LLM)
        quick = get_hardcoded_response(command)
        if quick:
            last_fallback_response = quick
            show_fallback_in_hud(quick)
            print("🗣️ Quick hardcoded reply:", quick)
            human_speak(quick)
            resume_listening()
            set_session_mode(False)
            _last_processed_ts = now
            return quick

        # 2) personal/profile queries should be routed early
        from LAVIS.jarvis.nlp.intent_detector import is_personal_query
        if hasattr(profile, "get") and is_personal_query(command):
            print("🔁 Routing to: Profile Answer")
            profile_answer = answer_about_user(command, profile)
            if profile_answer:
                system_prompt = build_system_prompt(profile)
                combined_prompt = f"{system_prompt}\n\nUser asked: {command}\nHere is the known fact: {profile_answer}\nRespond naturally as Jarvis."
                jarvis_reply = llm_fallback.ask(combined_prompt)
                reply = jarvis_reply or profile_answer
                last_fallback_response = reply
                show_fallback_in_hud(reply)
                print("🗣️ Speaking (profile):", reply)
                human_speak(reply)
                resume_listening()
                set_session_mode(False)
                _last_processed_ts = now
                return reply

        # 3) baseline checks
        intent = detect_intent(command)
        emotion = detect_emotion(command)
        mood = profile.get("personality_traits", {}).get("mood", "neutral")
        print(f"[🧠 Intent] {intent}, [Emotion] {emotion}, [Mood] {mood}")

        # if input is too terse (but passed ignore checks), ask for clarification
        if len(command.strip().split()) < 2 and "?" not in command:
            return "I need a bit more detail to help you out."

        cfg = load_config()
        fallback_order = cfg.get("fallback_priority", ["llm", "wikipedia", "duckduckgo", "chatbot"])
        auto_converse = cfg.get("fallback_auto_converse", True)

        set_session_mode(True)
        print("🧠 Session mode: ON")

        BAD_RESPONSES = [
            "i apologize", "i'm not sure", "please provide", "no text", "i don’t know",
            "i'm sorry", "as an ai", "not found", "i cannot", "i can't", "i don’t"
        ]

        # 4) Try sources in configured order, but treat weak LLM replies as "try next"
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
                    # reject weak answers and try next source
                    if any(bad in cleaned for bad in BAD_RESPONSES) or len(cleaned.split()) <= 2:
                        print(f"⚠️ Rejected weak/short response from {method}: \"{response}\"")
                        # attempt to answer from profile memory before skipping
                        profile_response = answer_about_user(command, profile)
                        if profile_response:
                            show_fallback_in_hud(profile_response)
                            print("🗣️ Speaking (fallback profile):", profile_response)
                            human_speak(profile_response)
                            resume_listening()
                            set_session_mode(False)
                            last_fallback_response = profile_response
                            _last_processed_ts = time.time()
                            return profile_response
                        # else continue to next method
                        continue

                    # Acceptable response
                    last_fallback_response = response
                    show_fallback_in_hud(response)
                    print("🗣️ Speaking:", response)
                    human_speak(response)

                    # session control
                    if auto_converse and is_conversational(command):
                        print("🔁 Keeping session open for further conversation...")
                        # don't resume listening yet — keep session active for follow-up
                    else:
                        print("🔕 Ending session after one-shot reply...")
                        resume_listening()
                        set_session_mode(False)

                    _last_processed_ts = time.time()
                    return response

            except Exception as e:
                print(f"❌ {method} failed: {e}")
                continue

        # 5) nothing returned useful
        speak("Sorry, I couldn’t find anything useful.")
        resume_listening()
        set_session_mode(False)
        _last_processed_ts = time.time()
        return "Sorry, I couldn’t find anything useful."

    except Exception as e:
        print(f"[Fallback Error] Critical failure: {e}")
        resume_listening()
        set_session_mode(False)
        return "An error occurred while processing your request."
