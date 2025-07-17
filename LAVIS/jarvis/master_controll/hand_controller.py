import cv2
import numpy as np
import mediapipe as mp
import pyautogui
import time
#from LAVIS.hud_display import #show_hud_reply

pyautogui.FAILSAFE = False

class HandControl:
    def __init__(self):
        self.cam_width = 640
        self.cam_height = 480
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7)
        self.mp_draw = mp.solutions.drawing_utils
        self.screen_width, self.screen_height = pyautogui.size()

        self.prev_x, self.prev_y = 0, 0
        self.smooth_x, self.smooth_y = 0, 0
        self.smoothing = 0.2
        self.velocity_threshold = 40
        self.last_action_time = 0

    def get_landmarks(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)
        landmarks = []

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                for id, lm in enumerate(hand_landmarks.landmark):
                    cx = int(lm.x * self.cam_width)
                    cy = int(lm.y * self.cam_height)
                    landmarks.append((cx, cy))
                self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        return landmarks

    def fingers_up(self, lm_list):
        tips = [4, 8, 12, 16, 20]
        fingers = []
        fingers.append(lm_list[4][0] > lm_list[3][0])  # Thumb
        for i in range(1, 5):
            fingers.append(lm_list[tips[i]][1] < lm_list[tips[i] - 2][1])  # Other fingers
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

        #show_hud_reply("🖐️ Hand control mode activated. Press ESC to exit.")

        while True:
            ret, frame = cap.read()
            frame = cv2.flip(frame, 1)
            landmarks = self.get_landmarks(frame)

            if landmarks:
                index = landmarks[8]
                x, y = index
                fingers = self.fingers_up(landmarks)
                up_count, down_count = self.analyze_finger_directions(landmarks)

                screen_x = np.interp(x, (100, self.cam_width - 100), (0, self.screen_width))
                screen_y = np.interp(y, (100, self.cam_height - 100), (0, self.screen_height))

                self.smooth_x = self.smooth_x + (screen_x - self.smooth_x) * self.smoothing
                self.smooth_y = self.smooth_y + (screen_y - self.smooth_y) * self.smoothing

                # Gesture: Index + Middle finger for move and horizontal scroll
                if fingers[1] and fingers[2] and not any(fingers[3:]):
                    pyautogui.moveTo(self.smooth_x, self.smooth_y)
                    dx = x - self.prev_x
                    if time.time() - self.last_action_time > 0.4:
                        if dx > self.velocity_threshold:
                            pyautogui.hscroll(30)
                            #show_hud_reply("➡️ Scroll Right")
                            self.last_action_time = time.time()
                        elif dx < -self.velocity_threshold:
                            pyautogui.hscroll(-30)
                            #show_hud_reply("⬅️ Scroll Left")
                            self.last_action_time = time.time()
                    self.prev_x, self.prev_y = x, y

                elif fingers[2] and not fingers[1] and not any(fingers[3:]):
                    pyautogui.click(button='right')
                    #show_hud_reply("🖱️ Right Click")
                    time.sleep(0.2)

                elif fingers[1] and not fingers[2] and not any(fingers[3:]):
                    pyautogui.click(button='left')
                    #show_hud_reply("🖱️ Left Click")
                    time.sleep(0.2)

                elif up_count in [3, 4]:
                    pyautogui.scroll(30)
                    #show_hud_reply("⬆️ Scrolling Up")
                    time.sleep(0.2)

                elif down_count in [3, 4]:
                    pyautogui.scroll(-30)
                    #show_hud_reply("⬇️ Scrolling Down")
                    time.sleep(0.2)

                elif not any(fingers[1:]):
                    pyautogui.doubleClick()
                    #show_hud_reply("🖱️ Double Click")
                    time.sleep(0.3)

                elif self.is_thumb_index_touching(landmarks):
                    pyautogui.mouseDown(button='left')
                    #show_hud_reply("✋ Dragging...")
                    time.sleep(0.3)
                    pyautogui.mouseUp(button='left')
                    #show_hud_reply("🖱️ Drag Complete")

                elif fingers[0] and not any(fingers[1:]):
                    pyautogui.hotkey('win', 'down')
                    #show_hud_reply("🧊 Minimize Window")
                    time.sleep(0.3)

                elif all(fingers):
                    pyautogui.hotkey('win', 'up')
                    #show_hud_reply("🪟 Maximize/Restore Window")
                    time.sleep(0.3)

                # 🔥 New Gesture 1: Backhand Scroll Down
                if all(fingers) and down_count >= 4:
                    pyautogui.scroll(-90)  # Fast scroll down
                    #show_hud_reply("💨 Fast Scroll Down (Backhand Detected)")
                    time.sleep(0.15)

                # 🔥 New Gesture 2: Upward Swipe to Scroll Up
                curr_time = time.time()
                dy = self.prev_y - y
                if fingers[1] and all(fingers[2:]) and dy > 60 and (curr_time - self.last_action_time) > 0.5:
                    pyautogui.scroll(90)  # Fast scroll up
                    #show_hud_reply("👆 Scroll Up (Hand Swipe Detected)")
                    self.last_action_time = curr_time

                self.prev_x, self.prev_y = x, y

            cv2.imshow("Jarvis Hand Control", frame)
            if cv2.waitKey(1) == 27:
                break

        cap.release()
        cv2.destroyAllWindows()
if __name__=='__main__':
    HandControl().run()