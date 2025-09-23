import requests

# 🔑 Gemini API Key (from Google AI Studio)
GEMINI_API_KEY = "AIzaSyCf29NxuCUdPvdwSdxyoHTjW-G10e6EiGo"

# ⚡ Choose model
GEMINI_MODEL = "gemini-1.5-flash-latest"  # Or "models/gemini-1.5-pro-latest"

def ask_gemini(prompt: str) -> str:
    """
    Send a prompt directly to Google's Gemini API and return the response.
    """
    if not GEMINI_API_KEY:
        print("❌ Gemini API key not set.")
        return None

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ]
            },
            timeout=15
        )

        if response.status_code != 200:
            print(f"❌ Gemini API error: {response.status_code}")
            print(response.text)
            return None

        data = response.json()

        # Extract text safely
        if "candidates" in data and len(data["candidates"]) > 0:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            return None

    except Exception as e:
        print("❌ Exception in Gemini API:", e)
        return None


if __name__ == "__main__":
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            break
        reply = ask_gemini(user_input)
        if reply:
            print("Lavis:", reply)
