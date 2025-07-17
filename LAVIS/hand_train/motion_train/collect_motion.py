# collect_motion.py (SMOOTH VERSION)
import cv2
import mediapipe as mp
import numpy as np
import os
from collections import deque
import time

class MotionGestureCollector:
    def __init__(self, gesture_name, sequence_length=20, samples=50):
        self.gesture_name = gesture_name
        self.sequence_length = sequence_length
        self.samples = samples
        self.data = []
        self.buffer = deque(maxlen=sequence_length)

        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils

    def collect(self):
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffering lag

        print(f"🎥 Show motion gesture: {self.gesture_name} — Capturing {self.samples} sequences of {self.sequence_length} frames each...")
        os.makedirs("gesture_data", exist_ok=True)

        saved_count = 0
        prev_time = time.time()

        while saved_count < self.samples:
            ret, frame = cap.read()
            if not ret:
                continue

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.process(rgb)

            if result.multi_hand_landmarks and result.multi_handedness:
                for hand_landmarks, hand_info in zip(result.multi_hand_landmarks, result.multi_handedness):
                    hand_label = hand_info.classification[0].label
                    hand_encoded = 0 if hand_label == "Left" else 1

                    landmarks = []
                    for lm in hand_landmarks.landmark:
                        landmarks.extend([lm.x, lm.y])

                    self.buffer.append([hand_encoded] + landmarks)

                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                    if len(self.buffer) == self.sequence_length:
                        self.data.append(list(self.buffer))
                        saved_count += 1
                        self.buffer.clear()
                        print(f"✅ Sequence {saved_count}/{self.samples} captured")

            # === Optional FPS Display ===
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time + 1e-5)
            prev_time = curr_time
            cv2.putText(frame, f"FPS: {int(fps)}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            cv2.putText(frame, f"Sequences: {saved_count}/{self.samples}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

            cv2.imshow("Motion Gesture Collector", frame)

            if cv2.waitKey(1) & 0xFF == 27:  # ESC to exit
                break

        cap.release()
        cv2.destroyAllWindows()

        data_array = np.array(self.data)
        save_path = f"gesture_data/{self.gesture_name}_motion.npy"
        np.save(save_path, data_array)
        print(f"💾 Saved {saved_count} sequences to {save_path}")

if __name__ == "__main__":
    gesture_name = input("Enter dynamic gesture name (e.g. 'flick_right'): ")
    collector = MotionGestureCollector(gesture_name)
    collector.collect()
