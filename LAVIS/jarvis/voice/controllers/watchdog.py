# watchdog.py

import threading
import time
import traceback

class VoiceWatchdog:
    def __init__(self, name, target_thread_func, health_check_func, restart_func, check_interval=5):
        self.name = name
        self._target_thread_func = target_thread_func
        self._health_check_func = health_check_func
        self._restart_func = restart_func
        self._check_interval = check_interval

        self._watchdog_thread = None
        self._active = False

    def _watchdog_loop(self):
        print(f"🛡️ {self.name} Watchdog started.")
        while self._active:
            time.sleep(self._check_interval)

            try:
                target_thread = self._target_thread_func()
                is_alive = target_thread.is_alive() if target_thread else False
                is_healthy = self._health_check_func()

                if not is_alive:
                    print(f"💥 {self.name} thread is dead. Restarting...")
                    self._restart_func()
                    continue

                if not is_healthy:
                    print(f"⚠️ {self.name} health check failed. Restarting...")
                    self._restart_func()
            except Exception:
                print(f"❌ {self.name} Watchdog crash:")
                traceback.print_exc()

    def start(self):
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            print(f"⚠️ {self.name} Watchdog already running.")
            return
        self._active = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def stop(self):
        self._active = False
