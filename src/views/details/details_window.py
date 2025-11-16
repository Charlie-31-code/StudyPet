# -*- coding: utf-8 -*-
"""
详情窗口 - 用于展示学习模式专注度详情和对话记录.
"""

import os
import json
import logging
import threading
import time
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
    QTextEdit, QLabel, QScrollArea, QMessageBox, QGroupBox, QGridLayout,
    QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from PyQt5.QtGui import QFont

# 导入matplotlib相关库
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.font_manager as fm

from src.views.base.base_window import BaseWindow
from src.utils.common_utils import get_app_data_dir
from src.utils.config_manager import ConfigManager
from src.application import Application

logger = logging.getLogger(__name__)


class DetailsWindow(BaseWindow):
    """
    详情窗口类，继承自基础窗口类.
    """
    
    # 定义信号
    window_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        初始化详情窗口.
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("学习详情")
        self.resize(600, 500)
        self.setMinimumSize(500, 400)
        
        # 学习报告目录
        self._report_dir = os.path.join(get_app_data_dir(), "config", "study_reports")
        
        # 添加定时器用于定期更新数据
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_display_data)
        
        self._init_ui()
        # 延迟初始化报告列表，避免UI线程阻塞
        QTimer.singleShot(0, self._delayed_initialization_safe)
    
    def _delayed_initialization_safe(self):
        """安全的延迟初始化"""
        try:
            if hasattr(self, '_delayed_initialization'):
                self._delayed_initialization()
        except RuntimeError:
            # 窗口可能已被销毁
            pass
    

        
    def _init_ui(self):
        """
        初始化用户界面.
        """
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # 标题
        title_label = QLabel("学习详情")
        title_label.setFont(QFont("PingFang SC", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 按钮区域
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # 专注度详情按钮
        self.btn_focus_details = QPushButton("学习模式专注度详情")
        self.btn_focus_details.setMinimumHeight(40)
        self.btn_focus_details.setFont(QFont("PingFang SC", 12))
        self.btn_focus_details.clicked.connect(self._show_focus_details)
        buttons_layout.addWidget(self.btn_focus_details)
        
        # 移除对话记录按钮
        # self.btn_conversation = QPushButton("与小智的对话记录")
        # self.btn_conversation.setMinimumHeight(40)
        # self.btn_conversation.setFont(QFont("PingFang SC", 12))
        # self.btn_conversation.clicked.connect(self._show_conversation_history)
        # buttons_layout.addWidget(self.btn_conversation)
        
        main_layout.addLayout(buttons_layout)
        
        # 内容展示区域
        self.content_area = QScrollArea()
        self.content_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.content_area.setWidget(self.content_widget)
        main_layout.addWidget(self.content_area, 1)
        
        # 设置中心部件
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # 初始化时显示提示信息
        self._show_welcome_message()
    
    def showEvent(self, event):
        """
        窗口显示事件，启动定时更新.
        """
        super().showEvent(event)
        # 启动定时器，每5秒更新一次数据
        self._update_timer.start(5000)
        # 立即更新一次数据
        self._update_display_data()
    
    def hideEvent(self, event):
        """
        窗口隐藏事件，停止定时更新.
        """
        # 停止定时器
        self._update_timer.stop()
        super().hideEvent(event)
    
    def closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        # 停止定时器
        self._update_timer.stop()
        self.window_closed.emit()
        event.accept()
    
    def _update_display_data(self):
        """
        更新显示数据.
        """
        # 如果当前显示的是专注度详情，则更新专注度详情
        if self.content_widget.findChild(QGroupBox, "专注度数据详情") is not None:
            self._show_focus_details()
        # 如果当前显示的是对话记录，则更新对话记录
        elif self.content_widget.findChild(QGroupBox, "对话记录") is not None:
            self._load_conversation_history()
    
    def _show_welcome_message(self):
        """
        显示欢迎信息.
        """
        self._clear_content_area()
        
        welcome_label = QLabel("请选择上方按钮查看相应详情")
        welcome_label.setFont(QFont("PingFang SC", 14))
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("color: #666666; margin: 50px;")
        
        self.content_layout.addWidget(welcome_label)
    
    def _show_focus_details(self):
        """
        显示学习模式专注度详情，使用真实的学习报告数据.
        """
        self._clear_content_area()
        
        # 读取最新的学习报告
        report_data = self._get_latest_study_report()
        
        # 处理学习报告数据
        if report_data and 'report' in report_data:
            # 从学习报告中提取真实数据
            report = report_data['report']
            if report:
                # 创建专注度数据展示组
                focus_group = QGroupBox("专注度数据详情")
                focus_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
                
                grid_layout = QGridLayout()
                grid_layout.setSpacing(15)
                
                # 显示各项真实数据
                data_items = [
                    ("专注次数", report.get("focused_count", 0)),
                    ("分心次数", report.get("distracted_count", 0)),
                    ("离开次数", report.get("absent_count", 0)),
                    ("遮挡摄像头次数", report.get("blocked_count", 0)),
                    ("总检测次数", report.get("total_checks", 0)),
                    ("平均专注度分数", f"{int(report.get('avg_score', 0))}分")
                ]
                
                # 计算专注时长
                duration_seconds = report.get("duration", 0)
                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)
                duration_text = f"{minutes}分{seconds}秒"
                data_items.append(("专注学习时长", duration_text))
                
                for i, (label_text, value) in enumerate(data_items):
                    label = QLabel(f"{label_text}:")
                    label.setFont(QFont("PingFang SC", 12))
                    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    
                    value_label = QLabel(str(value))
                    value_label.setFont(QFont("PingFang SC", 12, QFont.Bold))
                    value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    value_label.setStyleSheet("color: #3366cc;")
                    
                    grid_layout.addWidget(label, i, 0)
                    grid_layout.addWidget(value_label, i, 1)
                
                focus_group.setLayout(grid_layout)
                self.content_layout.addWidget(focus_group)
                
                # 添加可视化图表
                self._add_visualization_charts(report)
                
                # 添加鼓励话语
                encouragement_group = QGroupBox("鼓励话语")
                encouragement_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
                
                encouragement_text = self._get_encouragement_text(report)
                encouragement_label = QLabel(encouragement_text)
                encouragement_label.setFont(QFont("PingFang SC", 12))
                encouragement_label.setWordWrap(True)
                encouragement_label.setStyleSheet("color: #ff6600; padding: 10px;")
                
                encouragement_layout = QVBoxLayout()
                encouragement_layout.addWidget(encouragement_label)
                encouragement_group.setLayout(encouragement_layout)
                
                # 添加报告生成时间
                timestamp = report_data.get('timestamp', time.time())
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                time_label = QLabel(f"报告生成时间: {time_str}")
                time_label.setFont(QFont("PingFang SC", 10))
                time_label.setStyleSheet("color: #999999; margin-top: 10px;")
                
                # 添加到布局
                self.content_layout.addWidget(encouragement_group)
                self.content_layout.addWidget(time_label)
                
                return
        
        # 如果没有有效数据，显示提示信息
        no_data_label = QLabel("暂无学习报告数据")
        no_data_label.setFont(QFont("PingFang SC", 14))
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_label.setStyleSheet("color: #999999; margin: 50px;")
        
        self.content_layout.addWidget(no_data_label)
    

    
    def _clear_content_area(self):
        """
        清空内容区域.
        """
        # 移除所有子部件
        while self.content_layout.count() > 0:
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
    
    def _get_latest_study_report(self) -> Dict[str, Any]:
        """
        获取最新的学习报告数据.
        
        Returns:
            学习报告数据字典，如果没有则返回None
        """
        try:
            if not os.path.exists(self._report_dir):
                return None
            
            # 获取所有报告文件
            report_files = [f for f in os.listdir(self._report_dir) if f.endswith('.json')]
            if not report_files:
                return None
            
            # 按文件名排序，获取最新的报告
            report_files.sort(reverse=True)
            latest_report = report_files[0]
            
            # 读取报告内容
            report_path = os.path.join(self._report_dir, latest_report)
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data
            
        except Exception as e:
            logger.error(f"读取学习报告失败: {e}", exc_info=True)
            return None
    
    def _get_mock_focus_data(self) -> Dict[str, Any]:
        """
        获取模拟的专注度数据.
        
        Returns:
            模拟的专注度数据字典
        """
        return {
            "distraction_count": 5,
            "leave_count": 2,
            "camera_block_count": 1,
            "focus_duration": "45分钟"
        }
    

    
    def _get_encouragement_text(self, report_data: Dict[str, Any]) -> str:
        """
        根据专注度数据生成鼓励话语.
        
        Args:
            report_data: 专注度数据
            
        Returns:
            鼓励话语文本
        """
        distraction_count = report_data.get("distraction_count", 0)
        focus_duration = report_data.get("focus_duration", "0分钟")
        
        if distraction_count < 5 and focus_duration.startswith("4"):
            return "太棒了！你今天的专注度非常棒，继续保持这样的学习状态，你一定会取得很大的进步！"
        elif distraction_count < 10:
            return "今天表现不错！虽然有一些分心，但整体专注度良好。再接再厉，相信你会做得更好！"
        else:
            return "学习是一个需要坚持的过程，偶尔分心是正常的。明天我们一起努力，提高专注度，你一定可以做到的！"
    
    def _load_conversation_history(self):
        """
        加载并显示对话历史记录
        """
        try:
            from src.utils.common_utils import get_app_data_dir
            import os
            import json
            
            # 构建对话记录文件路径
            chat_history_file = os.path.join(get_app_data_dir(), "config", "chat_history.json")
            
            # 检查文件是否存在
            if not os.path.exists(chat_history_file):
                self._clear_content_area()
                no_data_label = QLabel("暂无对话记录")
                no_data_label.setFont(QFont("PingFang SC", 14))
                no_data_label.setAlignment(Qt.AlignCenter)
                no_data_label.setStyleSheet("color: #999999; margin: 50px;")
                self.content_layout.addWidget(no_data_label)
                return
            
            # 读取对话记录
            with open(chat_history_file, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
            
            # 清空内容区域
            self._clear_content_area()
            
            # 创建对话记录展示组
            chat_group = QGroupBox("对话记录")
            chat_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
            chat_layout = QVBoxLayout()
            
            # 显示对话记录
            if not chat_history:
                no_data_label = QLabel("暂无对话记录")
                no_data_label.setFont(QFont("PingFang SC", 14))
                no_data_label.setAlignment(Qt.AlignCenter)
                no_data_label.setStyleSheet("color: #999999; margin: 50px;")
                chat_layout.addWidget(no_data_label)
            else:
                # 构建对话记录文本
                for record in chat_history[-20:]:  # 只显示最近20条记录
                    timestamp = record.get('timestamp', '')
                    user_msg = record.get('user', '')
                    ai_msg = record.get('ai', '')
                    
                    # 创建消息容器
                    msg_frame = QFrame()
                    msg_frame.setFrameStyle(QFrame.StyledPanel)
                    msg_layout = QVBoxLayout(msg_frame)
                    
                    # 格式化时间显示
                    if timestamp:
                        time_label = QLabel(f"[{timestamp}]")
                        time_label.setFont(QFont("PingFang SC", 10))
                        time_label.setStyleSheet("font-weight: bold; color: #666666;")
                        msg_layout.addWidget(time_label)
                    
                    # 添加用户消息
                    if user_msg:
                        user_label = QLabel(f"用户: {user_msg}")
                        user_label.setFont(QFont("PingFang SC", 11))
                        user_label.setWordWrap(True)
                        user_label.setStyleSheet("margin-left: 10px; padding: 5px;")
                        user_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                        msg_layout.addWidget(user_label)
                    
                    # 添加AI回复
                    if ai_msg:
                        ai_label = QLabel(f"小智: {ai_msg}")
                        ai_label.setFont(QFont("PingFang SC", 11))
                        ai_label.setWordWrap(True)
                        ai_label.setStyleSheet("margin-left: 10px; color: #3366cc; padding: 5px;")
                        ai_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                        msg_layout.addWidget(ai_label)
                    
                    # 添加分隔线
                    separator = QFrame()
                    separator.setFrameShape(QFrame.HLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setStyleSheet("background-color: #eeeeee;")
                    msg_layout.addWidget(separator)
                    
                    chat_layout.addWidget(msg_frame)
            
            # 设置滚动区域内容
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            content_widget = QWidget()
            content_widget.setLayout(chat_layout)
            scroll_area.setWidget(content_widget)
            
            # 添加到主布局
            chat_group_layout = QVBoxLayout()
            chat_group_layout.addWidget(scroll_area)
            chat_group.setLayout(chat_group_layout)
            
            self.content_layout.addWidget(chat_group)
        
        except Exception as e:
            logger.error(f"加载对话历史记录失败: {e}", exc_info=True)
            # 如果出现异常，显示错误信息
            self._clear_content_area()
            error_label = QLabel("加载对话记录时发生错误")
            error_label.setFont(QFont("PingFang SC", 14))
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #ff0000; margin: 50px;")
            self.content_layout.addWidget(error_label)
    
    def _add_visualization_charts(self, report):
        """
        添加可视化图表展示专注度数据.
        
        Args:
            report: 学习报告数据
        """
        # 创建图表组
        charts_group = QGroupBox("专注度数据可视化")
        charts_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
        charts_layout = QVBoxLayout()
        
        # 创建matplotlib图表
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        fig.tight_layout(pad=3.0)
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'PingFang SC', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 数据准备
        focused_count = report.get("focused_count", 0)
        distracted_count = report.get("distracted_count", 0)
        absent_count = report.get("absent_count", 0)
        blocked_count = report.get("blocked_count", 0)
        
        # 创建柱状图
        categories = ['专注', '分心', '离开', '遮挡']
        values = [focused_count, distracted_count, absent_count, blocked_count]
        colors = ['#4CAF50', '#FF9800', '#F44336', '#9C27B0']
        
        bars = ax1.bar(categories, values, color=colors)
        ax1.set_title('专注度状态分布', fontsize=12, pad=10)
        ax1.set_ylabel('次数', fontsize=10)
        
        # 在柱状图上添加数值标签
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{value}',
                    ha='center', va='bottom', fontsize=9)
        
        # 创建饼图
        non_zero_values = [v for v in values if v > 0]
        non_zero_categories = [cat for cat, val in zip(categories, values) if val > 0]
        non_zero_colors = [col for col, val in zip(colors, values) if val > 0]
        
        if non_zero_values:
            wedges, texts, autotexts = ax2.pie(non_zero_values, labels=non_zero_categories, 
                                               colors=non_zero_colors, autopct='%1.1f%%',
                                               startangle=90)
            ax2.set_title('专注度状态占比', fontsize=12, pad=10)
            
            # 设置饼图标签字体大小
            for text in texts:
                text.set_fontsize(9)
            for autotext in autotexts:
                autotext.set_fontsize(9)
        
        # 将图表嵌入到QWidget中
        canvas = FigureCanvas(fig)
        charts_layout.addWidget(canvas)
        
        charts_group.setLayout(charts_layout)
        self.content_layout.addWidget(charts_group)
        
        # 调整图表布局
        fig.subplots_adjust(left=0.1, right=0.9, top=0.85, bottom=0.15)