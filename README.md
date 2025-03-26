# Image Processing API

这是一个基于 FastAPI 的图像处理服务，提供多种图像处理功能，包括产品信息处理、尺寸图处理、轮播图处理等。

## 功能特点

- 产品信息图片处理
- 尺寸图处理
- 轮播图处理
- 白色背景处理
- 文件上传和管理
- 任务状态跟踪
- 健康检查

## 技术栈

- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Pillow
- OpenCV
- 阿里云 OSS

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/image-processing-api.git
cd image-processing-api
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置信息
```

### 5. 数据库迁移

```bash
alembic upgrade head
```

## 运行

### 开发环境

```bash
uvicorn app.main:app --reload
```

### 生产环境

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker 部署

### 构建镜像

```bash
docker build -t image-processing-api .
```

### 运行容器

```bash
docker-compose up -d
```

## API 文档

访问 http://localhost:8000/docs 查看交互式 API 文档

### 主要端点

1. **产品信息处理**
   - POST `/api/v1/product-info`
   - 处理产品信息图片，添加标题、数量、尺寸等信息

2. **尺寸图处理**
   - POST `/api/v1/dimension`
   - 处理产品尺寸图片，添加尺寸标注

3. **轮播图处理**
   - POST `/api/v1/carousel`
   - 处理产品轮播图，生成视频效果

4. **文件上传**
   - POST `/api/v1/upload`
   - 支持图片和 ZIP 文件上传

5. **任务管理**
   - GET `/api/v1/tasks/{task_id}`
   - GET `/api/v1/tasks/{task_id}/result`
   - GET `/api/v1/tasks`
   - DELETE `/api/v1/tasks/{task_id}`

6. **健康检查**
   - GET `/api/v1/health`

## 使用示例

### 产品信息处理

```python
import requests

url = "http://localhost:8000/api/v1/product-info"
data = {
    "title": "Product Name",
    "pcs": 200,
    "height_cm": 13.8,
    "length_cm": 14.3,
    "image_url": "https://example.com/product.png"
}

response = requests.post(url, json=data)
print(response.json())
```

### 尺寸图处理

```python
url = "http://localhost:8000/api/v1/dimension"
data = {
    "image_url": "https://example.com/product.png",
    "length": 10.5,
    "height": 15.2
}

response = requests.post(url, json=data)
print(response.json())
```

## 开发指南

### 目录结构

```
app/
├── api/            # API 路由
├── core/           # 核心功能
├── models/         # 数据模型
├── utils/          # 工具函数
├── assets/         # 静态资源
├── temp/           # 临时文件
└── output/         # 输出文件
```

### 添加新的处理器

1. 在 `app/core/` 目录下创建新的处理器类
2. 继承 `BaseImageProcessor` 类
3. 实现 `process_image` 方法
4. 在 `app/api/routes.py` 中添加新的路由

## 注意事项

1. 确保所有环境变量都已正确配置
2. 确保数据库已正确迁移
3. 确保 OSS 配置正确且有足够的权限
4. 定期清理临时文件和输出文件
5. 监控任务状态和错误日志

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License 