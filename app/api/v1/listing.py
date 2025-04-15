from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

from app.utils.listing_service import check_character_name

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(prefix="/listing", tags=["Listing"])

class CharacterNameRequest(BaseModel):
    """角色名称检查请求模型"""
    name: str = Field(..., description="要检查的角色名称")
    strict_mode: bool = Field(False, description="是否启用严格模式（更严格的检查）")

class CharacterNameResponse(BaseModel):
    """角色名称检查响应模型"""
    original_name: str = Field(..., description="原始角色名称")
    has_risk: bool = Field(..., description="是否存在侵权风险")
    alternative_name: Optional[str] = Field(None, description="建议的替代名称")
    risk_reason: Optional[str] = Field(None, description="风险评估原因")
    message: str = Field(..., description="处理结果消息")

@router.post("/check-character-name", response_model=CharacterNameResponse)
async def check_character_name_endpoint(request: CharacterNameRequest):
    """
    检查角色名称的合规性
    
    Args:
        request: CharacterNameRequest - 包含要检查的角色名称
        
    Returns:
        CharacterNameResponse - 包含检查结果和建议的替代名称
    """
    try:
        # 调用检查服务
        has_risk, alternative_name = await check_character_name(request.name)
        
        # 构建响应
        response = CharacterNameResponse(
            original_name=request.name,
            has_risk=has_risk,
            alternative_name=alternative_name if has_risk else None,
            risk_reason="Name may infringe on existing IP rights" if has_risk else None,
            message="Name check completed successfully"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error checking character name: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error checking character name: {str(e)}"
        ) 