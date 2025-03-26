import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import shutil
import zipfile
import requests
from io import BytesIO
from typing import Dict, Tuple, Optional
from app.config.settings import CANVAS_SIZE
import json
import logging
from abc import ABC, abstractmethod
import tempfile
import uuid
from tempfile import TemporaryDirectory
from app.utils.oss_client import oss_client

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

# 字体路径配置
FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"

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
            print(f"检测产品边界时出错: {str(e)}")
            # 如果检测失败，返回图片中心区域
            width, height = image.size
            center_x = width // 2
            center_y = height // 2
            return (center_x - 100, center_y - 100, 200, 200)

    @abstractmethod
    def process_image(self, image: Image.Image) -> Image.Image:
        """处理图片的抽象方法"""
        pass

class WhiteBackgroundProcessor(BaseImageProcessor):
    """白色背景处理器"""
    def __init__(self, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        super().__init__(canvas_size)
        # 定义允许绘制的区域
        self.draw_area = {
            'x': 110,
            'y': 140,
            'width': 780,
            'height': 790
        }

    def _calculate_placement(self, product_width: int, product_height: int) -> Tuple[int, int]:
        """计算产品在允许区域内的放置位置（居中靠下）"""
        # 计算缩放比例
        width_ratio = self.draw_area['width'] / product_width
        height_ratio = self.draw_area['height'] / product_height
        scale_ratio = min(width_ratio, height_ratio)
        
        # 计算缩放后的尺寸
        new_width = int(product_width * scale_ratio)
        new_height = int(product_height * scale_ratio)
        
        # 计算居中位置（水平居中，垂直靠下）
        x = self.draw_area['x'] + (self.draw_area['width'] - new_width) // 2
        # 确保y坐标不小于允许区域的最小y坐标
        y = max(
            self.draw_area['y'],
            self.draw_area['y'] + self.draw_area['height'] - new_height - 20  # 距离底部20像素
        )
        
        return (x, y, new_width, new_height)

    def process_image(self, image: Image.Image) -> Image.Image:
        """处理图片，添加白色背景并放置产品"""
        try:
            # 1. 检测产品边界
            product_bounds = self._detect_product_bounds(image)
            x, y, w, h = product_bounds
            
            # 2. 裁剪产品图片
            product_image = image.crop((x, y, x + w, y + h))
            
            # 3. 计算放置位置
            place_x, place_y, new_width, new_height = self._calculate_placement(w, h)
            
            # 4. 创建白色背景画布
            canvas = Image.new('RGB', self.canvas_size, (255, 255, 255))
            
            # 5. 缩放产品图片
            product_image = product_image.resize((new_width, new_height), Image.LANCZOS)
            
            # 6. 将产品图片粘贴到画布上
            canvas.paste(product_image, (place_x, place_y), product_image)
            
            return canvas
            
        except Exception as e:
            logger.error(f"Error processing image with white background: {str(e)}")
            raise

class DimensionProcessor(BaseImageProcessor):
    """尺寸标注处理器"""
    def __init__(self, length: float, height: float, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        super().__init__(canvas_size)
        self.length = length
        self.height = height
        # 定义允许绘制的区域
        self.draw_area = {
            'x': 200,
            'y': 220,
            'width': 600,
            'height': 625
        }
        # 加载字体
        self.title_font = self._load_font("Poppins-Bold.ttf", 48)
        self.text_font = self._load_font("Poppins-Regular.ttf", 28)

    def _load_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont:
        """加载字体"""
        font_path = os.path.join("app", "assets", "fonts", font_name)
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            logger.error(f"Error loading font {font_name}: {str(e)}")
            return ImageFont.load_default()

    def _calculate_placement(self, product_width: int, product_height: int) -> Tuple[int, int, int, int]:
        """计算产品在允许区域内的放置位置（居中靠下）"""
        # 计算缩放比例
        width_ratio = self.draw_area['width'] / product_width
        height_ratio = self.draw_area['height'] / product_height
        scale_ratio = min(width_ratio, height_ratio)
        
        # 计算缩放后的尺寸
        new_width = int(product_width * scale_ratio)
        new_height = int(product_height * scale_ratio)
        
        # 计算居中位置（水平居中，垂直靠下）
        x = self.draw_area['x'] + (self.draw_area['width'] - new_width) // 2
        y = max(
            self.draw_area['y'],
            self.draw_area['y'] + self.draw_area['height'] - new_height - 20  # 距离底部20像素
        )
        
        return (x, y, new_width, new_height)

    def _draw_arrow(self, draw: ImageDraw.Draw, x: int, y: int, direction: str, 
                   color: Tuple[int, int, int], width: int = 2, size: int = 10) -> None:
        """绘制箭头"""
        if direction == 'left':
            draw.line([(x, y), (x + size, y - size)], fill=color, width=width)
            draw.line([(x, y), (x + size, y + size)], fill=color, width=width)
        elif direction == 'right':
            draw.line([(x, y), (x - size, y - size)], fill=color, width=width)
            draw.line([(x, y), (x - size, y + size)], fill=color, width=width)
        elif direction == 'up':
            draw.line([(x, y), (x - size, y + size)], fill=color, width=width)
            draw.line([(x, y), (x + size, y + size)], fill=color, width=width)
        elif direction == 'down':
            draw.line([(x, y), (x - size, y - size)], fill=color, width=width)
            draw.line([(x, y), (x + size, y - size)], fill=color, width=width)

    def process_image(self, image: Image.Image) -> Image.Image:
        """处理图片，添加尺寸标注"""
        try:
            # 1. 检测产品边界
            product_bounds = self._detect_product_bounds(image)
            x, y, w, h = product_bounds
            
            # 2. 裁剪产品图片
            product_image = image.crop((x, y, x + w, y + h))
            
            # 3. 计算放置位置
            place_x, place_y, new_width, new_height = self._calculate_placement(w, h)
            
            # 4. 创建白色背景画布
            canvas = Image.new('RGB', self.canvas_size, (255, 255, 255))
            
            # 5. 缩放产品图片
            product_image = product_image.resize((new_width, new_height), Image.LANCZOS)
            
            # 6. 将产品图片粘贴到画布上
            canvas.paste(product_image, (place_x, place_y), product_image)
            
            # 7. 添加标题
            draw = ImageDraw.Draw(canvas)
            title = "Dimension"
            title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
            title_width = title_bbox[2] - title_bbox[0]
            # 计算标题在x方向上的居中位置
            title_x = (self.canvas_size[0] - title_width) // 2
            draw.text(
                (title_x, 71),
                title,
                fill=(0, 0, 0),
                font=self.title_font
            )
            
            # 8. 绘制右侧高度线条和文本
            height_line_y1 = place_y + (new_height - new_height) // 2
            height_line_y2 = place_y + new_height + (new_height - new_height) // 2
            
            # 计算线条、箭头和文本的x坐标（基于产品检测框右侧）
            line_x = place_x + new_width + 60  # 线条距离产品右侧80像素
            arrow_x = line_x  # 箭头与线条在同一位置
            text_x = line_x + 15  # 文本距离线条25像素
            
            # 绘制高度线条
            draw.line([(line_x, height_line_y1), (line_x, height_line_y2)], fill=(0, 0, 0), width=2)
            
            # 绘制箭头
            self._draw_arrow(draw, arrow_x, height_line_y1, 'up', (0, 0, 0))
            self._draw_arrow(draw, arrow_x, height_line_y2, 'down', (0, 0, 0))
            
            # 绘制高度文本
            height_text = f"{self.height}cm / {round(self.height/2.54, 2)}inch"
            txt = Image.new('RGBA', (200, 30), (0, 0, 0, 0))  # 增加宽度以适应更长的文本
            txt_draw = ImageDraw.Draw(txt)
            txt_draw.text((0, 0), height_text, fill=(0, 0, 0), font=self.text_font)
            txt = txt.rotate(-90, expand=True)
            text_y = height_line_y1 + (height_line_y2 - height_line_y1 - txt.size[1]) // 2
            canvas.paste(txt, (text_x, text_y), txt)
            
            # 9. 绘制底部长度线条和文本
            # 计算线条、箭头和文本的y坐标（基于产品检测框下侧）
            line_y = place_y + new_height + 60  # 线条距离产品下侧80像素
            text_y = line_y + 15  # 文本距离线条25像素
            
            # 绘制长度线条
            length_line_x1 = place_x + (new_width - new_width) // 2
            length_line_x2 = place_x + new_width + (new_width - new_width) // 2
            draw.line([(length_line_x1, line_y), (length_line_x2, line_y)], fill=(0, 0, 0), width=2)
            
            # 绘制箭头
            self._draw_arrow(draw, length_line_x1, line_y, 'left', (0, 0, 0))
            self._draw_arrow(draw, length_line_x2, line_y, 'right', (0, 0, 0))
            
            # 绘制长度文本
            length_text = f"{self.length}cm / {round(self.length/2.54, 2)}inch"
            text_bbox = draw.textbbox((0, 0), length_text, font=self.text_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_x = length_line_x1 + (length_line_x2 - length_line_x1 - text_width) // 2
            draw.text((text_x, text_y), length_text, fill=(0, 0, 0), font=self.text_font)
            
            return canvas
            
        except Exception as e:
            logger.error(f"Error processing image with dimensions: {str(e)}")
            raise

class CarouselImageProcessor(BaseImageProcessor):
    """轮播图处理器"""
    def __init__(self, dimensions_text: str, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        super().__init__(canvas_size)
        # 解析尺寸文本
        self.dimensions = self._parse_dimensions_text(dimensions_text)
        # 创建处理器
        self.white_bg_processor = WhiteBackgroundProcessor(canvas_size)
        self.dimension_processor = DimensionProcessor(
            length=self.dimensions['length'],
            height=self.dimensions['height']
        ) if self.dimensions else None

    def _parse_dimensions_text(self, text: str) -> Dict:
        """解析尺寸文本，提取高度和长度值
        支持的格式：
        1. 带空格或不带空格: "Length: 5.8" 或 "Length:5.8"
        2. 大小写不敏感: "LENGTH", "Length", "length" 都可以
        3. 带单位或不带单位: "5.8cm" 或 "5.8"
        4. 单位前后可有空格: "5.8 cm" 或 "5.8cm"
        """
        if not text:
            logger.warning("Empty dimensions text provided")
            return {}

        try:
            # 提取维度信息 - 支持多种格式
            pattern = r'(Length|Width|Height)\s*:\s*(\d+\.?\d*)\s*(?:cm)?'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            if not matches:
                logger.warning("No valid dimensions found in text")
                return {}
                
            # 构建维度字典
            dimensions = {}
            for dim_type, value in matches:
                dim_type = dim_type.lower()
                try:
                    dimensions[dim_type] = float(value)
                except ValueError:
                    continue
            
            if not dimensions:
                logger.warning("No valid dimensions were parsed")
            else:
                logger.info(f"Successfully parsed dimensions: {dimensions}")
            
            return dimensions

        except Exception as e:
            logger.error(f"Error parsing dimensions text: {str(e)}")
            return {}

    def process_image(self, image: Image.Image, image_name: str = "") -> Image.Image:
        """处理单张图片
        Args:
            image: 要处理的图片
            image_name: 图片名称，用于决定使用哪个处理器
        """
        try:
            # 只有2.png使用DimensionProcessor处理
            if image_name == "2.png" and self.dimension_processor:
                logger.info("Processing 2.png with DimensionProcessor")
                return self.dimension_processor.process_image(image)
            # 其他图片使用WhiteBackgroundProcessor处理
            else:
                logger.info(f"Processing {image_name} with WhiteBackgroundProcessor")
                return self.white_bg_processor.process_image(image)
        except Exception as e:
            logger.error(f"Error processing image {image_name}: {str(e)}")
            raise

    async def process_zip(self, zip_data: BytesIO) -> Dict[str, str]:
        """处理ZIP文件中的所有图片"""
        try:
            # 创建临时目录
            with TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                logger.info(f"Created temporary directory: {temp_dir_path}")

                # 解压ZIP文件
                with zipfile.ZipFile(zip_data, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir_path)
                logger.info(f"Extracted ZIP file to: {temp_dir_path}")

                # 处理透明背景图片
                transparent_dir = temp_dir_path / "media" / "image" / "transparent_bg_images"
                scene_dir = temp_dir_path / "media" / "image" / "scene_bg_images"
                processed_files = []

                # 处理1-5.png
                for i in range(1, 6):
                    img_path = transparent_dir / f"{i}.png"
                    if not img_path.exists():
                        logger.warning(f"Image {i}.png not found in transparent_bg_images")
                        continue

                    try:
                        logger.info(f"Processing image: {img_path}")
                        with Image.open(img_path) as img:
                            # 2.png使用DimensionProcessor，其他使用WhiteBackgroundProcessor
                            if i == 2 and self.dimension_processor:
                                processed_img = self.dimension_processor.process_image(img)
                            else:
                                processed_img = self.white_bg_processor.process_image(img)
                            
                            # 将处理后的图片转换为字节流
                            img_byte_arr = BytesIO()
                            processed_img.save(img_byte_arr, format='PNG')
                            img_byte_arr.seek(0)
                            processed_files.append((f"{i}.png", img_byte_arr.getvalue()))
                        logger.info(f"Successfully processed {i}.png")
                    except Exception as e:
                        logger.error(f"Error processing {i}.png: {str(e)}")
                        raise

                # 处理6.png（如果存在）
                if scene_dir.exists():
                    scene_images = list(scene_dir.glob("*.png"))
                    if scene_images:
                        img_path = scene_images[0]  # 使用第一个场景图片
                        try:
                            logger.info(f"Processing scene image: {img_path}")
                            with Image.open(img_path) as img:
                                processed_img = self.white_bg_processor.process_image(img)
                                img_byte_arr = BytesIO()
                                processed_img.save(img_byte_arr, format='PNG')
                                img_byte_arr.seek(0)
                                processed_files.append(("6.png", img_byte_arr.getvalue()))
                            logger.info(f"Successfully processed scene image as 6.png")
                        except Exception as e:
                            logger.error(f"Error processing scene image: {str(e)}")
                            raise

                # 创建新的ZIP文件
                output_zip = temp_dir_path / "processed.zip"
                with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for filename, img_data in processed_files:
                        zipf.writestr(filename, img_data)
                logger.info(f"Created processed ZIP file: {output_zip}")

                # 验证ZIP文件
                if not output_zip.exists():
                    raise FileNotFoundError("Output ZIP file not created")
                
                if output_zip.stat().st_size == 0:
                    raise ValueError("Generated ZIP file is empty")

                # 获取视频文件路径
                rotating_video_path = temp_dir_path / "media" / "video" / "rotating" / "rotating_video_white_bg.mp4"
                falling_bricks_video_path = temp_dir_path / "media" / "video" / "falling_bricks" / "falling_bricks_video_white_bg.mp4"

                # 生成唯一的OSS文件名
                zip_filename = f"processed_{uuid.uuid4()}.zip"
                rotating_video_filename = f"rotating_{uuid.uuid4()}.mp4"
                falling_bricks_video_filename = f"falling_bricks_{uuid.uuid4()}.mp4"

                # 上传文件到OSS
                try:
                    # 上传ZIP文件
                    output_url = await oss_client.upload_file(str(output_zip), zip_filename)
                    logger.info(f"Successfully uploaded ZIP file to OSS: {output_url}")
                    
                    # 初始化视频URL为None
                    rotating_video_url = None
                    falling_bricks_video_url = None
                    
                    # 如果视频文件存在，则上传
                    if rotating_video_path.exists():
                        rotating_video_url = await oss_client.upload_file(str(rotating_video_path), rotating_video_filename)
                        logger.info(f"Successfully uploaded rotating video to OSS: {rotating_video_url}")
                    else:
                        logger.warning(f"Rotating video file not found: {rotating_video_path}")
                    
                    if falling_bricks_video_path.exists():
                        falling_bricks_video_url = await oss_client.upload_file(str(falling_bricks_video_path), falling_bricks_video_filename)
                        logger.info(f"Successfully uploaded falling bricks video to OSS: {falling_bricks_video_url}")
                    else:
                        logger.warning(f"Falling bricks video file not found: {falling_bricks_video_path}")
                    
                    return {
                        "output_url": output_url,
                        "rotating_video_url": rotating_video_url,
                        "falling_bricks_video_url": falling_bricks_video_url
                    }
                except Exception as e:
                    logger.error(f"Failed to upload files to OSS: {str(e)}")
                    raise

        except Exception as e:
            logger.error(f"Error processing ZIP file: {str(e)}")
            raise

def create_processor(processor_type: str, **kwargs) -> BaseImageProcessor:
    """工厂方法创建处理器"""
    processors = {
        'white_bg': WhiteBackgroundProcessor,
        'dimension': DimensionProcessor,
        'carousel': CarouselImageProcessor
    }
    
    processor_class = processors.get(processor_type)
    if not processor_class:
        raise ValueError(f"Unknown processor type: {processor_type}")
    
    return processor_class(**kwargs)