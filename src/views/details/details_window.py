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
        
        # 对话记录存储和锁
        self._conversation_history = []
        self._conversation_lock = threading.Lock()
        self._app = Application.get_instance()
        
        # 对话历史文件路径
        self._chat_history_file = os.path.join(get_app_data_dir(), "config", "chat_history.json")
        
        self._init_ui()
        # 移除未实现的_load_conversation_history方法调用
        self._load_chat_history_from_file()
        # 延迟初始化报告列表，避免UI线程阻塞
        QTimer.singleShot(0, self._delayed_initialization)
    
    def _load_chat_history_from_file(self):
        """
        从文件加载历史对话记录
        """
        try:
            if os.path.exists(self._chat_history_file):
                with self._conversation_lock:
                    with open(self._chat_history_file, 'r', encoding='utf-8') as f:
                        conversations = json.load(f)
                        
                        # 直接更新内部对话历史，避免重复调用add_conversation
                        self._conversation_history = conversations
        except Exception as e:
            logger.error(f"加载对话历史时出错: {e}")
        
    def _init_ui(self):
        """
        初始化用户界面.
        """
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 标题
        title_label = QLabel("学习与对话详情")
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
        
        # 对话记录按钮
        self.btn_conversation = QPushButton("与小智的对话记录")
        self.btn_conversation.setMinimumHeight(40)
        self.btn_conversation.setFont(QFont("PingFang SC", 12))
        self.btn_conversation.clicked.connect(self._show_conversation_history)
        buttons_layout.addWidget(self.btn_conversation)
        
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
        
        # 创建专注度数据展示组
        focus_group = QGroupBox("专注度数据详情")
        focus_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        
        # 处理学习报告数据
        if report_data and 'report' in report_data:
            # 从学习报告中提取真实数据
            report = report_data['report']
            if report:
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
                focus_group.setLayout(grid_layout)
                self.content_layout.addWidget(focus_group)
                self.content_layout.addWidget(encouragement_group)
                self.content_layout.addWidget(time_label)
                
                return
        
        # 如果没有有效数据，显示提示信息
        no_data_label = QLabel("暂无学习报告数据")
        no_data_label.setFont(QFont("PingFang SC", 14))
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_label.setStyleSheet("color: #999999; margin: 50px;")
        
        self.content_layout.addWidget(no_data_label)
    
    def _show_conversation_history(self):
        """
        显示与小智的真实对话记录.
        """
        self._clear_content_area()
        
        # 创建通话记录展示区域
        history_group = QGroupBox("对话记录")
        history_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setAlignment(Qt.AlignTop)
        
        # 读取对话历史记录
        conversation_history = self._get_conversation_history()
        
        if conversation_history:
            # 显示每条对话记录
            for entry in conversation_history:
                # 创建对话条目容器
                entry_widget = QWidget()
                entry_layout = QVBoxLayout(entry_widget)
                entry_layout.setSpacing(5)
                
                # 显示时间
                time_label = QLabel(entry.get("time", "未知时间"))
                time_label.setFont(QFont("PingFang SC", 10))
                time_label.setStyleSheet("color: #999999;")
                entry_layout.addWidget(time_label)
                
                # 显示用户提问
                user_label = QLabel(f"<b>你：</b>{entry.get("user", "")}")
                user_label.setFont(QFont("PingFang SC", 12))
                user_label.setWordWrap(True)
                user_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                user_label.setStyleSheet("background-color: #f0f7ff; padding: 8px; border-radius: 5px;")
                entry_layout.addWidget(user_label)
                
                # 显示小智回答
                ai_label = QLabel(f"<b>小智：</b>{entry.get("ai", "")}")
                ai_label.setFont(QFont("PingFang SC", 12))
                ai_label.setWordWrap(True)
                ai_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                ai_label.setStyleSheet("background-color: #f0fff0; padding: 8px; border-radius: 5px;")
                entry_layout.addWidget(ai_label)
                
                # 添加分割线
                separator = QFrame()
                separator.setFrameShape(QFrame.HLine)
                separator.setFrameShadow(QFrame.Sunken)
                separator.setStyleSheet("background-color: #eeeeee;")
                entry_layout.addWidget(separator)
                
                content_layout.addWidget(entry_widget)
        else:
            # 如果没有对话记录，显示提示信息
            no_data_label = QLabel("暂无对话记录")
            no_data_label.setFont(QFont("PingFang SC", 14))
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: #999999; margin: 50px;")
            content_layout.addWidget(no_data_label)
        
        # 设置滚动区域内容
        scroll_area.setWidget(content_widget)
        
        # 添加到主布局
        history_layout = QVBoxLayout()
        history_layout.addWidget(scroll_area)
        history_group.setLayout(history_layout)
        
        self.content_layout.addWidget(history_group)
        
    def _get_conversation_history(self):
        """
        获取对话历史记录，从存储文件中读取真实的对话记录.
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self._chat_history_file), exist_ok=True)
            
            # 尝试读取对话历史文件
            if os.path.exists(self._chat_history_file):
                with self._conversation_lock:
                    with open(self._chat_history_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
            return []
        except Exception as e:
            print(f"读取对话历史失败: {e}")
            return []
    
    def add_conversation(self, user_message, ai_response, silent=False):
        """
        添加新的对话记录.
        此方法可以被Application调用，在每次用户与AI交互后保存对话.
        
        Args:
            user_message: 用户的消息
            ai_response: AI的回复
            silent: 是否静默添加（用于加载历史记录时不显示通知）
        """
        try:
            # 获取当前时间
            current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            
            # 创建新的对话条目
            new_entry = {
                "time": current_time,
                "user": user_message,
                "ai": ai_response
            }
            
            # 读取现有对话历史
            history = self._get_conversation_history()
            
            # 添加新条目
            history.append(new_entry)
            
            # 限制历史记录数量，只保留最近的100条
            if len(history) > 100:
                history = history[-100:]
            
            # 保存更新后的对话历史
            with self._conversation_lock:
                os.makedirs(os.path.dirname(self._chat_history_file), exist_ok=True)
                with open(self._chat_history_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")
            return False
    
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
            return "学习是一个需要坚持的过程，偶尔分心是正常的。明天让我们一起努力，提高专注度，你一定可以做到的！"
    
    def _load_conversation_history(self):
        """
        加载对话历史记录（这里简化处理）.
        """
        # 实际应用中，应该从应用的对话存储中获取
        # 这里只是预留接口
        pass
    
    def _delayed_initialization(self):
        """
        延迟初始化操作，避免阻塞UI线程
        """
        # 初始化报告列表
        self.refresh_report_list()
        
    def refresh_report_list(self):
        """
        刷新学习报告列表，从report_history.json加载所有报告
        """
        try:
            report_dir = os.path.join(get_app_data_dir(), "config", "study_reports")
            history_file = os.path.join(report_dir, "report_history.json")
            
            # 初始化报告列表属性
            self._all_reports = []
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    self._report_list = json.load(f)
                    # 只保存报告列表信息，不立即加载所有报告的详细内容
                    # 详细内容将在需要时（如点击查看）才加载
        except Exception as e:
            logger.error(f"刷新报告列表失败: {e}")
    
    def _load_all_study_reports(self, report_list):
        """
        加载并显示所有学习报告（按需加载）
        
        Args:
            report_list: 报告列表数据
        """
        # 这里只保存报告列表，不立即加载所有报告详情
        # 详细内容将在需要时（如点击查看）才加载
        self._report_list = report_list
        
        # 仅在需要更新显示时加载最新的报告
        if hasattr(self, '_update_focus_details_display'):
            # 先尝试获取最新报告的详细信息
            if report_list:
                self._get_latest_study_report()
            self._update_focus_details_display()
    
    def add_study_report(self, report_data):
        """
        添加新的学习报告
        
        Args:
            report_data: 报告数据
        """
        try:
            # 如果没有_all_reports属性，初始化它
            if not hasattr(self, '_all_reports'):
                self._all_reports = []
            
            # 添加新报告
            self._all_reports.insert(0, report_data)  # 最新的报告放在前面
            
            # 更新显示
            if hasattr(self, '_update_focus_details_display'):
                self._update_focus_details_display()
        except Exception as e:
            logger.error(f"添加学习报告失败: {e}")
    
    def closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        self.window_closed.emit()
        event.accept()