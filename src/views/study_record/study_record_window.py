# -*- coding: utf-8 -*-
"""
学习记录窗口 - 仅用于展示学习模式专注度详情.
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


class StudyRecordWindow(BaseWindow):
    """
    学习记录窗口类，继承自基础窗口类.
    """
    
    # 定义信号
    window_closed = pyqtSignal()
    
    def __init__(self, parent=None):
        """
        初始化学习记录窗口.
        
        Args:
            parent: 父窗口
        """
        super().__init__(parent)
        
        self.setWindowTitle("学习记录")
        self.resize(600, 500)
        self.setMinimumSize(500, 400)
        
        # 学习报告目录
        self._report_dir = os.path.join(get_app_data_dir(), "config", "study_reports")
        
        self._init_ui()
        # 延迟初始化报告列表，避免UI线程阻塞
        QTimer.singleShot(0, self._delayed_initialization)
    
    def _init_ui(self):
        """
        初始化用户界面.
        """
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 标题
        title_label = QLabel("学习记录")
        title_label.setFont(QFont("PingFang SC", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 按钮区域
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        # 学习详情按钮
        self.btn_study_details = QPushButton("学习详情")
        self.btn_study_details.setMinimumHeight(40)
        self.btn_study_details.setFont(QFont("PingFang SC", 12))
        self.btn_study_details.clicked.connect(self._show_study_details)
        buttons_layout.addWidget(self.btn_study_details)
        
        # 导出学习报告按钮
        self.btn_export_report = QPushButton("导出学习报告")
        self.btn_export_report.setMinimumHeight(40)
        self.btn_export_report.setFont(QFont("PingFang SC", 12))
        self.btn_export_report.clicked.connect(self._export_study_report)
        buttons_layout.addWidget(self.btn_export_report)
        
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
        
        welcome_label = QLabel("请选择上方按钮查看学习详情")
        welcome_label.setFont(QFont("PingFang SC", 14))
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("color: #666666; margin: 50px;")
        
        self.content_layout.addWidget(welcome_label)
    
    
    
    def _get_encouragement_text(self, report_data: Dict[str, Any]) -> str:
        """
        根据专注度数据生成鼓励话语.
        
        Args:
            report_data: 专注度数据
            
        Returns:
            鼓励话语文本
        """
        distraction_count = report_data.get("distracted_count", 0)
        duration_seconds = report_data.get("duration", 0)
        minutes = int(duration_seconds // 60)
        
        if distraction_count < 5 and minutes >= 30:
            return "太棒了！你今天的专注度非常棒，继续保持这样的学习状态，你一定会取得很大的进步！"
        elif distraction_count < 10:
            return "今天表现不错！虽然有一些分心，但整体专注度良好。再接再厉，相信你会做得更好！"
        else:
            return "学习是一个需要坚持的过程，偶尔分心是正常的。明天让我们一起努力，提高专注度，你一定可以做到的！"
    
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


    def _show_study_details(self):
        """
        显示学习详情.
        """
        self._clear_content_area()
        
        # 读取最新的学习报告
        report_data = self._get_latest_study_report()
        
        # 创建学习详情组
        details_group = QGroupBox("学习详情")
        details_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
        
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)
        
        # 处理学习报告数据
        if report_data and 'report' in report_data:
            # 从学习报告中提取真实数据
            report = report_data['report']
            if report:
                # 显示各项真实数据
                data_items = [
                    ("学习开始时间", report.get("start_time", "未知")),
                    ("学习结束时间", report.get("end_time", "未知")),
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
                details_group.setLayout(grid_layout)
                self.content_layout.addWidget(details_group)
                self.content_layout.addWidget(encouragement_group)
                self.content_layout.addWidget(time_label)
                
                return
        
        # 如果没有有效数据，显示提示信息
        no_data_label = QLabel("暂无学习详情数据")
        no_data_label.setFont(QFont("PingFang SC", 14))
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_label.setStyleSheet("color: #999999; margin: 50px;")
        
        self.content_layout.addWidget(no_data_label)

    def _export_study_report(self):
        """
        导出学习报告为txt格式.
        """
        try:
            # 读取最新的学习报告
            report_data = self._get_latest_study_report()
            
            if not report_data or 'report' not in report_data:
                QMessageBox.warning(self, "导出失败", "没有可导出的学习报告数据")
                return
            
            # 获取报告数据
            report = report_data['report']
            timestamp = report_data.get('timestamp', time.time())
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            
            # 构建报告内容
            report_content = f"""学习报告
====================

报告生成时间: {time_str}

学习详情:
--------
学习开始时间: {report.get("start_time", "未知")}
学习结束时间: {report.get("end_time", "未知")}
专注学习时长: {self._format_duration(report.get("duration", 0))}
专注次数: {report.get("focused_count", 0)}
分心次数: {report.get("distracted_count", 0)}
离开次数: {report.get("absent_count", 0)}
遮挡摄像头次数: {report.get("blocked_count", 0)}
总检测次数: {report.get("total_checks", 0)}
平均专注度分数: {int(report.get('avg_score', 0))}分

统计分析:
--------
专注率: {self._calculate_focus_rate(report):.1f}%
分心率: {self._calculate_distraction_rate(report):.1f}%

鼓励话语:
--------
{self._get_encouragement_text(report)}

====================
报告导出时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # 创建导出目录
            export_dir = os.path.join(get_app_data_dir(), "exports")
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            # 生成文件名
            filename = f"学习报告_{time.strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(export_dir, filename)
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            # 提示用户
            QMessageBox.information(self, "导出成功", f"学习报告已导出到:\n{filepath}")
            
        except Exception as e:
            logger.error(f"导出学习报告失败: {e}", exc_info=True)
            QMessageBox.critical(self, "导出失败", f"导出学习报告时发生错误:\n{str(e)}")

    def _format_duration(self, seconds):
        """
        格式化持续时间.
        
        Args:
            seconds: 秒数
            
        Returns:
            格式化的时间字符串
        """
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}分{secs}秒"

    def _calculate_focus_rate(self, report):
        """
        计算专注率.
        
        Args:
            report: 报告数据
            
        Returns:
            专注率百分比
        """
        total_checks = report.get("total_checks", 0)
        focused_count = report.get("focused_count", 0)
        if total_checks == 0:
            return 0
        return (focused_count / total_checks) * 100

    def _calculate_distraction_rate(self, report):
        """
        计算分心率.
        
        Args:
            report: 报告数据
            
        Returns:
            分心率百分比
        """
        total_checks = report.get("total_checks", 0)
        distracted_count = report.get("distracted_count", 0)
        if total_checks == 0:
            return 0
        return (distracted_count / total_checks) * 100