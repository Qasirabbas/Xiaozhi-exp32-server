import time
import asyncio
import datetime
from typing import Dict, List, Optional, Union, Any
import threading
import json
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# Function description for timer
TIMER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "set_timer",
        "description": "设置一个倒计时计时器，到时间后会提醒用户。适用于如'设置3分钟的计时器'、'帮我定一个5分钟后的计时器'等请求",
        "parameters": {
            "type": "object",
            "properties": {
                "duration": {
                    "type": "integer",
                    "description": "计时器的持续时间，以秒为单位"
                },
                "label": {
                    "type": "string",
                    "description": "计时器的标签，如'煮饭'、'运动'等，可选参数"
                },
                "response_success": {
                    "type": "string",
                    "description": "成功设置计时器时的友好回复，可以使用{duration}、{label}和{end_time}占位符"
                },
                "response_failure": {
                    "type": "string",
                    "description": "无法设置计时器时的友好回复"
                }
            },
            "required": ["duration", "response_success", "response_failure"]
        }
    }
}

# Function description for alarm
ALARM_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "set_alarm",
        "description": "设置一个闹钟，在指定的时间提醒用户。适用于如'明天早上7点叫我起床'、'设置一个下午3点的闹钟'等请求",
        "parameters": {
            "type": "object",
            "properties": {
                "hour": {
                    "type": "integer",
                    "description": "小时，24小时制（0-23）"
                },
                "minute": {
                    "type": "integer",
                    "description": "分钟（0-59）"
                },
                "day_offset": {
                    "type": "integer",
                    "description": "相对于今天的天数偏移，0表示今天，1表示明天，以此类推，默认为0"
                },
                "label": {
                    "type": "string",
                    "description": "闹钟的标签，如'起床'、'会议'等，可选参数"
                },
                "response_success": {
                    "type": "string",
                    "description": "成功设置闹钟时的友好回复，可以使用{time}、{label}和{day}占位符"
                },
                "response_failure": {
                    "type": "string",
                    "description": "无法设置闹钟时的友好回复"
                }
            },
            "required": ["hour", "minute", "response_success", "response_failure"]
        }
    }
}

# Function description for checking timers and alarms
CHECK_TIMERS_ALARMS_DESC = {
    "type": "function",
    "function": {
        "name": "check_timers_alarms",
        "description": "查询当前设置的计时器和闹钟。适用于如'查看我的计时器'、'有什么闹钟'等请求",
        "parameters": {
            "type": "object",
            "properties": {
                "check_type": {
                    "type": "string",
                    "description": "查询的类型，可以是'timer'（计时器）、'alarm'（闹钟）或'all'（全部）",
                    "enum": ["timer", "alarm", "all"]
                },
                "response_success": {
                    "type": "string",
                    "description": "成功查询时的友好回复"
                },
                "response_failure": {
                    "type": "string",
                    "description": "无法查询时的友好回复"
                }
            },
            "required": ["check_type", "response_success", "response_failure"]
        }
    }
}

# Function description for canceling timers and alarms
CANCEL_TIMERS_ALARMS_DESC = {
    "type": "function",
    "function": {
        "name": "cancel_timer_alarm",
        "description": "取消已设置的计时器或闹钟。适用于如'取消计时器'、'停止闹钟'等请求",
        "parameters": {
            "type": "object",
            "properties": {
                "cancel_type": {
                    "type": "string",
                    "description": "取消的类型，可以是'timer'（计时器）、'alarm'（闹钟）或'all'（全部）",
                    "enum": ["timer", "alarm", "all"]
                },
                "timer_id": {
                    "type": "string",
                    "description": "要取消的计时器ID，如果不指定则取消所有计时器"
                },
                "alarm_id": {
                    "type": "string",
                    "description": "要取消的闹钟ID，如果不指定则取消所有闹钟"
                },
                "response_success": {
                    "type": "string",
                    "description": "成功取消时的友好回复"
                },
                "response_failure": {
                    "type": "string",
                    "description": "无法取消时的友好回复"
                }
            },
            "required": ["cancel_type", "response_success", "response_failure"]
        }
    }
}

