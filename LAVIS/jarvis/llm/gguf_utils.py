# llm_integration/gguf_utils.py
from llama_cpp import Llama
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, build_system_prompt

# 🔧 Load GGUF model ONCE at startup
llm = Llama(
    model_path="ggml-model-q4_0.gguf",  # 👈 change to your real path
    n_ctx=2048,
    n_threads=8,
    use_mlock=True,
)

def ask_my_gguf(prompt: str) -> str:
    try:
        # 1. Load user profile and build Lavis system prompt
        profile = load_user_profile()
        system_prompt = build_system_prompt(profile)

        # 2. Combine system + user prompt
        full_prompt = f"{system_prompt}\n\nUser said: {prompt}\nLavis:"
        output = llm(
            prompt=full_prompt,
            stop=["\n", "User:", "Lavis:"],
            temperature=0.7,
            max_tokens=300,
        )
        return output["choices"][0]["text"].strip()

    except Exception as e:
        print("❌ GGUF model error:", e)
        return "I ran into an error while thinking."
