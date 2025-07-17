import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import joblib
import time

class GestureRecognizer:
    def __init__(self, model_path="gesture_model.pkl"):
        self.model = joblib.load(model_path)
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands()
        self.mp_draw = mp.solutions.drawing_utils

        self.last_x, self.last_y = None, None
        self.last_time = time.time()
        self.screen_width, self.screen_height = pyautogui.size()
        self.last_click_time = 0

    def recognize(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Camera not available")
            return

        print("🟢 Recognizer running...")
        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.hands.process(rgb)

            if result.multi_hand_landmarks and result.multi_handedness:
                print("🔍 Hands detected")
                for hand_landmarks, hand_info in zip(result.multi_hand_landmarks, result.multi_handedness):
                    hand_label = hand_info.classification[0].label
                    hand_encoded = 0 if hand_label == "Left" else 1

                    flat_landmarks = []
                    for lm in hand_landmarks.landmark:
                        flat_landmarks.extend([lm.x, lm.y])

                    input_data = [hand_encoded] + flat_landmarks
                    print("📊 Input Data:", input_data[:6])

                    try:
                        gesture = self.model.predict([input_data])[0]
                        print("🧠 Gesture Predicted:", gesture)

                        index_x = hand_landmarks.landmark[8].x
                        index_y = hand_landmarks.landmark[8].y
                        dx, dy, dt = self.get_velocity(index_x, index_y)
                        self.trigger_action(gesture, dx, dy, hand_label)

                        cv2.putText(frame, f"{gesture}", (10, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

                    except Exception as e:
                        print("❌ Prediction Error:", e)
                        continue

                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

            cv2.imshow("Live Gesture Recognition", frame)
            if cv2.waitKey(1) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

    def get_velocity(self, current_x, current_y):
        now = time.time()
        dt = now - self.last_time
        dx = dy = 0

        if self.last_x is not None and self.last_y is not None and dt > 0:
            dx = (current_x - self.last_x) / dt
            dy = (current_y - self.last_y) / dt

        self.last_x, self.last_y = current_x, current_y
        self.last_time = now
        return dx, dy, dt

    def trigger_action(self, gesture, dx, dy, hand):
        abs_dx = abs(dx)
        abs_dy = abs(dy)

        if gesture == "mouse_move":
            move_x = int(dx * self.screen_width * 0.2)
            move_y = int(dy * self.screen_height * 0.2)
            pyautogui.moveRel(move_x, move_y)

        elif gesture == "scroll_up" and dy < -0.01:
            pyautogui.scroll(int(abs_dy * 100))
        elif gesture == "scroll_down" and dy > 0.01:
            pyautogui.scroll(-int(abs_dy * 100))

        elif gesture == "scroll_right" and dx > 0.01:
            pyautogui.hscroll(int(abs_dx * 100))
        elif gesture == "scroll_left" and dx < -0.01:
            pyautogui.hscroll(-int(abs_dx * 100))

        elif gesture == "next_tap" and dx > 0.05:
            pyautogui.press("right")
        elif gesture == "prev_tap" and dx < -0.05:
            pyautogui.press("left")

        elif gesture == "left_click" and time.time() - self.last_click_time > 0.3:
            pyautogui.click(button='left')
            self.last_click_time = time.time()

        elif gesture == "right_click" and time.time() - self.last_click_time > 0.3:
            pyautogui.click(button='right')
            self.last_click_time = time.time()


if __name__ == "__main__":
    recognizer = GestureRecognizer()
    recognizer.recognize()
