from typing import Optional, Dict, Any
from dataclasses import dataclass
import os
from dotenv import load_dotenv
from .api_client import OrderAPIClient
import logging
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

@dataclass
class SimpleOrderRequest:
    """简化的订单请求数据类"""
    orderid: str
    num: int
    photo: str
    urgent: int = 0  # 默认非加急
    delivery: int = 0  # 默认配送方式
    specsCode: str = "SCDPLIVG0001"  # 默认规格代码
    receiverName: str = "Temu"  # 默认收货人
    receiverContact: str = "******"  # 默认联系方式
    receiverAddress: str = "******"  # 默认地址

class OrderService:
    """订单服务类"""
    
    def __init__(self):
        """初始化订单服务"""
        # 确保加载环境变量
        load_dotenv()
        
        # 验证必要的环境变量
        self._validate_environment()
        
        # 初始化API客户端
        self._api_client = OrderAPIClient()

    @staticmethod
    def _validate_environment() -> None:
        """验证必要的环境变量是否存在"""
        required_vars = ['API_APPID', 'API_KEY', 'API_BASE_URL']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _generate_unique_orderid(self, base_orderid: str) -> str:
        """
        生成唯一的订单号
        
        Args:
            base_orderid: 基础订单号
            
        Returns:
            str: 添加了日期后缀的唯一订单号
        """
        # 生成当前日期时间后缀，格式：MMDD
        date_suffix = datetime.now().strftime("%Y%m%d%H%M")
        return f"{base_orderid}-{date_suffix}"

    def create_order(self, order_request: SimpleOrderRequest) -> Dict[str, Any]:
        """
        创建订单的简化方法
        
        Args:
            order_request: SimpleOrderRequest对象，包含必要的订单信息
            
        Returns:
            Dict[str, Any]: API响应结果
        """
        try:
            # 生成唯一订单号
            unique_orderid = self._generate_unique_orderid(order_request.orderid)
            
            # 构建完整的订单数据，设置默认值
            full_order_data = {
                "orderid": unique_orderid,
                "num": order_request.num,
                "photo": order_request.photo,
                "urgent": order_request.urgent,
                # 以下是固定的默认值
                "buyerNickName": "惠凯",
                "receiverName": order_request.receiverName,  # 使用用户输入或默认值
                "receiverContact": order_request.receiverContact,  # 使用用户输入或默认值
                "receiverAddress": order_request.receiverAddress,  # 使用用户输入或默认值
                "specsCode": order_request.specsCode,  # 使用用户输入或默认值
                "orderRemark": f"temu仓库-{unique_orderid}-{order_request.num}件",
                "delivery": order_request.delivery,  # 使用用户输入或默认值
                "designNoticeTel": None,
                "buyerTel": None
            }

            logger.info("Creating order with ID: %s", unique_orderid)
            logger.debug("Order data: %s", full_order_data)

            # 调用API客户端创建订单
            result = self._api_client.create_order(full_order_data)
            
            if result.get("error"):
                logger.error("Failed to create order: %s", result["error"])
            else:
                logger.info("Order created successfully: %s", unique_orderid)
                
            return result
            
        except Exception as e:
            logger.error("Error creating order: %s", str(e))
            return {"error": str(e)} 