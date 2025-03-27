import json
import requests
import os
from pathlib import Path

def generate_postman_collection():
    """生成 Postman 集合"""
    # 获取 OpenAPI 规范
    base_url = "http://localhost:8000"  # 开发环境
    # base_url = "https://your-production-url.com"  # 生产环境
    
    try:
        # 获取 OpenAPI 规范
        response = requests.get(f"{base_url}/api/v1/openapi.json")
        response.raise_for_status()
        openapi_spec = response.json()
        
        # 创建 Postman 集合
        collection = {
            "info": {
                "name": "Canva API Collection",
                "description": "Canva API 接口集合",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }
        
        # 按标签组织接口
        tags = {}
        for path, methods in openapi_spec["paths"].items():
            for method, details in methods.items():
                # 获取标签
                tag = details.get("tags", [{}])[0].get("name", "Uncategorized")
                if tag not in tags:
                    tags[tag] = []
                
                # 创建请求项
                request_item = {
                    "name": details.get("summary", path),
                    "request": {
                        "method": method.upper(),
                        "header": [
                            {
                                "key": "Content-Type",
                                "value": "application/json"
                            }
                        ],
                        "url": {
                            "raw": f"{{base_url}}{path}",
                            "host": ["{{base_url}}"],
                            "path": path.strip("/").split("/")
                        }
                    }
                }
                
                # 添加请求体（如果有）
                if "requestBody" in details:
                    request_item["request"]["body"] = {
                        "mode": "raw",
                        "raw": "{}"
                    }
                
                tags[tag].append(request_item)
        
        # 将标签添加到集合中
        for tag, items in tags.items():
            collection["item"].append({
                "name": tag,
                "item": items
            })
        
        # 创建输出目录
        output_dir = Path("postman")
        output_dir.mkdir(exist_ok=True)
        
        # 保存集合文件
        collection_path = output_dir / "canva_api_collection.json"
        with open(collection_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)
        
        print(f"Postman 集合已生成: {collection_path}")
        
        # 创建环境文件
        environment = {
            "id": "your-environment-id",
            "name": "Canva API Environment",
            "values": [
                {
                    "key": "base_url",
                    "value": base_url,
                    "type": "default"
                }
            ]
        }
        
        environment_path = output_dir / "canva_api_environment.json"
        with open(environment_path, "w", encoding="utf-8") as f:
            json.dump(environment, f, ensure_ascii=False, indent=2)
        
        print(f"Postman 环境文件已生成: {environment_path}")
        
    except Exception as e:
        print(f"生成 Postman 集合时出错: {str(e)}")
        raise

if __name__ == "__main__":
    generate_postman_collection() 