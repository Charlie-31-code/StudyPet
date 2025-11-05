# Copyright (c) 2025 StudyPet Team(Mia-au,Charlie-31-code,Xenia-www,Sylvia0601)
# MIT License

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
from enum import Enum

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None  # 在无 cv2 环境下仍可导入模块，但无法启用摄像头
    np = None

# 尝试导入YOLO相关库
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    YOLO = None

from src.utils.common_utils import play_audio_nonblocking

logger = logging.getLogger(__name__)


class DetectionMethod(Enum):
    """人脸检测方法枚举"""
    HAAR_CASCADE = "haar_cascade"
    YOLO = "yolo"


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
        detection_method: DetectionMethod = DetectionMethod.HAAR_CASCADE,
        yolo_model_path: str = "yolov8n.pt",
        yolo_device: str = "0" if YOLO_AVAILABLE else "cpu",
        on_status: Optional[Callable[[str, int], None]] = None,
        on_frame: Optional[Callable[[object], None]] = None,
        show_window: bool = False,
    ):
        """初始化 FaceMonitor.

        参数:
            camera_index: 摄像头索引
            check_interval: 检测间隔（秒）
            detection_method: 使用的检测方法（Haar 或 YOLO）
            yolo_model_path: YOLO 模型路径（若使用 YOLO）
            yolo_device: 设备字符串（例如 '0' 或 'cpu'）
            on_status: 状态回调函数(status: str, score: int)
            on_frame: 每帧回调(frame: np.ndarray)
            show_window: 是否显示调试窗口
        """
        self.camera_index = camera_index
        self.check_interval = max(1, int(check_interval))
        self.detection_method = detection_method
        self.yolo_model_path = yolo_model_path
        self.yolo_device = yolo_device  # GPU设备设置
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
        
        # YOLO模型
        self.yolo_model = None
        
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

        # 尝试加载YOLO模型
        if YOLO_AVAILABLE and self.detection_method == DetectionMethod.YOLO:
            try:
                self.yolo_model = YOLO(self.yolo_model_path)
                logger.info(f"成功加载YOLO模型: {self.yolo_model_path}")
            except Exception as e:
                logger.warning(f"加载YOLO模型失败: {e}")
                self.detection_method = DetectionMethod.HAAR_CASCADE  # 回退到Haar Cascade

        self._last_decision = None
        self._last_check_time = 0.0

        # 连续性平滑（防止单帧噪声导致误判）
        # 记录每种状态的连续帧计数
        self._streaks = {"focused": 0, "distracted": 0, "absent": 0, "blocked": 0}
        # 需要连续多少次才认为状态已稳定（可调）
        # 将 absent 的阈值适当提高，避免短暂低头/遮挡被误判为离开
        self._streak_thresholds = {"focused": 1, "distracted": 3, "absent": 3, "blocked": 2}

        # 记录上次检测到人脸的时间，用于短时内优先判定为 distracted（避免误报 absent）
        self._last_face_seen_ts: Optional[float] = None

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
                # 设置缓冲区大小为1以减少延迟
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # 添加额外的缓冲区设置以确保最小延迟
                self._cap.set(cv2.CAP_PROP_FPS, 30)

                # 启动检测线程
                self._running = True
                self._thread = threading.Thread(target=self._detect_loop, daemon=True)
                self._thread.start()
                logger.info("FaceMonitor 已启动")
            except Exception as e:
                logger.error(f"启动摄像头失败: {e}")
                self._running = False

    def start_session(self):
        """开始新的监控会话"""
        self._session_start = time.time()
        self._distracted_count = 0
        self._absent_count = 0
        self._blocked_count = 0
        self._focused_count = 0
        self._total_checks = 0
        self._score_acc = 0.0
        self.score = 50
        logger.info("FaceMonitor 会话已开始")

    def end_session(self):
        """结束当前会话并返回统计信息"""
        self._session_end = time.time()
        
        # 计算平均分数
        avg_score = 0
        if self._total_checks > 0:
            avg_score = self._score_acc / self._total_checks
            
        session_data = {
            "duration": self._session_end - self._session_start if self._session_start else 0,
            "avg_score": avg_score,
            "focused_count": self._focused_count,
            "distracted_count": self._distracted_count,
            "absent_count": self._absent_count,
            "blocked_count": self._blocked_count,
            "total_checks": self._total_checks,
        }
        
        logger.info(f"FaceMonitor 会话已结束: {session_data}")
        return session_data

    def stop(self):
        with self._lock:
            if not self._running:
                return
            logger.info("正在停止 FaceMonitor...")
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
            if self._cap:
                self._cap.release()
                self._cap = None
            logger.info("FaceMonitor 已停止")

    def _detect_loop(self):
        """检测主循环"""
        while self._running:
            try:
                if self._cap is None:
                    logger.warning("摄像头未初始化")
                    time.sleep(1)
                    continue
                    
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning("无法从摄像头读取帧")
                    time.sleep(0.1)
                    continue

                current_time = time.time()
                # 控制检测频率
                if current_time - self._last_check_time >= self.check_interval:
                    self._last_check_time = current_time
                    status = self._analyze_frame(frame)
                    self._apply_status(status)
                
                # 调用帧回调（用于UI显示）
                if self.on_frame:
                    try:
                        self.on_frame(frame)
                    except Exception as e:
                        logger.error(f"帧回调出错: {e}")
                        
                # 可选：显示窗口
                if self.show_window and frame is not None:
                    try:
                        cv2.imshow("Face Monitor", frame)
                        cv2.waitKey(1)
                    except Exception as e:
                        logger.error(f"显示窗口出错: {e}")
                        
            except Exception as e:
                logger.error(f"检测循环出错: {e}")
                time.sleep(0.1)
                
        # 清理窗口
        if self.show_window:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

    def _analyze_frame_haar(self, frame) -> str:
        """使用Haar Cascade检测人脸和眼睛"""
        # 返回 'focused' | 'distracted' | 'absent' | 'blocked'
        if frame is None or self.face_cascade is None:
            return "absent"

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 画面亮度与纹理统计，用于区分被遮挡(blocked)与无人(absent)
            mean_brightness = float(gray.mean())
            std_brightness = float(gray.std())

            # 计算边缘数量（Canny）与拉普拉斯方差（纹理）以判断画面是否为单色块或被遮挡
            try:
                edges = cv2.Canny(gray, 50, 150)
                edge_count = int((edges > 0).sum())
            except Exception:
                edge_count = 0

            try:
                lap = cv2.Laplacian(gray, cv2.CV_64F)
                lap_var = float(lap.var())
            except Exception:
                lap_var = 0.0

            # 被遮挡/画面为单色/过暗的判定条件（更鲁棒且更灵敏）：
            # - 平均亮度较低且亮度方差较小；或
            # - 边缘数量较少且拉普拉斯方差低（表示画面无细节）
            # 这些阈值经过放宽以便更早检测到部分遮挡或手掌遮挡等情况。
            if (mean_brightness < 90 and std_brightness < 35) or (edge_count < 200 and lap_var < 40.0):
                return "blocked"

            # 更灵敏的检测参数（降低 minSize、减小 scaleFactor）用于检测人脸
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40)
            )
            if len(faces) == 0:
                # 如果最近短时间内（例如 4 秒内）曾检测到人脸，说明可能是短时偏头或遮挡，
                # 在这种情况下优先判为 distracted 而不是直接 absent，从而减少误报。
                try:
                    now_ts = time.time()
                    if self._last_face_seen_ts and (now_ts - self._last_face_seen_ts) < 4.0:
                        return "distracted"
                except Exception:
                    pass
                return "absent"

            # 检测是否能检测到眼睛（简单视为正脸/专注）
            for (x, y, w, h) in faces:
                roi_gray = gray[y : y + h, x : x + w]
                eyes = self.eye_cascade.detectMultiScale(
                    roi_gray, scaleFactor=1.05, minNeighbors=3, minSize=(10, 10)
                )
                if len(eyes) >= 1:
                    # 记录最近检测到人脸的时间
                    try:
                        self._last_face_seen_ts = time.time()
                    except Exception:
                        pass
                    return "focused"
            # 有脸但没检测到眼睛 -> 可能分心或侧脸
            return "distracted"
        except Exception as e:
            logger.exception(f"人脸分析失败: {e}")
            return "absent"

    def _analyze_frame_yolo(self, frame) -> str:
        """使用YOLO检测人脸和姿态"""
        # 返回 'focused' | 'distracted' | 'absent' | 'blocked'
        if frame is None or self.yolo_model is None:
            return "absent"

        try:
            # 检测摄像头是否被遮挡或画面过暗（均值过低）
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness = float(gray.mean())
            if mean_brightness < 18:
                # 画面非常暗，可能被遮挡
                return "blocked"

            # 使用YOLO进行检测，启用GPU加速
            results = self.yolo_model(frame, verbose=False, device=self.yolo_device)
            detections = results[0].boxes
            
            if detections is None or len(detections) == 0:
                return "absent"
            
            # 检查是否检测到人脸
            face_detected = False
            face_center_x, face_center_y = 0, 0
            face_width, face_height = 0, 0
            frame_height, frame_width = frame.shape[:2]
            
            # 存储所有人脸信息用于进一步分析
            faces_info = []
            
            for box in detections:
                # 获取检测框坐标
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = box.conf[0].cpu().numpy()
                cls = int(box.cls[0].cpu().numpy())
                
                # 仅考虑置信度较高的检测
                if conf > 0.5:
                    # 如果是人脸类（根据模型而定，coco数据集中是0表示person）
                    if cls == 0:  # person class
                        face_detected = True
                        # 计算人脸中心点和尺寸
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        width = x2 - x1
                        height = y2 - y1
                        
                        faces_info.append({
                            'center_x': center_x,
                            'center_y': center_y,
                            'width': width,
                            'height': height,
                            'confidence': conf,
                            'x1': x1,
                            'y1': y1,
                            'x2': x2,
                            'y2': y2
                        })
            
            if not face_detected:
                return "absent"
            
            # 选择置信度最高的人脸进行分析
            best_face = max(faces_info, key=lambda x: x['confidence'])
            face_center_x = best_face['center_x']
            face_center_y = best_face['center_y']
            face_width = best_face['width']
            face_height = best_face['height']
            
            # 分析人脸位置和尺寸判断专注度
            # 计算画面中心区域（假设专注时人脸在画面中央区域）
            center_x_min = frame_width * 0.3
            center_x_max = frame_width * 0.7
            center_y_min = frame_height * 0.2
            center_y_max = frame_height * 0.8
            
            # 判断人脸是否在中心区域
            in_center_area = (center_x_min <= face_center_x <= center_x_max and 
                             center_y_min <= face_center_y <= center_y_max)
            
            # 判断人脸大小（太远或太近都不利于专注）
            expected_face_width = frame_width * 0.3  # 期望的人脸宽度为画面宽度的30%
            size_ratio = face_width / expected_face_width
            
            # 判断是否正面（通过人脸框的宽高比）
            aspect_ratio = face_width / face_height if face_height > 0 else 1
            
            # 综合判断专注度
            # 更精细的判断逻辑
            if in_center_area:
                if 0.4 <= size_ratio <= 1.6 and 0.5 <= aspect_ratio <= 1.3:
                    return "focused"
                else:
                    # 在中心但尺寸不合适或角度不对
                    return "distracted"
            else:
                # 不在中心区域
                return "distracted"
                
        except Exception as e:
            logger.exception(f"YOLO人脸分析失败: {e}")
            return "absent"

    def _analyze_frame(self, frame) -> str:
        """根据配置的方法分析帧"""
        if self.detection_method == DetectionMethod.YOLO and YOLO_AVAILABLE and self.yolo_model is not None:
            return self._analyze_frame_yolo(frame)
        else:
            return self._analyze_frame_haar(frame)

    def _apply_status(self, status: str):
        # 状态平滑：使用连续计数(streaks)来判断状态是否稳定，避免单帧噪声导致误判。
        try:
            # 更新各状态的连续计数
            for k in self._streaks.keys():
                if k == status:
                    self._streaks[k] += 1
                else:
                    self._streaks[k] = 0

            # 判断是否满足稳定阈值
            if self._streaks.get(status, 0) >= self._streak_thresholds.get(status, 1):
                eff_status = status
            else:
                # 当尚未达到阈值时，保留上一次的决策（若存在），否则暂时使用当前原始状态
                eff_status = self._last_decision if self._last_decision is not None else status
        except Exception:
            eff_status = status

        # 根据最终决定的状态调整分数与统计
        old = self.score
        # 统计次数只在使用了有效决策时计入
        self._total_checks += 1

        if eff_status == "focused":
            # 专注时缓慢提升
            self.score = min(100, self.score + 2)
            self._focused_count += 1
            # 回到专注后重置分心计数
            self._distracted_count = 0
        elif eff_status == "distracted":
            self.score = max(0, self.score - 3)
            self._distracted_count += 1
        elif eff_status == "blocked":
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

        # 回调（始终回调最终决定的状态）
        try:
            if self.on_status:
                self.on_status(eff_status, self.score)
        except Exception:
            pass

        # 专注时可以触发正向反馈（例如 UI 切换到开心表情），由回调处理
        self._last_decision = eff_status

    def get_score(self) -> int:
        return int(self.score)

    def set_detection_method(self, method: DetectionMethod):
        """动态设置检测方法"""
        self.detection_method = method
        if method == DetectionMethod.YOLO and YOLO_AVAILABLE and self.yolo_model is None:
            try:
                self.yolo_model = YOLO(self.yolo_model_path)
                logger.info(f"成功加载YOLO模型: {self.yolo_model_path}")
            except Exception as e:
                logger.warning(f"加载YOLO模型失败: {e}")
                self.detection_method = DetectionMethod.HAAR_CASCADE

__all__ = ["FaceMonitor", "DetectionMethod"]