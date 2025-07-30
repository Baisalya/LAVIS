from langchain_core.language_models import LLM
from typing import List, Optional
from .groq_client import ask_groq
from .ollama_client import ask_ollama


class GroqLLM(LLM):
    """
    Custom LLM wrapper to call Groq models.
    """
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        return ask_groq(prompt)

    @property
    def _llm_type(self) -> str:
        return "groq_llm"


class OllamaLLM(LLM):
    """
    Custom LLM wrapper to call Ollama models.
    """
    def __init__(self, model_name: str = "tinyllama"):
        super().__init__()  # required by pydantic.BaseModel under LLM
        object.__setattr__(self, "model_name", model_name)

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        return ask_ollama(prompt, model=self.model_name)

    @property
    def _llm_type(self) -> str:
        return "ollama_llm"
