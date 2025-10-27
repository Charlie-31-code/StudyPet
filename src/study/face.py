"""简易人脸专注度监控模块

功能：
- 每隔 check_interval 秒检测一次摄像头画面，判断专心/分心/缺席
- 维护一个 0-100 的专注度分数（focused 增加，distracted/absent 降低）
- 提供回调 on_status(status: str, score: int) 和 frame 回调 on_frame(frame: np.ndarray)
- 在分心/缺席时调用系统 TTS 进行温和提醒（使用 src.utils.common_utils.play_audio_nonblocking）

实现以线程方式运行摄像头采集与定时检测，UI 可订阅 frame 回调将小人脸窗口显示在倒计时旁。
"""
from __future__ import annotations

import threading
import time
import logging
from typing import Callable, Optional

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None  # 在无 cv2 环境下仍可导入模块，但无法启用摄像头
    np = None

from src.utils.common_utils import play_audio_nonblocking

logger = logging.getLogger(__name__)


class FaceMonitor:
    """摄像头人脸监控器。

    回调：
    - on_status(status: str, score: int) 当每次检测后调用，status one of ('focused','distracted','absent')
    - on_frame(frame: np.ndarray) 每帧回调（UI 可用于显示小窗口），非必须
    """

    def __init__(
        self,
        camera_index: int = 0,
        check_interval: int = 5,
    on_status: Optional[Callable[[str, int], None]] = None,
    on_frame: Optional[Callable[[object], None]] = None,
        show_window: bool = False,
    ):
        self.camera_index = camera_index
        self.check_interval = max(1, int(check_interval))
        self.on_status = on_status
        self.on_frame = on_frame
        self.show_window = show_window

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 专注度分数 0-100
        self.score = 50

        # 会话统计
        self._session_start = None
        self._session_end = None
        self._distracted_count = 0
        self._absent_count = 0
        self._blocked_count = 0
        self._focused_count = 0
        self._total_checks = 0
        self._score_acc = 0.0

        # Haar 级联
        self.face_cascade = None
        self.eye_cascade = None
        if cv2 is not None:
            try:
                self.face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                )
                self.eye_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_eye.xml"
                )
            except Exception as e:
                logger.warning(f"加载 Haar 级联失败: {e}")

        self._last_decision = None
        self._last_check_time = 0.0

        # 摄像头对象按需创建
        self._cap = None

    def start(self):
        with self._lock:
            if self._running:
                return
            if cv2 is None:
                logger.error("cv2 未安装，无法启动 FaceMonitor")
                return
            try:
                self._cap = cv2.VideoCapture(self.camera_index)
            except Exception as e:
                logger.error(f"打开摄像头失败: {e}")
                self._cap = None
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            logger.info("FaceMonitor 已启动")

    def start_session(self):
        """开始一个统计会话，调用于番茄计时开始时"""
        self._session_start = time.time()
        self._session_end = None
        self._distracted_count = 0
        self._absent_count = 0
        self._blocked_count = 0
        self._focused_count = 0
        self._total_checks = 0
        self._score_acc = 0.0

    def end_session(self) -> dict:
        """结束当前会话并返回统计报告字典"""
        self._session_end = time.time()
        duration = None
        if self._session_start and self._session_end:
            duration = int(self._session_end - self._session_start)
        avg_score = None
        if self._total_checks > 0:
            avg_score = float(self._score_acc) / float(self._total_checks)
        report = {
            "start_time": self._session_start,
            "end_time": self._session_end,
            "duration_seconds": duration,
            "total_checks": int(self._total_checks),
            "focused_count": int(self._focused_count),
            "distracted_count": int(self._distracted_count),
            "absent_count": int(self._absent_count),
            "blocked_count": int(self._blocked_count),
            "avg_score": avg_score,
        }
        return report

    def stop(self):
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        if self.show_window and cv2 is not None:
            try:
                cv2.destroyWindow("Face Monitor")
            except Exception:
                pass
        logger.info("FaceMonitor 已停止")

    def _run_loop(self):
        # 采集帧并每 check_interval 做一次决策
        last_frame = None
        while self._running:
            try:
                if not self._cap or not self._cap.isOpened():
                    time.sleep(0.5)
                    continue

                ret, frame = self._cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue

                last_frame = frame

                # 非阻塞地回调帧（UI 可显示小窗口）
                if self.on_frame:
                    try:
                        self.on_frame(frame)
                    except Exception:
                        pass

                # 显示简单窗口（可选，headless 环境可能无效）
                if self.show_window and cv2 is not None:
                    try:
                        disp = cv2.resize(frame, (450, 350))
                        cv2.imshow("Face Monitor", disp)
                        cv2.waitKey(1)
                    except Exception:
                        pass

                now = time.time()
                if now - self._last_check_time >= self.check_interval:
                    self._last_check_time = now
                    status = self._analyze_frame(last_frame)
                    self._apply_status(status)

                # short sleep to reduce cpu
                time.sleep(0.05)

            except Exception as e:
                logger.exception(f"FaceMonitor 循环出错: {e}")
                time.sleep(0.5)

    def _analyze_frame(self, frame) -> str:
        # 返回 'focused' | 'distracted' | 'absent' | 'blocked'
        if frame is None or self.face_cascade is None:
            return "absent"

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 检测摄像头是否被遮挡或画面过暗（均值过低）
            mean_brightness = float(gray.mean())
            if mean_brightness < 18:
                # 画面非常暗，可能被遮挡
                return "blocked"

            # 更灵敏的检测参数（降低 minSize、减小 scaleFactor）
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40)
            )
            if len(faces) == 0:
                return "absent"

            # 检测是否能检测到眼睛（简单视为正脸/专注）
            for (x, y, w, h) in faces:
                roi_gray = gray[y : y + h, x : x + w]
                eyes = self.eye_cascade.detectMultiScale(
                    roi_gray, scaleFactor=1.05, minNeighbors=3, minSize=(10, 10)
                )
                if len(eyes) >= 1:
                    return "focused"
            # 有脸但没检测到眼睛 -> 可能分心或侧脸
            return "distracted"
        except Exception as e:
            logger.exception(f"人脸分析失败: {e}")
            return "absent"

    def _apply_status(self, status: str):
        # 根据状态调整分数
        old = self.score
        # 统计次数
        self._total_checks += 1

        if status == "focused":
            # 专注时缓慢提升
            self.score = min(100, self.score + 2)
            self._focused_count += 1
            # 回到专注后重置分心计数
            self._distracted_count = 0
        elif status == "distracted":
            self.score = max(0, self.score - 3)
            self._distracted_count += 1
        elif status == "blocked":
            # 摄像头被遮挡，较大幅度下降
            self.score = max(0, self.score - 8)
            self._blocked_count += 1
        else:  # absent
            self.score = max(0, self.score - 6)
            self._absent_count += 1

        # 累计分数用于会话平均
        try:
            self._score_acc += float(self.score)
        except Exception:
            pass

        # 回调（始终回调状态）
        try:
            if self.on_status:
                self.on_status(status, self.score)
        except Exception:
            pass

        # 提醒策略已由 UI 层统一控制。为了避免在番茄计时过程中重复打断用户，
        # FaceMonitor 不再在检测循环中直接触发语音提醒。
        # 如果需要在外部触发一次性提醒（例如开始/结束时），请由 UI 插件
        # 使用配置的语音风格调用 play_audio_personalized。

        # 专注时可以触发正向反馈（例如 UI 切换到开心表情），由回调处理
        self._last_decision = status

    def get_score(self) -> int:
        return int(self.score)


__all__ = ["FaceMonitor"]
