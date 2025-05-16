from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
import hashlib
import json
import requests
import time
from typing import Dict, Any

TAG = __name__
logger = setup_logging()

# Function description for xiaozhi function calling
KUAIDI100_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "kuaidi100_tracking",
        "description": "查询快递物流信息，根据快递单号和快递公司查询快递的详细运输轨迹。",
        "parameters": {
            "type": "object",
            "properties": {
                "tracking_number": {
                    "type": "string",
                    "description": "快递单号，例如：YT9693083639795"
                },
                "company": {
                    "type": "string",
                    "description": "快递公司代码，例如：'yuantong'代表圆通，'shunfeng'代表顺丰，其他常用公司代码：'zhongtong'(中通),'yunda'(韵达),'jd'(京东),'ems'(EMS)"
                },
                "phone": {
                    "type": "string",
                    "description": "收件人或寄件人手机号后四位，用于提高查询精度，可选"
                },
                "response_success": {
                    "type": "string",
                    "description": "成功查询到快递信息时的友好回复，例如：'这是您的{company_name}快递(单号{tracking_number})的最新跟踪信息'"
                },
                "response_failure": {
                    "type": "string",
                    "description": "查询失败时的友好回复，例如：'抱歉，我无法查询到这个快递信息'"
                }
            },
            "required": ["tracking_number", "company", "response_success", "response_failure"]
        }
    }
}

# 快递公司代码到中文名的映射
COMPANY_MAP = {
    'yuantong': '圆通速递',
    'shunfeng': '顺丰速运',
    'zhongtong': '中通快递',
    'yunda': '韵达快递',
    'jd': '京东物流',
    'ems': 'EMS',
    'shentong': '申通快递',
    'youzhengguonei': '邮政包裹',
    'tiantian': '天天快递',
    'guotongkuaidi': '国通快递',
    'debangwuliu': '德邦物流',
    'huitongkuaidi': '百世快递',
}

# 状态码映射
STATE_MAP = {
    '0': '在途中',
    '1': '已揽收',
    '2': '疑难',
    '3': '已签收',
    '4': '退签',
    '5': '派送中',
    '6': '退回',
    '7': '转单',
    '8': '清关',
    '9': '待清关',
    '10': '待揽收',
    '11': '已停运',
    '12': '已取消'
}

