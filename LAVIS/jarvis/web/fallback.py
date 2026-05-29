# fallback.py — Optimized + Noise Filter + Profile-aware Fallback
import re, time, json, requests, traceback, wikipedia
from typing import Optional

from LAVIS.jarvis.llm.llm_ask import LLMFallback
from LAVIS.jarvis.voice.speaker import human_speak, speak
from LAVIS.jarvis.apps.chatbot import chatbot
from LAVIS.jarvis.network import is_connected
from LAVIS.jarvis.voice.recognizer import resume_listening, set_session_mode
from LAVIS.hud_display import show_fallback_in_hud
from LAVIS.jarvis.nlp.intent_detector import detect_intent, is_personal_query
from LAVIS.jarvis.apps.userai.user_profile import (
    load_user_profile, answer_about_user, build_system_prompt
)

# ---------------- Globals ----------------
last_fallback_response = None
llm_fallback = LLMFallback()
_last_processed_ts = 0.0
_recent_texts = []

# ---------------- Ignore/Noise Config ----------------
_IGNORE_CFG = {
    "ignore_min_words": 3,
    "ignore_min_chars": 2,
    "ignore_max_stopword_ratio": 0.65,
    "ignore_min_avg_word_len": 2.5,
    "ignore_partial_token_min_len": 2,
    "ignore_fillers": ["uh","um","hmm","huh","ok","okay","yeah","yep","nope","mm","ah","oh","hm"],
    "ignore_comma_fragment_len": 40,
    "min_confidence": 0.45,
    "debounce_ms": 650,
    "duplicate_window_s": 2.0,
    "repeat_to_accept": 3,
    "single_word_allowed_keywords": ["weather","time","date","news","joke","music","song","battery","volume","jarvis","stop","yes","no","play","pause"],
}

_STOPWORDS = {"the","a","an","and","or","but","if","then","so","of","in","on","for","to",
              "is","are","was","were","i","you","he","she","it","we","they","me","him",
              "her","them","this","that","these","those","with","as","at","by","from",
              "about","into","over","after","before","between"}

_VERB_KEYWORDS = {"is","are","do","does","did","have","has","will","can","could","would",
                  "should","make","take","go","play","show","tell","give","find","search",
                  "open","close","turn","set","call","remind","schedule","add","remove",
                  "create","start","stop","pause","resume","translate","define","explain",
                  "weather","time","date","who","what","when","where","why","how"}

# ---------------- Helpers ----------------
def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except Exception:
        return {
            "fallback_priority": ["llm", "wikipedia", "duckduckgo", "chatbot"],
            "fallback_auto_converse": True
        }

def detect_emotion(text: str) -> str:
    txt = text.lower()
    if any(w in txt for w in ["sad","lonely","depressed","upset","tired","angry","cry"]): return "negative"
    if any(w in txt for w in ["happy","excited","love","awesome","great","thank you","grateful"]): return "positive"
    if "?" in txt: return "curious"
    return "neutral"

def is_question_like(text: str) -> bool:
    qwords = ["what","why","how","who","when","where","do you","can you"]
    return "?" in text or any(text.lower().startswith(w) for w in qwords)

def is_conversational(text: str) -> bool:
    return is_question_like(text) or detect_emotion(text) in ["positive","negative"]

# --- Noise/Ignore Heuristic ---
def should_ignore_transcript(text: str, confidence: Optional[float] = None, is_partial: bool = False) -> bool:
    if not text: return True
    cfg, t = _IGNORE_CFG, text.strip()
    words = [w.strip("',.?").lower() for w in re.sub(r"[^\w\s'.,?]", "", t).split() if w.strip("',.?")]
    if not words: return True
    if t.endswith("?"): return False

    if len(words) == 1 and words[0] in cfg["single_word_allowed_keywords"]: return False
    if all(w in cfg["ignore_fillers"] for w in words): return True
    if len(t) < cfg["ignore_min_chars"]: return True
    if len(words) < cfg["ignore_min_words"]:
        avg_len = sum(len(w) for w in words)/max(1,len(words))
        if not any(w in _VERB_KEYWORDS for w in words) and avg_len < cfg["ignore_min_avg_word_len"]:
            return True
    stop_ratio = sum(1 for w in words if w in _STOPWORDS)/len(words)
    if stop_ratio > cfg["ignore_max_stopword_ratio"] and len(words)<6: return True
    if is_partial: return True
    if ',' in t and len(words)<10 and len(t)<cfg["ignore_comma_fragment_len"]: return True
    if confidence is not None and confidence < cfg["min_confidence"]: return True
    return False

