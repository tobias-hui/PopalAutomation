from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
import logging
from pathlib import Path
import requests
from io import BytesIO
from .base_processor import BaseImageProcessor

# 配置日志
logger = logging.getLogger(__name__)

class ComplianceLabelProcessor(BaseImageProcessor):
    """合规标签模板处理器"""
    def __init__(self, batch_code: str, barcode_url: str, canvas_size: Tuple[int, int] = (1000, 1000)):
        """
        初始化合规标签处理器
        Args:
            batch_code: 批次号字符串
            barcode_url: 条形码图片的URL地址
            canvas_size: 画布尺寸，默认1000x1000
        """
        super().__init__(canvas_size)
        self.batch_code = batch_code
        self.barcode_url = barcode_url
        
        # 设置字体目录
        self.fonts_dir = Path(__file__).parent.parent / 'assets' / 'fonts'
        self.font_path = self.fonts_dir / 'Poppins-Bold.ttf'
        
        # 加载字体
        self._load_fonts()
        
        # 定义文本位置
        self.text_positions = [
            (223, 263),  # 第一个batch code位置
            (709, 263)   # 第二个batch code位置
        ]
        
        # 定义条形码位置和尺寸
        self.barcode_box = {
            'x': 30,
            'y': 790,
            'width': 710,
            'height': 205
        }

    def _load_fonts(self):
        """加载字体文件"""
        try:
            self.font = ImageFont.truetype(str(self.font_path), 21)  # 修改字体大小为21
        except Exception as e:
            logger.warning(f"无法加载Poppins字体: {str(e)}")
            logger.warning(f"请确保字体文件存在于路径: {self.fonts_dir}")
            self.font = ImageFont.load_default()

    def _load_image_from_url(self, url: str) -> Image.Image:
        """
        从URL加载图片
        Args:
            url: 图片的URL地址
        Returns:
            PIL Image对象
        Raises:
            Exception: 当图片加载失败时抛出异常
        """
        try:
            response = requests.get(url)
            response.raise_for_status()  # 检查请求是否成功
            image = Image.open(BytesIO(response.content))
            
            # 确保图片是RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            logger.error(f"从URL加载图片失败: {str(e)}")
            raise Exception(f"无法从URL加载图片: {url}")

    def process_image(self, image: Optional[Image.Image] = None) -> Image.Image:
        """
        处理合规标签模板图片
        Args:
            image: 可选的基础图片，如果不提供则使用默认模板
        Returns:
            处理后的图片
        """
        # 加载基础模板
        if image is None:
            template_path = Path(__file__).parent.parent / 'assets' / 'templates' / 'ComplianceBasic.png'
            if not template_path.exists():
                raise FileNotFoundError(f"模板文件未找到: {template_path}")
            image = Image.open(template_path)
            
            # 确保模板图片是RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
        
        # 创建绘图对象
        draw = ImageDraw.Draw(image)
        
        # 添加batch code文本
        for position in self.text_positions:
            draw.text(position, self.batch_code, fill='black', font=self.font)
        
        # 处理条形码图片
        try:
            # 从URL加载条形码图片
            barcode_image = self._load_image_from_url(self.barcode_url)
            
            # 调整条形码图片大小
            barcode_image = barcode_image.resize(
                (self.barcode_box['width'], self.barcode_box['height']),
                Image.Resampling.LANCZOS
            )
            
            # 确保条形码图片是RGB模式
            if barcode_image.mode != 'RGB':
                barcode_image = barcode_image.convert('RGB')
            
            # 粘贴条形码图片
            image.paste(
                barcode_image,
                (self.barcode_box['x'], self.barcode_box['y'])
            )
        except Exception as e:
            logger.error(f"处理条形码图片时出错: {str(e)}")
            raise
        
        return image 

class BricksComplianceLabelProcessor(BaseImageProcessor):
    """积木合规标签处理器"""
    
    def __init__(
        self,
        batch_code: str,
        model: str,
        barcode_url: str,
        canvas_size: Tuple[int, int] = (1000, 1000)
    ):
        """
        初始化积木合规标签处理器
        
        Args:
            batch_code: 批次号
            model: 型号
            barcode_url: 条形码图片URL
            canvas_size: 画布大小，默认(1000, 1000)
        """
        super().__init__(canvas_size)
        self.batch_code = batch_code
        self.model = model
        self.barcode_url = barcode_url
        self.fonts_dir = Path(__file__).parent.parent / 'assets' / 'fonts'
        self.font_path = self.fonts_dir / 'Poppins-Bold.ttf'
        self._load_fonts()
        
    def _load_fonts(self):
        """加载字体文件"""
        try:
            self.font = ImageFont.truetype(str(self.font_path), 21)
        except Exception as e:
            logger.warning(f"无法加载Poppins字体: {str(e)}")
            logger.warning(f"请确保字体文件存在于路径: {self.fonts_dir}")
            self.font = ImageFont.load_default()
            
    def _load_image_from_url(self, url: str) -> Image.Image:
        """从URL加载图片"""
        try:
            response = requests.get(url)
            if response.status_code != 200:
                raise ValueError(f"Failed to download image: HTTP {response.status_code}")
            return Image.open(BytesIO(response.content))
        except Exception as e:
            logger.error(f"Error loading image from URL: {str(e)}")
            raise ValueError(f"Failed to load image from URL: {str(e)}")
            
    def process_image(self) -> Image.Image:
        """处理图片"""
        try:
            # 加载基础模板
            template_path = Path(__file__).parent.parent / 'assets' / 'templates' / 'BricksComplianceBasic.png'
            if not template_path.exists():
                raise FileNotFoundError(f"模板文件未找到: {template_path}")
            image = Image.open(template_path)
            
            # 确保模板图片是RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # 创建画布
            canvas = Image.open(template_path).convert('RGBA')
            
            # 创建绘图上下文
            draw = ImageDraw.Draw(canvas)
            
            # 绘制批次号（位置1）
            draw.text(
                (633, 248),
                self.batch_code,
                font=self.font,
                fill=(0, 0, 0)
            )
            
            # 绘制批次号（位置2）
            draw.text(
                (847, 294),
                self.batch_code,
                font=self.font,
                fill=(0, 0, 0)
            )
            
            # 绘制型号
            draw.text(
                (549, 294),
                self.model,
                font=self.font,
                fill=(0, 0, 0)
            )
            
            # 加载并放置条形码
            barcode_image = self._load_image_from_url(self.barcode_url)
            barcode_image = barcode_image.resize((691, 199))
            canvas.paste(barcode_image, (309, 801))
            
            return canvas
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise ValueError(f"Failed to process image: {str(e)}") 