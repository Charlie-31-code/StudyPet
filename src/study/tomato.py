# -*- coding: utf-8 -*-
"""
番茄工作法计时器实现
"""

import asyncio
import time
from typing import Callable, Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PomodoroState(Enum):
    """番茄钟状态枚举"""
    STOPPED = "stopped"
    FOCUSING = "focusing"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    DISTRACTED = "distracted"


class TomatoTimer:
    """番茄工作法计时器
    
    实现标准番茄工作法：
    - 25分钟专注学习
    - 5分钟短休息
    - 4个番茄钟后15分钟长休息
    """

    def __init__(self, 
                 app=None,
                 focus_duration: int = 25 * 60,
                 short_break_duration: int = 5 * 60,
                 long_break_duration: int = 15 * 60,
                 cycles_before_long: int = 4):
        self.app = app
        self.focus_duration = focus_duration
        self.short_break_duration = short_break_duration
        self.long_break_duration = long_break_duration
        self.cycles_before_long = cycles_before_long

        # 番茄钟状态
        self.state = PomodoroState.STOPPED
        self.start_time: Optional[float] = None
        self.duration: float = 0.0  # 当前阶段总时长
        self.remaining: float = 0.0  # 剩余时间
        self.completed_pomodoros = 0  # 完成的番茄钟数
        self.is_paused = False
        self.pause_time: Optional[float] = None

        # 座位状态
        self._seated = True
        self._seat_timer_task: Optional[asyncio.Task] = None

        # 运行控制
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 回调函数
        self.on_tick: Optional[Callable[[int, int], None]] = None
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_cycle_complete: Optional[Callable[[str], None]] = None

    def set_durations(self, focus: int, short_break: int, long_break: int):
        """设置各阶段时长
        
        Args:
            focus: 专注时长（秒）
            short_break: 短休息时长（秒）
            long_break: 长休息时长（秒）
        """
        self.focus_duration = focus
        self.short_break_duration = short_break
        self.long_break_duration = long_break

    def set_on_tick(self, cb: Callable[[int, int], None]):
        self.on_tick = cb

    def set_on_state_change(self, cb: Callable[[str], None]):
        self.on_state_change = cb

    def set_on_cycle_complete(self, cb: Callable[[str], None]):
        self.on_cycle_complete = cb

    async def start(self):
        """开始番茄钟"""
        if self._running:
            return

        self._running = True
        self.completed_pomodoros = 0
        await self._start_focus()

    def start(self):
        """开始番茄钟（同步包装）"""
        if not self._running:
            asyncio.create_task(self._start_async())

    async def _start_async(self):
        """异步启动入口"""
        self._running = True
        self.completed_pomodoros = 0
        await self._start_focus()

    async def pause(self):
        """暂停番茄钟"""
        if not self._running or self.is_paused:
            return

        self.is_paused = True
        self.pause_time = time.time()
        logger.info("番茄钟已暂停")

    def pause(self):
        """暂停番茄钟（同步包装）"""
        if self._running and not self.is_paused:
            asyncio.create_task(self._pause_async())

    async def _pause_async(self):
        """异步暂停"""
        self.is_paused = True
        self.pause_time = time.time()
        logger.info("番茄钟已暂停")

    async def resume(self):
        """恢复番茄钟"""
        if not self._running or not self.is_paused:
            return

        # 调整开始时间以补偿暂停时间
        if self.start_time and self.pause_time:
            paused_duration = time.time() - self.pause_time
            self.start_time += paused_duration

        self.is_paused = False
        self.pause_time = None
        logger.info("番茄钟已恢复")

    def resume(self):
        """恢复番茄钟（同步包装）"""
        if self._running and self.is_paused:
            asyncio.create_task(self._resume_async())

    async def _resume_async(self):
        """异步恢复"""
        if self.start_time and self.pause_time:
            paused_duration = time.time() - self.pause_time
            self.start_time += paused_duration

        self.is_paused = False
        self.pause_time = None
        logger.info("番茄钟已恢复")

    async def stop(self):
        """停止番茄钟"""
        self._running = False
        self.is_paused = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # 取消座位检测任务
        if self._seat_timer_task and not self._seat_timer_task.done():
            self._seat_timer_task.cancel()
            self._seat_timer_task = None

        self.state = PomodoroState.STOPPED
        self.start_time = None
        self.remaining = 0.0
        self._notify_state_change()
        logger.info("番茄钟已停止")

    def stop(self):
        """停止番茄钟（同步包装）"""
        if self._running:
            asyncio.create_task(self._stop_async())

    async def _stop_async(self):
        """异步停止"""
        self._running = False
        self.is_paused = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # 取消座位检测任务
        if self._seat_timer_task and not self._seat_timer_task.done():
            self._seat_timer_task.cancel()
            self._seat_timer_task = None

        self.state = PomodoroState.STOPPED
        self.start_time = None
        self.remaining = 0.0
        self._notify_state_change()
        logger.info("番茄钟已停止")

    async def _start_focus(self):
        """开始专注阶段"""
        self.state = PomodoroState.FOCUSING
        self.duration = self.focus_duration
        self.start_time = time.time()
        self.remaining = self.duration
        self._notify_state_change()
        logger.info("开始专注阶段")

        self._task = asyncio.create_task(self._run_timer())

    async def _start_break(self):
        """开始休息阶段"""
        # 判断是短休息还是长休息
        if (self.completed_pomodoros) % self.cycles_before_long == 0:
            # 长休息
            self.state = PomodoroState.LONG_BREAK
            self.duration = self.long_break_duration
            logger.info("开始长休息")
        else:
            # 短休息
            self.state = PomodoroState.SHORT_BREAK
            self.duration = self.short_break_duration
            logger.info("开始短休息")

        self.start_time = time.time()
        self.remaining = self.duration
        self._notify_state_change()

        self._task = asyncio.create_task(self._run_timer())

    async def _run_timer(self):
        """运行计时器"""
        try:
            while self._running and self.remaining > 0:
                # 如果暂停则等待
                if self.is_paused:
                    await asyncio.sleep(0.5)
                    continue

                # 计算剩余时间
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    self.remaining = max(0, self.duration - elapsed)

                # 通知状态更新
                self._notify_state_change()

                # 更新UI
                self._update_ui()

                # 短暂休眠以避免过度占用CPU
                await asyncio.sleep(0.5)

            # 计时结束
            if self._running:
                await self._on_timer_complete()

        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            logger.error(f"番茄钟运行出错: {e}")

    async def _on_timer_complete(self):
        """计时完成回调"""
        if self.state == PomodoroState.FOCUSING:
            # 专注阶段完成
            self.completed_pomodoros += 1
            logger.info(f"第 {self.completed_pomodoros} 个番茄钟完成")

            # 触发周期完成回调
            if self.on_cycle_complete:
                try:
                    self.on_cycle_complete("study")
                except Exception as e:
                    logger.error(f"Error in on_cycle_complete callback: {e}")

            # 开始休息
            await self._start_break()
        else:
            # 休息阶段完成
            logger.info("休息结束")

            # 触发周期完成回调
            if self.on_cycle_complete:
                try:
                    if self.state == PomodoroState.SHORT_BREAK:
                        self.on_cycle_complete("short_break")
                    else:
                        self.on_cycle_complete("long_break")
                except Exception as e:
                    logger.error(f"Error in on_cycle_complete callback: {e}")

            # 开始下一个专注阶段
            await self._start_focus()

    def _update_ui(self):
        """更新UI显示"""
        # 计算百分比
        percentage = 0
        if self.duration > 0:
            percentage = max(0, min(100, round((self.duration - self.remaining) / self.duration * 100)))

        # 通知tick回调
        if self.on_tick:
            try:
                self.on_tick(int(round(self.remaining)), percentage)
            except Exception as e:
                logger.error(f"Error in on_tick callback: {e}")

    def get_progress(self) -> Dict[str, Any]:
        """获取当前进度信息
        
        Returns:
            Dict包含状态、剩余时间、百分比等信息
        """
        # 计算百分比（已处理除零情况）
        percentage = 0
        if self.duration > 0:
            percentage = max(0, min(100, round((self.duration - self.remaining) / self.duration * 100)))

        # 格式化剩余时间为 MM:SS
        minutes = int(self.remaining // 60)
        seconds = int(self.remaining % 60)
        remaining_formatted = f"{minutes:02d}:{seconds:02d}"

        return {
            "state": self.state.value,
            "remaining": self.remaining,
            "remaining_formatted": remaining_formatted,
            "percentage": percentage,
            "completed_pomodoros": self.completed_pomodoros,
            "is_paused": self.is_paused
        }

    def _notify_state_change(self):
        """通知状态变更"""
        if self.on_state_change:
            try:
                self.on_state_change(self.state.value)
            except Exception as e:
                logger.error(f"状态变更回调出错: {e}")

    # 简单的座位状态处理：离座后 3 秒变 distracted
    def set_seated(self, seated: bool):
        self._seated = seated
        # cancel existing
        if self._seat_timer_task and not self._seat_timer_task.done():
            self._seat_timer_task.cancel()
            self._seat_timer_task = None

        if not seated:
            # 启动 3 秒计时器
            async def _delayed():
                try:
                    await asyncio.sleep(3)
                    # 如果仍然未就座，则触发 distracted
                    if not self._seated:
                        self.state = PomodoroState.DISTRACTED
                        self._notify_state_change()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error in seat timer task: {e}")

            self._seat_timer_task = asyncio.create_task(_delayed())
        else:
            # 回座 -> 设为 focusing（若正在计时）
            if self._running and not self._stop:
                self.state = PomodoroState.FOCUSING
                self._notify_state_change()