# 导入异步编程库，用于处理并发操作
import asyncio
# 导入垃圾回收库，用于内存管理
import gc
# 导入时间库，用于时间相关操作
import time
# 导入双端队列，用于缓冲区管理
from collections import deque
# 导入可选类型提示
from typing import Optional

# 尝试导入numpy库，用于音频数据处理
try:
    import numpy as np
except Exception:
    np = None

# 尝试导入opuslib库，用于Opus音频编解码
try:
    import opuslib
    _OPUS_AVAILABLE = True
except Exception:
    opuslib = None
    _OPUS_AVAILABLE = False

# 尝试导入sounddevice库，用于音频设备管理
try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except Exception:
    sd = None
    _SD_AVAILABLE = False

# 尝试导入soxr库，用于高质量重采样
try:
    import soxr
    _SOXR_AVAILABLE = True
except Exception:
    soxr = None
    _SOXR_AVAILABLE = False

# 从项目模块导入AEC处理器
from src.audio_codecs.aec_processor import AECProcessor
# 从项目模块导入音频配置常量
from src.constants.constants import AudioConfig
# 从项目模块导入配置管理器
from src.utils.config_manager import ConfigManager
# 从项目模块导入日志配置
from src.utils.logging_config import get_logger

# 创建日志记录器
logger = get_logger(__name__)


