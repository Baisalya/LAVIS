from ctransformers import AutoModelForCausalLM

# Load the GGUF model
llm = AutoModelForCausalLM.from_pretrained(
    '.',  # current directory
    model_file='ggml-model-q4_0.gguf',  # your model file name
    model_type='llama',  # TinyLlama is based on LLaMA
    max_new_tokens=256,
    gpu_layers=0 # use 0 for CPU only; increase if you have GPU
)

# Interactive loop
print("🦙 TinyLlama Chat. Type 'exit' to quit.")
while True:
    question = input("\nYou: ")
    if question.strip().lower() in ['exit', 'quit']:
        print("Goodbye!")
        break
    answer = llm(question)
    print("TinyLlama:", answer)