# 全局存储计时器和闹钟
class TimerAlarmManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TimerAlarmManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.timers = {}  # {timer_id: {duration, start_time, end_time, label, task}}
            self.alarms = {}  # {alarm_id: {time, label, day_offset, task}}
            self._initialized = True
    
    @staticmethod
    def get_instance():
        return TimerAlarmManager()
    
    def add_timer(self, duration, label=None):
        """添加一个计时器"""
        timer_id = f"timer_{int(time.time())}_{len(self.timers)}"
        start_time = time.time()
        end_time = start_time + duration
        
        self.timers[timer_id] = {
            "duration": duration,
            "start_time": start_time,
            "end_time": end_time,
            "label": label,
            "task": None  # 将由调用函数设置
        }
        
        return timer_id
    
    def add_alarm(self, hour, minute, day_offset=0, label=None):
        """添加一个闹钟"""
        alarm_id = f"alarm_{int(time.time())}_{len(self.alarms)}"
        
        # 获取目标时间
        now = datetime.datetime.now()
        target_date = now.date() + datetime.timedelta(days=day_offset)
        target_time = datetime.datetime.combine(target_date, datetime.time(hour, minute))
        
        # 如果目标时间已经过去，并且day_offset为0，则设置为明天
        if target_time < now and day_offset == 0:
            target_date = now.date() + datetime.timedelta(days=1)
            target_time = datetime.datetime.combine(target_date, datetime.time(hour, minute))
        
        self.alarms[alarm_id] = {
            "hour": hour,
            "minute": minute,
            "day_offset": day_offset,
            "time": target_time,
            "label": label,
            "task": None  # 将由调用函数设置
        }
        
        return alarm_id
    
    def cancel_timer(self, timer_id=None):
        """取消计时器"""
        if timer_id is None:
            # 取消所有计时器
            for tid, timer in list(self.timers.items()):
                if timer["task"] and not timer["task"].done():
                    timer["task"].cancel()
            self.timers.clear()
            return len(self.timers) > 0
        
        # 取消指定计时器
        if timer_id in self.timers:
            timer = self.timers[timer_id]
            if timer["task"] and not timer["task"].done():
                timer["task"].cancel()
            del self.timers[timer_id]
            return True
        
        return False
    
    def cancel_alarm(self, alarm_id=None):
        """取消闹钟"""
        if alarm_id is None:
            # 取消所有闹钟
            for aid, alarm in list(self.alarms.items()):
                if alarm["task"] and not alarm["task"].done():
                    alarm["task"].cancel()
            self.alarms.clear()
            return len(self.alarms) > 0
        
        # 取消指定闹钟
        if alarm_id in self.alarms:
            alarm = self.alarms[alarm_id]
            if alarm["task"] and not alarm["task"].done():
                alarm["task"].cancel()
            del self.alarms[alarm_id]
            return True
        
        return False
    
    def get_timers(self):
        """获取所有计时器"""
        # 过滤掉已完成的计时器
        active_timers = {}
        for timer_id, timer in list(self.timers.items()):
            if timer["end_time"] > time.time():
                active_timers[timer_id] = timer
            else:
                # 自动清理已完成的计时器
                if timer["task"] and not timer["task"].done():
                    timer["task"].cancel()
                del self.timers[timer_id]
        
        return active_timers
    
    def get_alarms(self):
        """获取所有闹钟"""
        return self.alarms

