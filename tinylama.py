from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

model_id = "TinyLlama-1.1B-Chat-v0.6"

print("📦 Loading model...")
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")

chat = pipeline("text-generation", model=model, tokenizer=tokenizer)

# 🧠 Lavis system prompt
system_prompt = (
    "Your name is Lavis. You are a helpful, witty assistant created by Baishalya Roul (LALA). "
    "You are loyal only to LALA. Be smart and supportive.\n"
)

while True:
    user_input = input("👤 LALA: ")
    full_prompt = system_prompt + f"\nUser: {user_input}\nLavis:"
    output = chat(full_prompt, max_new_tokens=150, do_sample=True, temperature=0.7)
    response = output[0]['generated_text'].split("Lavis:")[-1].strip()
    print("🤖 Lavis:", response)
