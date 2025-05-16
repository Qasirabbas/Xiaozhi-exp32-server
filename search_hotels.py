from amadeus import Client, ResponseError
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
import datetime
import json

TAG = __name__
logger = setup_logging()

# Function description for xiaozhi function calling
HOTEL_SEARCH_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "search_hotels",
        "description": "搜索指定城市的酒店信息，包括价格、评分和基本设施。可以指定日期和价格范围。",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称，如'北京'、'上海'、'广州'、'深圳'等"
                },
                "check_in": {
                    "type": "string",
                    "description": "出发日期，可以是'tomorrow'/'today'等相对日期术语或YYYY-MM-DD格式的具体日期。函数将自动解析相对日期。例如传入'tomorrow'而不是转换后的日期。"
                },
                "check_out": {
                    "type": "string",
                    "description": "退房日期，格式为YYYY-MM-DD，例如'2025-04-18'"
                },
                "adults": {
                    "type": "integer",
                    "description": "成人人数，默认为1"
                },
                "price_range": {
                    "type": "string",
                    "description": "价格范围，格式为'最低价格-最高价格'，例如'300-1000'，单位为人民币，可选参数"
                },
                "lang": {
                    "type": "string",
                    "description": "返回语言，如'zh-CN'表示中文，'en-US'表示英文，默认为'zh-CN'"
                },
                "response_success": {
                    "type": "string",
                    "description": "搜索成功时的友好回复，例如'以下是{city}的酒店信息，共找到{count}家酒店'"
                },
                "response_failure": {
                    "type": "string",
                    "description": "搜索失败时的友好回复，例如'抱歉，无法找到{city}的酒店信息'"
                }
            },
            "required": ["city", "check_in", "check_out", "response_success", "response_failure"]
        }
    }
}

