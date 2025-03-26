from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import Optional, Literal, Dict, List
from datetime import datetime
from PIL import Image
from io import BytesIO

class Dimension(BaseModel):
    """尺寸数据模型"""
    value: float = Field(..., gt=0, description="尺寸值")
    unit: Literal["cm", "inch"] = Field(default="cm", description="单位（厘米或英寸）")

class DimensionSet(BaseModel):
    """完整的尺寸集合"""
    length: Dimension = Field(..., description="长度尺寸")
    height: Dimension = Field(..., description="高度尺寸")
    width: Optional[Dimension] = Field(None, description="宽度尺寸（可选）")

    def to_processor_format(self) -> Dict:
        """转换为处理器所需的格式"""
        def to_inches(cm_value: float) -> float:
            return round(cm_value / 2.54, 2)

        result = {}
        for dim_name in ["length", "height", "width"]:
            dim = getattr(self, dim_name)
            if dim is not None:
                result[dim_name] = {
                    "value": dim.value,
                    "unit": dim.unit,
                    "inch": to_inches(dim.value) if dim.unit == "cm" else dim.value
                }
        return result

class WhiteBackgroundRequest(BaseModel):
    """白色背景处理请求"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    image: Image.Image
    task_id: str

class DimensionImageRequest(BaseModel):
    """尺寸图处理请求"""
    image_url: HttpUrl
    length: float = Field(..., description="产品长度(cm)")
    height: float = Field(..., description="产品高度(cm)")
    task_id: str = Field(..., description="任务ID")

class CarouselRequest(BaseModel):
    """轮播图处理请求"""
    zip_url: HttpUrl
    dimensions_text: str = Field(..., description="尺寸文本")
    task_name: str = Field(..., description="任务名称")

class ProcessResponse(BaseModel):
    """处理响应模型"""
    task_id: str
    status: str
    output_url: Optional[str] = None
    rotating_video_url: Optional[str] = None
    falling_bricks_video_url: Optional[str] = None
    error: Optional[str] = None

class ImageProcessingTask(BaseModel):
    """图片处理任务"""
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None
    progress: Optional[float] = None
    estimated_time: Optional[int] = None
    result: Optional[Dict] = None

class TaskQueryResponse(BaseModel):
    """任务查询响应"""
    status: str
    task: Optional[ImageProcessingTask] = None
    error: Optional[str] = None

class UploadResponse(BaseModel):
    """上传响应"""
    status: str
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    error: Optional[str] = None

class ProductInfoRequest(BaseModel):
    """产品信息处理请求模型"""
    title: str = Field(..., description="产品标题")
    pcs: int = Field(..., description="产品数量")
    height_cm: float = Field(..., description="产品高度（厘米）")
    length_cm: float = Field(..., description="产品长度（厘米）")
    image_url: HttpUrl = Field(..., description="产品图片URL") 