# --- Knowledge Sources ---
def search_wikipedia(query): 
    try: return wikipedia.summary(query, sentences=2)
    except: return None
def search_duckduckgo(query):
    try:
        data = requests.get(f"https://api.duckduckgo.com/?q={query}&format=json").json()
        return data.get("AbstractText") or data.get("Answer")
    except: return None

# --- Hardcoded quick replies ---
def get_hardcoded_response(text: str) -> Optional[str]:
    q = (text or "").lower().strip()
    quick = {
        "who are you":"I'm Lavis, your assistant.",
        "what is your name":"My name is Lavis.",
        "how are you":"I'm doing great! And you?",
        "tell me a joke":"Why don’t robots get scared? Because they have nerves of steel!",
        "are you alive":"Not quite, but I enjoy our conversations.",
        "what can you do":"I can answer, reason, control apps, and chat. Just ask!"
    }
    for k,v in quick.items():
        if k in q: return v
    return None

# ---------------- Main Handler ----------------
def handle_fallback(command: str, confidence: Optional[float]=None, is_partial: bool=False) -> str:
    global last_fallback_response, _last_processed_ts, _recent_texts
    profile = load_user_profile()
    user_emotion = detect_emotion(command)
    now = time.time()

    # Debounce rapid events
    if now - _last_processed_ts < _IGNORE_CFG["debounce_ms"]/1000.0:
        _recent_texts.append((command, now))
        _recent_texts=[(t,ts) for t,ts in _recent_texts if now-ts<=_IGNORE_CFG["duplicate_window_s"]]
        return ""

    # Update buffer
    _recent_texts.append((command.strip(), now))
    _recent_texts=[(t,ts) for t,ts in _recent_texts if now-ts<=_IGNORE_CFG["duplicate_window_s"]]
    occurrences = sum(1 for t,ts in _recent_texts if t==command.strip())
    force_accept = occurrences>=_IGNORE_CFG["repeat_to_accept"]

    # Filter junk
    if not force_accept and should_ignore_transcript(command, confidence, is_partial):
        show_fallback_in_hud("Ignored noise")
        resume_listening(); set_session_mode(False)
        _last_processed_ts = now
        return ""

    # Quick hardcoded answers
    quick = get_hardcoded_response(command)
    if quick:
        show_fallback_in_hud(quick); human_speak(quick, emotion=user_emotion)
        resume_listening(); set_session_mode(False)
        last_fallback_response=quick; _last_processed_ts=now
        return quick

    # Profile-aware answers
    if is_personal_query(command):
        profile_ans = answer_about_user(command, profile)
        if profile_ans:
            sys_prompt=build_system_prompt(profile)
            prompt=f"{sys_prompt}\nUser asked: {command}\nKnown fact: {profile_ans}\nRespond naturally as Jarvis."
            reply=llm_fallback.ask(prompt) or profile_ans
            show_fallback_in_hud(reply); human_speak(reply, emotion=user_emotion)
            resume_listening(); set_session_mode(False)
            last_fallback_response=reply; _last_processed_ts=now
            return reply

    # Intent/emotion logging
    intent=detect_intent(command); emotion=user_emotion
    print(f"[🧠 Intent] {intent}, [Emotion] {emotion}")

    cfg=load_config()
    fallback_order=cfg["fallback_priority"]; auto_converse=cfg["fallback_auto_converse"]
    set_session_mode(True)

    BAD=["i apologize","i'm not sure","please provide","i don’t know","i'm sorry",
         "as an ai","not found","i cannot","i can't","i don’t"]

    for method in fallback_order:
        try:
            resp=None
            if method=="llm": resp=llm_fallback.ask(command)
            elif method=="wikipedia" and is_connected(): resp=search_wikipedia(command)
            elif method=="duckduckgo" and is_connected(): resp=search_duckduckgo(command)
            elif method=="chatbot": resp=str(chatbot.get_response(command))

            if resp:
                if any(b in resp.lower() for b in BAD) or len(resp.split())<3:
                    continue
                last_fallback_response=resp
                show_fallback_in_hud(resp); human_speak(resp, emotion=emotion)
                if not (auto_converse and is_conversational(command)):
                    resume_listening(); set_session_mode(False)
                _last_processed_ts=now; return resp
        except Exception: continue

    speak("Sorry, I couldn’t find anything useful.")
    resume_listening(); set_session_mode(False)
    _last_processed_ts=now
    return "Sorry, I couldn’t find anything useful."
