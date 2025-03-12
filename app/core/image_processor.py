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

# 配置日志
logger = logging.getLogger(__name__)

# 默认画布大小
DEFAULT_CANVAS_SIZE = (800, 600)

class BaseImageProcessor(ABC):
    """图片处理器基类"""
    def __init__(self, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        self.canvas_size = canvas_size

    def resize_and_center(self, image: Image.Image) -> Image.Image:
        """调整图片大小并居中"""
        # 创建白色背景画布，使用原始图片尺寸
        canvas = Image.new('RGBA', image.size, (255, 255, 255, 255))
        # 直接粘贴原始图片
        canvas.paste(image, (0, 0), image)
        return canvas

    @abstractmethod
    def process_image(self, image: Image.Image) -> Image.Image:
        """处理图片的抽象方法"""
        pass

class DimensionImageProcessor(BaseImageProcessor):
    """尺寸图处理器"""
    def __init__(self, dimensions: Dict[str, Dict[str, float]], canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        super().__init__(canvas_size)
        self.dimensions = dimensions

    def process_image(self, image: Image.Image) -> Image.Image:
        """处理尺寸图片"""
        # 保持原始尺寸，只添加白色背景
        background = self.resize_and_center(image)
        
        # 获取图片边界
        img_array = np.array(background)
        edges = self._detect_edges(img_array)
        product_bounds = self._get_product_bounds(edges, background.size)
        
        # 添加尺寸标注
        self._add_dimension_labels(background, product_bounds)
        
        return background

    def _detect_edges(self, img_array: np.ndarray) -> np.ndarray:
        """使用OpenCV检测边缘"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = np.ones((3,3), np.uint8)
        return cv2.dilate(edges, kernel, iterations=1)

    def _get_product_bounds(self, edges: np.ndarray, image_size: Tuple[int, int]) -> Tuple[int, int, int, int]:
        """获取产品边界"""
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # 找到最大轮廓
            max_contour = max(contours, key=cv2.contourArea)
            return cv2.boundingRect(max_contour)
        else:
            # 如果没有找到轮廓，使用图片中心区域
            center_x = image_size[0] // 2
            center_y = image_size[1] // 2
            width = image_size[0] // 3
            height = image_size[1] // 3
            return (
                center_x - width // 2,
                center_y - height // 2,
                width,
                height
            )

    def _get_font(self, size: int = 48) -> ImageFont.FreeTypeFont:
        """获取字体"""
        font_paths = [
            "C:/Windows/Fonts/Arial.ttf",  # Windows
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Docker
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        
        logger.warning("No suitable font found, using default font")
        return ImageFont.load_default()

    def _add_dimension_labels(self, image: Image.Image, bounds: Tuple[int, int, int, int]) -> None:
        """添加尺寸标注"""
        x, y, w, h = bounds
        draw = ImageDraw.Draw(image)

        # 设置字体
        font_title = self._get_font(48)
        font_dimension = self._get_font(25)

        # 绘制标题
        title = "DIMENSION"
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        # 使用实际图片尺寸来计算标题位置
        text_y = int(image.size[1] * 0.08)  # 图片高度的8%位置
        draw.text(
            ((image.size[0] - title_width) // 2, text_y),  # 水平居中
            title,
            fill=(0, 0, 0),
            font=font_title
        )

        # 设置尺寸线参数
        margin = 30
        line_color = (0, 0, 0)
        line_width = 2
        arrow_size = 8

        # 绘制底部长度线
        bottom_y = y + h + margin
        left_x = x - margin // 2
        right_x = x + w + margin // 2
        
        # 绘制长度线和箭头
        draw.line([(left_x, bottom_y), (right_x, bottom_y)], fill=line_color, width=line_width)
        self._draw_arrow(draw, left_x, bottom_y, 'left', line_color, line_width, arrow_size)
        self._draw_arrow(draw, right_x, bottom_y, 'right', line_color, line_width, arrow_size)

        # 绘制长度文本
        length_text = f"{self.dimensions['length']['value']}cm/{self.dimensions['length']['inch']}inch"
        text_bbox = draw.textbbox((0, 0), length_text, font=font_dimension)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(
            (x + (w - text_width) // 2, bottom_y + 5),
            length_text,
            fill=line_color,
            font=font_dimension
        )

        # 绘制右侧高度线
        side_x = x + w + margin
        top_y = y - margin // 2
        bottom_y = y + h + margin // 2
        
        # 绘制高度线和箭头
        draw.line([(side_x, top_y), (side_x, bottom_y)], fill=line_color, width=line_width)
        self._draw_arrow(draw, side_x, top_y, 'up', line_color, line_width, arrow_size)
        self._draw_arrow(draw, side_x, bottom_y, 'down', line_color, line_width, arrow_size)

        # 绘制高度文本
        height_text = f"{self.dimensions['height']['value']}cm/{self.dimensions['height']['inch']}inch"
        text_bbox = draw.textbbox((0, 0), height_text, font=font_dimension)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # 创建并旋转高度文本
        txt = Image.new('RGBA', (text_width + 10, text_height + 10), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt)
        txt_draw.text((5, 5), height_text, fill=line_color, font=font_dimension)
        txt = txt.rotate(90, expand=True)
        
        # 粘贴旋转后的文字
        text_y = y + (h - txt.size[1]) // 2
        image.paste(txt, (side_x + 5, text_y), txt)

    def _draw_arrow(self, draw: ImageDraw.Draw, x: int, y: int, direction: str, 
                   color: Tuple[int, int, int], width: int, size: int) -> None:
        """绘制箭头
        direction: 'left', 'right', 'up', 'down'
        """
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

class CarouselImageProcessor(BaseImageProcessor):
    """轮播图处理器"""
    def __init__(self, dimensions_text: str, canvas_size: Tuple[int, int] = DEFAULT_CANVAS_SIZE):
        super().__init__(canvas_size)
        self.dimensions = self._parse_dimensions_text(dimensions_text)
        self.temp_dir: Optional[Path] = None
        self.output_dir: Optional[Path] = None

    def process_zip(self, zip_data: BytesIO) -> str:
        """处理ZIP文件中的图片
        Args:
            zip_data: ZIP文件的二进制数据
        Returns:
            str: 处理后的ZIP文件路径
        """
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                self.temp_dir = Path(temp_dir)
                self.output_dir = self.temp_dir / "output"
                self.output_dir.mkdir(exist_ok=True)

                # 解压ZIP文件
                self._extract_zip(zip_data)

                # 处理所有图片
                self._process_all_images()

                # 创建输出ZIP文件
                output_zip = "processed_carousel_images.zip"
                self._create_output_zip(output_zip)

                return output_zip

        except Exception as e:
            logger.error(f"Error processing carousel zip: {str(e)}")
            raise
        finally:
            # 清理临时文件
            self._cleanup()

    def process_image(self, image: Image.Image) -> Image.Image:
        """处理单张轮播图片"""
        try:
            # 调整图片大小并居中
            processed = self.resize_and_center(image)
            
            # 如果是尺寸图，添加尺寸标注
            if self.dimensions:
                processed = self._add_dimension_labels(processed)
            
            return processed

        except Exception as e:
            logger.error(f"Error processing carousel image: {str(e)}")
            raise

    def _parse_dimensions_text(self, text: str) -> Dict:
        """解析尺寸文本"""
        if not text:
            return {}

        try:
            # 预处理文本
            # 处理可能的JSON格式
            try:
                cleaned_str = text.replace('\r\n', '\\n').replace('\n', '\\n')
                json_data = json.loads(cleaned_str)
                if isinstance(json_data, dict) and 'dimensions_text' in json_data:
                    text = json_data['dimensions_text']
            except (json.JSONDecodeError, TypeError):
                pass

            # 标准化文本格式
            text = ''.join(line.strip() for line in text.splitlines())
            
            # 提取维度信息
            pattern = r'(Length|Width|Height):(\d+\.?\d*)cm'
            matches = re.findall(pattern, text, re.IGNORECASE)
            
            if not matches:
                return {}
                
            # 构建维度字典
            dimensions = {}
            for dim_type, value in matches:
                dim_type = dim_type.lower()
                try:
                    value = float(value)
                    dimensions[dim_type] = {
                        'value': value,
                        'unit': 'cm',
                        'inch': round(value / 2.54, 2)
                    }
                except ValueError:
                    continue
            
            return dimensions

        except Exception as e:
            logger.error(f"Error parsing dimensions text: {str(e)}")
            return {}

    def _extract_zip(self, zip_data: BytesIO) -> None:
        """解压ZIP文件"""
        try:
            with zipfile.ZipFile(zip_data, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
        except Exception as e:
            raise Exception(f"Error extracting zip file: {str(e)}")

    def _should_process_image(self, filename: str) -> bool:
        """判断是否需要处理该图片"""
        if filename.lower() == 'untitled.png':
            return True
        pattern = r'_\d+'
        return bool(re.search(pattern, filename)) and any(
            filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']
        )

    def _process_all_images(self) -> None:
        """处理所有图片"""
        if not self.temp_dir or not self.output_dir:
            raise ValueError("Temporary directories not initialized")

        for image_path in self.temp_dir.rglob('*'):
            if not self._should_process_image(image_path.name):
                continue

            try:
                # 获取图片编号
                match = re.search(r'_(\d+)', image_path.name)
                if not match:
                    # Keep original image with unique name
                    unique_name = f"{image_path.stem}_{uuid.uuid4()}{image_path.suffix}"
                    shutil.copy2(image_path, self.output_dir / unique_name)
                    continue

                number = match.group(1)
                is_dimension_image = '_2' in image_path.name

                # 处理图片
                with Image.open(image_path).convert("RGBA") as img:
                    if is_dimension_image:
                        # Add white background and dimension labels
                        white_bg = Image.new("RGBA", img.size, "WHITE")
                        white_bg.paste(img, mask=img)
                        processed_image = self._add_dimension_labels(white_bg)
                        output_name = f'dimension_{number}_{uuid.uuid4()}.png'
                    else:
                        # Only add white background
                        white_bg = Image.new("RGBA", img.size, "WHITE")
                        white_bg.paste(img, mask=img)
                        processed_image = white_bg
                        output_name = f'{number}_{uuid.uuid4()}.png'

                    processed_image.save(self.output_dir / output_name)

            except Exception as e:
                logger.error(f"Error processing image {image_path}: {str(e)}")
                continue

    def _create_output_zip(self, output_zip: str) -> None:
        """创建输出ZIP文件"""
        try:
            with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in self.output_dir.rglob('*'):
                    zipf.write(file_path, file_path.relative_to(self.output_dir))
        except Exception as e:
            raise Exception(f"Error creating output zip: {str(e)}")

    def _cleanup(self) -> None:
        """清理临时文件"""
        try:
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
            if self.output_dir and self.output_dir.exists():
                shutil.rmtree(self.output_dir)
        except Exception as e:
            logger.warning(f"Error cleaning up temporary files: {str(e)}")

    def _add_dimension_labels(self, image: Image.Image) -> Image.Image:
        """为尺寸图添加标注"""
        if not self.dimensions:
            return image

        # 创建尺寸处理器
        dimension_processor = DimensionImageProcessor(
            dimensions=self.dimensions,
            canvas_size=self.canvas_size
        )
        
        # 处理图片
        return dimension_processor.process_image(image)

def create_processor(processor_type: str, **kwargs) -> BaseImageProcessor:
    """工厂方法创建处理器"""
    processors = {
        'dimension': DimensionImageProcessor,
        'carousel': CarouselImageProcessor
    }
    
    processor_class = processors.get(processor_type)
    if not processor_class:
        raise ValueError(f"Unknown processor type: {processor_type}")
    
    return processor_class(**kwargs)

class ImageProcessor:
    def __init__(self, dimensions: Dict[str, Dict[str, float]], canvas_size: Tuple[int, int] = CANVAS_SIZE):
        self.dimensions = dimensions
        self.canvas_size = canvas_size

    @staticmethod
    def download_zip_from_url(url: str) -> BytesIO:
        """从URL下载zip文件到内存"""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return BytesIO(response.content)
        except Exception as e:
            raise Exception(f"Error downloading zip file: {str(e)}")

    @staticmethod
    def extract_zip(zip_file: BytesIO | str, extract_path: str | Path) -> bool:
        """解压zip文件到指定目录"""
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            return True
        except Exception as e:
            raise Exception(f"Error extracting zip file: {str(e)}")

    @staticmethod
    def should_process_image(filename: str) -> bool:
        """判断是否需要处理该图片"""
        if filename.lower() == 'untitled.png':
            return True
        pattern = r'_\d+'
        return bool(re.search(pattern, filename)) and any(
            filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg']
        )

    def process_single_image(self, image_path: str | Path, output_dir: str | Path) -> bool:
        """处理单张图片"""
        try:
            image_path = Path(image_path)
            output_dir = Path(output_dir)
            base_name = image_path.name

            # 检查是否为需要处理的图片
            match = re.search(r'_(\d+)', base_name)
            if not match:
                # Keep original image
                shutil.copy2(image_path, output_dir / base_name)
                return True

            number = match.group(1)
            is_dimension_image = '_2' in base_name

            # 打开并处理图片
            original_image = Image.open(image_path).convert("RGBA")

            if is_dimension_image:
                # Add white background and dimension labels
                white_bg = Image.new("RGBA", original_image.size, "WHITE")
                white_bg.paste(original_image, mask=original_image)
                final_image = self.create_dimension_image(white_bg)
                output_name = f'dimension_{number}_{uuid.uuid4()}.png'
            else:
                # Only add white background
                white_bg = Image.new("RGBA", original_image.size, "WHITE")
                white_bg.paste(original_image, mask=original_image)
                final_image = white_bg
                output_name = f'{number}_{uuid.uuid4()}.png'

            # 保存结果
            final_image.save(output_dir / output_name)
            return True

        except Exception as e:
            raise Exception(f"Error processing image {image_path}: {str(e)}")

    def create_dimension_image(self, image: Image.Image) -> Image.Image:
        """创建带尺寸标注的图片"""
        # 调整图片大小并居中
        background, (offset_x, offset_y), (img_width, img_height) = self.resize_and_center(image, margin_ratio=0.15)
        draw = ImageDraw.Draw(background)

        # 使用OpenCV进行边缘检测
        img_array = np.array(background)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
        # 使用高斯模糊减少噪声
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        # 使用Canny边缘检测
        edges = cv2.Canny(blurred, 50, 150)
        # 使用膨胀操作连接边缘
        kernel = np.ones((3,3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # 找到轮廓
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # 找到最大轮廓
            max_contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(max_contour)
            # 更新产品边界
            product_left = x
            product_right = x + w
            product_top = y
            product_bottom = y + h
        else:
            # 如果没有找到轮廓，使用原始尺寸
            product_left = offset_x
            product_right = offset_x + img_width
            product_top = offset_y
            product_bottom = offset_y + img_height

        # 获取字体
        try:
            windows_font = "C:/Windows/Fonts/Arial.ttf"
            linux_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            docker_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            
            if os.path.exists(windows_font):
                font_path = windows_font
            elif os.path.exists(linux_font):
                font_path = linux_font
            elif os.path.exists(docker_font):
                font_path = docker_font
            else:
                raise FileNotFoundError("No suitable font found")
            
            font_title = ImageFont.truetype(font_path, 48)  # 改回原来的大小
            font_dimension = ImageFont.truetype(font_path, 25)  # 改回原来的大小
        except Exception as e:
            print(f"Font loading error: {e}")
            font_title = ImageFont.load_default()
            font_dimension = ImageFont.load_default()

        # 绘制标题
        title = "DIMENSION"
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        text_y = int(self.canvas_size[1] * 0.08)
        draw.text(
            ((self.canvas_size[0] - title_width) // 2, text_y),
            title,
            fill=(0, 0, 0),
            font=font_title
        )

        # 设置尺寸线参数
        margin = 30  # 减小边距使线条更贴近产品
        line_color = (0, 0, 0)
        line_width = 2
        arrow_size = 8

        # 底部长度线 - 使用检测到的产品边界
        bottom_y = product_bottom + margin
        left_x = product_left - margin // 2
        right_x = product_right + margin // 2

        # 绘制底部长度线
        draw.line([(left_x, bottom_y), (right_x, bottom_y)], fill=line_color, width=line_width)
        
        # 绘制箭头函数
        def draw_arrow(x, y, direction):
            """绘制箭头
            direction: 'left', 'right', 'up', 'down'
            """
            if direction == 'left':
                draw.line([(x, y), (x + arrow_size, y - arrow_size)], fill=line_color, width=line_width)
                draw.line([(x, y), (x + arrow_size, y + arrow_size)], fill=line_color, width=line_width)
            elif direction == 'right':
                draw.line([(x, y), (x - arrow_size, y - arrow_size)], fill=line_color, width=line_width)
                draw.line([(x, y), (x - arrow_size, y + arrow_size)], fill=line_color, width=line_width)
            elif direction == 'up':
                draw.line([(x, y), (x - arrow_size, y + arrow_size)], fill=line_color, width=line_width)
                draw.line([(x, y), (x + arrow_size, y + arrow_size)], fill=line_color, width=line_width)
            elif direction == 'down':
                draw.line([(x, y), (x - arrow_size, y - arrow_size)], fill=line_color, width=line_width)
                draw.line([(x, y), (x + arrow_size, y - arrow_size)], fill=line_color, width=line_width)

        # 绘制长度线的箭头
        draw_arrow(left_x, bottom_y, 'left')
        draw_arrow(right_x, bottom_y, 'right')

        # 长度文本
        length_text = f"{self.dimensions['length']['value']}cm/{self.dimensions['length']['inch']}inch"
        text_bbox = draw.textbbox((0, 0), length_text, font=font_dimension)
        text_width = text_bbox[2] - text_bbox[0]
        draw.text(
            (product_left + (w - text_width) // 2, bottom_y + 5),
            length_text,
            fill=line_color,
            font=font_dimension
        )

        # 右侧高度线 - 使用检测到的产品边界
        side_x = product_right + margin
        top_y = product_top - margin // 2
        bottom_y = product_bottom + margin // 2

        # 绘制右侧高度线
        draw.line([(side_x, top_y), (side_x, bottom_y)], fill=line_color, width=line_width)
        
        # 绘制高度线的箭头
        draw_arrow(side_x, top_y, 'up')
        draw_arrow(side_x, bottom_y, 'down')

        # 高度文本
        height_text = f"{self.dimensions['height']['value']}cm/{self.dimensions['height']['inch']}inch"
        text_bbox = draw.textbbox((0, 0), height_text, font=font_dimension)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # 创建临时图片用于旋转文字
        txt = Image.new('RGBA', (text_width + 10, text_height + 10), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt)
        txt_draw.text((5, 5), height_text, fill=line_color, font=font_dimension)
        txt = txt.rotate(90, expand=True)
        
        # 粘贴旋转后的文字
        text_y = product_top + (h - txt.size[1]) // 2
        background.paste(txt, (side_x + 5, text_y), txt)

        return background

def process_images(zip_url: str, dimensions_str: str) -> str:
    """
    处理图片的主函数
    :param zip_url: ZIP文件的URL
    :param dimensions_str: 尺寸信息字符串
    :return: 处理后的ZIP文件路径
    """
    # 解析尺寸信息
    dimensions = parse_dimensions(dimensions_str)
    
    # 创建处理器实例
    processor = ImageProcessor(dimensions)
    
    # 设置工作目录
    temp_dir = Path("temp")
    output_dir = Path("processed_images")
    # 使用UUID生成唯一的输出文件名
    unique_id = uuid.uuid4()
    output_zip = f"processed_images_{unique_id}.zip"
    
    try:
        # 创建必要的目录
        temp_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
        
        # 下载并解压文件
        zip_file = processor.download_zip_from_url(zip_url)
        processor.extract_zip(zip_file, temp_dir)
        
        # 处理图片
        for file_path in temp_dir.rglob('*'):
            if processor.should_process_image(file_path.name):
                processor.process_single_image(file_path, output_dir)
        
        # 压缩处理后的图片
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in output_dir.rglob('*'):
                zipf.write(file_path, file_path.relative_to(output_dir))
        
        return output_zip
        
    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        if output_dir.exists():
            shutil.rmtree(output_dir)

def parse_dimensions(dimensions_str: str) -> Dict[str, Dict[str, float]]:
    """解析尺寸信息"""
    if not dimensions_str:
        raise ValueError("Dimensions text cannot be empty")

    try:
        # 预处理输入文本
        # 1. 处理输入可能是JSON字符串的情况
        try:
            # 如果输入是字符串形式的JSON，先将所有换行符替换为 \n
            cleaned_str = dimensions_str.replace('\r\n', '\\n').replace('\n', '\\n')
            json_data = json.loads(cleaned_str)
            if isinstance(json_data, dict) and 'dimensions_text' in json_data:
                # 保留换行符
                dimensions_str = json_data['dimensions_text']
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. 标准化文本格式
        # 移除所有空白字符（保留换行符用于调试）
        text = ''.join(line.strip() for line in dimensions_str.splitlines())
        
        # 使用正则表达式提取维度信息
        pattern = r'(Length|Width|Height):(\d+\.?\d*)cm'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if not matches:
            raise ValueError("No valid dimensions found in input text")
            
        # 构建维度字典
        dimensions_data = {}
        for dim_type, value in matches:
            dim_type = dim_type.lower()
            try:
                value = float(value)
                dimensions_data[dim_type] = value
            except ValueError:
                continue
                
        # 验证必需的维度
        if 'length' not in dimensions_data:
            raise ValueError("Missing required dimension: length")
        if 'height' not in dimensions_data:
            raise ValueError("Missing required dimension: height")
            
        # 如果没有宽度，使用长度
        if 'width' not in dimensions_data:
            dimensions_data['width'] = dimensions_data['length']
            
        # 构建最终的维度字典
        dimensions = {}
        for dim_type in ['length', 'width', 'height']:
            value = dimensions_data[dim_type]
            dimensions[dim_type] = {
                'value': value,
                'unit': 'cm',
                'inch': round(value / 2.54, 2)
            }
            
        return dimensions
        
    except Exception as e:
        print(f"解析错误: {str(e)}")  # 调试输出
        raise ValueError(f"Failed to parse dimensions: {str(e)}")

def test_parse_dimensions():
    """测试尺寸解析函数"""
    test_cases = [
        # 标准格式
        {
            "input": "Length:15.0cm\nWidth:9.0cm\nHeight:13.0cm",
            "name": "标准格式"
        },
        # JSON格式
        {
            "input": '{"dimensions_text": "Length:15.0cm\\nWidth:9.0cm\\nHeight:13.0cm"}',
            "name": "JSON格式"
        },
        # 带空格的格式
        {
            "input": "Length: 15.0cm\nWidth: 9.0cm\nHeight: 13.0cm",
            "name": "带空格的格式"
        },
        # 只有长度和高度
        {
            "input": "Length: 15.0cm\nHeight: 13.0cm",
            "name": "缺少宽度"
        },
        # 带换行符的格式
        {
            "input": "Length:15.0cm\\nWidth:9.0cm\\nHeight:13.0cm",
            "name": "转义换行符格式"
        }
    ]
    
    print("开始测试 parse_dimensions 函数...")
    for case in test_cases:
        try:
            print(f"\n测试用例: {case['name']}")
            print(f"输入: {case['input']}")
            result = parse_dimensions(case['input'])
            print("结果:", json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"错误: {str(e)}")
    print("\n测试完成")

if __name__ == "__main__":
    test_parse_dimensions() 