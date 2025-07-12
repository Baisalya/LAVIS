import re

def parse_command(text):
    text = text.lower()
    if "search" in text:
        match = re.search(r"search for (.+)", text)
        if match:
            return {"intent": "search_web", "query": match.group(1)}
    elif "open" in text:
        match = re.search(r"open (.+)", text)
        if match:
            return {"intent": "open_app", "app": match.group(1)}
    elif "click" in text:
        match = re.search(r"click (.+)", text)
        if match:
            return {"intent": "click_text", "text": match.group(1)}
    elif "scroll down" in text:
        return {"intent": "scroll", "direction": "down"}
    return {"intent": "unknown"}
