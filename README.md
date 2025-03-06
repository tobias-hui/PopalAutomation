# Image Processing API

这是一个用于处理产品图片的FastAPI应用，可以处理图片并添加尺寸标注。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行服务器

```bash
uvicorn api:app --reload
```

服务器将在 http://localhost:8000 启动

## API 使用说明

### 1. API文档
访问 http://localhost:8000/docs 查看交互式API文档

### 2. 处理图片
发送POST请求到 `/process/` 端点，需要提供以下JSON数据：
- `zip_url`: 包含待处理图片的ZIP文件的URL（阿里云OSS或其他可访问的URL）
- `dimensions_text`: 包含尺寸信息的文本内容

dimensions_text 的格式示例：
```text
length: 10.5cm
height: 15.2cm
```

### 3. 使用示例（Python）

```python
import requests

url = "http://localhost:8000/process/"
data = {
    "zip_url": "https://your-bucket.oss-cn-region.aliyuncs.com/images.zip",
    "dimensions_text": "length: 10.5cm\nheight: 15.2cm"
}

response = requests.post(url, json=data)

if response.status_code == 200:
    with open('processed_images.zip', 'wb') as f:
        f.write(response.content)
    print("处理完成，已保存为 processed_images.zip")
else:
    print("处理失败:", response.text)
```

### 4. 使用示例（curl）

```bash
curl -X POST "http://localhost:8000/process/" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "zip_url": "https://your-bucket.oss-cn-region.aliyuncs.com/images.zip",
    "dimensions_text": "length: 10.5cm\nheight: 15.2cm"
  }' \
  --output processed_images.zip
```

## 注意事项

1. 确保提供的ZIP文件URL是可以公开访问的
2. dimensions_text 必须包含正确的尺寸信息（length和height）
3. 处理大文件可能需要一些时间，请耐心等待
4. 服务器会返回处理后的ZIP文件 