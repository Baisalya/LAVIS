import time
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Optional

from LAVIS.jarvis.llm.ollama_client import ask_ollama

# profile helpers
from LAVIS.jarvis.apps.userai.user_profile import (
    load_user_profile,
    build_system_prompt,
    answer_about_user
)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
_embed_model = None
LLM_TIMEOUT_SECONDS = float(os.getenv("LAVIS_LLM_TIMEOUT", "18"))
_llm_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="lavis-llm")


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


class SimpleMemory:
    """A tiny in-memory vector DB for short-term memory using FAISS."""
    def __init__(self, dim=None):
        self.index = None
        self.items = []
        self.dim = dim

    def add(self, text: str):
        self.items.append((time.time(), text))
        try:
            import numpy as np
            import faiss
            model = _get_embed_model()
            vec = model.encode([text]).astype(np.float32)
            if self.index is None:
                self.index = faiss.IndexFlatL2(vec.shape[1])
            self.index.add(vec)
        except Exception as e:
            print(f"[LLM memory] Vector memory disabled for this item: {e}")

    def retrieve(self, query: str, k=3):
        if not self.items:
            return []

        try:
            if self.index is None:
                return [text for _, text in self.items[-k:]]
            import numpy as np
            qv = _get_embed_model().encode([query]).astype(np.float32)
            _, ids = self.index.search(qv, min(k, len(self.items)))
            return [self.items[i][1] for i in ids[0] if i < len(self.items)]
        except Exception as e:
            print(f"[LLM memory] Falling back to recent memory: {e}")
            return [text for _, text in self.items[-k:]]


class LLMFallback:
    def __init__(self, profile_path="user_profile.json"):
        # ONLY OLLAMA
        self.ask_ollama = ask_ollama

        # load user profile
        self.profile = load_user_profile(profile_path)

        # persona system prompt
        self.system_prompt = build_system_prompt(self.profile) + "\nAnswer in Lavis persona."

        # memory
        self.mem = SimpleMemory()

    def _compose_prompt(self, user_query: str) -> str:
        profile_answer = answer_about_user(user_query, self.profile)

        # retrieve memory
        retrieved = self.mem.retrieve(user_query, k=4)
        memory_context = ""
        if retrieved:
            memory_context = "\nRecent relevant memories:\n- " + "\n- ".join(retrieved)

        prompt = (
            f"SYSTEM:\n{self.system_prompt}\n\n"
            f"{memory_context}\n\n"
            f"USER: {user_query}\n\n"
            "ASSISTANT:"
        )

        if profile_answer:
            prompt += f"\n\n(HINT: {profile_answer})\n\nASSISTANT:"

        return prompt

    def ask(self, user_query: str) -> str:
        prompt = self._compose_prompt(user_query)

        try:
            future = _llm_executor.submit(self.ask_ollama, prompt)
            response = future.result(timeout=LLM_TIMEOUT_SECONDS)

            if response and isinstance(response, str):
                # store memory (truncate to save space)
                mem_text = f"Q: {user_query} | A: {response[:400]}"
                self.mem.add(mem_text)

                return response

            return "I heard you, but my local language model did not return a reply."

        except Exception as e:
            if isinstance(e, TimeoutError):
                return "My local language model is taking too long right now. I heard you, though."
            return f"My local language model is unavailable right now: {e}"


if __name__ == "__main__":
    llm = LLMFallback()
    print("Lavis (Ollama only) is ready. Type exit/quit to stop.")

    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}:
            break

        print("Lavis:", llm.ask(q), "\n")
