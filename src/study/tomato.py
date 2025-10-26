# -*- coding: utf-8 -*-
"""
轻量级番茄计时器实现：用于学习模式 UI 的后台计时与状态回调。

提供：start(), stop(), pause(), resume(), set_seated(bool)

回调：on_tick(seconds_remaining, percent_complete)，on_state_change(state_str)

注：使用 asyncio 任务，需要在与应用相同的事件循环中运行（Application 使用 asyncio）。
"""

import asyncio
import time
from typing import Callable, Optional


class TomatoTimer:
	def __init__(
		self,
		app=None,
		study_seconds: int = 25 * 60,
		short_break: int = 5 * 60,
		long_break: int = 15 * 60,
		cycles_before_long: int = 4,
	):
		self.app = app
		self.study_seconds = study_seconds
		self.short_break = short_break
		self.long_break = long_break
		self.cycles_before_long = cycles_before_long

		self._task: Optional[asyncio.Task] = None
		self._running = False
		self._paused = asyncio.Event()
		self._paused.set()
		self._stop = False

		# callbacks
		self.on_tick: Optional[Callable[[int, int], None]] = None
		self.on_state_change: Optional[Callable[[str], None]] = None
		self.on_cycle_complete: Optional[Callable[[str], None]] = None

		# seat detection
		self._seated = True
		self._seat_timer_task: Optional[asyncio.Task] = None

		self._completed_cycles = 0

	def set_on_tick(self, cb: Callable[[int, int], None]):
		self.on_tick = cb

	def set_on_state_change(self, cb: Callable[[str], None]):
		self.on_state_change = cb

	def set_on_cycle_complete(self, cb: Callable[[str], None]):
		self.on_cycle_complete = cb

	def start(self):
		if self._running:
			return
		self._stop = False
		self._running = True
		self._paused.set()
		self._task = asyncio.create_task(self._run())

	def stop(self):
		self._stop = True
		self._running = False
		if self._task and not self._task.done():
			self._task.cancel()
		self._task = None
		# cancel seat timer
		if self._seat_timer_task and not self._seat_timer_task.done():
			self._seat_timer_task.cancel()
			self._seat_timer_task = None

	def pause(self):
		self._paused.clear()

	def resume(self):
		self._paused.set()

	def is_running(self) -> bool:
		return self._running and not self._stop

	async def _run_phase(self, seconds: int, phase_name: str):
		start = time.time()
		end = start + seconds
		while time.time() < end:
			if self._stop:
				return False
			await self._paused.wait()
			remaining = int(max(0, end - time.time()))
			percent = int((1 - remaining / seconds) * 100)
			if self.on_tick:
				try:
					self.on_tick(remaining, percent)
				except Exception:
					pass
			await asyncio.sleep(1)
		# 完成阶段
		if self.on_cycle_complete:
			try:
				self.on_cycle_complete(phase_name)
			except Exception:
				pass
		return True

	async def _run(self):
		# 循环执行 study -> break -> ...
		try:
			while not self._stop:
				# 切到 studying 状态
				if self.on_state_change:
					try:
						self.on_state_change("studying")
					except Exception:
						pass

				ok = await self._run_phase(self.study_seconds, "study")
				if not ok or self._stop:
					break

				# 完成一个学习周期
				self._completed_cycles += 1

				# 短暂休息或长休息
				if self._completed_cycles % self.cycles_before_long == 0:
					# long break
					if self.on_state_change:
						try:
							self.on_state_change("long_break")
						except Exception:
							pass
					ok = await self._run_phase(self.long_break, "long_break")
				else:
					if self.on_state_change:
						try:
							self.on_state_change("short_break")
						except Exception:
							pass
					ok = await self._run_phase(self.short_break, "short_break")

				if not ok or self._stop:
					break

				# continue next cycle
			# 结束
		except asyncio.CancelledError:
			pass
		finally:
			self._running = False
			if self.on_state_change:
				try:
					self.on_state_change("idle")
				except Exception:
					pass

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
					if not self._seated and self.on_state_change:
						try:
							self.on_state_change("distracted")
						except Exception:
							pass
				except asyncio.CancelledError:
					pass

			self._seat_timer_task = asyncio.create_task(_delayed())
		else:
			# 回座 -> 设为 studying（若正在计时）
			if self.on_state_change:
				try:
					self.on_state_change("studying")
				except Exception:
					pass

