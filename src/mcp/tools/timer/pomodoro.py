import threading
import time
from enum import Enum

class PomodoroState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    BREAK = "break"

class PomodoroTimer:
    def __init__(self, work_minutes=25, break_minutes=5, on_tick=None, on_state_change=None):
        self.work_seconds = int(work_minutes * 60)
        self.break_seconds = int(break_minutes * 60)
        self.on_tick = on_tick
        self.on_state_change = on_state_change
        self._timer = None
        self._remaining = self.work_seconds
        self.state = PomodoroState.IDLE
        self._lock = threading.Lock()

    def _run_tick(self):
        with self._lock:
            if self.state != PomodoroState.RUNNING:
                return
            self._remaining -= 1
            if self.on_tick:
                self.on_tick(self._remaining)
            if self._remaining <= 0:
                # 切换到休息或结束
                self.state = PomodoroState.BREAK if self.state == PomodoroState.RUNNING else PomodoroState.IDLE
                if self.on_state_change:
                    self.on_state_change(self.state)
                # 如果进入休息，启动休息计时
                if self.state == PomodoroState.BREAK:
                    self._remaining = self.break_seconds
                    self._schedule_tick()
                return
            self._schedule_tick()

    def _schedule_tick(self):
        self._timer = threading.Timer(1.0, self._run_tick)
        self._timer.daemon = True
        self._timer.start()

    def start(self):
        with self._lock:
            if self.state == PomodoroState.RUNNING:
                return
            self.state = PomodoroState.RUNNING
            if self._remaining <= 0:
                self._remaining = self.work_seconds
            if self.on_state_change:
                self.on_state_change(self.state)
            self._schedule_tick()

    def pause(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if self.state == PomodoroState.RUNNING:
                self.state = PomodoroState.PAUSED
                if self.on_state_change:
                    self.on_state_change(self.state)

    def stop(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self.state = PomodoroState.IDLE
            self._remaining = self.work_seconds
            if self.on_state_change:
                self.on_state_change(self.state)

    def remaining_seconds(self):
        with self._lock:
            return self._remaining