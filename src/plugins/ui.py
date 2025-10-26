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
                self.app.tomato.start()
        except Exception:
            pass

    async def _study_stop(self):
        """从 UI 停止番茄计时并关闭学习模式。"""
        try:
            if getattr(self.app, "tomato", None):
                self.app.tomato.stop()
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