# 城市名称到IATA代码的映射
CITY_TO_IATA = {
    "北京": "BJS",
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
    # 英文名称
    "Beijing": "BJS",
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

def get_city_code(amadeus, city_name):
    """获取城市代码"""
    # 首先检查本地映射
    if city_name in CITY_TO_IATA:
        logger.bind(tag=TAG).info(f"Found IATA code {CITY_TO_IATA[city_name]} for city: {city_name} in local mapping")
        return CITY_TO_IATA[city_name]
    
    try:
        # 使用Amadeus API查询城市代码
        response = amadeus.reference_data.locations.get(
            keyword=city_name,
            subType='CITY',
            page={'limit': 1}
        )
        
        # 检查是否有结果
        if response.data and len(response.data) > 0:
            logger.bind(tag=TAG).info(f"Found IATA code {response.data[0]['iataCode']} for city: {city_name}")
            return response.data[0]['iataCode']
        else:
            logger.bind(tag=TAG).warning(f"No IATA code found for city: {city_name}")
            return None
    except Exception as e:
        logger.bind(tag=TAG).error(f"Error getting city code: {e}")
        return None

def search_hotels(amadeus, city_code, check_in, check_out, adults=1, price_range=None):
    """搜索酒店信息"""
    try:
        # 基本请求参数
        params = {
            'cityCode': city_code,
            'checkInDate': check_in,
            'checkOutDate': check_out,
            'adults': adults,
            'includeClosed': False,
            'bestRateOnly': True,
            'view': 'FULL',
            'sort': 'PRICE'
        }
        
        # 处理价格范围
        if price_range:
            try:
                min_price, max_price = price_range.split('-')
                params['priceRange'] = f"{min_price}-{max_price}"
            except ValueError:
                logger.bind(tag=TAG).warning(f"Invalid price range format: {price_range}, should be 'min-max'")
        
        # 搜索酒店
        logger.bind(tag=TAG).info(f"Searching hotels in {city_code} from {check_in} to {check_out}")
        response = amadeus.shopping.hotel_offers_search.get(**params)
        return response.data
    except ResponseError as e:
        logger.bind(tag=TAG).error(f"Amadeus API error: {e}")
        return None
    except Exception as e:
        logger.bind(tag=TAG).error(f"Error searching hotels: {e}")
        return None

def generate_mock_hotels(city, check_in, check_out, adults=1, count=5):
    """生成模拟酒店数据（当API调用失败时使用）"""
    hotels = []
    hotel_names = {
        "北京": ["北京国际饭店", "北京希尔顿酒店", "北京丽思卡尔顿酒店", "北京香格里拉酒店", "北京万豪酒店"],
        "上海": ["上海和平饭店", "上海外滩茂悦大酒店", "上海半岛酒店", "上海浦东香格里拉大酒店", "上海四季酒店"],
        "广州": ["广州白天鹅宾馆", "广州香格里拉大酒店", "广州富力丽思卡尔顿酒店", "广州文华东方酒店", "广州W酒店"],
        "深圳": ["深圳大梅沙京基喜来登度假酒店", "深圳福田香格里拉大酒店", "深圳湾万怡酒店", "深圳四季酒店", "深圳华侨城洲际大酒店"]
    }
    
    # 确保有适当的酒店名称列表
    if city not in hotel_names:
        if "Beijing" in city:
            city_key = "北京"
        elif "Shanghai" in city:
            city_key = "上海"
        elif "Guangzhou" in city:
            city_key = "广州"
        elif "Shenzhen" in city:
            city_key = "深圳"
        else:
            city_key = list(hotel_names.keys())[0]  # 默认使用第一个城市
    else:
        city_key = city
    
    for i in range(min(count, len(hotel_names.get(city_key, ["酒店"]*5)))):
        # 生成模拟价格
        base_price = 500 + (i * 150)
        total_price = base_price * ((datetime.datetime.fromisoformat(check_out) - 
                                    datetime.datetime.fromisoformat(check_in)).days)
        
        hotel = {
            "name": hotel_names.get(city_key, ["酒店"]*5)[i],
            "rating": min(5, 3.5 + (i * 0.3)),
            "price": {
                "base": base_price,
                "total": total_price,
                "currency": "CNY"
            },
            "address": {
                "city": city,
                "district": f"{city}区{i+1}号",
                "street": f"{city}大道{(i+1)*100}号"
            },
            "amenities": ["Wi-Fi", "空调", "停车场", "健身中心", "餐厅"],
            "distance_to_center": f"{i+1}.{i*2} 公里",
            "available_rooms": 5 - i,
        }
        
        hotels.append(hotel)
        
    return hotels

def format_hotel_data(hotels_data, city, check_in, check_out, lang="zh-CN"):
    """将API返回的酒店数据格式化为易于阅读的格式"""
    formatted_hotels = []
    
    if not hotels_data:
        return formatted_hotels
    
    for hotel in hotels_data:
        try:
            hotel_info = {}
            
            # 从API响应中提取酒店信息
            if "hotel" in hotel:
                hotel_info["name"] = hotel["hotel"].get("name", "未知酒店")
                hotel_info["rating"] = hotel["hotel"].get("rating", "无评分")
                
                # 地址信息
                address = hotel["hotel"].get("address", {})
                hotel_info["address"] = {
                    "city": address.get("cityName", city),
                    "district": address.get("lines", [""])[0] if "lines" in address and address["lines"] else "",
                    "street": address.get("postalCode", "")
                }
                
                # 设施信息
                amenities = []
                for facility in hotel["hotel"].get("amenities", []):
                    amenities.append(facility)
                hotel_info["amenities"] = amenities[:5] if amenities else ["信息不详"]
            
            # 价格信息
            if "offers" in hotel and hotel["offers"]:
                offer = hotel["offers"][0]
                hotel_info["price"] = {
                    "base": offer.get("price", {}).get("base", "价格不详"),
                    "total": offer.get("price", {}).get("total", "价格不详"),
                    "currency": offer.get("price", {}).get("currency", "CNY")
                }
                hotel_info["available_rooms"] = 1  # API通常不直接提供可用房间数
            
            formatted_hotels.append(hotel_info)
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error formatting hotel data: {e}")
            continue
    
    return formatted_hotels

def format_response(template, **kwargs):
    """格式化响应，替换模板中的变量"""
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        template = template.replace(placeholder, str(value))
    return template

@register_function('search_hotels', HOTEL_SEARCH_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def search_hotels_function(conn, city, check_in, check_out, adults=1, price_range=None, lang="zh_CN", 
                         response_success=None, response_failure=None):
    """
    搜索酒店信息的函数
    
    Args:
        conn: 连接对象
        city: 城市名称
        check_in: 入住日期
        check_out: 退房日期
        adults: 成人人数
        price_range: 价格范围
        lang: 返回语言
        response_success: 成功时的响应模板
        response_failure: 失败时的响应模板
    
    Returns:
        ActionResponse: 包含查询结果的响应
    """
    logger.bind(tag=TAG).info(f"开始搜索酒店: 城市={city}, 入住={check_in}, 退房={check_out}, 人数={adults}")
    
    try:
        # 处理相对日期表达，比如"tomorrow"、"明天"等
        today = datetime.datetime.now()
        
        # 处理入住日期
        if check_in in ('today', 'today\'s', '今天', '今日'):
            check_in_date = today
        elif check_in in ('tomorrow', '明天', '明日'):
            check_in_date = today + datetime.timedelta(days=1)
        elif check_in in ('next day', '后天', '后日'):
            check_in_date = today + datetime.timedelta(days=2)
        else:
            # 尝试解析具体的日期格式
            try:
                check_in_date = datetime.datetime.strptime(check_in, '%Y-%m-%d')
            except ValueError:
                error_msg = "日期格式不正确，应为YYYY-MM-DD"
                logger.bind(tag=TAG).warning(error_msg)
                return ActionResponse(
                    action=Action.RESPONSE,
                    result=error_msg,
                    response=format_response(response_failure, city=city, reason=error_msg)
                )
        
        # 格式化入住日期为字符串
        check_in_str = check_in_date.strftime('%Y-%m-%d')
        
        # 处理退房日期
        if check_out in ('today', 'today\'s', '今天', '今日'):
            check_out_date = today
        elif check_out in ('tomorrow', '明天', '明日'):
            check_out_date = today + datetime.timedelta(days=1)
        elif check_out in ('next day', '后天', '后日'):
            check_out_date = today + datetime.timedelta(days=2)
        else:
            # 尝试解析具体的日期格式
            try:
                check_out_date = datetime.datetime.strptime(check_out, '%Y-%m-%d')
            except ValueError:
                # 如果退房日期无效，则默认设置为入住日期后的第二天
                check_out_date = check_in_date + datetime.timedelta(days=1)
                logger.bind(tag=TAG).warning(f"退房日期格式不正确，默认设置为入住日期后的第二天: {check_out_date.strftime('%Y-%m-%d')}")
        
        # 格式化退房日期为字符串
        check_out_str = check_out_date.strftime('%Y-%m-%d')
        
        # 确保退房日期晚于入住日期
        if check_out_date <= check_in_date:
            check_out_date = check_in_date + datetime.timedelta(days=1)
            check_out_str = check_out_date.strftime('%Y-%m-%d')
            logger.bind(tag=TAG).warning(f"退房日期不能早于或等于入住日期，已调整为: {check_out_str}")
        
        # 检查日期是否在过去
        if check_in_date < today.replace(hour=0, minute=0, second=0, microsecond=0):
            error_msg = f"入住日期({check_in_str})不能早于今天"
            logger.bind(tag=TAG).warning(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result=error_msg,
                response=format_response(response_failure, city=city, reason=error_msg)
            )
        
        # 创建Amadeus客户端
        amadeus = Client(
            client_id='52MdnjM6nfPg80bGsejdch6JdSLbsRXG',
            client_secret='sx4Ruyec4Z796FGE'
        )
        
        # 获取城市代码
        city_code = get_city_code(amadeus, city)
        if not city_code:
            error_msg = f"无法获取城市({city})的代码"
            logger.bind(tag=TAG).warning(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result=error_msg,
                response=format_response(response_failure, city=city, reason=error_msg)
            )
        
        # 搜索酒店
        hotels_data = search_hotels(amadeus, city_code, check_in_str, check_out_str, adults, price_range)
        
        # 处理没有找到酒店的情况
        if not hotels_data:
            error_msg = f"在{city}没有找到符合条件的酒店"
            logger.bind(tag=TAG).warning(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result=error_msg,
                response=format_response(response_failure, city=city, reason=error_msg)
            )
        
        # 格式化酒店数据
        hotels = format_hotel_data(hotels_data, city, check_in_str, check_out_str, lang)
        
        # 处理没有找到酒店的情况（二次检查）
        if not hotels:
            error_msg = f"在{city}没有找到符合条件的酒店"
            logger.bind(tag=TAG).warning(error_msg)
            return ActionResponse(
                action=Action.RESPONSE,
                result=error_msg,
                response=format_response(response_failure, city=city, reason=error_msg)
            )
        
        # 构建酒店信息报告
        if lang.startswith("zh"):
            hotel_report = f"在{city}找到{len(hotels)}家酒店，入住日期{check_in_str}，退房日期{check_out_str}：\n\n"
        else:
            hotel_report = f"Found {len(hotels)} hotels in {city}, check-in {check_in_str}, check-out {check_out_str}:\n\n"
        
        # 添加酒店详细信息
        for i, hotel in enumerate(hotels[:5], 1):  # 限制为前5家酒店
            if lang.startswith("zh"):
                hotel_report += f"酒店{i}: {hotel['name']}\n"
                if "rating" in hotel:
                    hotel_report += f"评分: {hotel['rating']}\n"
                if "price" in hotel:
                    price = hotel["price"]
                    hotel_report += f"价格: {price['total']} {price['currency']}\n"
                if "address" in hotel:
                    address = hotel["address"]
                    hotel_report += f"地址: {address.get('city', '')}{address.get('district', '')}{address.get('street', '')}\n"
                if "amenities" in hotel and hotel["amenities"]:
                    hotel_report += f"设施: {', '.join(hotel['amenities'][:5])}\n"
                if "available_rooms" in hotel:
                    hotel_report += f"可用房间: {hotel['available_rooms']}\n"
            else:
                hotel_report += f"Hotel {i}: {hotel['name']}\n"
                if "rating" in hotel:
                    hotel_report += f"Rating: {hotel['rating']}\n"
                if "price" in hotel:
                    price = hotel["price"]
                    hotel_report += f"Price: {price['total']} {price['currency']}\n"
                if "address" in hotel:
                    address = hotel["address"]
                    hotel_report += f"Address: {address.get('city', '')}{address.get('district', '')}{address.get('street', '')}\n"
                if "amenities" in hotel and hotel["amenities"]:
                    hotel_report += f"Amenities: {', '.join(hotel['amenities'][:5])}\n"
                if "available_rooms" in hotel:
                    hotel_report += f"Available rooms: {hotel['available_rooms']}\n"
            
            hotel_report += "\n"
        
        # 格式化成功响应
        response = format_response(
            response_success,
            city=city,
            count=len(hotels),
            check_in=check_in_str,
            check_out=check_out_str
        )
        
        return ActionResponse(
            action=Action.REQLLM,
            result=hotel_report,
            response=response
        )
    
    except Exception as e:
        logger.bind(tag=TAG).error(f"搜索酒店时发生异常: {e}")
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=format_response(response_failure, city=city, reason="系统错误，请稍后再试")
        )