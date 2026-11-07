"""
知识库小助手 —— 独立服务包。

这个包和主后端（main.py / API/ / Dao/）完全独立：
主后端一行都不用改，小助手单独跑、单独部署、单独挂掉。
"""

from .prompts import ASSISTANT_NAME, ASSISTANT_TITLE

__all__ = ['ASSISTANT_NAME', 'ASSISTANT_TITLE']
