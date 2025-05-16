from amadeus import Client, ResponseError
import requests
from bs4 import BeautifulSoup
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
import datetime
import re
import calendar
from dateutil.relativedelta import relativedelta

TAG = __name__
logger = setup_logging()

GET_FLIGHTS_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "get_flights",
        "description": (
            "查询航班信息，用户应提供出发城市、到达城市和日期。"
            "例如用户说'查询从深圳到北京2025年4月1日的航班'，"
            "参数为：depart_city='深圳', arrival_city='北京', date='2025-04-01'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "depart_city": {
                    "type": "string",
                    "description": "出发城市名称，例如深圳、上海、北京等"
                },
                "arrival_city": {
                    "type": "string",
                    "description": "到达城市名称，例如深圳、上海、北京等"
                },
                "date": {
                    "type": "string",
                    "description": "出发日期。重要：对于相对日期表述，请直接传入原始词汇（如'today'、'tomorrow'、'next week'、'next month'等），不要将其转换为具体日期格式。函数内部会自动处理相对日期的解析和转换。。"
                },
                "lang": {
                    "type": "string",
                    "description": "返回用户使用的语言code，例如zh_CN/zh_HK/en_US/ja_JP等，默认zh_CN"
                }
            },
            "required": ["depart_city", "arrival_city", "date", "lang"]
        }
    }
}

# 城市名称到IATA代码的映射，添加中英文映射
CITY_TO_IATA = {
    "北京": "PEK",
    "上海": "SHA",
    "广州": "CAN",
    "深圳": "SZX",
    "成都": "CTU",
    "杭州": "HGH",
    "西安": "XIY",
    "重庆": "CKG",
    "南京": "NKG",
    "武汉": "WUH",
    "青岛": "TAO",
    "厦门": "XMN",
    "昆明": "KMG",
    "天津": "TSN",
    "大连": "DLC",
    "长沙": "CSX",
    "海口": "HAK",
    "三亚": "SYX",
    "哈尔滨": "HRB",
    "长春": "CGQ",
    "宜春": "YIC",  # Yichun Airport code
    # 添加英文映射
    "Beijing": "PEK",
    "Shanghai": "SHA",
    "Guangzhou": "CAN",
    "Shenzhen": "SZX",
    "Chengdu": "CTU",
    "Hangzhou": "HGH",
    "Xian": "XIY",
    "Chongqing": "CKG",
    "Nanjing": "NKG",
    "Wuhan": "WUH",
    "Qingdao": "TAO",
    "Xiamen": "XMN",
    "Kunming": "KMG",
    "Tianjin": "TSN",
    "Dalian": "DLC",
    "Changsha": "CSX",
    "Haikou": "HAK",
    "Sanya": "SYX",
    "Harbin": "HRB",
    "Changchun": "CGQ"
}

# 英文月份名称到数字的映射
MONTH_NAME_TO_NUMBER = {
    'january': 1, 'jan': 1,
    'february': 2, 'feb': 2,
    'march': 3, 'mar': 3,
    'april': 4, 'apr': 4,
    'may': 5,
    'june': 6, 'jun': 6,
    'july': 7, 'jul': 7,
    'august': 8, 'aug': 8,
    'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10,
    'november': 11, 'nov': 11,
    'december': 12, 'dec': 12
}

# 中文月份名称到数字的映射
CHINESE_MONTH_TO_NUMBER = {
    '一月': 1, '1月': 1,
    '二月': 2, '2月': 2,
    '三月': 3, '3月': 3,
    '四月': 4, '4月': 4,
    '五月': 5, '5月': 5,
    '六月': 6, '6月': 6,
    '七月': 7, '7月': 7,
    '八月': 8, '8月': 8,
    '九月': 9, '9月': 9,
    '十月': 10, '10月': 10,
    '十一月': 11, '11月': 11,
    '十二月': 12, '12月': 12
}

# 中文和英文星期名称到数字的映射 (0 = 周一, 6 = 周日)
WEEKDAY_TO_NUMBER = {
    'monday': 0, 'mon': 0, '周一': 0, '星期一': 0, '礼拜一': 0,
    'tuesday': 1, 'tue': 1, '周二': 1, '星期二': 1, '礼拜二': 1,
    'wednesday': 2, 'wed': 2, '周三': 2, '星期三': 2, '礼拜三': 2,
    'thursday': 3, 'thu': 3, '周四': 3, '星期四': 3, '礼拜四': 3,
    'friday': 4, 'fri': 4, '周五': 4, '星期五': 4, '礼拜五': 4,
    'saturday': 5, 'sat': 5, '周六': 5, '星期六': 5, '礼拜六': 5,
    'sunday': 6, 'sun': 6, '周日': 6, '周天': 6, '星期日': 6, '星期天': 6, '礼拜日': 6, '礼拜天': 6
}

