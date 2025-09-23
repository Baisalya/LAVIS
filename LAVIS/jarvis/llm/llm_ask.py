# llm_ask_enhanced.py  (replace or add next to existing llm_ask.py)
import json
import os
import time
from typing import Optional

from LAVIS.jarvis.llm.gemini_client import ask_gemini
from LAVIS.jarvis.llm.groq_client import ask_groq
from LAVIS.jarvis.llm.ollama_client import ask_ollama

# profile helpers
from LAVIS.jarvis.apps.userai.user_profile import load_user_profile, build_system_prompt, answer_about_user

# embeddings & vector store (FAISS)
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # small & fast; swap if you want
_embed_model = SentenceTransformer(EMBED_MODEL_NAME)


class SimpleMemory:
    """A tiny in-memory vector DB for short-term memory using FAISS."""
    def __init__(self, dim=384):
        self.dim = dim
        self.index = faiss.IndexFlatL2(dim)
        self.items = []  # list of (timestamp, text)

    def add(self, text: str):
        vec = _embed_model.encode([text]).astype(np.float32)
        self.index.add(vec)
        self.items.append((time.time(), text))

    def retrieve(self, query: str, k=3):
        if len(self.items) == 0:
            return []
        qv = _embed_model.encode([query]).astype(np.float32)
        dists, ids = self.index.search(qv, min(k, len(self.items)))
        results = []
        for idx in ids[0]:
            if idx < len(self.items):
                results.append(self.items[idx][1])
        return results


class LLMFallback:
    def __init__(self, profile_path="user_profile.json"):
        self.ask_gemini = ask_gemini
        self.ask_groq = ask_groq
        self.ask_ollama = ask_ollama

        # load user profile
        self.profile = load_user_profile(profile_path)

        # build persona system prompt only (no explicit reasoning text)
        self.system_prompt = build_system_prompt(self.profile) + "\nAnswer in Lavis persona."

        # memory
        emb_dim = _embed_model.get_sentence_embedding_dimension()
        self.mem = SimpleMemory(dim=emb_dim)

    def _compose_prompt(self, user_query: str) -> str:
        # quick check for direct profile question
        profile_answer = answer_about_user(user_query, self.profile)

        # retrieve recent short-term memory
        retrieved = self.mem.retrieve(user_query, k=4)
        memory_context = ""
        if retrieved:
            memory_context = "\nRecent relevant memories:\n- " + "\n- ".join(retrieved)

        # construct system + user prompt
        composed = (
            f"SYSTEM:\n{self.system_prompt}\n\n"
            f"{memory_context}\n\n"
            f"USER: {user_query}\n\n"
            "ASSISTANT:"
        )

        # inject profile answer hint if applicable
        if profile_answer:
            composed += f"\n\n(HINT: {profile_answer})\n\nASSISTANT:"

        return composed

    def _call_provider(self, provider_name, func, prompt):
        try:
            return func(prompt)
        except Exception as e:
            print(f"⚠️ {provider_name} failed: {e}")
            return None

    def ask(self, user_query: str) -> str:
        prompt = self._compose_prompt(user_query)

        for name, func in [("Gemini", self.ask_gemini),
                           ("Groq", self.ask_groq),
                           ("Ollama", self.ask_ollama)]:
            resp = self._call_provider(name, func, prompt)
            if resp and isinstance(resp, str) and len(resp.strip()) > 0:
                # store short memory (be careful with PII)
                mem_text = f"Q: {user_query} | A: {resp[:400]}"  # truncate to save space
                self.mem.add(mem_text)
                print(f"✅ Answered by {name}")
                return resp

        return "❌ All providers failed."


if __name__ == "__main__":
    llm = LLMFallback()
    print("Lavis is ready. Type exit/quit to stop.")
    while True:
        q = input("You: ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        print("Lavis:", llm.ask(q), "\n")
