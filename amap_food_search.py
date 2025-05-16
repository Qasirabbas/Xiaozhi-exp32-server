from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging
import requests
import json
from typing import Dict, Any, List, Optional

TAG = __name__
logger = setup_logging()

# Function description for xiaozhi function calling
AMAP_FOOD_SEARCH_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "amap_food_search",
        "description": "搜索附近的美食或特定菜品，支持按照关键词、位置和半径查询。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词，如菜品名称、餐厅名称或美食种类，例如'火锅'、'烤鸭'、'小龙虾'"
                },
                "location": {
                    "type": "string",
                    "description": "搜索中心点坐标，格式为'经度,纬度'，例如'116.481028,39.989643'。如果不提供，会尝试使用当前位置。"
                },
                "city": {
                    "type": "string",
                    "description": "搜索城市，例如'北京'、'上海'、'广州'"
                },
                "radius": {
                    "type": "integer",
                    "description": "搜索半径，单位为米，取值范围:0-50000，默认3000"
                },
                "page": {
                    "type": "integer",
                    "description": "页码，默认为1"
                },
                "page_size": {
                    "type": "integer",
                    "description": "每页结果数，默认为10"
                },
                "sort_type": {
                    "type": "string",
                    "description": "排序类型，可选'distance'(距离优先)、'weight'(权重优先，默认值)"
                },
                "response_success": {
                    "type": "string",
                    "description": "成功查询到美食信息时的友好回复，例如：'我找到了{count}家提供{keyword}的地方'"
                },
                "response_failure": {
                    "type": "string",
                    "description": "查询失败时的友好回复，例如：'抱歉，我没有找到{keyword}相关的美食'"
                }
            },
            "required": ["keyword", "response_success", "response_failure"]
        }
    }
}

# 中国主要城市的坐标（经度,纬度）
CITY_COORDINATES = {
    "北京": "116.407526,39.904030",
    "上海": "121.473701,31.230416",
    "广州": "113.264385,23.129112",
    "深圳": "114.085947,22.547",
    "成都": "104.065735,30.659462",
    "杭州": "120.209947,30.245853",
    "武汉": "114.305393,30.593099",
    "西安": "108.948024,34.263161",
    "南京": "118.796877,32.060255",
    "重庆": "106.551556,29.563009",
    "天津": "117.190182,39.125596",
    "苏州": "120.585316,31.298886",
    "厦门": "118.089425,24.479834",
    "青岛": "120.383428,36.067235",
    "长沙": "112.938814,28.228209",
    "大连": "121.618622,38.914589",
    # 英文名称映射
    "Beijing": "116.407526,39.904030",
    "Shanghai": "121.473701,31.230416",
    "Guangzhou": "113.264385,23.129112",
    "Shenzhen": "114.085947,22.547",
    "Chengdu": "104.065735,30.659462",
    "Hangzhou": "120.209947,30.245853",
    "Wuhan": "114.305393,30.593099",
    "Xian": "108.948024,34.263161",
    "Nanjing": "118.796877,32.060255",
    "Chongqing": "106.551556,29.563009",
    "Tianjin": "117.190182,39.125596",
    "Suzhou": "120.585316,31.298886",
    "Xiamen": "118.089425,24.479834",
    "Qingdao": "120.383428,36.067235",
    "Changsha": "112.938814,28.228209",
    "Dalian": "121.618622,38.914589"
}