def is_valid_date_format(date_str):
    """检查日期是否符合YYYY-MM-DD格式"""
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def parse_date_reference(date_str):
    """
    Parse various date expressions including relative dates, specific dates and vague expressions
    
    Args:
        date_str: Date string expression
        
    Returns:
        YYYY-MM-DD formatted date string
    """
    # Get current date/time directly from system clock
    today = datetime.datetime.now()
    
    # Log the input and current date
    logger.bind(tag=TAG).info(f"Parsing date reference: '{date_str}', current date: {today.strftime('%Y-%m-%d')}")
    
    if not date_str or not isinstance(date_str, str):
        result = today.strftime('%Y-%m-%d')
        logger.bind(tag=TAG).info(f"Empty or invalid date string, using today: {result}")
        return result
    
    # Clean up the date string
    date_str = date_str.lower().strip()
    
    # If already in YYYY-MM-DD format, return directly
    if is_valid_date_format(date_str):
        logger.bind(tag=TAG).info(f"Date already in valid format: {date_str}")
        return date_str
    
    # 1. Handle clear relative dates like "today", "tomorrow"
    if date_str in ('today', 'today\'s', 'tonight', '今天', '今日', '当天', '现在', '本日'):
        result = today.strftime('%Y-%m-%d')
        logger.bind(tag=TAG).info(f"Parsed 'today': {result}")
        return result
    
    if date_str in ('tomorrow', 'next day', '明天', '明日', '次日'):
        tomorrow = today + datetime.timedelta(days=1)
        result = tomorrow.strftime('%Y-%m-%d')
        logger.bind(tag=TAG).info(f"Parsed 'tomorrow': {result}")
        return result
        
    # Continue with other date parsing logic...
    
    # If unable to parse, default to today's date
    logger.bind(tag=TAG).warning(f"Unable to parse date: '{date_str}', defaulting to today")
    return today.strftime('%Y-%m-%d')

def convert_chinese_number(cn_num):
    """将中文数字转换为阿拉伯数字"""
    cn_to_arabic = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'
    }
    # 简单转换，只处理基本数字
    if cn_num in cn_to_arabic:
        return cn_to_arabic[cn_num]
    return cn_num  # 如果无法转换，返回原始字符串

def get_city_code(amadeus, city_name):
    """
    Convert a city name to its IATA code using Amadeus API
    """
    try:
        # First check our local mapping
        if city_name in CITY_TO_IATA:
            logger.bind(tag=TAG).info(f"Found IATA code {CITY_TO_IATA[city_name]} for city: {city_name} in local mapping")
            return CITY_TO_IATA[city_name]
        
        # Use the Airport and City Search API to find the IATA code
        response = amadeus.reference_data.locations.get(
            keyword=city_name,
            subType='CITY',
            page={'limit': 1}
        )
        
        # Check if we got any results
        if response.data and len(response.data) > 0:
            # Return the IATA code of the first result
            logger.bind(tag=TAG).info(f"Found IATA code {response.data[0]['iataCode']} for city: {city_name}")
            return response.data[0]['iataCode']
        else:
            logger.bind(tag=TAG).warning(f"No IATA code found for city: {city_name}")
            return None
            
    except ResponseError as error:
        logger.bind(tag=TAG).error(f"Error looking up city code for {city_name}: {error}")
        # Fallback to our local mapping
        return CITY_TO_IATA.get(city_name)
    except Exception as error:
        logger.bind(tag=TAG).error(f"Unexpected error looking up city code for {city_name}: {error}")
        # Fallback to our local mapping
        return CITY_TO_IATA.get(city_name)

def search_flights(amadeus, depart_city, arrival_city, date):
    """
    Search for flights using the Amadeus API
    """
    try:
        # First, convert city names to IATA codes
        depart_code = get_city_code(amadeus, depart_city)
        arrival_code = get_city_code(amadeus, arrival_city)
        
        if not depart_code:
            logger.bind(tag=TAG).error(f"Could not find IATA code for departure city: {depart_city}")
            return None
        
        if not arrival_code:
            logger.bind(tag=TAG).error(f"Could not find IATA code for arrival city: {arrival_city}")
            return None
        
        logger.bind(tag=TAG).info(f"Searching flights from {depart_city} ({depart_code}) to {arrival_city} ({arrival_code}) on {date}")
        
        # Search for flights using the codes
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode=depart_code,
            destinationLocationCode=arrival_code,
            departureDate=date,
            adults=1)
        
        return response.data
        
    except ResponseError as error:
        logger.bind(tag=TAG).error(f"Amadeus API error: {error}")
        return None
    except Exception as error:
        logger.bind(tag=TAG).error(f"Unexpected error in flight search: {error}")
        return None


