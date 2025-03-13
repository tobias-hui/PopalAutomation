from pydantic import BaseModel, Field, HttpUrl
from typing import Optional

class OrderRequest(BaseModel):
    """订单请求模型"""
    orderid: str = Field(..., description="订单ID")
    num: int = Field(..., ge=1, description="订单数量")
    photo: HttpUrl = Field(..., description="图片URL")
    urgent: int = Field(0, ge=0, le=1, description="是否加急：0-否，1-是")
    delivery: int = Field(0, description="配送方式")
    specsCode: str = Field("SCDPLIVG0001", description="规格代码")
    receiverName: str = Field("Temu", description="收货人")
    receiverContact: str = Field("******", description="联系方式")
    receiverAddress: str = Field("******", description="收货地址")

class OrderResponse(BaseModel):
    """订单响应模型"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[dict] = Field(None, description="响应数据") 