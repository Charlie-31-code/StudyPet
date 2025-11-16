from typing import Any, Optional
import time
from pathlib import Path

from src.constants.constants import AbortReason, DeviceState
from src.plugins.base import Plugin


class UIPlugin(Plugin):
    """UI 插件 - 管理 CLI/GUI 显示"""

    name = "ui"

    # 设备状态文本映射
    STATE_TEXT_MAP = {
        DeviceState.IDLE: "待命",
        DeviceState.LISTENING: "聆听中...",
        DeviceState.SPEAKING: "说话中...",
    }

    def __init__(self, mode: Optional[str] = None) -> None:
        super().__init__()
        self.app = None
        self.mode = (mode or "cli").lower()
        self.display = None
        self._is_gui = False
        self.is_first = True
        # 会话内提醒——使用时间戳和冷却来允许重复提醒但避免频繁打断
        # 记录上一次播放时间（Unix timestamp, 0 表示未播放）
        self._last_notification_time = {"absent": 0.0, "blocked": 0.0, "distracted": 0.0}
        # 冷却时长（秒）：在冷却期内同类提醒不会重复播放
        self._notification_cooldown = 60
        # 会话内连贯的分心计数（用于每累计 3 次分心后提醒）
        self._distracted_local_count = 0
        # 详情窗口引用，用于对话记录保存
        self.details_window = None

    async def setup(self, app: Any) -> None:
        """
        初始化 UI 插件.
        """
        self.app = app

        # 创建对应的 display 实例
        self.display = self._create_display()

        # 禁用应用内控制台输入
        if hasattr(app, "use_console_input"):
            app.use_console_input = False

    def _create_display(self):
        """
        根据模式创建 display 实例.
        """
        if self.mode == "gui":
            from src.display.gui_display import GuiDisplay

            self._is_gui = True
            return GuiDisplay()
        else:
            from src.display.cli_display import CliDisplay

            self._is_gui = False
            return CliDisplay()

    async def start(self) -> None:
        """
        启动 UI 显示.
        """
        if not self.display:
            return

        # 绑定回调
        await self._setup_callbacks()

        # 启动显示
        self.app.spawn(self.display.start(), name=f"ui:{self.mode}:start")
        
        # 如果是GUI模式，设置一个定时器来定期检查详情窗口是否已创建
        if self._is_gui:
            from PyQt5.QtCore import QTimer
            def check_details_window():
                try:
                    if hasattr(self.display, '_details_window') and self.display._details_window:
                        self.details_window = self.display._details_window
                        # 窗口已找到，可以停止定时器
                        timer.stop()
                except Exception:
                    pass
            
            timer = QTimer()
            timer.timeout.connect(check_details_window)
            timer.start(1000)  # 每秒检查一次，直到找到详情窗口

    async def _setup_callbacks(self) -> None:
        """
        设置 display 回调.
        """
        if self._is_gui:
            # GUI 需要调度到异步任务
            callbacks = {
                "press_callback": self._wrap_callback(self._press),
                "release_callback": self._wrap_callback(self._release),
                "auto_callback": self._wrap_callback(self._auto_toggle),
                "abort_callback": self._wrap_callback(self._abort),
                "send_text_callback": self._send_text,
                # 学习模式回调
                "study_start_callback": self._wrap_callback(self._study_start),
                "study_start_already_callback": self._wrap_callback(self._study_start_already),
                "study_stop_callback": self._wrap_callback(self._study_stop),
            }
            # 若存在番茄计时器，则把 UI 更新回调绑定到 timer
            try:
                tomato = getattr(self.app, "tomato", None)
                if tomato and self.display:
                    # 每秒 tick -> 更新 UI（使用 schedule_command_nowait 在主 loop 调度）
                    def _on_tick(remaining, percent):
                        m = remaining // 60
                        s = remaining % 60
                        text = f"{m:02d}:{s:02d}"
                        try:
                            self.app.schedule_command_nowait(
                                lambda: setattr(self.display.display_model, "studyTimerText", text)
                            )
                            self.app.schedule_command_nowait(
                                lambda: setattr(self.display.display_model, "studyProgress", int(percent))
                            )
                        except Exception:
                            pass

                    def _on_state(state):
                        try:
                            self.app.schedule_command_nowait(
                                lambda: setattr(self.display.display_model, "petState", state)
                            )
                            # 根据简单状态映射改变表情（可扩展）
                            if state == "distracted":
                                self.app.schedule_command_nowait(
                                    lambda: self.display.update_emotion("sad")
                                )
                            elif state == "studying":
                                self.app.schedule_command_nowait(
                                    lambda: self.display.update_emotion("focus")
                                )
                            else:
                                self.app.schedule_command_nowait(
                                    lambda: self.display.update_emotion("neutral")
                                )
                        except Exception:
                            pass

                    tomato.set_on_tick(_on_tick)
                    tomato.set_on_state_change(_on_state)
                    # 番茄完成回调 -> 播放庆祝、生成学习报告与记录（UI 可显示动画）
                    def _on_cycle_complete(phase_name: str):
                        try:
                            # 显示完成动画/表情
                            self.app.schedule_command_nowait(
                                lambda: self.display.update_emotion("happy")
                            )
                            # 语音庆祝与生成报告
                            from src.utils.common_utils import play_audio_nonblocking
                            from src.utils.config_manager import ConfigManager
                            import json, time

                            # 先获取 face monitor 的会话统计
                            report = None
                            fm_local = getattr(self.app, 'face_monitor', None)
                            if fm_local:
                                try:
                                    report = fm_local.end_session()
                                except Exception:
                                    report = None

                            # 保存报告到配置目录
                            try:
                                cfg = ConfigManager.get_instance()
                                reports_dir = cfg.config_dir / 'study_reports'
                                reports_dir.mkdir(parents=True, exist_ok=True)
                                ts = int(time.time())
                                session_id = f"session_{ts}"
                                fname = reports_dir / f"report_{ts}.json"
                                data = {
                                    'phase': phase_name,
                                    'timestamp': ts,
                                    'report': report,
                                    'session_id': session_id
                                }
                                fname.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                                
                                # 同时更新历史报告索引文件，记录所有报告
                                history_file = reports_dir / "report_history.json"
                                all_reports = []
                                
                                # 读取现有历史
                                if history_file.exists():
                                    try:
                                        all_reports = json.loads(history_file.read_text(encoding='utf-8'))
                                    except Exception:
                                        all_reports = []
                                
                                # 添加新报告信息
                                all_reports.append({
                                    "timestamp": data["timestamp"],
                                    "file": fname.name,
                                    "duration": report.get("duration", 0) if report else 0,
                                    "focus_time": report.get("focused_time", 0) if report else 0,
                                    "session_id": data["session_id"],
                                    "phase": phase_name
                                })
                                
                                # 按时间戳倒序排列，方便查看最新报告
                                all_reports.sort(key=lambda x: x["timestamp"], reverse=True)
                                
                                # 保存历史索引
                                history_file.write_text(json.dumps(all_reports, ensure_ascii=False, indent=2), encoding='utf-8')
                                
                                # 如果有详情窗口，更新数据
                                if hasattr(self, 'details_window') and self.details_window:
                                    try:
                                        if hasattr(self.details_window, 'add_study_report'):
                                            self.details_window.add_study_report(data)
                                        # 通知详情窗口刷新报告列表
                                        if hasattr(self.details_window, 'refresh_report_list'):
                                            self.details_window.refresh_report_list()
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                            # 播放更有人情味的庆祝语与简短总结
                            try:
                                if report and report.get('avg_score') is not None:
                                    avg = int(report.get('avg_score', 0))
                                    focused = report.get('focused_count', 0)
                                    distracted = report.get('distracted_count', 0)
                                    absent = report.get('absent_count', 0)
                                    msg = f"太棒了！本次学习完成，平均专注度 {avg} 分，专注 {focused} 次，分心 {distracted} 次，离开 {absent} 次。休息一下，准备下一轮吧！"
                                else:
                                    msg = "太棒了！你完成了一个番茄钟，干得漂亮！休息一下，准备下一轮吧！"
                                play_audio_nonblocking(msg)
                            except Exception:
                                play_audio_nonblocking("恭喜！你完成了一个番茄钟，干得漂亮！")
                        except Exception:
                            pass

                    tomato.set_on_cycle_complete(_on_cycle_complete)
            except Exception:
                pass
        else:
            # CLI 直接传递协程函数
            callbacks = {
                "auto_callback": self._auto_toggle,
                "abort_callback": self._abort,
                "send_text_callback": self._send_text,
            }

        await self.display.set_callbacks(**callbacks)

    async def _study_start_already(self):
        """当用户在已经处于学习模式时再次点击开始，播放一次提示语音（单次）。"""
        try:
            from src.utils.common_utils import play_audio_personalized
            from src.utils.config_manager import ConfigManager

            cfg = ConfigManager.get_instance()
            personality = cfg.get_config("VOICE.PERSONALITY", "gentle")
            # 使用非个性化语音播放一次提示（不要包含“太棒了”前缀）
            from src.utils.common_utils import play_audio_nonblocking
            play_audio_nonblocking("学习模式已在运行中。如需停止请点击停止按钮。")
        except Exception:
            pass

    async def _study_start(self):
        """从 UI 启动番茄计时。"""
        try:
            if getattr(self.app, "tomato", None):
                # 打开学习面板（保持在 UI）
                if self.display:
                    try:
                        self.display.display_model.studyModeActive = True
                    except Exception:
                        pass
                # 播放开始语音（个性化）
                try:
                    from src.utils.common_utils import play_audio_personalized
                    from src.utils.config_manager import ConfigManager

                    cfg = ConfigManager.get_instance()
                    # 获取主界面语音风格，若未配置则默认使用 gentle（年轻温柔）
                    personality = cfg.get_config("VOICE.PERSONALITY", "gentle")
                    # 先播放简短提示，具体时长将在读取配置后播报
                    play_audio_personalized("学习模式已开始。", style=personality)
                except Exception:
                    pass
                # 重置会话内一次性提醒标志与分心计数
                try:
                    self._study_notification_flags = {"absent": False, "blocked": False}
                    self._distracted_local_count = 0
                except Exception:
                    pass
                # 启动番茄计时器
                # 在启动前读取自定义时长（优先从配置读取），并应用约束：
                # - 学习时长（分钟）：默认 25，最小 1，最大 180
                # - 休息时长（分钟）：默认 5，最小 5，最大 36
                try:
                    # 优先使用 UI 上 display_model 的自定义值（实时修改），若不存在再回退到配置
                    dm = getattr(self.display, 'display_model', None)
                    from src.utils.config_manager import ConfigManager
                    cfg = ConfigManager.get_instance()
                    if dm:
                        try:
                            preset = (dm.preset or "default").lower()
                        except Exception:
                            preset = (cfg.get_config("TOMATO.preset", "default") or "default").lower()
                    else:
                        preset = (cfg.get_config("TOMATO.preset", "default") or "default").lower()
                    # 支持预设：default(25/5)、deep(50/10)、short(15/5)
                    if preset == "deep":
                        study_min = 50
                        break_min = 10
                    elif preset == "short":
                        study_min = 15
                        break_min = 5
                    else:
                        # default - try UI model first
                        if dm:
                            try:
                                study_min = int(getattr(dm, 'studyMinutes', cfg.get_config("TOMATO.study_minutes", 25)))
                            except Exception:
                                study_min = int(cfg.get_config("TOMATO.study_minutes", 25) or 25)
                            try:
                                break_min = int(getattr(dm, 'breakMinutes', cfg.get_config("TOMATO.break_minutes", 5)))
                            except Exception:
                                break_min = int(cfg.get_config("TOMATO.break_minutes", 5) or 5)
                        else:
                            study_min = int(cfg.get_config("TOMATO.study_minutes", 25) or 25)
                            break_min = int(cfg.get_config("TOMATO.break_minutes", 5) or 5)
                        study_min = max(1, min(180, study_min))
                        break_min = max(5, min(36, break_min))

                    # long break 优先使用配置指定值（若存在），否则使用短休息的两倍并限制在 15-30 分钟区间
                    # long break: prefer UI value if present, else config
                    long_cfg = None
                    if dm:
                        try:
                            long_cfg = getattr(dm, 'longBreakMinutes', None)
                        except Exception:
                            long_cfg = None
                    if long_cfg is None:
                        long_cfg = cfg.get_config("TOMATO.long_break_minutes", None)
                    if long_cfg is not None:
                        try:
                            long_min = int(long_cfg)
                        except Exception:
                            long_min = None
                    else:
                        long_min = None

                    if long_min is None:
                        long_min = max(15, min(30, int(break_min) * 2))
                    else:
                        # clamp provided value into allowed range 15-30
                        try:
                            long_min = max(15, min(30, int(long_min)))
                        except Exception:
                            long_min = max(15, min(30, int(break_min) * 2))

                    # cycles before long break
                    cycles_before_long = int(cfg.get_config("TOMATO.cycles_before_long", 4) or 4)
                    if cycles_before_long < 1:
                        cycles_before_long = 4

                    # 应用到 TomatoTimer（以秒为单位）
                    try:
                        self.app.tomato.study_seconds = int(study_min) * 60
                        self.app.tomato.short_break = int(break_min) * 60
                        self.app.tomato.long_break = int(long_min) * 60
                        self.app.tomato.cycles_before_long = int(cycles_before_long)
                    except Exception:
                        pass

                    # 播放带时长的提示
                    try:
                        from src.utils.common_utils import play_audio_personalized
                        play_audio_personalized(f"开始 {study_min} 分钟专注时间。", style=personality)
                    except Exception:
                        pass
                except Exception:
                    pass

                self.app.tomato.start()
                # 标记会话为激活状态（用于 QML 判断是否重复启动）
                try:
                    self.display.display_model.studySessionActive = True
                    # 设置初始倒计时显示为用户设置的时间
                    study_minutes = self.display.display_model.studyMinutes
                    self.display.display_model.studyTimerText = f"{study_minutes:02d}:00"
                    # 重置进度条
                    self.display.display_model.studyProgress = 0
                except Exception:
                    pass
                # 启动人脸监控（如果存在）并绑定回调
                fm = getattr(self.app, "face_monitor", None)
                if fm:
                    try:
                        def _on_face_status(status: str, score: int):
                            # 记录调试日志到 logs/face_monitor_events.log，便于排查未触发提醒的问题
                            try:
                                import os, time
                                logs_dir = Path(__file__).resolve().parents[2] / 'logs'
                                logs_dir.mkdir(parents=True, exist_ok=True)
                                log_file = logs_dir / 'face_monitor_events.log'
                                now_s = int(time.time())
                                # 记录基础信息（status, score），后面会追加是否会触发语音的判断
                                with open(log_file, 'a', encoding='utf-8') as f:
                                    f.write(f"{now_s}\tstatus={status}\tscore={score}\n")
                            except Exception:
                                pass
                            # 在主 loop 调度 UI 更新与 tomato.seated
                            def _ui_update():
                                try:
                                    # 更新 petState
                                    try:
                                        self.display.display_model.petState = status
                                    except Exception:
                                        pass
                                    
                                    # 检查是否处于学习模式
                                    try:
                                        study_mode_active = getattr(self.display.display_model, 'studyModeActive', False)
                                        study_session_active = getattr(self.display.display_model, 'studySessionActive', False)
                                    except Exception:
                                        study_mode_active = False
                                        study_session_active = False
                                    
                                    # 只在学习模式下更新表情和语音播报
                                    if study_mode_active and study_session_active:
                                        # 添加状态持续时间控制，避免表情过快切换
                                        import time
                                        current_time = time.time()
                                        
                                        # 获取上次状态更新时间
                                        last_update_time = getattr(self, '_last_emotion_update_time', 0)
                                        last_status = getattr(self, '_last_face_status', '')
                                        
                                        # 定义需要延长显示时间的特殊状态到表情映射
                                        special_emotion_map = {
                                            "focused": "Super Focused",
                                            "distracted": "Extremely Distracted", 
                                            "absent": "Strong Reminder",
                                            "blocked": "Hurry up and study",
                                            "achievement unlocked": "Achievement Unlocked",
                                            "acrobatics": "Acrobatics",
                                            "extremely distracted": "Extremely Distracted",
                                            "hurry up and study": "Hurry up and study",
                                            "level-up celebration": "Level-Up Celebration",
                                            "strong reminder": "Strong Reminder",
                                            "study hard": "Study Hard",
                                            "super focused": "Super Focused"
                                        }
                                        
                                        # 检查是否需要更新表情
                                        should_update = False
                                        # 如果状态发生变化，立即更新表情
                                        if status != last_status:
                                            should_update = True
                                            self.display.logger.debug(f"状态发生变化: {last_status} -> {status}, 即将更新表情")
                                        # 如果状态相同，但距离上次更新超过5秒，也要更新（确保表情持续播放）
                                        elif status == last_status and (current_time - last_update_time) > 5.0:
                                            should_update = True
                                            self.display.logger.debug(f"状态未变但超过5秒: {status}, 重新更新表情确保持续播放")
                                        # 特殊处理：对于blocked状态，确保表情持续显示
                                        elif status == "blocked" and status == last_status and (current_time - last_update_time) > 5.0:
                                            should_update = True
                                        
                                        if should_update:
                                            # 根据状态修改表情，使用指定的表情包
                                            emotion_map = {
                                                "focused": "Super Focused",
                                                "distracted": "Extremely Distracted", 
                                                "absent": "Strong Reminder",
                                                "blocked": "Hurry up and study"
                                            }
                                            
                                            # 获取对应的表情名称，如果没有匹配则使用默认的Achievement Unlocked
                                            emotion_name = emotion_map.get(status, "Achievement Unlocked")
                                            
                                            self.display.logger.debug(f"映射状态到表情: {status} -> {emotion_name}")
                                            
                                            # 调度表情更新
                                            self.app.schedule_command_nowait(
                                                lambda en=emotion_name: self.display.update_emotion(en)
                                            )
                                            
                                            # 更新最后更新时间和状态
                                            self._last_emotion_update_time = current_time
                                            self._last_face_status = status
                                            # 使用display的logger而不是self.logger
                                            self.display.logger.debug(f"更新学习模式表情: {status} -> {emotion_name}")
                                            
                                            # 添加学习模式下的语音播报（降低频率）
                                            try:
                                                status_messages = {
                                                    "focused": "太棒了，你很专注哦！",
                                                    "distracted": "注意注意力，回到学习中来！",
                                                    "absent": "咦，你去哪了？快回来学习吧！",
                                                    "blocked": "不要遮挡摄像头，让我看到你！"
                                                }
                                                
                                                message = status_messages.get(status)
                                                if message:
                                                    # 检查是否需要播报语音（控制频率）
                                                    last_voice_time = getattr(self, '_last_voice_time', {})
                                                    last_voice_timestamp = last_voice_time.get(status, 0)
                                                    current_timestamp = time.time()
                                                    
                                                    # 定义播报间隔（秒）
                                                    voice_intervals = {
                                                        "focused": 30,  # 专注状态每30秒播报一次
                                                        "distracted": 60,  # 分心状态每60秒播报一次
                                                        "absent": 60,  # 离开状态每60秒播报一次
                                                        "blocked": 60   # 遮挡状态每60秒播报一次
                                                    }
                                                    
                                                    interval = voice_intervals.get(status, 60)
                                                    
                                                    if current_timestamp - last_voice_timestamp >= interval:
                                                        from src.utils.common_utils import play_audio_nonblocking
                                                        play_audio_nonblocking(message)
                                                        self._last_voice_time[status] = current_timestamp
                                            except Exception as e:
                                                self.display.logger.error(f"学习模式语音播报出错: {e}")
                                except Exception:
                                    pass

                            try:
                                self.app.schedule_command_nowait(_ui_update)
                            except Exception:
                                pass

                            # 通知番茄计时器座位状态：focused -> seated True, else False
                            try:
                                if getattr(self.app, "tomato", None):
                                    self.app.tomato.set_seated(status == "focused")
                            except Exception:
                                pass

                            # 会话内语音提醒（基于冷却时间以支持重复提醒）
                            try:
                                if status in ("absent", "blocked"):
                                    now_ts = time.time()
                                    last = float(self._last_notification_time.get(status, 0.0))
                                    if now_ts - last >= float(self._notification_cooldown):
                                        from src.utils.common_utils import play_audio_nonblocking
                                        if status == "absent":
                                            # 用更贴近实际的提示文本：指出是离开工位/座位
                                            play_audio_nonblocking("你暂时离开了工位，等你回来我们继续哦~")
                                        else:
                                            play_audio_nonblocking("摄像头似乎被挡住了，请确认摄像头可见~")
                                        self._last_notification_time[status] = now_ts
                            except Exception:
                                pass

                            # 分心提醒：统计连续分心次数，当累计到 3 次时，在冷却允许下提醒一次；专注会重置计数和部分提醒时间
                            try:
                                if status == "distracted":
                                    self._distracted_local_count += 1
                                    if (self._distracted_local_count > 0) and (self._distracted_local_count % 3 == 0):
                                        now_ts = time.time()
                                        last = float(self._last_notification_time.get("distracted", 0.0))
                                        if now_ts - last >= float(self._notification_cooldown):
                                            from src.utils.common_utils import play_audio_nonblocking
                                            play_audio_nonblocking("小提示：把注意力收回到任务上，你可以的！")
                                            self._last_notification_time["distracted"] = now_ts
                                elif status == "focused":
                                    # 回到专注后重置分心计数并清除 absent/blocked 提示时间，
                                    # 使得下次缺席或被挡能更快触发提示
                                    self._distracted_local_count = 0
                                    self._last_notification_time["absent"] = 0.0
                                    self._last_notification_time["blocked"] = 0.0
                            except Exception:
                                pass

                        fm.on_status = _on_face_status
                        # 帧回调：为了提升主线程流畅性，采用生产者/消费者模式：
                        # - on_frame 仅把最新帧放入队列（非阻塞）
                        # - 后台编码线程按目标帧率（默认 4 FPS）取最新帧进行 JPEG 编码并调度更新 QML
                        # 这样可以避免在主线程进行耗时的 JPEG 编码与 base64 操作，减少 UI 卡顿
                        try:
                            import queue as _queue
                            import threading as _threading
                            import time as _time
                            import base64 as _base64
                            import cv2 as _cv2
                        except Exception:
                            _queue = None

                        if _queue is None:
                            # 回退到原来的简单实现（若环境缺少 cv2/queue）
                            def _on_frame(frame):
                                try:
                                    import base64
                                    import cv2 as _cv2
                                    if frame is None:
                                        return
                                    try:
                                        small = _cv2.resize(frame, (240, 180))
                                    except Exception:
                                        small = frame
                                    ret, buf = _cv2.imencode('.jpg', small, [int(_cv2.IMWRITE_JPEG_QUALITY), 70])
                                    if not ret:
                                        return
                                    b64 = base64.b64encode(buf.tobytes()).decode('ascii')
                                    data_url = f"data:image/jpeg;base64,{b64}"
                                    try:
                                        self.app.schedule_command_nowait(
                                            lambda: setattr(self.display.display_model, 'faceImage', data_url)
                                        )
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            try:
                                fm.on_frame = _on_frame
                            except Exception:
                                pass
                        else:
                            # 创建线程安全队列和编码线程
                            fm._frame_queue = _queue.Queue(maxsize=4)
                            fm._encoder_running = True
                            # 目标帧率（可按需调整）：4 FPS 足以保证视觉连贯且 CPU 友好
                            fm._encoder_fps = 4.0

                            def _encoder_worker():
                                last_sent = 0.0
                                min_interval = 1.0 / max(1.0, fm._encoder_fps)
                                while getattr(fm, '_encoder_running', False):
                                    try:
                                        # 等待一段时间后取出最新帧
                                        try:
                                            frame = fm._frame_queue.get(timeout=min_interval)
                                        except Exception:
                                            frame = None
                                        # 尝试排空队列只保留最新帧，降低延迟
                                        try:
                                            while not fm._frame_queue.empty():
                                                frame = fm._frame_queue.get_nowait()
                                        except Exception:
                                            pass

                                        if frame is None:
                                            continue

                                        # 编码并发送（质量保持在 70）
                                        try:
                                            small = _cv2.resize(frame, (240, 180))
                                        except Exception:
                                            small = frame
                                        ret, buf = _cv2.imencode('.jpg', small, [int(_cv2.IMWRITE_JPEG_QUALITY), 70])
                                        if not ret:
                                            continue
                                        b64 = _base64.b64encode(buf.tobytes()).decode('ascii')
                                        data_url = f"data:image/jpeg;base64,{b64}"
                                        # 调度到主 loop 更新 QML
                                        try:
                                            self.app.schedule_command_nowait(
                                                lambda d=data_url: setattr(self.display.display_model, 'faceImage', d)
                                            )
                                        except Exception:
                                            pass
                                    except Exception:
                                        # 防止线程因异常退出
                                        time.sleep(0.05)
                                # 线程结束

                            fm._encoder_thread = _threading.Thread(target=_encoder_worker, daemon=True)
                            fm._encoder_thread.start()

                            # 非阻塞地把帧放入队列（若队列满则丢弃旧帧）
                            def _on_frame(frame):
                                try:
                                    if frame is None:
                                        return
                                    try:
                                        fm._frame_queue.put_nowait(frame)
                                    except Exception:
                                        # 队列满时替换为最新（丢弃一项再尝试）
                                        try:
                                            _ = fm._frame_queue.get_nowait()
                                            fm._frame_queue.put_nowait(frame)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass

                            try:
                                fm.on_frame = _on_frame
                            except Exception:
                                pass
                        # 启动摄像头监控线程并开始会话统计
                        try:
                            try:
                                fm.start_session()
                            except Exception:
                                pass
                            fm.start()
                        except Exception:
                            pass
                    except Exception:
                        pass
        except Exception:
            pass

    async def _study_stop(self):
        """从 UI 停止番茄计时并关闭学习模式。"""
        try:
            if getattr(self.app, "tomato", None):
                self.app.tomato.stop()
                # 播放停止语音（个性化）
                try:
                    from src.utils.common_utils import play_audio_personalized
                    from src.utils.config_manager import ConfigManager

                    cfg = ConfigManager.get_instance()
                    personality = cfg.get_config("VOICE.PERSONALITY", "gentle")
                    play_audio_personalized("学习已结束，已停止计时。记得休息一下。", style=personality)
                except Exception:
                    pass
            # 停止人脸监控（若存在）
            fm = getattr(self.app, "face_monitor", None)
            if fm:
                try:
                    # 结束会话并保存简短报告
                    try:
                        report = fm.end_session()
                        # 可在此处保存或上传报告（已在 cycle_complete 里处理主要保存）
                    except Exception:
                        pass
                    fm.stop()
                except Exception:
                    pass
                # 清除会话激活标志并重置会话内提醒计数
                try:
                    self.display.display_model.studySessionActive = False
                except Exception:
                    pass
                try:
                    self._study_notification_flags = {"absent": False, "blocked": False}
                    self._distracted_local_count = 0
                except Exception:
                    pass
            if self.display:
                try:
                    self.display.display_model.studyModeActive = False
                except Exception:
                    pass
        except Exception:
            pass

    def _wrap_callback(self, coro_func):
        """
        包装协程函数为可调度的 lambda.
        """
        return lambda: self.app.spawn(coro_func(), name="ui:callback")

    async def on_incoming_json(self, message: Any) -> None:
        """
        处理传入的 JSON 消息.
        """
        if not self.display or not isinstance(message, dict):
            return

        msg_type = message.get("type")

        # tts/stt 都更新文本
        if msg_type in ("tts", "stt"):
            if text := message.get("text"):
                await self.display.update_text(text)

        # llm 更新表情
        elif msg_type == "llm":
            if emotion := message.get("emotion"):
                await self.display.update_emotion(emotion)

    async def on_device_state_changed(self, state: Any) -> None:
        """
        设备状态变化处理.
        """
        if not self.display:
            return

        # 跳过首次调用
        if self.is_first:
            self.is_first = False
            return

        # 更新表情和状态
        await self.display.update_emotion("neutral")
        if status_text := self.STATE_TEXT_MAP.get(state):
            await self.display.update_status(status_text, True)

    async def shutdown(self) -> None:
        """
        清理 UI 资源，关闭窗口.
        """
        if self.display:
            await self.display.close()
            self.display = None

    # ===== 回调函数 =====

    async def _send_text(self, text: str):
        """
        发送文本到服务端.
        """
        if self.app.device_state == DeviceState.SPEAKING:
            audio_plugin = self.app.plugins.get_plugin("audio")
            if audio_plugin:
                await audio_plugin.codec.clear_audio_queue()
            await self.app.abort_speaking(None)
        if await self.app.connect_protocol():
            await self.app.protocol.send_wake_word_detected(text)

    async def _press(self):
        """
        手动模式：按下开始录音.
        """
        await self.app.start_listening_manual()

    async def _release(self):
        """
        手动模式：释放停止录音.
        """
        await self.app.stop_listening_manual()

    async def _auto_toggle(self):
        """
        自动模式切换.
        """
        await self.app.start_auto_conversation()

    async def _abort(self):
        """
        中断对话.
        """
        await self.app.abort_speaking(AbortReason.USER_INTERRUPTION)