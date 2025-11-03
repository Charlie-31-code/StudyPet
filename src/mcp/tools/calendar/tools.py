"""
日程管理MCP工具函数 提供给MCP服务器调用的异步工具函数.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .manager import get_calendar_manager
from .models import CalendarEvent

logger = get_logger(__name__)


async def create_event(args: Dict[str, Any]) -> str:
    """
    创建日程事件.
    """
    try:
        title = args["title"]
        start_time = args["start_time"]
        end_time = args.get("end_time")
        description = args.get("description", "")
        category = args.get("category", "默认")
        reminder_minutes = args.get("reminder_minutes", 15)

        # 如果没有结束时间，根据分类智能设置默认时长
        if not end_time:
            start_dt = datetime.fromisoformat(start_time)

            # 根据分类设置不同的默认时长
            if category in ["提醒", "休息", "站立"]:
                # 短时间活动：5分钟
                end_dt = start_dt + timedelta(minutes=5)
            elif category in ["会议", "工作"]:
                # 工作相关：1小时
                end_dt = start_dt + timedelta(hours=1)
            elif (
                "提醒" in title.lower()
                or "站立" in title.lower()
                or "休息" in title.lower()
            ):
                # 根据标题判断：短时间活动
                end_dt = start_dt + timedelta(minutes=5)
            else:
                # 默认情况：30分钟
                end_dt = start_dt + timedelta(minutes=30)

            end_time = end_dt.isoformat()

        # 验证时间格式
        datetime.fromisoformat(start_time)
        datetime.fromisoformat(end_time)

        # 创建事件
        event = CalendarEvent(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            category=category,
            reminder_minutes=reminder_minutes,
        )

        manager = get_calendar_manager()
        if manager.add_event(event):
            return json.dumps(
                {
                    "success": True,
                    "message": "日程创建成功",
                    "event_id": event.id,
                    "event": event.to_dict(),
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程创建失败，可能存在时间冲突"},
                ensure_ascii=False,
            )

    except Exception as e:
        logger.error(f"创建日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"创建日程失败: {str(e)}"}, ensure_ascii=False
        )


async def get_events_by_date(args: Dict[str, Any]) -> str:
    """
    按日期查询日程.
    """
    try:
        date_type = args.get("date_type", "today")  # today, tomorrow, week, month
        specific_date = args.get("specific_date")   # 支持查询特定日期
        category = args.get("category")
        limit = args.get("limit", 50)  # 限制返回结果数量

        now = datetime.now()

        if specific_date:
            # 查询特定日期
            target_date = datetime.fromisoformat(specific_date)
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif date_type == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif date_type == "tomorrow":
            start_date = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=1)
        elif date_type == "week":
            # 本周
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=7)
        elif date_type == "month":
            # 本月
            start_date = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1)
            else:
                end_date = start_date.replace(month=now.month + 1)
        else:
            # 默认查询今天
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)

        # 转换为ISO格式字符串
        start_date_iso = start_date.isoformat()
        end_date_iso = end_date.isoformat()

        # 查询事件
        manager = get_calendar_manager()
        events = manager.get_events(
            start_date=start_date_iso, end_date=end_date_iso, category=category
        )

        # 按开始时间排序
        events.sort(key=lambda x: x.start_time)
        
        # 限制返回结果数量
        if limit and len(events) > limit:
            events = events[:limit]

        # 转换为字典列表
        events_dict = [event.to_dict() for event in events]

        return json.dumps(
            {
                "success": True,
                "count": len(events_dict),
                "events": events_dict,
                "date_range": {
                    "start": start_date_iso,
                    "end": end_date_iso,
                    "type": date_type
                }
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"查询日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"查询日程失败: {str(e)}"}, ensure_ascii=False
        )


async def get_event_by_id(args: Dict[str, Any]) -> str:
    """
    根据ID查询单个日程.
    """
    try:
        event_id = args["event_id"]

        manager = get_calendar_manager()
        event = manager.get_event_by_id(event_id)

        if event:
            return json.dumps(
                {"success": True, "event": event.to_dict()}, ensure_ascii=False
            )
        else:
            return json.dumps(
                {"success": False, "message": "未找到指定的日程"}, ensure_ascii=False
            )

    except Exception as e:
        logger.error(f"查询日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"查询日程失败: {str(e)}"}, ensure_ascii=False
        )


async def update_event(args: Dict[str, Any]) -> str:
    """
    更新日程事件.
    """
    try:
        event_id = args["event_id"]
        update_data = {
            k: v
            for k, v in args.items()
            if k
            in [
                "title",
                "start_time",
                "end_time",
                "description",
                "category",
                "reminder_minutes",
            ]
        }

        # 验证时间格式
        if "start_time" in update_data:
            datetime.fromisoformat(update_data["start_time"])
        if "end_time" in update_data:
            datetime.fromisoformat(update_data["end_time"])

        manager = get_calendar_manager()
        success = manager.update_event(event_id, **update_data)

        if success:
            updated_event = manager.get_event_by_id(event_id)
            return json.dumps(
                {
                    "success": True,
                    "message": "日程更新成功",
                    "event": updated_event.to_dict() if updated_event else None,
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程更新失败"}, ensure_ascii=False
            )

    except Exception as e:
        logger.error(f"更新日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"更新日程失败: {str(e)}"}, ensure_ascii=False
        )


async def delete_event(args: Dict[str, Any]) -> str:
    """
    删除日程事件.
    """
    try:
        event_id = args["event_id"]

        manager = get_calendar_manager()
        success = manager.delete_event(event_id)

        if success:
            return json.dumps(
                {"success": True, "message": "日程删除成功"}, ensure_ascii=False
            )
        else:
            return json.dumps(
                {"success": False, "message": "日程删除失败"}, ensure_ascii=False
            )

    except Exception as e:
        logger.error(f"删除日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"删除日程失败: {str(e)}"}, ensure_ascii=False
        )


async def delete_events_batch(args: Dict[str, Any]) -> str:
    """
    批量删除日程事件.
    """
    try:
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        category = args.get("category")
        delete_all = args.get("delete_all", False)
        date_type = args.get("date_type")

        # 处理date_type参数（类似get_events_by_date）
        if date_type and not (start_date and end_date):
            now = datetime.now()

            if date_type == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif date_type == "tomorrow":
                start_date = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=1)
            elif date_type == "week":
                # 本周
                days_since_monday = now.weekday()
                start_date = (now - timedelta(days=days_since_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=7)
            elif date_type == "month":
                # 本月
                start_date = now.replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
                if now.month == 12:
                    end_date = start_date.replace(year=now.year + 1, month=1)
                else:
                    end_date = start_date.replace(month=now.month + 1)

            # 转换为ISO格式字符串
            if isinstance(start_date, datetime):
                start_date = start_date.isoformat()
            if isinstance(end_date, datetime):
                end_date = end_date.isoformat()

        manager = get_calendar_manager()
        result = manager.delete_events_batch(
            start_date=start_date,
            end_date=end_date,
            category=category,
            delete_all=delete_all,
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"批量删除日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"批量删除日程失败: {str(e)}"},
            ensure_ascii=False,
        )


async def get_categories(args: Dict[str, Any]) -> str:
    """
    获取所有日程分类.
    """
    try:
        manager = get_calendar_manager()
        categories = manager.get_categories()

        return json.dumps(
            {"success": True, "categories": categories}, ensure_ascii=False
        )

    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取分类失败: {str(e)}"}, ensure_ascii=False
        )


async def get_upcoming_events(args: Dict[str, Any]) -> str:
    """
    获取即将到来的日程（未来24小时内）
    """
    try:
        hours = args.get("hours", 24)  # 默认查询未来24小时
        limit = args.get("limit", 10)  # 限制返回结果数量

        now = datetime.now()
        end_time = now + timedelta(hours=hours)

        manager = get_calendar_manager()
        events = manager.get_events(
            start_date=now.isoformat(), end_date=end_time.isoformat()
        )

        # 按开始时间排序
        events.sort(key=lambda x: x.start_time)
        
        # 限制返回结果数量
        if limit and len(events) > limit:
            events = events[:limit]

        # 计算提醒时间
        upcoming_events = []
        for event in events:
            event_dict = event.to_dict()
            start_dt = datetime.fromisoformat(event.start_time)

            # 计算距离开始的时间
            time_until = start_dt - now
            if time_until.total_seconds() > 0:
                days = int(time_until.total_seconds() // 86400)
                hours = int((time_until.total_seconds() % 86400) // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)

                # 更准确的时间描述
                if days > 0:
                    time_str = f"{days}天{hours}小时后"
                elif hours > 0:
                    time_str = f"{hours}小时{minutes}分钟后"
                else:
                    time_str = f"{minutes}分钟后"
            else:
                time_str = "现在"

            event_dict["time_until"] = time_str
            upcoming_events.append(event_dict)

        return json.dumps(
            {
                "success": True,
                "count": len(upcoming_events),
                "events": upcoming_events,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"获取即将到来的日程失败: {e}")
        return json.dumps(
            {"success": False, "message": f"获取即将到来的日程失败: {str(e)}"},
            ensure_ascii=False,
        )
