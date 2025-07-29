from langchain_core.language_models import LLM
from typing import List
from .groq_client import ask_groq
from .ollama_client import ask_ollama

class GroqLLM(LLM):
    def _call(self, prompt: str, stop: List[str] = None) -> str:
        return ask_groq(prompt)

    @property
    def _llm_type(self) -> str:
        return "groq_llm"


class OllamaLLM(LLM):
    def __init__(self, model_name: str = "tinyllama"):
        self.model_name = model_name

    def _call(self, prompt: str, stop: List[str] = None) -> str:
        return ask_ollama(prompt, model=self.model_name)

    @property
    def _llm_type(self) -> str:
        return "ollama_llm"