class Kuaidi100Client:
    def __init__(self, key, customer):
        self.key = key
        self.customer = customer
        self.url = 'https://poll.kuaidi100.com/poll/query.do'
    
    def track(self, com, num, phone='', ship_from='', ship_to=''):
        param = {
            'com': com,
            'num': num,
            'phone': phone,
            'from': ship_from,
            'to': ship_to,
            'resultv2': '1',
            'show': '0',
            'order': 'desc'
        }
        
        param_str = json.dumps(param)
        
        # 签名加密
        temp_sign = param_str + self.key + self.customer
        md = hashlib.md5()
        md.update(temp_sign.encode())
        sign = md.hexdigest().upper()
        
        request_data = {
            'customer': self.customer,
            'param': param_str,
            'sign': sign
        }
        
        # 添加日志
        logger.bind(tag=TAG).info(f"请求快递100 API: {self.url}")
        logger.bind(tag=TAG).debug(f"请求参数: {request_data}")
        
        try:
            response = requests.post(self.url, request_data, timeout=10)
            response.raise_for_status()  # 检查HTTP错误
            result = response.json()
            logger.bind(tag=TAG).info(f"快递100 API响应: 状态={result.get('status')}, 消息={result.get('message')}")
            return result
        except requests.exceptions.RequestException as e:
            logger.bind(tag=TAG).error(f"快递100 API请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.bind(tag=TAG).error(f"解析快递100 API响应失败: {e}, 原始响应: {response.text}")
            raise

def get_company_name(code):
    """获取快递公司中文名"""
    return COMPANY_MAP.get(code, code)

def get_state_desc(state):
    """获取状态描述"""
    return STATE_MAP.get(state, f"未知状态({state})")

def format_response(template: str, **kwargs) -> str:
    """格式化响应，替换模板中的变量"""
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        template = template.replace(placeholder, str(value))
    return template

@register_function('kuaidi100_tracking', KUAIDI100_FUNCTION_DESC, ToolType.WAIT)
def kuaidi100_tracking(tracking_number, company, response_success, response_failure, phone=''):
    """
    快递100物流查询
    
    Args:
        tracking_number: 快递单号
        company: 快递公司代码
        response_success: 成功时的响应模板
        response_failure: 失败时的响应模板
        phone: 收件人或寄件人手机号后四位(可选)
        
    Returns:
        ActionResponse: 包含查询结果的响应
    """
    logger.bind(tag=TAG).info(f"开始查询快递: 公司={company}, 单号={tracking_number}, 手机={phone}")
    
    try:
        # 使用你的API凭证 (注意: 实际使用中应当从配置文件读取而不是硬编码)
        key = "IOMHASQf7643"
        customer = "2741380CF5EDF6CFE4670BF9"
        
        client = Kuaidi100Client(key, customer)
        company_name = get_company_name(company)
        
        # 尝试查询快递
        result = client.track(
            com=company,
            num=tracking_number,
            phone=phone
        )
        
        # 检查是否查询成功
        if result.get('message') == 'ok' and result.get('status') == '200':
            # 提取和格式化物流信息
            state = result.get('state', '')
            state_desc = get_state_desc(state)
            
            tracking_info = f"快递查询结果 - {company_name}（{tracking_number}）\n"
            tracking_info += f"当前状态：{state_desc}\n\n"
            tracking_info += "物流轨迹：\n"
            
            # 添加物流轨迹
            data = result.get('data', [])
            latest_info = ""
            if not data:
                tracking_info += "暂无物流信息\n"
                latest_info = "暂无物流信息"
            else:
                for i, item in enumerate(data, 1):
                    time_str = item.get('time', '')
                    context = item.get('context', '')
                    location = item.get('location', '')
                    
                    entry = f"{i}. {time_str}"
                    if location:
                        entry += f" [{location}]"
                    entry += f"：{context}\n"
                    
                    tracking_info += entry
                    
                    # 记录最新的物流信息(第一条)
                    if i == 1:
                        latest_time = time_str
                        latest_status = context
                        latest_location = f"[{location}]" if location else ""
                        latest_info = f"{latest_time} {latest_location}：{latest_status}"
            
            # 添加数据更新时间
            update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            tracking_info += f"\n数据更新时间：{update_time}"
            
            logger.bind(tag=TAG).info(f"快递查询成功: {company_name}({tracking_number}), 状态={state_desc}")
            
            # 格式化成功响应
            response = format_response(
                response_success,
                company_name=company_name,
                tracking_number=tracking_number,
                status=state_desc,
                latest=latest_info,
                update_time=update_time
            )
            
            return ActionResponse(
                action=Action.REQLLM,
                result=tracking_info,
                response=response
            )
        else:
            # 查询失败
            error_msg = result.get('message', '未知错误')
            error_code = result.get('status', 'unknown')
            
            logger.bind(tag=TAG).warning(f"快递查询失败: 代码={error_code}, 消息={error_msg}")
            
            # 根据错误类型给出不同提示
            if "单号不存在" in error_msg or "单号错误" in error_msg:
                failure_reason = f"未能找到该快递信息，请检查您输入的快递单号({tracking_number})是否正确"
            elif "快递公司" in error_msg:
                failure_reason = f"快递公司代码({company})可能不正确，请尝试其他快递公司代码"
            else:
                failure_reason = f"查询时遇到问题：{error_msg}"
            
            # 格式化失败响应
            response = format_response(
                response_failure,
                company_name=company_name,
                tracking_number=tracking_number,
                reason=failure_reason
            )
            
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"查询失败: 代码={error_code}, 消息={error_msg}",
                response=response
            )
    except Exception as e:
        # 处理其他异常
        logger.bind(tag=TAG).error(f"查询快递信息时发生异常: {e}")
        
        # 格式化失败响应
        company_name = get_company_name(company)
        response = format_response(
            response_failure,
            company_name=company_name,
            tracking_number=tracking_number,
            reason="系统错误，请稍后再试"
        )
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response
        )