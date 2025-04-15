from fastapi import APIRouter, HTTPException
import logging

from app.utils.order_service import OrderService, SimpleOrderRequest
from app.models.order_models import OrderRequest, OrderResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/orders", tags=["Orders"])

# 创建订单服务实例
order_service = OrderService()

@router.post("", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    """
    创建订单API端点
    
    Args:
        request: OrderRequest - 订单请求数据
        
    Returns:
        OrderResponse - 订单创建响应
    """
    try:
        # 转换请求数据
        simple_request = SimpleOrderRequest(
            orderid=request.orderid,
            num=request.num,
            photo=str(request.photo),
            urgent=request.urgent,
            delivery=request.delivery,
            specsCode=request.specsCode,
            receiverName=request.receiverName,
            receiverContact=request.receiverContact,
            receiverAddress=request.receiverAddress
        )
        
        # 调用订单服务
        result = order_service.create_order(simple_request)
        
        # 检查响应
        if isinstance(result, dict) and result.get("error"):
            return OrderResponse(
                success=False,
                message=f"订单创建失败: {result['error']}",
                data=result
            )
            
        return OrderResponse(
            success=True,
            message="订单创建成功",
            data=result
        )
        
    except Exception as e:
        logger.error(f"创建订单失败: {str(e)}")
        return OrderResponse(
            success=False,
            message=f"订单创建失败: {str(e)}",
            data=None
        ) 