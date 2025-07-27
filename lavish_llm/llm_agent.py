from transformers import pipeline
from langchain.llms import HuggingFacePipeline

class LLMEngine:
    def __init__(self, model_name="tiiuae/falcon-7b-instruct"):
        pipe = pipeline("text-generation", model=model_name, max_new_tokens=256)
        self.llm = HuggingFacePipeline(pipeline=pipe)
