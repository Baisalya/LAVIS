import json
import re
from datetime import datetime
from fuzzywuzzy import fuzz

def load_user_profile(path="user_profile.json") -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def extract_keywords(text: str):
    text = text.lower()
    return set(re.findall(r"\b(name|age|birthday|dob|creator|created|father|loyal|loyalty|color|favourite|favorite|live|location|hobby|photo|image|picture|purpose|version|yourself|jarvis|who|you|do you do|abilities|what can you do|personality|goal)\b", text))

def answer_about_user(query: str, profile: dict) -> str:
    query = query.lower()
    keywords = extract_keywords(query)

    # === Jarvis self-awareness ===
    if any(k in query for k in ["who are you", "what are you", "what can you do", "jarvis", "yourself", "purpose", "creator", "who created you", "version"]):
        jarvis = profile.get("jarvis_self", {})
        if not jarvis:
            return "I am your assistant, but I don't have a self-profile yet."

        response = (
            f"I am {jarvis.get('name', 'your assistant')}, version {jarvis.get('version', 'unknown')}.\n"
            f"I was created by {jarvis.get('created_by', 'an unknown creator')}.\n"
            f"My personality is {jarvis.get('personality', 'supportive')}.\n"
            f"My main goal is: {jarvis.get('goal', 'assist you')}."
        )
        abilities = jarvis.get("abilities", [])
        if abilities:
            response += "\nI am capable of: " + ", ".join(abilities) + "."
        return response

    # === Personal details about the user ===
    if "name" in keywords:
        return f"Your name is {profile.get('name', 'not set')}."
    
    if "age" in keywords or "birthday" in keywords or "dob" in keywords:
        dob = profile.get("dob")
        if dob:
            birth_year = int(dob.split("-")[0])
            age = datetime.now().year - birth_year
            return f"You were born in {dob}, and you are approximately {age} years old."
        return "I couldn't determine your age."

    if "creator" in keywords or "created" in keywords or "father" in keywords:
        return f"My creator is {profile.get('creator', 'unknown')}."

    if "loyal" in keywords or "loyalty" in keywords:
        return f"I am loyal to {profile.get('loyal_to', 'my creator')}."

    if "color" in keywords or "favourite" in keywords or "favorite" in keywords:
        return f"Your favorite color is {profile.get('favorite_color', 'unknown')}."

    if "hobby" in keywords:
        hobbies = profile.get("hobbies", [])
        return f"Your hobbies include {', '.join(hobbies)}."

    if "live" in keywords or "location" in keywords:
        return f"You live in {profile.get('location', 'an unknown location')}."

    if "photo" in keywords or "image" in keywords or "picture" in keywords:
        return f"Your photo is stored at {profile.get('photo', 'not available')}."

    if "purpose" in keywords or "do you do" in query:
        return profile.get("purpose", "I assist you, but my purpose is not defined.")

    # === Fuzzy fallback: best-effort semantic match ===
    best_score = 0
    best_key = None
    for key in profile:
        if isinstance(profile[key], str):
            score = fuzz.partial_ratio(query, key)
            if score > best_score:
                best_score = score
                best_key = key

    if best_score > 70:
        return f"{best_key.capitalize()}: {profile[best_key]}"

    return None  # Let fallback handle if nothing matched