class AmapClient:
    def __init__(self, api_key):
        """
        初始化高德地图API客户端
        
        Args:
            api_key: 高德Web服务API密钥
        """
        self.api_key = api_key
        self.base_url = "https://restapi.amap.com/v3"
        self.session = requests.Session()
    
    def search_poi(self, keyword, location=None, city=None, radius=3000, 
                   page=1, page_size=10, extensions="all", sort_type="weight"):
        """
        搜索POI信息
        
        Args:
            keyword: 搜索关键词
            location: 搜索中心点坐标，格式为'经度,纬度'
            city: 搜索城市
            radius: 搜索半径，单位为米
            page: 页码
            page_size: 每页结果数
            extensions: 返回信息详略，"base"或"all"
            sort_type: 排序类型，"distance"或"weight"
            
        Returns:
            搜索结果
        """
        url = f"{self.base_url}/place/around"
        
        params = {
            "key": self.api_key,
            "keywords": keyword,
            "offset": page_size,
            "page": page,
            "extensions": extensions,
            "radius": radius,
            "sortrule": sort_type,
            "types": "050000" # 餐饮服务类POI
        }
        
        # 添加位置参数
        if location:
            params["location"] = location
        
        # 添加城市参数
        if city:
            params["city"] = city
        
        logger.bind(tag=TAG).info(f"搜索美食: {keyword}, 位置: {location or city or '未指定'}, 半径: {radius}米")
        logger.bind(tag=TAG).debug(f"请求参数: {params}")
        
        try:
            response = self.session.get(url, params=params, timeout=20)  # 增加超时时间到20秒
            response.raise_for_status()
            result = response.json()
            logger.bind(tag=TAG).info(f"搜索结果: 状态={result.get('status')}, 计数={result.get('count')}")
            return result
        except Exception as e:
            logger.bind(tag=TAG).error(f"搜索失败: {e}")
            raise

def format_response(template: str, **kwargs) -> str:
    """格式化响应，替换模板中的变量"""
    for key, value in kwargs.items():
        placeholder = "{" + key + "}"
        template = template.replace(placeholder, str(value))
    return template

def calculate_distance_text(distance):
    """将距离格式化为易读的文本"""
    if distance is None:
        return "未知距离"
    
    try:
        dist = float(distance)
        if dist < 1000:
            return f"{int(dist)}米"
        else:
            return f"{dist/1000:.1f}公里"
    except (ValueError, TypeError):
        return str(distance)

def get_city_coordinates(city_name):
    """获取城市坐标"""
    if not city_name:
        return None
    
    # 检查直接匹配
    if city_name in CITY_COORDINATES:
        return CITY_COORDINATES[city_name]
    
    # 尝试部分匹配
    for city, coords in CITY_COORDINATES.items():
        if city_name in city or city in city_name:
            return coords
    
    return None

