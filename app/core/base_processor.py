from abc import ABC, abstractmethod
from PIL import Image
from typing import Tuple
import numpy as np
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 默认画布大小
DEFAULT_CANVAS_SIZE = (1000, 1000)
DEFAULT_DRAW_AREA = {
    'x': 100,
    'y': 100,
    'width': 800,
    'height': 800
}

class BaseImageProcessor(ABC):
    """图片处理器基类"""
    def __init__(self, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        self.canvas_size = canvas_size
        self.draw_area = DEFAULT_DRAW_AREA.copy()

    def resize_and_center(self, image: Image.Image) -> Image.Image:
        """调整图片大小并居中"""
        # 保持原始图片模式（包括透明背景）
        canvas = Image.new(image.mode, image.size, (255, 255, 255, 0) if image.mode == 'RGBA' else (255, 255, 255))
        canvas.paste(image, (0, 0))
        return canvas

    def _detect_product_bounds(self, image: Image.Image) -> Tuple[int, int, int, int]:
        """检测产品边界"""
        try:
            # 确保图片是RGBA模式
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 使用alpha通道检测产品边界
            alpha = img_array[:, :, 3]
            rows = np.any(alpha > 0, axis=1)
            cols = np.any(alpha > 0, axis=0)
            
            # 获取边界
            ymin, ymax = np.where(rows)[0][[0, -1]]
            xmin, xmax = np.where(cols)[0][[0, -1]]
            
            return (xmin, ymin, xmax - xmin + 1, ymax - ymin + 1)
            
        except Exception as e:
            logger.error(f"检测产品边界时出错: {str(e)}")
            # 如果检测失败，返回图片中心区域
            width, height = image.size
            center_x = width // 2
            center_y = height // 2
            return (center_x - 100, center_y - 100, 200, 200)

    @abstractmethod
    def process_image(self, image: Image.Image) -> Image.Image:
        """处理图片的抽象方法"""
        pass