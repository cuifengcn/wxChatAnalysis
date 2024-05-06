import asyncio
import re
from functools import wraps


AD_NAME = "元助手AI"
AD_URL = "http://yuanzhushou.com"
ai_url = "脱敏"


def async_partial(f, *args):
    @wraps(f)
    async def f2(*args2):
        result = f(*args, *args2)
        if asyncio.iscoroutinefunction(f):
            result = await result
        return result

    return f2


def extract_chinese(text):
    pattern = re.compile(r"[\u4e00-\u9fa5]")  # 匹配中文字符的正则表达式
    chinese_chars = pattern.findall(text)  # 查找字符串中所有匹配的中文字符
    chinese_text = "".join(chinese_chars)  # 将匹配到的中文字符连接成字符串
    return chinese_text


def get_time_interval(interval: int):
    if interval < 60:
        return f"{int(interval)}秒"
    if interval < 60 * 60:
        return f"{int(interval / 60)}分钟"
    if interval < 60 * 60 * 24:
        return f"{int(interval / 60 / 60)}小时"
    return f"{int(interval / 60 / 60 / 24)}天"
