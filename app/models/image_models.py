from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal, Dict
from datetime import datetime

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

class ImageProcessingTask(BaseModel):
    """图片处理任务基础模型"""
    task_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None
    error: Optional[str] = None

class DimensionImageRequest(BaseModel):
    """尺寸图处理请求"""
    image_url: HttpUrl = Field(..., description="图片URL")
    dimensions: DimensionSet = Field(..., description="尺寸信息")
    task_name: Optional[str] = Field(None, description="任务名称")

class CarouselRequest(BaseModel):
    """轮播图处理请求"""
    zip_url: str = Field(..., description="ZIP文件URL")
    dimensions_text: str = Field(..., description="尺寸文本信息")
    task_name: Optional[str] = Field(None, description="任务名称")

class ProcessResponse(BaseModel):
    """处理响应"""
    task_id: str
    status: str
    message: str

    created_at: datetime

class UploadResponse(BaseModel):
    """文件上传响应模型"""
    file_url: str = Field(..., description="文件访问URL")
    file_name: str = Field(..., description="文件名")
    file_size: int = Field(..., description="文件大小（字节）")
    created_at: datetime = Field(..., description="创建时间")

class TaskQueryResponse(BaseModel):
    """任务查询响应"""
    task_id: str
    status: str
    progress: Optional[float] = None
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_url: Optional[str] = None
    error: Optional[str] = None
    estimated_time: Optional[int] = None  # 预计剩余时间（秒）
    result: Optional[Dict] = None  # 添加结果字段 