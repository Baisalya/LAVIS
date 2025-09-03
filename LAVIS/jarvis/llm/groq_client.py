import requests
import json
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, build_system_prompt

GROQ_API_KEY = "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"
GROQ_MODEL = "llama-3.3-70b-versatile"
def ask_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        print("❌ Groq API key not set.")
        return None

    # 🔁 Load latest profile & build system context dynamically
    profile = load_user_profile()
    system_context = build_system_prompt(profile)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_context},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            },
            timeout=15
        )

        if response.status_code != 200:
            print(f"❌ Groq API error: {response.status_code}")
            print(response.text)
            return None

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print("❌ Exception in Groq API:", e)
        return None
if __name__ == "__main__":
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        reply = ask_groq(user_input)
        if reply:
            print("Lavis:", reply)