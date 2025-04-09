import os
import logging
from typing import Tuple, Optional
from openai import OpenAI
from dotenv import load_dotenv

# 配置日志
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 初始化OpenAI客户端
client = OpenAI(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY")
)

async def check_character_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    检查角色名称是否存在侵权风险，如果存在则生成模糊名称
    
    Args:
        name: 要检查的角色名称
        
    Returns:
        Tuple[bool, Optional[str]]: 
            - 第一个元素表示是否存在侵权风险 (True表示有风险)
            - 第二个元素是生成的模糊名称 (如果有风险)
    """
    try:
        # 构建系统提示
        system_prompt = """You are a professional copyright risk assessment expert. Your tasks are:
        1. Assess whether the given character name poses copyright infringement risks
        2. If there is a risk, generate a similar but non-infringing name
        
        Assessment criteria:
        - Similarity to well-known IP character names
        - Inclusion of copyrighted names
        - Potential for confusion
        
        Name generation rules:
        - Keep the style and characteristics of the original name
        - Length should not exceed 1.5 times the original name
        - Use simple, memorable words
        - Avoid complex or obscure vocabulary
        - Maintain name conciseness and readability
        - Output must be in English only
        - Remove any version numbers (e.g., v.1, v2.0)
        - Remove any special characters or symbols
        - Convert any non-English characters to their English equivalents
        
        If there is a risk, generate a similar name that maintains the original style while avoiding infringement."""
        
        # 构建用户提示
        user_prompt = f"""Please assess the following character name for copyright infringement risks:
        {name}
        
        If there is a risk, generate a similar name. Please respond in the following format:
        Risk Assessment: [Risky/Safe]
        Alternative Name: [Leave blank if safe]
        
        Note: The alternative name should be:
        - Concise and memorable
        - In English only
        - No version numbers or special characters
        - Length not exceeding 1.5 times the original name."""
        
        # 调用API
        response = client.chat.completions.create(
            model="ep-20250207104632-fwv4x",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # 解析响应
        result = response.choices[0].message.content
        logger.info(f"API response for name '{name}': {result}")
        
        # 解析风险评估和模糊名称
        has_risk = "Risk Assessment: Risky" in result
        fuzzy_name = None
        
        if has_risk:
            # 提取模糊名称
            fuzzy_name_line = [line for line in result.split('\n') if "Alternative Name: " in line]
            if fuzzy_name_line:
                fuzzy_name = fuzzy_name_line[0].split("Alternative Name: ")[1].strip()
        
        return has_risk, fuzzy_name
        
    except Exception as e:
        logger.error(f"Error checking character name: {str(e)}")
        # 发生错误时默认认为有风险，返回原始名称
        return True, name
