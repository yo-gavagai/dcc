# dc_delete_strategy.py
import re
from dc_logger import log

async def find_delete_button(page):
    selectors = [
        'button.btn_grey.cancle',
        "button:has-text('삭제')",
        "input[type=button][value=삭제]"
    ]
    for selector in selectors:
        btn = await page.query_selector(selector)
        if btn:
            log(f"삭제 버튼 탐색 성공! 셀렉터: {selector}")
            return btn
    log("삭제 버튼 탐색 실패.", level="WARN")
    return None

async def try_meta_delete(page):
    content = await page.content()
    m = re.search(r"goDelete\('([^']+)'\)", content)
    if m:
        meta_delete_url = m.group(1)
        log(f"[META] delete url candidate: {meta_delete_url}")
        response = await page.request.post(meta_delete_url)
        log(f"[META] delete POST status: {response.status}")
        return response.status == 200
    log("[META] delete url extraction failed", level="ERROR")
    return False
