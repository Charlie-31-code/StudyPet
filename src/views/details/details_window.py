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
        try:
            self._clear_content_area()
            
            # 先刷新报告列表，确保获取最新数据
            self.refresh_report_list()
            
            # 读取最新的学习报告
            report_data = self._get_latest_study_report()
            
            # 创建专注度数据展示组
            focus_group = QGroupBox("专注度数据详情")
            focus_group.setObjectName("focus_data_group")
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
                    
                    # 修改传递给鼓励话语方法的参数格式，确保数据结构正确
                    encouragement_text = self._get_encouragement_text({
                        "distraction_count": report.get("distracted_count", 0), 
                        "focus_duration": duration_text
                    })
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
            
            # 添加提示文字
            help_label = QLabel("完成一次学习模式后，这里会显示您的专注度统计信息")
            help_label.setAlignment(Qt.AlignCenter)
            help_label.setWordWrap(True)
            help_label.setStyleSheet("color: #666666; margin-top: 10px;")
            
            self.content_layout.addWidget(no_data_label)
            self.content_layout.addWidget(help_label)
        except Exception as e:
            logger.error(f"显示专注度详情时出错: {e}", exc_info=True)
            self._clear_content_area()
            error_label = QLabel(f"加载数据时出错: {str(e)}")
            error_label.setStyleSheet("color: #ff4444;")
            self.content_layout.addWidget(error_label)
    
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
            logger.info("尝试获取最新的学习报告数据")
            
            # 确保报告目录路径已设置
            if not hasattr(self, '_report_dir'):
                logger.info("初始化报告目录路径")
                self._report_dir = os.path.join(get_app_data_dir(), "config", "study_reports")
            
            # 确保报告目录存在
            if not os.path.exists(self._report_dir):
                logger.warning(f"报告目录不存在: {self._report_dir}")
                return None
            
            # 尝试从目录中获取最新的报告文件
            report_files = [f for f in os.listdir(self._report_dir) 
                          if f.endswith('.json') and f.startswith('report_')]
            
            if not report_files:
                logger.info("报告目录中没有找到学习报告文件")
                return None
            
            # 按文件名排序，获取最新的报告文件（report_后面的数字是时间戳）
            report_files.sort(reverse=True)
            latest_file_name = report_files[0]
            latest_file_path = os.path.join(self._report_dir, latest_file_name)
            
            # 读取最新的报告文件
            with open(latest_file_path, 'r', encoding='utf-8') as f:
                latest_report_data = json.load(f)
            
            logger.info(f"成功获取最新学习报告: {latest_file_name}")
            return latest_report_data
            
        except Exception as e:
            logger.error(f"获取最新学习报告失败: {e}", exc_info=True)
            return None
    
    def _get_mock_focus_data(self) -> Dict[str, Any]:
        """
        获取模拟的专注度数据.
        
        Returns:
            模拟的专注度数据字典
        """
        import random
        # 构建与真实报告格式一致的模拟数据
        return {
            "report": {
                "duration": 1500,  # 25分钟
                "focused_count": random.randint(20, 30),
                "distraction_count": random.randint(0, 5),
                "distracted_count": random.randint(0, 5),
                "absent_count": random.randint(0, 3),
                "blocked_count": random.randint(0, 2),
                "total_checks": random.randint(30, 40),
                "avg_score": random.randint(70, 95)
            },
            "session_id": f"mock_session_{random.randint(1000, 9999)}",
            "timestamp": time.time()
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
        刷新报告列表
        """
        try:
            logger.info("刷新学习报告列表")
            
            # 设置报告历史文件路径
            self._report_dir = os.path.join(get_app_data_dir(), "config", "study_reports")
            self._report_history_file = os.path.join(self._report_dir, "report_history.json")
            
            # 读取报告历史文件
            if os.path.exists(self._report_history_file):
                with open(self._report_history_file, 'r', encoding='utf-8') as f:
                    all_reports = json.load(f)
                
                # 保存报告列表引用
                self._all_reports = all_reports
                logger.info(f"从历史文件加载了 {len(all_reports)} 个报告")
            else:
                # 如果历史文件不存在，从目录扫描报告文件并创建索引
                logger.info("报告历史文件不存在，正在创建报告索引")
                
                # 获取目录中的所有报告文件
                report_files = [f for f in os.listdir(self._report_dir) 
                              if f.endswith('.json') and f.startswith('report_')]
                
                if report_files:
                    # 创建报告索引列表
                    all_reports = []
                    for report_file in report_files:
                        # 尝试获取时间戳
                        try:
                            # 从文件名提取时间戳
                            timestamp_str = report_file.replace('report_', '').replace('.json', '')
                            timestamp = float(timestamp_str)
                            
                            # 添加到报告列表
                            all_reports.append({
                                'file_name': report_file,
                                'timestamp': timestamp
                            })
                        except Exception as e:
                            logger.warning(f"处理报告文件 {report_file} 时出错: {e}")
                    
                    # 按时间戳排序，最新的报告在前
                    all_reports.sort(key=lambda x: x['timestamp'], reverse=True)
                    
                    # 保存到实例和文件
                    self._all_reports = all_reports
                    
                    # 尝试保存到历史文件
                    try:
                        with open(self._report_history_file, 'w', encoding='utf-8') as f:
                            json.dump(all_reports, f, ensure_ascii=False, indent=2)
                        logger.info(f"成功创建报告索引，共 {len(all_reports)} 个报告")
                    except Exception as e:
                        logger.warning(f"保存报告索引失败: {e}")
                else:
                    self._all_reports = []
                    logger.info("没有找到学习报告文件")
            
        except Exception as e:
            logger.error(f"刷新报告列表失败: {e}", exc_info=True)
            # 初始化一个空列表，避免后续操作出错
            if not hasattr(self, '_all_reports'):
                self._all_reports = []
    
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
        添加新的学习报告并更新显示
        
        Args:
            report_data: 报告数据
        """
        try:
            # 直接刷新报告列表，从文件系统重新加载，确保数据一致性
            self.refresh_report_list()
            
            # 如果当前显示的是专注度详情页面，则自动更新显示内容
            if self.content_widget and self.content_layout.count() > 0:
                # 检查第一个子组件是否为专注度数据详情组
                first_item = self.content_layout.itemAt(0)
                if first_item and first_item.widget() and first_item.widget().objectName() == "focus_data_group":
                    # 重新显示专注度详情，使用最新的报告数据
                    self._show_focus_details()
            
            # 记录日志表示报告已添加
            logger.info(f"新的学习报告已添加: {report_data.get('session_id')}")
        except Exception as e:
            logger.error(f"添加学习报告失败: {e}")
    
    def closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        self.window_closed.emit()
        event.accept()