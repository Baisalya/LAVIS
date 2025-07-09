# intent_parser.py
import re

# Sample rules-based intent parser

def parse_intent(text):
    text = text.lower().strip()

    # Wake/sleep
    if "wake up" in text:
        return {"action": "wake_up"}
    if "sleep" in text:
        return {"action": "sleep"}

    # Learning mode
    if "learn" in text:
        return {"action": "learn"}

    # Listing learned commands
    if "what have you learned" in text or "list learned commands" in text:
        return {"action": "list learned"}

    # Renaming commands
    if "rename a command" in text or "rename command" in text:
        return {"action": "rename command"}

    # Deleting commands
    if "forget command" in text or "delete command" in text:
        return {"action": "forget command"}

    # Generic command extraction
    match = re.match(r"(?:jarvis)?\s*(open|start|launch|run)?\s*(.*)", text)
    if match:
        action, command = match.groups()
        return {
            "action": action or "run",
            "command": command.strip()
        }

    # Fallback
    return None
