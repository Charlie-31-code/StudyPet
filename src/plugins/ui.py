from typing import Any, Optional

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
                                fname = reports_dir / f"report_{ts}.json"
                                data = {
                                    'phase': phase_name,
                                    'timestamp': ts,
                                    'report': report,
                                }
                                fname.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
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
                    play_audio_personalized("学习模式已开始。开始 25 分钟专注时间。", style=personality)
                except Exception:
                    pass
                self.app.tomato.start()
                # 启动人脸监控（如果存在）并绑定回调
                fm = getattr(self.app, "face_monitor", None)
                if fm:
                    try:
                        def _on_face_status(status: str, score: int):
                            # 在主 loop 调度 UI 更新与 tomato.seated
                            def _ui_update():
                                try:
                                    # 更新 petState
                                    try:
                                        self.display.display_model.petState = status
                                    except Exception:
                                        pass
                                    # 根据状态修改表情
                                    if status == "focused":
                                        self.display.update_emotion("focus")
                                    elif status == "distracted":
                                        self.display.update_emotion("sad")
                                    else:
                                        self.display.update_emotion("neutral")
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

                        fm.on_status = _on_face_status
                        # 帧回调：把 BGR 帧编码为 data URL 并更新到 display_model.faceImage（QML 可直接使用）
                        def _on_frame(frame):
                            try:
                                # 延迟导入，避免没有 cv2 时导入失败
                                import base64
                                import cv2 as _cv2

                                if frame is None:
                                    return
                                # 缩放为小图以减少流量
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
                                    # 在主 loop 更新显示模型
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