@register_function('amap_food_search', AMAP_FOOD_SEARCH_FUNCTION_DESC, ToolType.WAIT)
def amap_food_search(keyword, response_success, response_failure, location=None, city=None, 
                     radius=3000, page=1, page_size=10, sort_type="weight"):
    """
    搜索附近美食
    
    Args:
        keyword: 搜索关键词
        response_success: 成功时的响应模板
        response_failure: 失败时的响应模板
        location: 搜索中心点坐标
        city: 搜索城市
        radius: 搜索半径
        page: 页码
        page_size: 每页结果数
        sort_type: 排序类型
        
    Returns:
        ActionResponse: 包含查询结果的响应
    """
    logger.bind(tag=TAG).info(f"开始搜索美食: 关键词={keyword}, 位置={location or city or '未指定'}, 半径={radius}米")
    
    try:
        # 使用你的实际高德Web服务API密钥
        api_key = "8fcaec7eaa25ed5d3f1fc6427a2ef92e"
        
        # 处理位置信息
        search_location = location
        search_city = city
        city_for_response = city
        
        # 如果提供了城市名称但没有坐标，尝试获取城市坐标
        if city and not location:
            city_coords = get_city_coordinates(city)
            if city_coords:
                search_location = city_coords
                logger.bind(tag=TAG).info(f"使用城市{city}的坐标: {city_coords}")
        
        # 如果提供了坐标但没有城市名称，尝试反向查找城市名称用于响应
        if location and not city:
            for c_name, c_coords in CITY_COORDINATES.items():
                if c_coords == location:
                    city_for_response = c_name
                    break
            
            if not city_for_response:
                city_for_response = "当前位置"
        
        # 如果没有位置信息，使用默认位置(北京)
        if not search_location and not search_city:
            search_location = CITY_COORDINATES["北京"]
            city_for_response = "北京"
            logger.bind(tag=TAG).warning("未提供位置信息，使用默认位置(北京)")
        
        client = AmapClient(api_key)
        
        # 搜索美食
        search_result = client.search_poi(keyword, search_location, search_city, radius, page, page_size, "all", sort_type)
        
        # 检查搜索是否成功
        if search_result.get("status") != "1":
            error_msg = search_result.get("info", "未知错误")
            logger.bind(tag=TAG).warning(f"搜索失败: {error_msg}")
            
            # 格式化失败响应
            response = format_response(
                response_failure,
                keyword=keyword,
                reason=error_msg,
                city=city_for_response
            )
            
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"搜索失败: {error_msg}",
                response=response
            )
        
        # 提取搜索结果
        count = int(search_result.get("count", "0"))
        pois = search_result.get("pois", [])
        
        # 检查是否有搜索结果
        if count == 0 or not pois:
            logger.bind(tag=TAG).warning(f"没有找到相关美食: {keyword}")
            
            # 格式化失败响应
            response = format_response(
                response_failure,
                keyword=keyword,
                reason="没有找到相关美食",
                city=city_for_response
            )
            
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"没有找到关于\"{keyword}\"的美食",
                response=response
            )
        
        # 构建美食信息
        food_info = f"关于\"{keyword}\"的美食搜索结果 (共找到 {count} 处):\n\n"
        
        # 记录餐厅名称列表
        restaurant_list = []
        
        for i, poi in enumerate(pois[:min(page_size, len(pois))], 1):
            name = poi.get("name", "未知餐厅")
            restaurant_list.append(name)
            
            food_info += f"{i}. {name}\n"
            
            # 地址
            address = poi.get("address", "")
            if address:
                food_info += f"   地址: {address}\n"
            
            # 电话
            tel = poi.get("tel", "")
            if tel:
                food_info += f"   电话: {tel}\n"
            
            # 评分
            rating = poi.get("biz_ext", {}).get("rating", "")
            if rating:
                food_info += f"   评分: {rating}分\n"
            
            # 价格
            cost = poi.get("biz_ext", {}).get("cost", "")
            if cost:
                food_info += f"   人均: ¥{cost}\n"
            
            # 营业时间
            open_time = poi.get("business_area", poi.get("biz_ext", {}).get("open_time", ""))
            if open_time:
                food_info += f"   营业时间: {open_time}\n"
            
            # 距离
            distance = poi.get("distance", "")
            if distance:
                food_info += f"   距离: {calculate_distance_text(distance)}\n"
            
            # 类型
            poi_type = poi.get("type", "")
            if poi_type:
                food_info += f"   类型: {poi_type}\n"
            
            food_info += "\n"
        
        # 生成响应中的餐厅列表文本
        restaurants_text = ", ".join(restaurant_list[:5])
        if len(restaurant_list) > 5:
            restaurants_text += "等"
        
        # 格式化成功响应
        response = format_response(
            response_success,
            keyword=keyword,
            count=count,
            restaurant_list=restaurants_text,
            city=city_for_response,
            radius=f"{radius/1000:.1f}公里" if radius >= 1000 else f"{radius}米"
        )
        
        return ActionResponse(
            action=Action.REQLLM,
            result=food_info,
            response=response
        )
    
    except Exception as e:
        # 处理其他异常
        logger.bind(tag=TAG).error(f"搜索美食时发生异常: {e}")
        
        # 格式化失败响应
        city_name = city or "当前位置"
        response = format_response(
            response_failure,
            keyword=keyword,
            reason="系统错误，请稍后再试",
            city=city_name
        )
        
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"错误: {str(e)}",
            response=response
        )