async def timer_callback(conn, timer_id, label):
    """计时器到期时的回调函数"""
    try:
        manager = TimerAlarmManager.get_instance()
        if timer_id in manager.timers:
            timer = manager.timers[timer_id]
            
            # 构建提醒消息
            if label:
                message = f"您设置的 {label} 计时器时间到了！"
            else:
                message = f"您设置的计时器时间到了！"
            
            # 发送提醒
            if hasattr(conn, 'websocket') and conn.websocket:
                from core.handle.sendAudioHandle import send_stt_message
                await send_stt_message(conn, message)
                
                # 将消息提交给LLM处理
                if conn.use_function_call_mode:
                    conn.executor.submit(conn.chat_with_function_calling, message)
                else:
                    conn.executor.submit(conn.chat, message)
            
            # 删除计时器
            del manager.timers[timer_id]
            logger.bind(tag=TAG).info(f"计时器 {timer_id} 已触发: {message}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"计时器回调出错: {e}")

async def alarm_callback(conn, alarm_id, label):
    """闹钟到期时的回调函数"""
    try:
        manager = TimerAlarmManager.get_instance()
        if alarm_id in manager.alarms:
            alarm = manager.alarms[alarm_id]
            
            # 构建提醒消息
            if label:
                message = f"您设置的{label}闹钟时间到了！"
            else:
                message = f"闹钟时间到了！现在是{alarm['hour']}点{alarm['minute']}分。"
            
            # 发送提醒
            if hasattr(conn, 'websocket') and conn.websocket:
                from core.handle.sendAudioHandle import send_stt_message
                await send_stt_message(conn, message)
                
                # 将消息提交给LLM处理
                if conn.use_function_call_mode:
                    conn.executor.submit(conn.chat_with_function_calling, message)
                else:
                    conn.executor.submit(conn.chat, message)
            
            # 删除闹钟
            del manager.alarms[alarm_id]
            logger.bind(tag=TAG).info(f"闹钟 {alarm_id} 已触发: {message}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"闹钟回调出错: {e}")

def format_time_duration(seconds):
    """将秒数格式化为可读的时间段"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        if seconds == 0:
            return f"{minutes}分钟"
        return f"{minutes}分钟{seconds}秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        if minutes == 0 and seconds == 0:
            return f"{hours}小时"
        elif seconds == 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时{minutes}分钟{seconds}秒"

def format_day_text(day_offset):
    """将天数偏移格式化为可读文本"""
    if day_offset == 0:
        return "今天"
    elif day_offset == 1:
        return "明天"
    elif day_offset == 2:
        return "后天"
    else:
        return f"{day_offset}天后"

@register_function('set_timer', TIMER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def set_timer(conn, duration, response_success, response_failure, label=None):
    """设置计时器"""
    try:
        # 参数验证
        if duration <= 0:
            return ActionResponse(
                action=Action.RESPONSE,
                result="无效的持续时间",
                response="计时器的持续时间必须大于0秒。"
            )
        
        # 创建计时器
        manager = TimerAlarmManager.get_instance()
        timer_id = manager.add_timer(duration, label)
        
        # 计算结束时间的文本表示
        end_time = time.time() + duration
        end_time_str = time.strftime("%H:%M:%S", time.localtime(end_time))
        
        # 格式化持续时间
        duration_text = format_time_duration(duration)
        
        # 创建异步任务
        task = asyncio.run_coroutine_threadsafe(
            timer_callback(conn, timer_id, label),
            conn.loop
        )
        
        # 设置延迟执行
        def delayed_execution():
            time.sleep(duration)
            # 任务会在适当的时候被执行
        
        # 启动后台线程，而不阻塞当前执行
        threading.Thread(target=delayed_execution, daemon=True).start()
        
        # 保存任务引用
        manager.timers[timer_id]["task"] = task
        
        logger.bind(tag=TAG).info(f"已设置计时器: {timer_id}, 持续时间: {duration_text}, 标签: {label}")
        
        # 格式化成功响应
        response = response_success.replace("{duration}", duration_text)
        response = response.replace("{end_time}", end_time_str)
        if label:
            response = response.replace("{label}", label)
        else:
            response = response.replace("{label}", "")
            response = response.replace("{label}", "")
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"计时器已设置: {duration_text}",
            response=response
        )
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"设置计时器错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response_failure
        )

@register_function('set_alarm', ALARM_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def set_alarm(conn, hour, minute, response_success, response_failure, day_offset=0, label=None):
    """设置闹钟"""
    try:
        # 参数验证
        if not (0 <= hour <= 23):
            return ActionResponse(
                action=Action.RESPONSE,
                result="无效的小时",
                response="小时必须在0到23之间。"
            )
        
        if not (0 <= minute <= 59):
            return ActionResponse(
                action=Action.RESPONSE,
                result="无效的分钟",
                response="分钟必须在0到59之间。"
            )
        
        if day_offset < 0:
            return ActionResponse(
                action=Action.RESPONSE,
                result="无效的天数偏移",
                response="天数偏移必须大于或等于0。"
            )
        
        # 创建闹钟
        manager = TimerAlarmManager.get_instance()
        alarm_id = manager.add_alarm(hour, minute, day_offset, label)
        
        # 获取闹钟信息
        alarm = manager.alarms[alarm_id]
        time_diff = (alarm["time"] - datetime.datetime.now()).total_seconds()
        
        # 创建异步任务
        task = asyncio.run_coroutine_threadsafe(
            alarm_callback(conn, alarm_id, label),
            conn.loop
        )
        
        # 设置延迟执行
        def delayed_execution():
            time.sleep(time_diff)
            # 任务会在适当的时候被执行
        
        # 启动后台线程，而不阻塞当前执行
        threading.Thread(target=delayed_execution, daemon=True).start()
        
        # 保存任务引用
        manager.alarms[alarm_id]["task"] = task
        
        # 格式化时间表示
        time_str = f"{hour:02d}:{minute:02d}"
        day_str = format_day_text(day_offset)
        
        logger.bind(tag=TAG).info(f"已设置闹钟: {alarm_id}, 时间: {day_str} {time_str}, 标签: {label}")
        
        # 格式化成功响应
        response = response_success.replace("{time}", time_str)
        response = response.replace("{day}", day_str)
        if label:
            response = response.replace("{label}", label)
        else:
            response = response.replace("{label}", "")
            response = response.replace("{label}", "")
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"闹钟已设置: {day_str} {time_str}",
            response=response
        )
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"设置闹钟错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response_failure
        )

@register_function('check_timers_alarms', CHECK_TIMERS_ALARMS_DESC, ToolType.SYSTEM_CTL)
def check_timers_alarms(conn, check_type, response_success, response_failure):
    """查询当前的计时器和闹钟"""
    try:
        manager = TimerAlarmManager.get_instance()
        
        result = []
        summary_text = ""
        
        if check_type in ["timer", "all"]:
            # 获取所有活跃的计时器
            active_timers = manager.get_timers()
            
            if active_timers:
                timer_text = "当前计时器:\n"
                
                for i, (timer_id, timer) in enumerate(active_timers.items(), 1):
                    remaining = timer["end_time"] - time.time()
                    if remaining <= 0:
                        continue  # 跳过已过期的计时器
                        
                    remaining_text = format_time_duration(int(remaining))
                    end_time_str = time.strftime("%H:%M:%S", time.localtime(timer["end_time"]))
                    
                    label_text = f" ({timer['label']})" if timer["label"] else ""
                    timer_text += f"{i}. 剩余{remaining_text}{label_text}，将在{end_time_str}提醒\n"
                
                result.append(timer_text)
            else:
                timer_text = "没有正在进行的计时器。"
                result.append(timer_text)
            
            summary_text += f"计时器: {len(active_timers)}个 "
        
        if check_type in ["alarm", "all"]:
            # 获取所有闹钟
            alarms = manager.get_alarms()
            
            if alarms:
                alarm_text = "当前闹钟:\n"
                
                for i, (alarm_id, alarm) in enumerate(alarms.items(), 1):
                    target_time = alarm["time"]
                    now = datetime.datetime.now()
                    
                    # 计算天数差异
                    days_diff = (target_time.date() - now.date()).days
                    day_text = format_day_text(days_diff)
                    
                    time_str = f"{alarm['hour']:02d}:{alarm['minute']:02d}"
                    label_text = f" ({alarm['label']})" if alarm["label"] else ""
                    
                    alarm_text += f"{i}. {day_text} {time_str}{label_text}\n"
                
                result.append(alarm_text)
            else:
                alarm_text = "没有设置的闹钟。"
                result.append(alarm_text)
            
            summary_text += f"闹钟: {len(alarms)}个"
        
        # 组合结果
        if not result:
            return ActionResponse(
                action=Action.RESPONSE,
                result="没有找到计时器或闹钟",
                response="您当前没有设置任何计时器或闹钟。"
            )
        
        response_text = "\n\n".join(result)
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=summary_text.strip(),
            response=response_text
        )
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"查询计时器和闹钟错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response_failure
        )

@register_function('cancel_timer_alarm', CANCEL_TIMERS_ALARMS_DESC, ToolType.SYSTEM_CTL)
def cancel_timer_alarm(conn, cancel_type, response_success, response_failure, timer_id=None, alarm_id=None):
    """取消计时器或闹钟"""
    try:
        manager = TimerAlarmManager.get_instance()
        result = False
        message = ""
        
        if cancel_type in ["timer", "all"]:
            # 获取计时器状态，用于反馈信息
            active_timers = manager.get_timers()
            timer_count = len(active_timers)
            
            # 取消计时器
            result = manager.cancel_timer(timer_id)
            
            if result:
                if timer_id:
                    message += f"已取消1个计时器。"
                else:
                    message += f"已取消所有计时器，共{timer_count}个。"
            elif timer_count == 0:
                message += "没有正在进行的计时器。"
            else:
                message += f"未找到指定的计时器。"
        
        if cancel_type in ["alarm", "all"]:
            # 获取闹钟状态，用于反馈信息
            alarms = manager.get_alarms()
            alarm_count = len(alarms)
            
            # 取消闹钟
            alarm_result = manager.cancel_alarm(alarm_id)
            result = result or alarm_result
            
            if alarm_result:
                if alarm_id:
                    message += f"已取消1个闹钟。"
                else:
                    message += f"已取消所有闹钟，共{alarm_count}个。"
            elif alarm_count == 0:
                if message:
                    message += " "
                message += "没有设置的闹钟。"
            else:
                if message:
                    message += " "
                message += f"未找到指定的闹钟。"
        
        if result:
            return ActionResponse(
                action=Action.RESPONSE,
                result="取消成功",
                response=message
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="没有找到计时器或闹钟",
                response=message
            )
        
    except Exception as e:
        logger.bind(tag=TAG).error(f"取消计时器和闹钟错误: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response_failure
        )