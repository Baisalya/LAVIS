    import requests
    import json

    def ask_gemini(prompt: str) -> str:
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                print("📄 Loaded config:", config)  # Debug print
                key = config.get("gemini_api_key")
                if not key:
                    print("📄 Gemini API key not found in config:", config)
                    return None
        except Exception as e:
            print("⚠️ Error reading config.json:", e)
            return None

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        try:
            response = requests.post(f"{url}?key={key}", headers=headers, json=payload)
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print("Gemini error:", e)
            return None
