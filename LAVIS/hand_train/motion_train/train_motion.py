# train_motion.py
import os
import numpy as np
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import ModelCheckpoint

# === Config ===
DATA_DIR = "gesture_data"
SEQUENCE_LENGTH = 20

# === Load Data ===
X, y = [], []
label_map = {}
label_index = 0

for file in os.listdir(DATA_DIR):
    if file.endswith("_motion.npy"):
        label = file.replace("_motion.npy", "")
        if label not in label_map:
            label_map[label] = label_index
            label_index += 1

        data = np.load(os.path.join(DATA_DIR, file))
        X.extend(data)
        y.extend([label_map[label]] * len(data))

X = np.array(X)
y = to_categorical(np.array(y))

print("✅ Data Loaded:", X.shape, "Labels:", y.shape)
print("📚 Classes:", label_map)

# === Train/Test Split ===
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# === Build LSTM Model ===
model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(SEQUENCE_LENGTH, 43)),
    Dropout(0.3),
    LSTM(64),
    Dense(64, activation='relu'),
    Dense(len(label_map), activation='softmax')
])

model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
model.summary()

# === Train ===
model.fit(X_train, y_train, epochs=20, batch_size=16,
          validation_data=(X_test, y_test),
          callbacks=[ModelCheckpoint("motion_model.h5", save_best_only=True)])

# === Save Label Map ===
import json
with open("label_map.json", "w") as f:
    json.dump(label_map, f)

print("✅ Model saved as motion_model.h5")
print("🧠 Labels saved to label_map.json")
