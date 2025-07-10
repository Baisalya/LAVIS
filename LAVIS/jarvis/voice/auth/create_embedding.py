# create_embedding.py
# 🧠 Extracts a voiceprint (embedding) from 'enrolled.wav' and saves it for fast future authentication
#Run this once after generating enrolled.wav. Then the system authenticates you instantly using the saved embedding.


from voice_auth import save_embedding

# Create a .pt file that stores your unique voice vector
save_embedding()  # -> generates 'enrolled_embedding.pt'

print("✅ Voice embedding saved as 'enrolled_embedding.pt'")
