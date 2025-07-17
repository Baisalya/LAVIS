import joblib

model = joblib.load("gesture_model.pkl")
print("🧠 Gesture classes the model is trained on:")
print(model.classes_)
