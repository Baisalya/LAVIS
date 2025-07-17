# scroll_controller.py
import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import joblib
import time

class ScrollController:
    def __init__(self, model_path="gesture_model.pkl"):
        self.model = joblib.load(model_path)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands()
        self.mp_draw = mp.solutions.drawing_utils

        self.last_x, self.last_y = None, None
        self.last_time = time.time()

    def get_velocity(self, current_x, current_y):
        now = time.time()
        dt = now - self.last_time
        dx = dy = 0
        if self.last_x is not None and self.last_y is not None and dt > 0:
            dx = (current_x - self.last_x) / dt
            dy = (current_y - self.last_y) / dt
        self.last_x, self.last_y = current_x, current_y
        self.last_time = now
        return dx, dy

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Could not open camera.")
            return

        print("🖐️ Scroll control mode running. Use 'scroll up' and 'scroll down' gestures. ESC to stop.")

        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.process(rgb)

            if result.multi_hand_landmarks and result.multi_handedness:
                for hand_landmarks, hand_info in zip(result.multi_hand_landmarks, result.multi_handedness):
                    flat_landmarks = []
                    for lm in hand_landmarks.landmark:
                        flat_landmarks.extend([lm.x, lm.y])
                    hand_label = hand_info.classification[0].label
                    hand_encoded = 0 if hand_label == "Left" else 1
                    input_data = [hand_encoded] + flat_landmarks

                    try:
                        gesture = self.model.predict([input_data])[0]
                        index_x = hand_landmarks.landmark[8].x
                        index_y = hand_landmarks.landmark[8].y
                        dx, dy = self.get_velocity(index_x, index_y)

                        if gesture == "scroll up" and dy < -0.01:
                            scroll_amount = int(abs(dy) * 100)
                            pyautogui.scroll(scroll_amount)
                            print(f"⬆️ Scrolling up ({scroll_amount})")

                        elif gesture == "scroll down" and dy > 0.01:
                            scroll_amount = int(abs(dy) * 100)
                            pyautogui.scroll(-scroll_amount)
                            print(f"⬇️ Scrolling down ({scroll_amount})")

                        cv2.putText(frame, f"{gesture}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                        self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

                    except Exception as e:
                        print("❌ Error:", e)

            cv2.imshow("🖱️ Scroll Controller", frame)
            if cv2.waitKey(1) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    ScrollController().run()