class AudioCodec:
    """
    音频编解码器，负责录音编码和播放解码
    主要功能：
    1. 录音：麦克风 -> 重采样16kHz -> Opus编码 -> 发送
    2. 播放：接收 -> Opus解码24kHz -> 播放队列 -> 扬声器
    """

    def __init__(self):
        # 获取配置管理器实例
        self.config = ConfigManager.get_instance()

        # 初始化Opus编解码器：录音16kHz编码，播放24kHz解码
        self.opus_encoder = None  # 用于编码录音数据
        self.opus_decoder = None  # 用于解码播放数据

        # 设备信息存储
        self.device_input_sample_rate = None   # 设备输入采样率
        self.device_output_sample_rate = None  # 设备输出采样率
        self.mic_device_id = None             # 麦克风设备ID（固定索引，一经写入配置不再覆盖）
        self.speaker_device_id = None         # 扬声器设备ID（固定索引）

        # 重采样器：录音重采样到16kHz，播放重采样到设备采样率
        self.input_resampler = None   # 设备采样率 -> 16kHz
        self.output_resampler = None  # 24kHz -> 设备采样率(播放用)

        # 重采样缓冲区
        self._resample_input_buffer = deque()  # 输入重采样缓冲区
        self._resample_output_buffer = deque() # 输出重采样缓冲区

        self._device_input_frame_size = None  # 设备输入帧大小
        self._is_closing = False              # 关闭状态标志

        # 音频流对象
        self.input_stream = None   # 录音流
        self.output_stream = None  # 播放流

        # 队列：唤醒词检测和播放缓冲
        self._wakeword_buffer = asyncio.Queue(maxsize=100)  # 唤醒词检测缓冲队列
        self._output_buffer = asyncio.Queue(maxsize=500)    # 播放缓冲队列

        # 实时编码回调（直接发送，不走队列）
        self._encoded_audio_callback = None

        # AEC处理器及启用状态
        self.aec_processor = AECProcessor()  # 回声消除处理器
        self._aec_enabled = False            # AEC启用状态

    # -----------------------
    # 自动选择设备的辅助方法
    # -----------------------
    def _auto_pick_device(self, kind: str) -> Optional[int]:
        """
        自动挑选一个稳定的设备索引（优先 WASAPI）。
        kind: 'input' 或 'output'
        """
        assert kind in ("input", "output")  # 确保kind参数合法
        
        try:
            # 查询所有音频设备
            devices = sd.query_devices()
            # 查询主机API
            hostapis = sd.query_hostapis()
        except Exception as e:
            logger.warning(f"枚举设备失败：{e}")
            return None

        # 1) 优先使用 WASAPI HostAPI 的默认设备（如果有）
        wasapi_index = None
        for idx, ha in enumerate(hostapis):
            name = ha.get("name", "")
            if "WASAPI" in name:
                key = (
                    "default_input_device"
                    if kind == "input"
                    else "default_output_device"
                )
                cand = ha.get(key, -1)
                if isinstance(cand, int) and 0 <= cand < len(devices):
                    d = devices[cand]
                    if (kind == "input" and d["max_input_channels"] > 0) or (
                        kind == "output" and d["max_output_channels"] > 0
                    ):
                        wasapi_index = cand
                        break
        if wasapi_index is not None:
            return wasapi_index

        # 2) 退而求其次：根据系统默认（kind）返回的名字匹配 + 优先 WASAPI
        try:
            default_info = sd.query_devices(kind=kind)  # 不会触发 -1
            default_name = default_info.get("name")
        except Exception:
            default_name = None

        scored = []  # 存储评分和设备索引
        for i, d in enumerate(devices):
            if kind == "input":
                ok = d["max_input_channels"] > 0
            else:
                ok = d["max_output_channels"] > 0
            if not ok:
                continue
            host_name = hostapis[d["hostapi"]]["name"]
            score = 0
            if "WASAPI" in host_name:
                score += 5  # WASAPI设备加分
            if default_name and d["name"] == default_name:
                score += 10  # 默认设备加分
            # 小加分：常见可用端点关键词
            if any(
                k in d["name"]
                for k in [
                    "Speaker",
                    "扬声器",
                    "Realtek",
                    "USB",
                    "AMD",
                    "HDMI",
                    "Monitor",
                ]
            ):
                score += 1
            scored.append((score, i))  # 添加评分和索引

        if scored:
            scored.sort(reverse=True)  # 按评分降序排序
            return scored[0][1]  # 返回最高分的设备索引

        # 3) 最后保底：第一个具备通道的设备
        for i, d in enumerate(devices):
            if (kind == "input" and d["max_input_channels"] > 0) or (
                kind == "output" and d["max_output_channels"] > 0
            ):
                return i
        return None

    async def initialize(self):
        """
        初始化音频设备.
        """
        try:
            # 显示并选择音频设备（首次自动选择并写入配置；之后不覆盖）
            await self._select_audio_devices()

            # 安全获取输入/输出默认信息（避免 -1）
            if self.mic_device_id is not None and self.mic_device_id >= 0:
                input_device_info = sd.query_devices(self.mic_device_id)
            else:
                input_device_info = sd.query_devices(kind="input")

            if self.speaker_device_id is not None and self.speaker_device_id >= 0:
                output_device_info = sd.query_devices(self.speaker_device_id)
            else:
                output_device_info = sd.query_devices(kind="output")

            # 获取设备的默认采样率
            self.device_input_sample_rate = int(input_device_info["default_samplerate"])
            self.device_output_sample_rate = int(
                output_device_info["default_samplerate"]
            )

            # 计算设备输入帧大小
            frame_duration_sec = AudioConfig.FRAME_DURATION / 1000
            self._device_input_frame_size = int(
                self.device_input_sample_rate * frame_duration_sec
            )

            logger.info(
                f"输入采样率: {self.device_input_sample_rate}Hz, 输出: {self.device_output_sample_rate}Hz"
            )

            # 创建重采样器
            await self._create_resamplers()

            # 不强行改全局默认，让每个流自己带 device / samplerate
            sd.default.samplerate = None
            sd.default.channels = AudioConfig.CHANNELS
            sd.default.dtype = np.int16

            # 创建音频流
            await self._create_streams()

            # 初始化Opus编解码器
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,  # 16kHz输入采样率
                AudioConfig.CHANNELS,           # 通道数
                opuslib.APPLICATION_AUDIO,      # 音频应用类型
            )
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE, # 24kHz输出采样率
                AudioConfig.CHANNELS            # 通道数
            )

            # 初始化AEC处理器
            try:
                await self.aec_processor.initialize()
                self._aec_enabled = True
                logger.info("AEC处理器启用")
            except Exception as e:
                logger.warning(f"AEC处理器初始化失败，将使用原始音频: {e}")
                self._aec_enabled = False

            logger.info("音频初始化完成")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _create_resamplers(self):
        """
        创建重采样器 输入：设备采样率 -> 16kHz（用于编码） 输出：24kHz -> 设备采样率（播放用）
        """
        # 输入重采样器：设备采样率 -> 16kHz（用于编码）
        if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
            self.input_resampler = soxr.ResampleStream(
                self.device_input_sample_rate,     # 输入采样率
                AudioConfig.INPUT_SAMPLE_RATE,     # 输出采样率（16kHz）
                AudioConfig.CHANNELS,              # 通道数
                dtype="int16",                     # 数据类型
                quality="QQ",                      # 快速质量模式
            )
            logger.info(f"输入重采样: {self.device_input_sample_rate}Hz -> 16kHz")

        # 输出重采样器：24kHz -> 设备采样率
        if self.device_output_sample_rate != AudioConfig.OUTPUT_SAMPLE_RATE:
            self.output_resampler = soxr.ResampleStream(
                AudioConfig.OUTPUT_SAMPLE_RATE,    # 输入采样率（24kHz）
                self.device_output_sample_rate,    # 输出采样率（设备采样率）
                AudioConfig.CHANNELS,              # 通道数
                dtype="int16",                     # 数据类型
                quality="QQ",                      # 快速质量模式
            )
            logger.info(
                f"输出重采样: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz -> {self.device_output_sample_rate}Hz"
            )

    async def _select_audio_devices(self):
        """显示并选择音频设备.

        优先使用配置文件中的设备，如果没有则自动选择并保存到配置（只在首次写入，之后不覆盖）。
        """
        try:
            # 获取音频设备配置
            audio_config = self.config.get_config("AUDIO_DEVICES", {}) or {}

            # 检查配置是否已存在（决定是否写回）
            had_cfg_input = "input_device_id" in audio_config
            had_cfg_output = "output_device_id" in audio_config

            # 从配置获取设备ID
            input_device_id = audio_config.get("input_device_id")
            output_device_id = audio_config.get("output_device_id")

            # 查询所有音频设备
            devices = sd.query_devices()

            # --- 验证配置中的输入设备 ---
            if input_device_id is not None:
                try:
                    if isinstance(input_device_id, int) and 0 <= input_device_id < len(
                        devices
                    ):
                        d = devices[input_device_id]
                        if d["max_input_channels"] > 0:
                            # 配置有效，保存到实例变量
                            self.mic_device_id = input_device_id
                            logger.info(
                                f"使用配置的麦克风设备: [{input_device_id}] {d['name']}"
                            )
                        else:
                            logger.warning(
                                f"配置的设备[{input_device_id}]不支持输入，将自动选择"
                            )
                            self.mic_device_id = None
                    else:
                        logger.warning(
                            f"配置的输入设备ID[{input_device_id}]无效，将自动选择"
                        )
                        self.mic_device_id = None
                except Exception as e:
                    logger.warning(f"验证配置输入设备失败: {e}，将自动选择")
                    self.mic_device_id = None
            else:
                self.mic_device_id = None

            # --- 验证配置中的输出设备 ---
            if output_device_id is not None:
                try:
                    if isinstance(
                        output_device_id, int
                    ) and 0 <= output_device_id < len(devices):
                        d = devices[output_device_id]
                        if d["max_output_channels"] > 0:
                            # 配置有效，保存到实例变量
                            self.speaker_device_id = output_device_id
                            logger.info(
                                f"使用配置的扬声器设备: [{output_device_id}] {d['name']}"
                            )
                        else:
                            logger.warning(
                                f"配置的设备[{output_device_id}]不支持输出，将自动选择"
                            )
                            self.speaker_device_id = None
                    else:
                        logger.warning(
                            f"配置的输出设备ID[{output_device_id}]无效，将自动选择"
                        )
                        self.speaker_device_id = None
                except Exception as e:
                    logger.warning(f"验证配置输出设备失败: {e}，将自动选择")
                    self.speaker_device_id = None
            else:
                self.speaker_device_id = None

            # --- 若任一为空，则自动选择（仅首次会写入配置） ---
            picked_input = self.mic_device_id
            picked_output = self.speaker_device_id

            if picked_input is None:
                picked_input = self._auto_pick_device("input")
                if picked_input is not None:
                    self.mic_device_id = picked_input
                    d = devices[picked_input]
                    logger.info(f"自动选择麦克风设备: [{picked_input}] {d['name']}")
                else:
                    logger.warning(
                        "未找到可用输入设备（将使用系统默认，且不写入索引）。"
                    )

            if picked_output is None:
                picked_output = self._auto_pick_device("output")
                if picked_output is not None:
                    self.speaker_device_id = picked_output
                    d = devices[picked_output]
                    logger.info(f"自动选择扬声器设备: [{picked_output}] {d['name']}")
                else:
                    logger.warning(
                        "未找到可用输出设备（将使用系统默认，且不写入索引）。"
                    )

            # --- 仅当配置原本缺少对应条目时，才写入（避免第二次覆盖） ---
            need_write = (not had_cfg_input and picked_input is not None) or (
                not had_cfg_output and picked_output is not None
            )
            if need_write:
                await self._save_default_audio_config(
                    input_device_id=picked_input if not had_cfg_input else None,
                    output_device_id=picked_output if not had_cfg_output else None,
                )

        except Exception as e:
            logger.warning(f"设备选择失败: {e}，将使用系统默认（不写入配置）")
            # 允许 None，让 PortAudio 用系统默认端点
            self.mic_device_id = (
                self.mic_device_id if isinstance(self.mic_device_id, int) else None
            )
            self.speaker_device_id = (
                self.speaker_device_id
                if isinstance(self.speaker_device_id, int)
                else None
            )

    async def _save_default_audio_config(
        self, input_device_id: Optional[int], output_device_id: Optional[int]
    ):
        """
        保存默认音频设备配置到配置文件（仅针对传入的非空设备；不会覆盖已有字段）。
        """
        try:
            devices = sd.query_devices()
            audio_config_patch = {}  # 临时配置补丁

            # 保存输入设备配置
            if input_device_id is not None and 0 <= input_device_id < len(devices):
                d = devices[input_device_id]
                audio_config_patch.update(
                    {
                        "input_device_id": input_device_id,      # 设备ID
                        "input_device_name": d["name"],          # 设备名称
                        "input_sample_rate": int(d["default_samplerate"]),  # 采样率
                    }
                )

            # 保存输出设备配置
            if output_device_id is not None and 0 <= output_device_id < len(devices):
                d = devices[output_device_id]
                audio_config_patch.update(
                    {
                        "output_device_id": output_device_id,    # 设备ID
                        "output_device_name": d["name"],         # 设备名称
                        "output_sample_rate": int(d["default_samplerate"]),  # 采样率
                    }
                )

            if audio_config_patch:
                # 合并：不覆盖已有键
                current = self.config.get_config("AUDIO_DEVICES", {}) or {}
                for k, v in audio_config_patch.items():
                    if k not in current:  # 只在原来没有时写入
                        current[k] = v
                success = self.config.update_config("AUDIO_DEVICES", current)
                if success:
                    logger.info("已写入默认音频设备到配置（首次）。")
                else:
                    logger.warning("保存音频设备配置失败")
        except Exception as e:
            logger.error(f"保存默认音频设备配置失败: {e}")

    async def _create_streams(self):
        """
        创建音频流.
        """
        try:
            # 麦克风输入流
            self.input_stream = sd.InputStream(
                device=self.mic_device_id,  # None=系统默认；或固定索引
                samplerate=self.device_input_sample_rate,  # 采样率
                channels=AudioConfig.CHANNELS,              # 通道数
                dtype=np.int16,                            # 数据类型
                blocksize=self._device_input_frame_size,   # 块大小
                callback=self._input_callback,             # 回调函数
                finished_callback=self._input_finished_callback,  # 完成回调
                latency="low",                             # 低延迟
            )

            # 根据设备支持的采样率选择输出采样率
            if self.device_output_sample_rate == AudioConfig.OUTPUT_SAMPLE_RATE:
                # 设备支持24kHz，直接使用
                output_sample_rate = AudioConfig.OUTPUT_SAMPLE_RATE
                device_output_frame_size = AudioConfig.OUTPUT_FRAME_SIZE
            else:
                # 设备不支持24kHz，使用设备默认采样率并启用重采样
                output_sample_rate = self.device_output_sample_rate
                device_output_frame_size = int(
                    self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
                )

            # 扬声器输出流
            self.output_stream = sd.OutputStream(
                device=self.speaker_device_id,  # None=系统默认；或固定索引
                samplerate=output_sample_rate,   # 输出采样率
                channels=AudioConfig.CHANNELS,   # 通道数
                dtype=np.int16,                  # 数据类型
                blocksize=device_output_frame_size,  # 块大小
                callback=self._output_callback,      # 回调函数
                finished_callback=self._output_finished_callback,  # 完成回调
                latency="low",                     # 低延迟
            )

            logger.info(f"准备启动音频流，输入设备ID: {self.mic_device_id}, 输出设备ID: {self.speaker_device_id}")
            
            # 启动输入和输出流
            self.input_stream.start()
            logger.info("输入流已启动")
            
            self.output_stream.start()
            logger.info("输出流已启动")

            logger.info("音频流已启动")

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            logger.exception("详细错误信息:")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """
        录音回调，硬件驱动调用 处理流程：原始音频 -> 重采样16kHz -> 编码发送 + 唤醒词检测.
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            # 复制输入数据并展平为一维数组
            audio_data = indata.copy().flatten()

            # 重采样到16kHz（如果设备不是16kHz）
            if self.input_resampler is not None:
                audio_data = self._process_input_resampling(audio_data)
                if audio_data is None:
                    return

            # 应用AEC处理（仅 macOS 需要）
            if (
                self._aec_enabled
                and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE
                and self.aec_processor._is_macos
            ):
                try:
                    audio_data = self.aec_processor.process_audio(audio_data)
                except Exception as e:
                    logger.warning(f"AEC处理失败，使用原始音频: {e}")

            # 实时编码并发送（不走队列，减少延迟）
            if (
                self._encoded_audio_callback
                and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE
            ):
                try:
                    # 将音频数据转换为PCM格式并编码
                    pcm_data = audio_data.astype(np.int16).tobytes()
                    encoded_data = self.opus_encoder.encode(
                        pcm_data, AudioConfig.INPUT_FRAME_SIZE
                    )
                    if encoded_data:
                        self._encoded_audio_callback(encoded_data)
                except Exception as e:
                    logger.warning(f"实时录音编码失败: {e}")

            # 同时提供给唤醒词检测（走队列）
            self._put_audio_data_safe(self._wakeword_buffer, audio_data.copy())

        except Exception as e:
            logger.error(f"输入回调错误: {e}")
            logger.exception("详细错误信息:")

    def _process_input_resampling(self, audio_data):
        """
        输入重采样到16kHz.
        """
        try:
            # 使用重采样器处理音频数据
            resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
            if len(resampled_data) > 0:
                # 将重采样后的数据添加到缓冲区
                self._resample_input_buffer.extend(resampled_data.astype(np.int16))

            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._resample_input_buffer) < expected_frame_size:
                return None

            # 从缓冲区取出一个完整的帧
            frame_data = []
            for _ in range(expected_frame_size):
                frame_data.append(self._resample_input_buffer.popleft())

            return np.array(frame_data, dtype=np.int16)

        except Exception as e:
            logger.error(f"输入重采样失败: {e}")
            logger.exception("详细错误信息:")
            return None

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        播放回调，硬件驱动调用 从播放队列取数据输出到扬声器.
        """
        if status:
            if "underflow" not in str(status).lower():
                logger.warning(f"输出流状态: {status}")

        try:
            if self.output_resampler is not None:
                # 需要重采样：24kHz -> 设备采样率
                self._output_callback_with_resample(outdata, frames)
            else:
                # 直接播放：24kHz
                self._output_callback_direct(outdata, frames)

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            logger.exception("详细错误信息:")
            outdata.fill(0)  # 出错时填充静音

    def _output_callback_direct(self, outdata: np.ndarray, frames: int):
        """
        直接播放24kHz数据（设备支持24kHz时）
        """
        try:
            # 从播放队列获取音频数据
            audio_data = self._output_buffer.get_nowait()

            if len(audio_data) >= frames * AudioConfig.CHANNELS:
                # 数据足够，取所需帧数
                output_frames = audio_data[: frames * AudioConfig.CHANNELS]
                outdata[:] = output_frames.reshape(-1, AudioConfig.CHANNELS)
            else:
                # 数据不足，部分填充
                out_len = len(audio_data) // AudioConfig.CHANNELS
                if out_len > 0:
                    outdata[:out_len] = audio_data[
                        : out_len * AudioConfig.CHANNELS
                    ].reshape(-1, AudioConfig.CHANNELS)
                if out_len < frames:
                    outdata[out_len:] = 0  # 剩余空间填充静音

        except asyncio.QueueEmpty:
            # 无数据时输出静音，并输出调试信息
            logger.debug("播放队列为空，输出静音")
            outdata.fill(0)

    def _output_callback_with_resample(self, outdata: np.ndarray, frames: int):
        """
        重采样播放（24kHz -> 设备采样率）
        """
        try:
            # 持续处理24kHz数据进行重采样
            while len(self._resample_output_buffer) < frames * AudioConfig.CHANNELS:
                try:
                    audio_data = self._output_buffer.get_nowait()
                    # 24kHz -> 设备采样率重采样
                    resampled_data = self.output_resampler.resample_chunk(
                        audio_data, last=False
                    )
                    if len(resampled_data) > 0:
                        self._resample_output_buffer.extend(
                            resampled_data.astype(np.int16)
                        )
                except asyncio.QueueEmpty:
                    break

            need = frames * AudioConfig.CHANNELS
            if len(self._resample_output_buffer) >= need:
                # 有足够的重采样数据
                frame_data = [
                    self._resample_output_buffer.popleft() for _ in range(need)
                ]
                output_array = np.array(frame_data, dtype=np.int16)
                outdata[:] = output_array.reshape(-1, AudioConfig.CHANNELS)
            else:
                # 数据不足时输出静音
                logger.debug(f"重采样缓冲区数据不足，需要 {need}，实际 {len(self._resample_output_buffer)}")
                outdata.fill(0)

        except Exception as e:
            logger.warning(f"重采样输出失败: {e}")
            logger.exception("详细错误信息:")
            outdata.fill(0)
            
    def _put_audio_data_safe(self, queue, audio_data):
        """
        安全入队，队列满时丢弃最旧数据.
        """
        try:
            # 尝试将数据放入队列
            queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            try:
                # 如果队列已满，移除最旧的数据项后再添加新数据
                queue.get_nowait()
                queue.put_nowait(audio_data)
            except asyncio.QueueEmpty:
                queue.put_nowait(audio_data)

    async def write_audio(self, opus_data: bytes):
        """
        解码音频并播放 网络接收的Opus数据 -> 解码24kHz -> 播放队列.
        """
        try:
            # Opus解码为24kHz PCM数据
            pcm_data = self.opus_decoder.decode(
                opus_data, AudioConfig.OUTPUT_FRAME_SIZE
            )

            audio_array = np.frombuffer(pcm_data, dtype=np.int16)

            expected_length = AudioConfig.OUTPUT_FRAME_SIZE * AudioConfig.CHANNELS
            if len(audio_array) != expected_length:
                # 仅记录警告，但仍然尝试播放
                logger.warning(
                    f"解码音频长度异常: {len(audio_array)}, 期望: {expected_length}"
                )
                # 如果长度不对，尝试调整数据大小
                if len(audio_array) < expected_length:
                    # 填充静音
                    padding = np.zeros(expected_length - len(audio_array), dtype=np.int16)
                    audio_array = np.concatenate([audio_array, padding])
                elif len(audio_array) > expected_length:
                    # 截断多余部分
                    audio_array = audio_array[:expected_length]

            # 放入播放队列
            self._put_audio_data_safe(self._output_buffer, audio_array)

        except opuslib.OpusError as e:
            logger.warning(f"Opus解码失败，丢弃此帧: {e}")
            logger.exception("详细错误信息:")
        except Exception as e:
            logger.warning(f"音频写入失败，丢弃此帧: {e}")
            logger.exception("详细错误信息:")

    def _input_finished_callback(self):
        """
        输入流结束.
        """
        logger.info("输入流已结束")

    def _reference_finished_callback(self):
        """
        参考信号流结束.
        """
        logger.info("参考信号流已结束")

    def _output_finished_callback(self):
        """
        输出流结束.
        """
        logger.info("输出流已结束")

    async def reinitialize_stream(self, is_input=True):
        """
        重建音频流.
        """
        if self._is_closing:
            return False if is_input else None

        try:
            if is_input:
                if self.input_stream:
                    self.input_stream.stop()
                    self.input_stream.close()

                # 重新创建输入流
                self.input_stream = sd.InputStream(
                    device=self.mic_device_id,  # <- 修复：带上设备索引，避免回落到可能不稳定的默认端点
                    samplerate=self.device_input_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=self._device_input_frame_size,
                    callback=self._input_callback,
                    finished_callback=self._input_finished_callback,
                    latency="low",
                )
                self.input_stream.start()
                logger.info("输入流重新初始化成功")
                return True
            else:
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()

                # 根据设备支持的采样率选择输出采样率
                if self.device_output_sample_rate == AudioConfig.OUTPUT_SAMPLE_RATE:
                    # 设备支持24kHz，直接使用
                    output_sample_rate = AudioConfig.OUTPUT_SAMPLE_RATE
                    device_output_frame_size = AudioConfig.OUTPUT_FRAME_SIZE
                else:
                    # 设备不支持24kHz，使用设备默认采样率并启用重采样
                    output_sample_rate = self.device_output_sample_rate
                    device_output_frame_size = int(
                        self.device_output_sample_rate
                        * (AudioConfig.FRAME_DURATION / 1000)
                    )

                # 重新创建输出流
                self.output_stream = sd.OutputStream(
                    device=self.speaker_device_id,  # 指定扬声器设备ID
                    samplerate=output_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=device_output_frame_size,
                    callback=self._output_callback,
                    finished_callback=self._output_finished_callback,
                    latency="low",
                )
                self.output_stream.start()
                logger.info("输出流重新初始化成功")
                return None
        except Exception as e:
            stream_type = "输入" if is_input else "输出"
            logger.error(f"{stream_type}流重建失败: {e}")
            if is_input:
                return False
            else:
                raise

    async def get_raw_audio_for_detection(self) -> Optional[bytes]:
        """
        获取唤醒词音频数据.
        """
        try:
            if self._wakeword_buffer.empty():
                return None

            audio_data = self._wakeword_buffer.get_nowait()

            if hasattr(audio_data, "tobytes"):
                return audio_data.tobytes()
            elif hasattr(audio_data, "astype"):
                return audio_data.astype("int16").tobytes()
            else:
                return audio_data

        except asyncio.QueueEmpty:
            return None
        except Exception as e:
            logger.error(f"获取唤醒词音频数据失败: {e}")
            return None

    def set_encoded_audio_callback(self, callback):
        """
        设置编码回调.
        """
        self._encoded_audio_callback = callback

        if callback:
            logger.info("启用实时编码")
        else:
            logger.info("禁用编码回调")

    def is_aec_enabled(self) -> bool:
        """
        检查AEC是否启用.
        """
        return self._aec_enabled

    def get_aec_status(self) -> dict:
        """
        获取AEC状态信息.
        """
        if not self._aec_enabled or not self.aec_processor:
            return {"enabled": False, "reason": "AEC未启用或初始化失败"}

        try:
            return {"enabled": True, **self.aec_processor.get_status()}
        except Exception as e:
            return {"enabled": False, "reason": f"获取状态失败: {e}"}

    def toggle_aec(self, enabled: bool) -> bool:
        """切换AEC启用状态.

        Args:
            enabled: 是否启用AEC

        Returns:
            实际的AEC状态
        """
        if not self.aec_processor:
            logger.warning("AEC处理器未初始化，无法切换状态")
            return False

        self._aec_enabled = enabled and self.aec_processor._is_initialized