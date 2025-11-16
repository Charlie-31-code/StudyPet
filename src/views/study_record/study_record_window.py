# -*- coding: utf-8 -*-
"""
学习记录窗口 - 仅用于展示学习模式专注度详情.
"""

import os
import json
import logging
import threading
import time
import re
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
            parent: 父级窗口
        """
        super().__init__(parent)
        self.setWindowTitle("学习记录")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(600, 400)
        
        # 获取应用数据目录
        app_data_dir = get_app_data_dir()
        self._report_dir = os.path.join(app_data_dir, "study_reports")
        
        # 初始化UI
        self._init_ui()
        
        # 初始化定时器用于定期更新数据
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_study_details)
        self._update_timer.start(5000)  # 每5秒更新一次
        
        logger.info("学习记录窗口初始化完成")
    
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
        
        # 刷新按钮
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.setFont(QFont("PingFang SC", 12))
        self.btn_refresh.clicked.connect(self._refresh_study_details)
        buttons_layout.addWidget(self.btn_refresh)
        
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
    
    def showEvent(self, event):
        """
        窗口显示事件，启动定时更新.
        """
        super().showEvent(event)
        # 启动定时器，每5秒更新一次数据
        self._update_timer.start(5000)
        # 立即更新一次数据
        self._update_study_details()
    
    def hideEvent(self, event):
        """
        窗口隐藏事件，停止定时更新.
        """
        # 停止定时器
        self._update_timer.stop()
        super().hideEvent(event)
    
    def _refresh_study_details(self):
        """
        刷新学习详情.
        """
        # 停止定时器避免刷新过程中触发更新
        self._update_timer.stop()
        
        try:
            # 清除现有内容，提供即时反馈
            self._clear_content_area()
            
            # 重新加载最新的学习报告数据并显示
            # 先刷新报告列表
            if self.refresh_report_list():
                # 只有在报告列表刷新成功后才显示详情
                self._show_study_details()
            else:
                # 如果刷新失败，显示错误信息
                error_label = QLabel("数据刷新失败，请稍后重试")
                error_label.setFont(QFont("PingFang SC", 10))
                error_label.setStyleSheet("color: #ff0000; margin: 5px;")
                error_label.setAlignment(Qt.AlignCenter)
                self.content_layout.insertWidget(0, error_label)
                
                import weakref
                error_label_ref = weakref.ref(error_label)
                
                def remove_error_label():
                    label = error_label_ref()
                    if label and hasattr(self, 'content_layout'):
                        try:
                            if label.parent() is not None:
                                self.content_layout.removeWidget(label)
                                label.deleteLater()
                        except (RuntimeError, AttributeError):
                            pass
                
                QTimer.singleShot(3000, remove_error_label)
            
            # 显示刷新成功的提示
            refresh_label = QLabel("数据已刷新")
            refresh_label.setFont(QFont("PingFang SC", 10))
            refresh_label.setStyleSheet("color: #00aa00; margin: 5px;")
            refresh_label.setAlignment(Qt.AlignCenter)
            
            # 将提示信息添加到内容区域的顶部
            self.content_layout.insertWidget(0, refresh_label)
            
            # 使用弱引用避免循环引用问题
            import weakref
            refresh_label_ref = weakref.ref(refresh_label)
            
            # 3秒后自动移除提示信息
            def remove_refresh_label():
                # 检查窗口是否仍然存在
                if not self or not hasattr(self, 'content_layout'):
                    return
                    
                label = refresh_label_ref()
                if label:
                    try:
                        # 检查标签是否仍有父级且仍在布局中
                        if label.parent() is not None:
                            self.content_layout.removeWidget(label)
                            label.deleteLater()
                    except RuntimeError:
                        # 捕获可能的对象已删除错误
                        pass
            
            QTimer.singleShot(3000, remove_refresh_label)
            
        finally:
            # 无论成功与否都重新启动定时器
            self._update_timer.start(5000)

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

    def _parse_log_for_study_data(self) -> Dict[str, Any]:
        """
        从日志文件中解析学习数据
        """
        try:
            # 获取日志文件路径
            log_file_path = os.path.join(get_app_data_dir(), "logs", "app.log")
            if not os.path.exists(log_file_path):
                return None

            # 读取日志文件
            with open(log_file_path, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()

            # 查找最新的FaceMonitor会话结束记录
            session_end_pattern = r"FaceMonitor.*会话.*结束.*\{'duration': ([\d.]+), 'avg_score': ([\d.]+), 'focused_count': (\d+), 'distracted_count': (\d+), 'absent_count': (\d+), 'blocked_count': (\d+), 'total_checks': (\d+)\}"
            
            latest_session_data = None
            for line in reversed(log_lines):  # 从后往前查找最新的记录
                match = re.search(session_end_pattern, line)
                if match:
                    latest_session_data = {
                        'duration': float(match.group(1)),
                        'avg_score': float(match.group(2)),
                        'focused_count': int(match.group(3)),
                        'distracted_count': int(match.group(4)),
                        'absent_count': int(match.group(5)),
                        'blocked_count': int(match.group(6)),
                        'total_checks': int(match.group(7))
                    }
                    break
            
            return latest_session_data
        except Exception as e:
            logger.error(f"解析日志文件失败: {e}", exc_info=True)
            return None

    def _get_latest_study_report(self) -> Dict[str, Any]:
        """
        获取最新的学习报告数据.

        Returns:
            学习报告数据字典，如果没有则返回None
        """
        try:
            if not os.path.exists(self._report_dir):
                return None

            # 获取所有报告文件，排除report_history.json索引文件
            report_files = [f for f in os.listdir(self._report_dir) 
                           if f.endswith('.json') and f != 'report_history.json']
            if not report_files:
                return None

            # 按文件修改时间排序，获取最新的报告
            report_files_with_time = []
            for f in report_files:
                file_path = os.path.join(self._report_dir, f)
                report_files_with_time.append((f, os.path.getmtime(file_path)))

            # 按修改时间排序，最新的在前
            report_files_with_time.sort(key=lambda x: x[1], reverse=True)
            latest_report = report_files_with_time[0][0]

            # 读取报告内容
            report_path = os.path.join(self._report_dir, latest_report)
            with open(report_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return data

        except Exception as e:
            logger.error(f"读取学习报告失败: {e}", exc_info=True)
            return None
    
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
            return "学习是一个需要坚持的过程，偶尔分心是正常的。明天我们一起努力，提高专注度，你一定可以做到的！"
    
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
    
    def _delayed_initialization(self):
        """
        延迟初始化操作，避免阻塞UI线程
        """
        # 初始化报告列表
        self.refresh_report_list()
        
    def refresh_report_list(self) -> bool:
        """
        刷新学习报告列表，从report_history.json加载所有报告

        Returns:
            bool: 成功返回True，失败返回False
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
            else:
                logger.warning(f"报告历史文件不存在: {history_file}")
                self._report_list = []
            return True
        except Exception as e:
            logger.error(f"刷新报告列表失败: {e}", exc_info=True)
            self._report_list = []
            return False
    
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
        # 停止定时器
        self._update_timer.stop()
        self.window_closed.emit()
        event.accept()

    def _update_study_details(self):
        """
        更新学习详情数据.
        """
        # 只有在学习详情页面显示时才更新
        if self.content_widget.findChild(QGroupBox, "学习详情") is not None:
            self._show_study_details()

    def _show_study_details(self):
        """
        显示学习详情.
        """
        self._clear_content_area()
        
        # 首先尝试从学习报告获取数据
        report_data = self._get_latest_study_report()
        session_data = None
        
        # 如果没有学习报告，则从日志中解析数据
        if not report_data or 'report' not in report_data:
            session_data = self._parse_log_for_study_data()
        
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
                
                # 创建学习详情组
                details_group = QGroupBox("学习详情")
                details_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
                
                grid_layout = QGridLayout()
                grid_layout.setSpacing(15)
                
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
                
                details_group.setLayout(grid_layout)
                self.content_layout.addWidget(details_group)
                
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
        elif session_data:
            # 使用从日志中解析的数据
            # 显示各项真实数据
            data_items = [
                ("专注次数", session_data.get("focused_count", 0)),
                ("分心次数", session_data.get("distracted_count", 0)),
                ("离开次数", session_data.get("absent_count", 0)),
                ("遮挡摄像头次数", session_data.get("blocked_count", 0)),
                ("总检测次数", session_data.get("total_checks", 0)),
                ("平均专注度分数", f"{int(session_data.get('avg_score', 0))}分")
            ]
            
            # 计算专注时长
            duration_seconds = session_data.get("duration", 0)
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            duration_text = f"{minutes}分{seconds}秒"
            data_items.append(("专注学习时长", duration_text))
            
            # 创建学习详情组
            details_group = QGroupBox("学习详情")
            details_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
            
            grid_layout = QGridLayout()
            grid_layout.setSpacing(15)
            
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
            
            details_group.setLayout(grid_layout)
            self.content_layout.addWidget(details_group)
            
            # 添加可视化图表
            self._add_visualization_charts(session_data)
            
            # 添加鼓励话语
            encouragement_group = QGroupBox("鼓励话语")
            encouragement_group.setFont(QFont("PingFang SC", 13, QFont.Bold))
            
            encouragement_text = self._get_encouragement_text(session_data)
            encouragement_label = QLabel(encouragement_text)
            encouragement_label.setFont(QFont("PingFang SC", 12))
            encouragement_label.setWordWrap(True)
            encouragement_label.setStyleSheet("color: #ff6600; padding: 10px;")
            
            encouragement_layout = QVBoxLayout()
            encouragement_layout.addWidget(encouragement_label)
            encouragement_group.setLayout(encouragement_layout)
            
            # 添加数据来源说明
            time_label = QLabel("数据来源: 实时日志分析")
            time_label.setFont(QFont("PingFang SC", 10))
            time_label.setStyleSheet("color: #999999; margin-top: 10px;")
            
            # 添加到布局
            self.content_layout.addWidget(encouragement_group)
            self.content_layout.addWidget(time_label)
            
            return
        
        # 如果没有有效数据，显示提示信息
        no_data_label = QLabel("暂无学习详情数据")
        no_data_label.setFont(QFont("PingFang SC", 14))
        no_data_label.setAlignment(Qt.AlignCenter)
        no_data_label.setStyleSheet("color: #999999; margin: 50px;")
        
        self.content_layout.addWidget(no_data_label)

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