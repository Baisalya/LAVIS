import speech_recognition as sr

# Languages you want to support
LANGUAGES = {
    "en-IN": "English (India)",
    "hi-IN": "Hindi",
    "or-IN": "Odia"
}

def recognize_audio():
    r = sr.Recognizer()

    # List microphones so user can check which one is correct
    print("\nAvailable microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"{index}: {name}")

    # Use default mic (or set device_index=your_mic_index)
    with sr.Microphone() as source:
        print("\n🎤 Adjusting for ambient noise... please wait")
        r.adjust_for_ambient_noise(source, duration=2)

        print("🎤 Say something in English / Hindi / Odia...")
        audio = r.listen(source)

    # Try each language
    for code, lang_name in LANGUAGES.items():
        try:
            text = r.recognize_google(audio, language=code)
            if text.strip():
                print(f"\n✅ Detected {lang_name} [{code}]: {text}")
                return
        except sr.UnknownValueError:
            print(f"[{code}] ❌ Could not understand")
        except sr.RequestError as e:
            print(f"[{code}] ⚠️ API error: {e}")

    print("\n⚠️ Sorry, could not detect speech in any language.")

if __name__ == "__main__":
    recognize_audio()
