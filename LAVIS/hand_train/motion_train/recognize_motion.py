# recognize_motion.py
import cv2
import mediapipe as mp
import numpy as np
import time
import json
from collections import deque
from tensorflow.keras.models import load_model
import pyautogui

# === Load Model and Label Map ===
model = load_model("motion_model.h5")
with open("label_map.json", "r") as f:
    label_map = json.load(f)
rev_label_map = {v: k for k, v in label_map.items()}

# === Mediapipe ===
mp_hands = mp.solutions.hands
hands = mp_hands.Hands()
mp_draw = mp.solutions.drawing_utils

# === Config ===
SEQ_LEN = 20
buffer = deque(maxlen=SEQ_LEN)
last_prediction = ""
last_action_time = time.time()
prev_hand_center = None  # For motion speed tracking

# === Webcam ===
cap = cv2.VideoCapture(0)
print("🟢 Motion recognition + mouse control started (ESC to quit)")

while True:
    ret, frame = cap.read()
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if result.multi_hand_landmarks and result.multi_handedness:
        for hand_landmarks, hand_info in zip(result.multi_hand_landmarks, result.multi_handedness):
            hand_label = hand_info.classification[0].label
            hand_encoded = 0 if hand_label == "Left" else 1

            flat_landmarks = []
            cx, cy = 0, 0  # For calculating hand center

            for lm in hand_landmarks.landmark:
                flat_landmarks.extend([lm.x, lm.y])
                cx += lm.x
                cy += lm.y

            cx /= len(hand_landmarks.landmark)
            cy /= len(hand_landmarks.landmark)
            current_hand_center = (cx, cy)

            buffer.append([hand_encoded] + flat_landmarks)
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # === Mouse move and scroll speed detection ===
            speed_x, speed_y = 0, 0
            if prev_hand_center is not None:
                dx = current_hand_center[0] - prev_hand_center[0]
                dy = current_hand_center[1] - prev_hand_center[1]
                speed_x = dx * 1000  # Horizontal speed for mouse
                speed_y = dy * 1000  # Vertical speed for scroll/mouse

                # === Move Mouse ===
                pyautogui.moveRel(int(speed_x), int(speed_y), duration=0.05)  # smooth move

            prev_hand_center = current_hand_center

            if len(buffer) == SEQ_LEN:
                input_data = np.expand_dims(np.array(buffer), axis=0)
                prediction = model.predict(input_data)[0]
                pred_index = np.argmax(prediction)
                pred_label = rev_label_map[pred_index]
                confidence = prediction[pred_index]

                if confidence > 0.85 and time.time() - last_action_time > 0.5:
                    print(f"🧠 Gesture: {pred_label} ({confidence:.2f})")
                    last_action_time = time.time()

                    # === Scroll and Flick actions ===
                    if pred_label == "scroll up":
                        scroll_amt = int(min(max(speed_y, 50), 300))
                        pyautogui.scroll(scroll_amt)
                    elif pred_label == "scroll down":
                        scroll_amt = int(min(max(-speed_y, 50), 300))
                        pyautogui.scroll(-scroll_amt)
                    elif pred_label == "flick_right":
                        pyautogui.press("right")
                    elif pred_label == "flick_left":
                        pyautogui.press("left")

                    last_prediction = pred_label

                cv2.putText(frame, f"{pred_label} ({confidence:.2f})", (10, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("🖐️ Motion Recognizer + Mouse Control", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
