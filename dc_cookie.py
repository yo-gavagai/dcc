import json
from dc_logger import log_info, log_error

class DCCookieManager:
    def __init__(self, cookie_path):
        self.cookie_path = cookie_path

    def load_cookies(self):
        try:
            with open(self.cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            log_info(f"[cookie] 쿠키 로드 성공: {self.cookie_path}")
            return cookies
        except Exception as e:
            log_error(f"[cookie] 쿠키 로드 실패: {e}")
            return None

    def save_cookies(self, cookies):
        try:
            with open(self.cookie_path, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            log_info(f"[cookie] 쿠키 저장 성공: {self.cookie_path}")
        except Exception as e:
            log_error(f"[cookie] 쿠키 저장 실패: {e}")
