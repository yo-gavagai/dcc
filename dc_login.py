# dc_login.py
from playwright.async_api import async_playwright
from dotenv import load_dotenv
import os

async def login(page):
    load_dotenv()
    username = os.getenv('DC_USERNAME')
    password = os.getenv('DC_PASSWORD')
    # 로그인 로직 구현 (기존 로직 분리)
    # ...
    return True