def format_amadeus_flights(flights_data):
    """
    Format Amadeus API flight data into a more user-friendly format
    """
    formatted_flights = []
    
    for flight in flights_data:
        for itinerary in flight.get('itineraries', []):
            for segment in itinerary.get('segments', []):
                # Extract basic flight info
                airline_code = segment.get('carrierCode', '')
                flight_number = segment.get('number', '')
                
                # Get departure and arrival info
                departure = segment.get('departure', {})
                arrival = segment.get('arrival', {})
                
                # Calculate duration
                dep_time = departure.get('at', '').replace('T', ' ')
                arr_time = arrival.get('at', '').replace('T', ' ')
                
                # Format price
                price_info = flight.get('price', {})
                price = price_info.get('total', '0')
                currency = price_info.get('currency', 'RMB')
                
                # Create formatted flight entry
                formatted_flight = {
                    "id": flight.get('id', ''),
                    "flight_number": f"{airline_code}{flight_number}",
                    "airline": airline_code,  # Would need a mapping for full names
                    "departure": {
                        "airport": departure.get('iataCode', ''),
                        "terminal": departure.get('terminal', ''),
                        "time": departure.get('at', '')
                    },
                    "arrival": {
                        "airport": arrival.get('iataCode', ''),
                        "terminal": arrival.get('terminal', ''),
                        "time": arrival.get('at', '')
                    },
                    "duration": itinerary.get('duration', '').replace('PT', '').replace('H', '小时').replace('M', '分钟'),
                    "price": price,
                    "currency": currency,
                    "cabin_class": "经济舱",  # Default, would need mapping from actual data
                    "available_seats": "有座"  # Not usually provided in search results
                }
                
                formatted_flights.append(formatted_flight)
    
    return formatted_flights

