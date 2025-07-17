import cv2
import numpy as np
import mediapipe as mp
import pyautogui
import time

pyautogui.FAILSAFE = False

class HandControl:
    def __init__(self):
        self.cam_width = 640
        self.cam_height = 480
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        self.screen_width, self.screen_height = pyautogui.size()

        # Smooth cursor movement
        self.prev_x, self.prev_y = 0, 0
        self.smooth_x, self.smooth_y = 0, 0
        self.smoothing = 0.2

        # Scroll/swipe thresholds
        self.velocity_threshold = 40
        self.last_action_time = 0
        self.last_scroll_time = 0

        # === Control hand: Set to "Left" or "Right" ===
        self.control_hand = "Right"

    def get_landmarks(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        landmarks = []

        if results.multi_hand_landmarks and results.multi_handedness:
            for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                hand_label = results.multi_handedness[i].classification[0].label
                if hand_label == self.control_hand:
                    for id, lm in enumerate(hand_landmarks.landmark):
                        cx = int(lm.x * self.cam_width)
                        cy = int(lm.y * self.cam_height)
                        landmarks.append((cx, cy))
                    self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    return landmarks
        return []

    def fingers_up(self, lm_list):
        tips = [4, 8, 12, 16, 20]
        fingers = []
        fingers.append(lm_list[4][0] > lm_list[3][0])  # Thumb
        for i in range(1, 5):
            fingers.append(lm_list[tips[i]][1] < lm_list[tips[i] - 2][1])
        return fingers

    def analyze_finger_directions(self, lm_list):
        tips = [8, 12, 16, 20]
        up = 0
        down = 0
        for tip_id in tips:
            tip_y = lm_list[tip_id][1]
            base_y = lm_list[tip_id - 2][1]
            if tip_y < base_y - 10:
                up += 1
            elif tip_y > base_y + 10:
                down += 1
        return up, down

    def is_thumb_index_touching(self, lm_list):
        thumb_tip = lm_list[4]
        index_tip = lm_list[8]
        dist = np.linalg.norm(np.array(thumb_tip) - np.array(index_tip))
        return dist < 30

    def run(self):
        cap = cv2.VideoCapture(0)
        cap.set(3, self.cam_width)
        cap.set(4, self.cam_height)
        cap.set(cv2.CAP_PROP_FPS, 60)

        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            landmarks = self.get_landmarks(frame)

            if landmarks:
                index = landmarks[8]
                x, y = index
                fingers = self.fingers_up(landmarks)
                up_count, down_count = self.analyze_finger_directions(landmarks)

                # Map to screen coordinates
                screen_x = np.interp(x, (100, self.cam_width - 100), (0, self.screen_width))
                screen_y = np.interp(y, (100, self.cam_height - 100), (0, self.screen_height))

                # Smooth movement
                self.smooth_x = self.smooth_x + (screen_x - self.smooth_x) * self.smoothing
                self.smooth_y = self.smooth_y + (screen_y - self.smooth_y) * self.smoothing

                dx = x - self.prev_x
                dy = y - self.prev_y

                # === Move mouse only when index + middle are up ===
                if fingers[1] and fingers[2] and not any(fingers[3:]):
                    if abs(self.smooth_x - self.prev_x) > 1 or abs(self.smooth_y - self.prev_y) > 1:
                        pyautogui.moveTo(self.smooth_x, self.smooth_y)
                        self.prev_x, self.prev_y = self.smooth_x, self.smooth_y

                    # Horizontal scroll with fast hand movement
                    if time.time() - self.last_action_time > 0.4:
                        if dx > self.velocity_threshold:
                            pyautogui.hscroll(30)
                            self.last_action_time = time.time()
                        elif dx < -self.velocity_threshold:
                            pyautogui.hscroll(-30)
                            self.last_action_time = time.time()

                # === Right Click ===
                elif fingers[2] and not fingers[1] and not any(fingers[3:]):
                    pyautogui.click(button='right')
                    time.sleep(0.2)

                # === Left Click ===
                elif fingers[1] and not fingers[2] and not any(fingers[3:]):
                    pyautogui.click(button='left')
                    time.sleep(0.2)

                # === Scroll Up ===
                elif up_count in [3, 4]:
                    pyautogui.scroll(70)
                    time.sleep(0.2)

                # === Scroll Down ===
                elif down_count in [3, 4]:
                    pyautogui.scroll(-100)
                    time.sleep(0.2)

                # === Drag (thumb + index touch) ===
                elif self.is_thumb_index_touching(landmarks):
                    pyautogui.mouseDown(button='left')
                    time.sleep(0.3)
                    pyautogui.mouseUp(button='left')

                # === Double Click ===
                elif not any(fingers[1:]):
                    pyautogui.doubleClick()
                    time.sleep(0.3)

                # === Minimize ===
                elif fingers[0] and not any(fingers[1:]):
                    pyautogui.hotkey('win', 'down')
                    time.sleep(0.3)

                # === Maximize ===
                elif all(fingers):
                    pyautogui.hotkey('win', 'up')
                    time.sleep(0.3)

                # === Fast Swipe Up ===
                if fingers[1] and all(fingers[2:]) and dy < -60 and (time.time() - self.last_scroll_time) > 0.5:
                    pyautogui.scroll(90)
                    self.last_scroll_time = time.time()

                # === Fast Swipe Down ===
                if fingers[1] and all(fingers[2:]) and dy > 60 and (time.time() - self.last_scroll_time) > 0.5:
                    pyautogui.scroll(-90)
                    self.last_scroll_time = time.time()

                # Update previous index finger position
                self.prev_x, self.prev_y = x, y

            cv2.imshow("Jarvis Hand Control", frame)
            if cv2.waitKey(1) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    HandControl().run()
