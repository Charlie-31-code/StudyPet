# -*- coding: utf-8 -*-
"""
GUI 显示窗口数据模型 - 用于 QML 数据绑定.
"""

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal


class GuiDisplayModel(QObject):
    """
    GUI 主窗口的数据模型，用于 Python 和 QML 之间的数据绑定.
    """

    # 属性变化信号
    statusTextChanged = pyqtSignal()
    emotionPathChanged = pyqtSignal()
    ttsTextChanged = pyqtSignal()
    buttonTextChanged = pyqtSignal()
    modeTextChanged = pyqtSignal()
    autoModeChanged = pyqtSignal()

    # 用户操作信号
    manualButtonPressed = pyqtSignal()
    manualButtonReleased = pyqtSignal()
    autoButtonClicked = pyqtSignal()
    abortButtonClicked = pyqtSignal()
    modeButtonClicked = pyqtSignal()
    sendButtonClicked = pyqtSignal(str)  # 携带输入的文本
    settingsButtonClicked = pyqtSignal()
    detailsButtonClicked = pyqtSignal()
    studyRecordButtonClicked = pyqtSignal()  # 新增学习记录按钮点击信号

    def __init__(self, parent=None):
        super().__init__(parent)

        # 私有属性
        self._status_text = "状态: 未连接"
        self._emotion_path = ""  # 表情资源路径（GIF/图片）或 emoji 字符
        self._tts_text = "待命"
        self._button_text = "开始对话"  # 自动模式按钮文本
        self._mode_text = "手动对话"  # 模式切换按钮文本
        self._auto_mode = False  # 是否自动模式
        self._is_connected = False

    # 状态文本属性
    @pyqtProperty(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @statusText.setter
    def statusText(self, value):
        if self._status_text != value:
            self._status_text = value
            self.statusTextChanged.emit()

    # 表情路径属性
    @pyqtProperty(str, notify=emotionPathChanged)
    def emotionPath(self):
        return self._emotion_path

    @emotionPath.setter
    def emotionPath(self, value):
        if self._emotion_path != value:
            self._emotion_path = value
            self.emotionPathChanged.emit()

    # TTS 文本属性
    @pyqtProperty(str, notify=ttsTextChanged)
    def ttsText(self):
        return self._tts_text

    @ttsText.setter
    def ttsText(self, value):
        if self._tts_text != value:
            self._tts_text = value
            self.ttsTextChanged.emit()

    # 自动模式按钮文本属性
    @pyqtProperty(str, notify=buttonTextChanged)
    def buttonText(self):
        return self._button_text

    @buttonText.setter
    def buttonText(self, value):
        if self._button_text != value:
            self._button_text = value
            self.buttonTextChanged.emit()

    # 模式切换按钮文本属性
    @pyqtProperty(str, notify=modeTextChanged)
    def modeText(self):
        return self._mode_text

    @modeText.setter
    def modeText(self, value):
        if self._mode_text != value:
            self._mode_text = value
            self.modeTextChanged.emit()

    # 自动模式标志属性
    @pyqtProperty(bool, notify=autoModeChanged)
    def autoMode(self):
        return self._auto_mode

    @autoMode.setter
    def autoMode(self, value):
        if self._auto_mode != value:
            self._auto_mode = value
            self.autoModeChanged.emit()

    # 便捷方法
    def update_status(self, status: str, connected: bool):
        """
        更新状态文本和连接状态.
        """
        self.statusText = f"状态: {status}"
        self._is_connected = connected

    def update_text(self, text: str):
        """
        更新 TTS 文本.
        """
        self.ttsText = text

    def update_emotion(self, emotion_path: str):
        """
        更新表情路径.
        """
        self.emotionPath = emotion_path

    def update_button_text(self, text: str):
        """
        更新自动模式按钮文本.
        """
        self.buttonText = text

    def update_mode_text(self, text: str):
        """
        更新模式按钮文本.
        """
        self.modeText = text

    def set_auto_mode(self, is_auto: bool):
        """
        设置自动模式.
        """
        self.autoMode = is_auto
        if is_auto:
            self.modeText = "自动对话"
        else:
            self.modeText = "手动对话"

    # ---------- 学习模式相关属性 ----------
    studyModeActiveChanged = pyqtSignal()
    studyTimerTextChanged = pyqtSignal()
    studyProgressChanged = pyqtSignal()
    petStateChanged = pyqtSignal()
    studySessionActiveChanged = pyqtSignal()
    # 小脸图像（data URL）
    faceImageChanged = pyqtSignal()
    # 可配置的番茄计时属性
    studyMinutesChanged = pyqtSignal()
    breakMinutesChanged = pyqtSignal()
    presetChanged = pyqtSignal()
    longBreakMinutesChanged = pyqtSignal()
    cyclesBeforeLongChanged = pyqtSignal()

    def _init_study_props(self):
        self._study_mode_active = False
        self._study_session_active = False
        self._study_timer_text = "25:00"
        self._study_progress = 0  # 0-100
        self._pet_state = "idle"  # idle/studying/distracted
        self._face_image = ""
        # 可配置项的默认值（可由 UI 修改）
        try:
            from src.utils.config_manager import ConfigManager
            cfg = ConfigManager.get_instance()
            preset = (cfg.get_config("TOMATO.preset", "default") or "default")
            self._preset = preset
            self._study_minutes = int(cfg.get_config("TOMATO.study_minutes", 25) or 25)
            self._break_minutes = int(cfg.get_config("TOMATO.break_minutes", 5) or 5)
            self._long_break_minutes = int(cfg.get_config("TOMATO.long_break_minutes", 15) or 15)
            self._cycles_before_long = int(cfg.get_config("TOMATO.cycles_before_long", 4) or 4)
        except Exception:
            self._preset = "default"
            self._study_minutes = 25
            self._break_minutes = 5
            self._long_break_minutes = 15
            self._cycles_before_long = 4

    @pyqtProperty(bool, notify=studySessionActiveChanged)
    def studySessionActive(self):
        try:
            return self._study_session_active
        except AttributeError:
            self._init_study_props()
            return self._study_session_active

    @studySessionActive.setter
    def studySessionActive(self, value: bool):
        if getattr(self, "_study_session_active", False) != value:
            self._study_session_active = bool(value)
            self.studySessionActiveChanged.emit()

    @pyqtProperty(str, notify=studyTimerTextChanged)
    def studyTimerText(self):
        try:
            return self._study_timer_text
        except AttributeError:
            self._init_study_props()
            return self._study_timer_text

    @studyTimerText.setter
    def studyTimerText(self, value: str):
        if getattr(self, "_study_timer_text", "") != value:
            self._study_timer_text = value
            self.studyTimerTextChanged.emit()

    @pyqtProperty(int, notify=studyProgressChanged)
    def studyProgress(self):
        try:
            return self._study_progress
        except AttributeError:
            self._init_study_props()
            return self._study_progress

    @studyProgress.setter
    def studyProgress(self, value: int):
        if getattr(self, "_study_progress", -1) != value:
            self._study_progress = int(value)
            self.studyProgressChanged.emit()

    @pyqtProperty(str, notify=petStateChanged)
    def petState(self):
        try:
            return self._pet_state
        except AttributeError:
            self._init_study_props()
            return self._pet_state

    @petState.setter
    def petState(self, value: str):
        if getattr(self, "_pet_state", "") != value:
            self._pet_state = value
            self.petStateChanged.emit()

    @pyqtProperty(str, notify=faceImageChanged)
    def faceImage(self):
        try:
            return self._face_image
        except AttributeError:
            self._init_study_props()
            return self._face_image

    @faceImage.setter
    def faceImage(self, value: str):
        if getattr(self, "_face_image", "") != value:
            self._face_image = value
            self.faceImageChanged.emit()

    # --------- 可配置番茄计时属性的访问器 ---------
    @pyqtProperty(int, notify=studyMinutesChanged)
    def studyMinutes(self):
        try:
            return self._study_minutes
        except AttributeError:
            self._init_study_props()
            return self._study_minutes

    @studyMinutes.setter
    def studyMinutes(self, value: int):
        try:
            v = int(value)
        except Exception:
            return
        if getattr(self, "_study_minutes", None) != v:
            self._study_minutes = v
            self.studyMinutesChanged.emit()
            # 当学习时长更改时，同时更新界面上的倒计时显示
            if not self._study_session_active:
                self.studyTimerText = f"{v:02d}:00"

    def _update_study_timer_text(self):
        """更新学习模式倒计时文本显示"""
        # 只有在学习模式激活但会话未开始时才更新显示
        if self._study_mode_active and not self._study_session_active:
            minutes = self._study_minutes
            self.studyTimerText = f"{minutes:02d}:00"

    @pyqtProperty(bool, notify=studyModeActiveChanged)
    def studyModeActive(self):
        try:
            return self._study_mode_active
        except AttributeError:
            self._init_study_props()
            return self._study_mode_active

    @studyModeActive.setter
    def studyModeActive(self, value: bool):
        if getattr(self, "_study_mode_active", False) != value:
            self._study_mode_active = value
            self.studyModeActiveChanged.emit()
            # 当学习模式激活时，更新倒计时显示为设置的学习时长
            if value and not self._study_session_active:
                self._update_study_timer_text()

    @pyqtProperty(int, notify=breakMinutesChanged)
    def breakMinutes(self):
        try:
            return self._break_minutes
        except AttributeError:
            self._init_study_props()
            return self._break_minutes

    @breakMinutes.setter
    def breakMinutes(self, value: int):
        try:
            v = int(value)
        except Exception:
            return
        if getattr(self, "_break_minutes", None) != v:
            self._break_minutes = v
            self.breakMinutesChanged.emit()

    @pyqtProperty(str, notify=presetChanged)
    def preset(self):
        try:
            return self._preset
        except AttributeError:
            self._init_study_props()
            return self._preset

    @preset.setter
    def preset(self, value: str):
        if getattr(self, "_preset", "") != value:
            self._preset = str(value)
            self.presetChanged.emit()

    @pyqtProperty(int, notify=longBreakMinutesChanged)
    def longBreakMinutes(self):
        try:
            return self._long_break_minutes
        except AttributeError:
            self._init_study_props()
            return self._long_break_minutes

    @longBreakMinutes.setter
    def longBreakMinutes(self, value: int):
        try:
            v = int(value)
        except Exception:
            return
        if getattr(self, "_long_break_minutes", None) != v:
            self._long_break_minutes = v
            self.longBreakMinutesChanged.emit()

    @pyqtProperty(int, notify=cyclesBeforeLongChanged)
    def cyclesBeforeLong(self):
        try:
            return self._cycles_before_long
        except AttributeError:
            self._init_study_props()
            return self._cycles_before_long

    @cyclesBeforeLong.setter
    def cyclesBeforeLong(self, value: int):
        try:
            v = int(value)
        except Exception:
            return
        if getattr(self, "_cycles_before_long", None) != v:
            self._cycles_before_long = v
            self.cyclesBeforeLongChanged.emit()