@register_function('get_flights', GET_FLIGHTS_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def get_flights(conn, depart_city: str, arrival_city: str, date: str, lang: str = "zh_CN"):
    """
    获取航班信息并返回结果
    """
    logger.bind(tag=TAG).info(f"查询航班: 从{depart_city}到{arrival_city}，原始日期输入: {date}")
    
    try:
        # 处理相对日期表达式和各种日期格式
        parsed_date = parse_date_reference(date)
        if parsed_date != date:
            logger.bind(tag=TAG).info(f"日期解析结果: {date} -> {parsed_date}")
            date = parsed_date
        
        # 创建Amadeus客户端
        amadeus = Client(
            client_id='HqFGdl17R2phv5GZG3OCM7PAzxzBWzus',
            client_secret='dNRuGYdDzL9BBOZQ'
        )
        
        # 获取城市代码
        depart_code = get_city_code(amadeus, depart_city)
        arrival_code = get_city_code(amadeus, arrival_city)
        
        # 检查城市代码是否存在
        if not depart_code:
            error_message = f"无法找到出发城市({depart_city})的代码，请确认城市名称是否正确。"
            english_message = f"Could not find the code for departure city ({depart_city}). Please check if the city name is correct."
            
            # 根据语言返回相应消息
            if lang.startswith("zh"):
                return ActionResponse(Action.RESPONSE, error_message, error_message)
            else:
                return ActionResponse(Action.RESPONSE, english_message, english_message)
        
        if not arrival_code:
            error_message = f"无法找到到达城市({arrival_city})的代码，请确认城市名称是否正确。"
            english_message = f"Could not find the code for arrival city ({arrival_city}). Please check if the city name is correct."
            
            # 根据语言返回相应消息
            if lang.startswith("zh"):
                return ActionResponse(Action.RESPONSE, error_message, error_message)
            else:
                return ActionResponse(Action.RESPONSE, english_message, english_message)
        
        # 尝试使用Amadeus API获取航班信息
        logger.bind(tag=TAG).info(f"Searching flights from {depart_city} ({depart_code}) to {arrival_city} ({arrival_code}) on {date}")
        
        try:
            flights_data = amadeus.shopping.flight_offers_search.get(
                originLocationCode=depart_code,
                destinationLocationCode=arrival_code,
                departureDate=date,
                adults=1
            ).data
            
            # 检查是否有结果
            if flights_data and len(flights_data) > 0:
                logger.bind(tag=TAG).info(f"找到{len(flights_data)}个航班选项")
                flights = format_amadeus_flights(flights_data)
            else:
                # 没有找到航班，返回提示信息
                logger.bind(tag=TAG).warning("API返回了结果，但没有找到任何航班")
                error_message = f"未找到从{depart_city}到{arrival_city}在{date}的航班信息。可能是该航线不存在或该日期没有航班。"
                english_message = f"No flights found from {depart_city} to {arrival_city} on {date}. This route may not exist or there may be no flights on this date."
                
                if lang.startswith("zh"):
                    return ActionResponse(Action.RESPONSE, error_message, error_message)
                else:
                    return ActionResponse(Action.RESPONSE, english_message, english_message)
        
        except ResponseError as e:
            # 处理API错误
            logger.bind(tag=TAG).error(f"Amadeus API error: {e}")
            error_message = f"查询航班时发生API错误：未找到从{depart_city}到{arrival_city}在{date}的航班信息。可能是该航线不存在或该日期没有航班。"
            english_message = f"API error while searching for flights: Could not find flight information from {depart_city} to {arrival_city} on {date}."
            
            if lang.startswith("zh"):
                return ActionResponse(Action.RESPONSE, error_message, error_message)
            else:
                return ActionResponse(Action.RESPONSE, english_message, english_message)
            
    except Exception as e:
        # 处理其他异常
        logger.bind(tag=TAG).error(f"查询航班信息时发生异常: {e}")
        error_message = f"查询航班信息时发生错误: {str(e)}"
        english_message = f"Error occurred while querying flight information: {str(e)}"
        
        if lang.startswith("zh"):
            return ActionResponse(Action.RESPONSE, error_message, error_message)
        else:
            return ActionResponse(Action.RESPONSE, english_message, english_message)
    
    # 如果执行到这里，说明有航班数据可用
    # 格式化航班信息作为响应
    if lang.startswith("zh"):
        flight_report = f"根据下列数据，用{lang}回应用户的航班查询请求：\n\n"
        flight_report += f"从{depart_city}到{arrival_city}在{date}的航班信息：\n\n"
    else:
        flight_report = f"Based on the following data, respond to the user's flight query in {lang}:\n\n"
        flight_report += f"Flight information from {depart_city} to {arrival_city} on {date}:\n\n"
    
    for i, flight in enumerate(flights[:5], 1):  # 限制为前5个航班
        dep_time = flight["departure"]["time"].split("T")[1][:5] if "T" in flight["departure"]["time"] else flight["departure"]["time"][-5:]
        arr_time = flight["arrival"]["time"].split("T")[1][:5] if "T" in flight["arrival"]["time"] else flight["arrival"]["time"][-5:]
        
        if lang.startswith("zh"):
            flight_report += (
                f"航班{i}：\n"
                f"航空公司：{flight['airline']}\n"
                f"航班号：{flight['flight_number']}\n"
                f"起飞时间：{dep_time}\n"
                f"到达时间：{arr_time}\n"
                f"飞行时间：{flight['duration']}\n"
                f"价格：{flight['price']} {flight['currency']}\n"
            )
            if "available_seats" in flight and flight["available_seats"] != "有座":
                flight_report += f"可用座位数：{flight['available_seats']}\n"
        else:
            flight_report += (
                f"Flight {i}:\n"
                f"Airline: {flight['airline']}\n"
                f"Flight Number: {flight['flight_number']}\n"
                f"Departure Time: {dep_time}\n"
                f"Arrival Time: {arr_time}\n"
                f"Duration: {flight['duration']}\n"
                f"Price: {flight['price']} {flight['currency']}\n"
            )
            if "available_seats" in flight and flight["available_seats"] != "有座":
                flight_report += f"Available Seats: {flight['available_seats']}\n"
        
        flight_report += "\n"
    
    if lang.startswith("zh"):
        flight_report += (
            f"(请根据用户需求提供航班信息的摘要，关注起飞时间、价格和航空公司等关键信息。"
            f"如果用户想了解具体某个航班的详情，可以提供该航班的所有信息。"
            f"如果有特价或推荐航班，可以特别指出。只推荐1-2个最优选择，突出关键要素如起飞时间、价格。)"
        )
    else:
        flight_report += (
            f"(Please provide a summary of flight information based on the user's needs, focusing on key information such as departure time, price, and airline. "
            f"Only recommend 1-2 best options, highlighting key elements like departure time and price. "
            f"If the user wants to know the details of a specific flight, you can provide all the information for that flight. "
            f"If there are special offers or recommended flights, please highlight them.)"
        )
    
    return ActionResponse(Action.REQLLM, flight_report, None)