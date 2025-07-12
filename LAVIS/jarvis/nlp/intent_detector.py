# intent_detector.py

from LAVIS.jarvis.nlp.fallback_corrector import correct_command

def detect_intent(raw_text: str) -> str:
    """
    Takes a raw voice-to-text string, corrects it, and returns an intent category.
    """

    # === Step 1: Correct text (T5 + fuzzy + learn) ===
    text = correct_command(raw_text).lower().strip()

    # === Step 2: Intent classification ===

    # Conversation-like input
    if any(kw in text for kw in [
        "what is", "tell me about", "do you think", "why", "how does", "opinion", "should i", "explain",
        "give me information", "define", "difference between", "summarize", "who is"
    ]):
        return "conversation"

    # GUI Input Controls
    if any(kw in text for kw in [
        "move mouse", "click", "scroll", "type", "press", "drag", "drop",
        "switch window", "alt tab", "show desktop", "close window",
        "minimize window", "maximize window", "snap left", "snap right"
    ]):
        return "input_control"

    # File Explorer & System Navigation
    if any(kw in text for kw in [
        "open folder", "open file", "this pc", "list drives",
        "shutdown", "restart", "log out", "sign out"
    ]):
        return "explorer"

    # App launching or general commands
    if any(kw in text for kw in [
        "open", "close", "launch", "play", "start", "stop"
    ]):
        return "command"

    # Learning or training instructions
    if any(kw in text for kw in [
        "remember this", "learn this", "save this", "teach you"
    ]):
        return "learning"

    # Network-related commands
    if any(kw in text for kw in [
        "scan bluetooth", "scan network", "connect network", "connect to",
        "bluetooth", "wifi", "wi-fi"
    ]):
        return "network"

    return "unknown"
