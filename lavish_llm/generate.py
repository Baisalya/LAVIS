from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Load your trained model and tokenizer
MODEL_DIR = "custom_llm_knowledge"  # or use path where model is saved
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(MODEL_DIR)

# Simple text generation loop
print("🧠 Chat with your fine-tuned LLM (type 'exit' to quit):\n")
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        break

    inputs = tokenizer(user_input, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=True,
            top_k=50,
            top_p=0.95,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id
        )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Remove user's prompt from response
    reply = response[len(user_input):].strip()
    print("LLM:", reply)
