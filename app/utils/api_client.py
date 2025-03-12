"""
API客户端模块，用于与外部API通信
"""
import requests
import hashlib
import time
import random
import string
from typing import Dict, Any, Optional
import os
import json
from urllib.parse import urljoin
import urllib3
from datetime import datetime
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# 配置日志
logger = logging.getLogger(__name__)

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class APIClient:
    """通用API客户端基类"""
    
    def __init__(self, appid: Optional[str] = None, key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化API客户端
        
        Args:
            appid: API应用ID
            key: API密钥
            base_url: API基础URL
        """
        self.appid = appid or os.getenv('API_APPID')
        self.key = key or os.getenv('API_KEY')
        self.base_url = base_url or os.getenv('API_BASE_URL', "https://test.platform.maic.fun")
        
        # 获取重试和超时配置
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '30'))
        
        # 配置会话
        self.session = self._configure_session()
        
        if not all([self.appid, self.key]):
            raise ValueError("Missing required API credentials. Please check your environment variables.")

    def _configure_session(self) -> requests.Session:
        """配置请求会话，添加重试机制"""
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,  # 重试间隔时间
            status_forcelist=[500, 502, 503, 504],  # 需要重试的HTTP状态码
        )
        
        # 将重试策略应用到会话
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _generate_nonce_str(self, length: int = 32) -> str:
        """生成随机字符串"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """生成API签名"""
        # 过滤空值并转换所有值为字符串
        filtered_params = {k: str(v) for k, v in params.items() if v is not None}
        
        # 按ASCII顺序排序参数
        sorted_params = sorted(filtered_params.items(), key=lambda x: x[0])
        
        # 创建签名字符串
        sign_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        sign_string += f"&key={self.key}"
        
        logger.debug("Sign string: %s", sign_string)
        
        # 生成MD5并转换为大写
        return hashlib.md5(sign_string.encode()).hexdigest().upper()

    def _prepare_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """准备请求参数"""
        # 添加公共参数
        common_params = {
            "appid": self.appid,
            "timestamp": int(time.time()),
            "noncestr": self._generate_nonce_str()
        }
        
        # 合并参数
        full_params = {**common_params, **params}
        
        # 生成签名
        full_params["sign"] = self._generate_signature(full_params)
        
        return full_params

    def _make_request(self, endpoint: str, data: Dict[str, Any], method: str = "POST") -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            endpoint: API端点
            data: 请求数据
            method: 请求方法（默认POST）
            
        Returns:
            Dict[str, Any]: API响应
        """
        url = urljoin(self.base_url, endpoint)
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Python/3.10'
        }

        try:
            logger.debug("Sending request to: %s", url)
            logger.debug("Request headers: %s", json.dumps(headers, indent=2))
            logger.debug("Request parameters: %s", json.dumps(data, ensure_ascii=False, indent=2))
            
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                verify=False,
                allow_redirects=True,
                timeout=self.timeout
            )
            
            logger.debug("Response status code: %d", response.status_code)
            logger.debug("Response headers: %s", json.dumps(dict(response.headers), indent=2))
            logger.debug("Response content: %s", response.text)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    return {"error": f"Failed to parse JSON response: {str(e)}", "raw_response": response.text}
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.error("Request failed: %s", str(e))
            return {"error": str(e)}

class OrderAPIClient(APIClient):
    """订单API客户端"""
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建订单
        
        Args:
            order_data: 订单数据
            
        Returns:
            Dict[str, Any]: API响应
        """
        endpoint = "/qianzhi/api/v1/order/create"
        prepared_data = self._prepare_request(order_data)
        return self._make_request(endpoint, prepared_data) 