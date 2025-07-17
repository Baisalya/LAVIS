# collect.py
import cv2
import mediapipe as mp
import numpy as np
import os

class GestureCollector:
    def __init__(self, gesture_name, samples=100):
        self.gesture_name = gesture_name
        self.samples = samples
        self.data = []
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands()
        self.mp_draw = mp.solutions.drawing_utils

    def collect(self):
        cap = cv2.VideoCapture(0)
        print(f"👋 Show gesture: {self.gesture_name} — Capturing {self.samples} samples...")
        os.makedirs("gesture_data", exist_ok=True)

        while len(self.data) < self.samples:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.process(rgb)

            if result.multi_hand_landmarks and result.multi_handedness:
                for hand_landmarks, hand_info in zip(result.multi_hand_landmarks, result.multi_handedness):
                    hand_label = hand_info.classification[0].label  # 'Left' or 'Right'
                    landmarks = []
                    for lm in hand_landmarks.landmark:
                        landmarks.extend([lm.x, lm.y])
                    # Add 0 for Left, 1 for Right (numeric encoding)
                    hand_encoded = 0 if hand_label == "Left" else 1
                    self.data.append([hand_encoded] + landmarks)
                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

            cv2.putText(frame, f"Samples: {len(self.data)}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("Collect Gesture", frame)
            if cv2.waitKey(1) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

        np.save(f"gesture_data/{self.gesture_name}.npy", np.array(self.data))
        print(f"✅ Saved {len(self.data)} samples for: {self.gesture_name}")

if __name__ == "__main__":
    gesture_name = input("Enter gesture name (e.g. 'scroll_up'): ")
    collector = GestureCollector(gesture_name)
    collector.collect()
