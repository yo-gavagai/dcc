print("==== 현재 실행 중인 파일:", __file__)

import asyncio
import json
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from dc_logger import log, LOG_VERSION, log_task_start, log_task_end
import sys  # for exception logging

from dc_login import login as dc_login
from dc_post import fetch_posts
from dc_delete_strategy import find_delete_button, try_meta_delete

# 로그 파일: error_log_v1.2.0.txt 사용

class DCCleaner:
    def __init__(self):
        load_dotenv()
        self.username = os.getenv('DC_USERNAME')
        self.password = os.getenv('DC_PASSWORD')
        self.delay = 0.8  # Default delay between actions
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cookies_path = Path('dc_cookies.json')

    async def init_browser(self):
        log_task_start('init_browser', module='DCCleaner')
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=False,  # Run with GUI to handle CAPTCHAs
            args=['--window-size=1280,720'],
            timeout=60000  # Increase timeout to 60 seconds
        )
        # Use desktop user agent
        desktop_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=desktop_user_agent,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        self.page = await self.context.new_page()

    async def load_cookies(self) -> bool:
        log_task_start('load_cookies', module='DCCleaner')
        if not self.cookies_path.exists():
            return False
        cookies = json.loads(self.cookies_path.read_text())
        await self.context.add_cookies(cookies)
        log_task_end('load_cookies', module='DCCleaner')
        return True

    async def save_cookies(self):
        log_task_start('save_cookies', module='DCCleaner')
        cookies = await self.context.cookies()
        self.cookies_path.write_text(json.dumps(cookies))
        log_task_end('save_cookies', module='DCCleaner')

    async def login(self):
        log_task_start('login', module='DCCleaner')
        if not self.username or not self.password:
            raise ValueError("Please set DC_USERNAME and DC_PASSWORD in .env file")
        
        print(f"Attempting to login with username: {self.username}")

        if await self.load_cookies():
            # Verify if cookies are still valid
            await self.page.goto('https://www.dcinside.com', timeout=60000)  # 60 seconds timeout
            if await self.page.locator('#login_process').count() == 0:
                print("Successfully logged in using cookies")
                return

        print("Starting login process...")
        
        # Add initial delay before starting
        await asyncio.sleep(2 + random.random() * 3)
        
        try:
            # Go directly to login page
            print("Navigating to login page...")
            await self.page.goto('https://sign.dcinside.com/login', timeout=60000)
            await asyncio.sleep(2 + random.random() * 2)
            
            # Wait for login form fields
            print("Waiting for login form...")
            await self.page.wait_for_selector('#id', timeout=10000)
            await self.page.wait_for_selector('#pw', timeout=10000)
            print("Login form found")
            
            # Type credentials with random delays
            print("Entering credentials...")
            for c in self.username:
                await self.page.type('#id', c)
                await asyncio.sleep(0.1 + random.random() * 0.2)
            
            await asyncio.sleep(0.5 + random.random())
            
            for c in self.password:
                await self.page.type('#pw', c)
                await asyncio.sleep(0.1 + random.random() * 0.2)
            
            await asyncio.sleep(1 + random.random())
            
            # Click login button
            print("Clicking login button...")
            for selector in ['.btn_login', 'button[type="submit"]', '#login']:
                try:
                    login_button = await self.page.wait_for_selector(selector, timeout=5000)
                    if login_button:
                        print(f"Found login button with selector: {selector}")
                        await login_button.click()
                        break
                except Exception:
                    continue
            
            # Wait for navigation and logged-in state with increased timeout
            print("Waiting for navigation...")
            await self.page.wait_for_load_state('networkidle', timeout=60000)
            await asyncio.sleep(2 + random.random() * 2)
            
            # Go to main page to verify login
            await self.page.goto('https://www.dcinside.com', timeout=60000)
            await asyncio.sleep(2 + random.random() * 2)
            
            # Verify login success
            if await self.page.query_selector('.user_info') or await self.page.query_selector('.logout'):
                print("Login successful!")
            else:
                print("Login might have failed - could not find logged-in indicators")
                
                
        except Exception as e:
            print(f"Error during login process: {e}")
            
            raise
        
        # Save cookies for future use
        await self.save_cookies()
        print("Successfully logged in and saved cookies")
        log_task_end('login', module='DCCleaner')

    async def get_posts_from_gallog(self, hours_ago: float = 1.0) -> List[dict]:
        posts = []
        cutoff_time = datetime.now() - timedelta(hours=hours_ago)
        
        # Go to gallog
        print("Navigating to gallog...")
        await self.page.goto(f'https://gallog.dcinside.com/{self.username}/posting', timeout=60000)
        await self.page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        
        
        
        
        # Get all posts from the gallog
        print("Finding posts...")
        post_elements = await self.page.query_selector_all('.cont_listbox li, .list_box li')
        print(f"Found {len(post_elements)} post elements")
        
        for post in post_elements:
            try:
                # Try different date selectors
                date_text = None
                for selector in ['.date', '.gall_date', 'time']:
                    date_text = await post.query_selector(selector)
                    if date_text:
                        break
                
                if not date_text:
                    print("Could not find date element")
                    continue
                
                date_str = await date_text.inner_text()
                date_str = date_str.strip()
                print(f"Found date: {date_str}")
                
                # 시간이 없는 경우 현재 시간으로 설정
                if len(date_str.split()) == 1:
                    date_str = f"{date_str} 00:00"
                post_date = datetime.strptime(date_str, '%Y.%m.%d %H:%M')
                
                if post_date > cutoff_time:
                    continue
                
                # Try different title selectors
                title_element = None
                for selector in ['.txt_box', '.subject', 'a']:
                    title_element = await post.query_selector(selector)
                    if title_element:
                        break
                
                if not title_element:
                    print("Could not find title element")
                    continue
                
                title = await title_element.inner_text()
                
                # Try different link selectors
                link_element = await post.query_selector('a')
                if not link_element:
                    print("Could not find link element")
                    continue
                
                link = await link_element.get_attribute('href')
                
                print(f"Found post: {title} ({date_str})")
                posts.append({
                    'title': title,
                    'link': link,
                    'date': post_date
                })
            except Exception as e:
                print(f"Error parsing post: {e}")
                continue
            
        return posts

    async def delete_post(self, post: dict) -> bool:
        print("[DEBUG] delete_post 진입 (최상단)")
        log_task_start('delete_post', module='DCCleaner')
        from dc_logger import log_info, log_error
        import traceback
        max_retry = 2
        import time as _time
        for attempt in range(1, max_retry+1):
            print(f"[DEBUG] delete_post 루프 진입: attempt={attempt}")
            try:
                _start_time = _time.time()
                # 페이지/브라우저가 닫혀있으면 복구 시도
                if self.page.is_closed():
                    log_info(f"[delete_post] Page closed, reopening (attempt {attempt})")
                    self.page = await self.context.new_page()
                await self.page.goto(post['link'], timeout=45000)
                await self.page.wait_for_load_state('networkidle', timeout=45000)
                await asyncio.sleep(2)
                # 게시글 상세 페이지가 아니면 스크린샷/삭제 버튼 탐색 모두 생략
                if "/board/view" not in post['link']:
                    print("[DEBUG] delete_post: 링크 패턴 불일치 분기")
                    log_info(f"[delete_post] Invalid post link pattern: {post['link']} -> Skipping.")
                    return False

                current_url = self.page.url
                if "/board/view/" not in current_url and "/board/" not in current_url:
                    print("[DEBUG] delete_post: 상세페이지 아님 분기")
                    log_info(f"[delete_post] Not a post detail page: {current_url} (expected: {post['link']}) -> Skipping delete button search.")
                    ts = int(time.time())
                    
                    with open(f"not_detail_{ts}.html", "w", encoding="utf-8") as f:
                        f.write(await self.page.content())
                    return False
                print("[DEBUG] delete_post: 정상 상세페이지 진입")
                

                # 동영상 포함 게시물 감지 및 삭제 버튼 탐색 최적화
                video_selectors = [
                    'iframe[src*="youtube"]',
                    'iframe[src*="naver"]',
                    'iframe[src*="kakao"]',
                    'video',
                    '.video_area',
                    '.ytp-player'
                ]
                has_video = False
                for selector in video_selectors:
                    if await self.page.query_selector(selector):
                        has_video = True
                        break
                delete_button = None
                delete_selectors = [
                    'button.btn_grey.cancle',
                    "button:has-text('삭제')",
                    "input[type=button][value=삭제]"
                ]
                # 삭제 버튼 탐색/클릭 try-except로 감싸고, detach 발생 시 재탐색
                print("[DEBUG] delete_post: 삭제 버튼 탐색 루프 진입")
                for selector in delete_selectors:
                    try:
                        delete_button = await self.page.query_selector(selector)
                        if delete_button:
                            print(f"[DEBUG] delete_post: 삭제 버튼 발견 및 클릭 시도: {selector}")
                            try:
                                print("[DEBUG] 삭제 버튼 is_enabled:", await delete_button.is_enabled())
                                print("[DEBUG] 삭제 버튼 is_visible:", await delete_button.is_visible())
                                await delete_button.hover()
                                await asyncio.sleep(0.5)
                                await delete_button.focus()
                                await asyncio.sleep(0.2)
                                await self.page.evaluate('(el) => el.click()', delete_button)
                                await asyncio.sleep(0.5)
                                print(f"[DEBUG] 삭제 버튼 (사람처럼) 클릭 후 URL: {self.page.url}")
                                content_snippet = await self.page.content()
                                print(f"[DEBUG] 삭제 버튼 클릭 후 본문 일부: {content_snippet[:300]}")
                                
                                log_info(f"[delete_post] 삭제 버튼 클릭 성공: {selector}")
                                await asyncio.sleep(1)
                                # 삭제 확인 페이지 처리
                                if '/board/delete/' in self.page.url:
                                    print("[DEBUG] delete_post: 정상 삭제 확인 페이지 진입 (최신 네트워크/본문 판정 분기)")
                                    # robust selector for 최종 삭제 버튼
                                    confirm_btn = await self.page.query_selector("button.btn_blue.btn_svc[type=submit]:has-text('삭제')")
                                    if not confirm_btn:
                                        confirm_btn = await self.page.query_selector("input[type=submit][value=삭제], button:has-text('삭제')")
                                    if confirm_btn:
                                        try:
                                            import random
                                            log_info("[delete_post] [delete 페이지] 삭제 확인 버튼 클릭 전 스크린샷 저장")
                                            
                                            # 사람처럼 랜덤 대기
                                            rand_delay1 = random.uniform(1.2, 2.8)
                                            log_info(f"[delete_post] [anti-bot] 삭제 버튼 클릭 전 랜덤 대기: {rand_delay1:.2f}s")
                                            await asyncio.sleep(rand_delay1)
                                            # 마우스 이동
                                            box = await confirm_btn.bounding_box()
                                            if box:
                                                steps = random.randint(8, 20)
                                                await self.page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2, steps=steps)
                                                rand_delay2 = random.uniform(0.1, 0.4)
                                                log_info(f"[delete_post] [anti-bot] 삭제 버튼 마우스 이동 후 대기: {rand_delay2:.2f}s (steps={steps})")
                                                await asyncio.sleep(rand_delay2)
                                            # 클릭 (사람처럼 딜레이)
                                            click_delay = random.randint(80, 180)
                                            log_info(f"[delete_post] [anti-bot] 삭제 버튼 클릭 (delay={click_delay}ms)")
                                            await confirm_btn.click(delay=click_delay)
                                            log_info("[delete_post] 삭제 확인 버튼 클릭 성공 (최종 삭제)")
                                            await asyncio.sleep(0.5)
                                            log_info("[delete_post] [delete 페이지] 삭제 확인 버튼 클릭 후 스크린샷 저장")
                                            
                                            # 버튼 사라졌는지 또는 페이지 이동 확인
                                            gone = False
                                            try:
                                                await confirm_btn.is_visible()
                                            except Exception:
                                                gone = True
                                            if gone:
                                                log_info("[delete_post] 삭제 확인 버튼 클릭 후 버튼이 사라짐 또는 페이지 이동 감지")

                                            log_info("[delete_post] [delete 페이지] 삭제 확인 버튼 클릭 후 서버 반영 대기 (4초)")
                                            # --- 네트워크 응답 감지 ---
                                            delete_response = None
                                            try:
                                                async with self.page.expect_response(
                                                    lambda resp: ('delete' in resp.url or 'remove' in resp.url) and resp.status in [200, 302, 303, 204, 403], timeout=5000
                                                ) as resp_info:
                                                    await confirm_btn.click()
                                                delete_response = await resp_info.value
                                                log_info(f"[delete_post] [network] 삭제 관련 응답 감지: {delete_response.status} {delete_response.url}")
                                                print(f"[delete_post] [network] 삭제 관련 응답 감지: {delete_response.status} {delete_response.url}")
                                                # --- 본문까지 체크 ---
                                                resp_text = ""
                                                try:
                                                    resp_text = await delete_response.text()
                                                except Exception:
                                                    pass
                                                fail_patterns = [
                                                    "삭제할 권한이 없습니다",
                                                    "이미 삭제된 게시물",
                                                    "삭제 실패",
                                                    "not allowed",
                                                    "error",
                                                    "권한이 없습니다",
                                                    "삭제할 수 없습니다"
                                                ]
                                                if any(pat in resp_text for pat in fail_patterns):
                                                    print(f"[delete_post] [network] 삭제 응답 본문에 실패 메시지 감지: {resp_text[:100]}")
                                                    log_info(f"[delete_post] [network] 삭제 응답 본문에 실패 메시지 감지: {resp_text[:100]}")
                                                else:
                                                    print(f"[delete_post] [network] 삭제 응답 본문 OK: {resp_text[:100]}")
                                                    log_info(f"[delete_post] [network] 삭제 응답 본문 OK: {resp_text[:100]}")
                                            except Exception as e:
                                                log_info(f"[delete_post] [network] 삭제 관련 응답 감지 실패: {e}")
                                                print(f"[delete_post] [network] 삭제 관련 응답 감지 실패: {e}")
                                            await asyncio.sleep(4)
                                            # --- 삭제 후 페이지에서 성공/실패 텍스트 직접 확인 ---
                                            page_content = await self.page.content()
                                            success_phrases = [
                                                '삭제되었습니다',
                                                '존재하지 않는 게시물입니다',
                                                '복구할 수 없습니다',
                                                '삭제 처리',
                                                '삭제된 게시물',
                                                '삭제 완료',
                                            ]
                                            detected = None
                                            for phrase in success_phrases:
                                                if phrase in page_content:
                                                    detected = phrase
                                                    break
                                            if detected:
                                                log_info(f"[delete_post] [detect] 삭제 성공 텍스트 감지: '{detected}'")
                                                print(f"[delete_post] [detect] 삭제 성공 텍스트 감지: '{detected}'")
                                            else:
                                                log_info(f"[delete_post] [detect] 삭제 성공 텍스트 미감지. 본문 일부: {page_content[:200]}")
                                                print(f"[delete_post] [detect] 삭제 성공 텍스트 미감지. 본문 일부: {page_content[:200]}")
                                            # 삭제 성공 조건: 네트워크 응답이 200/302/303/204/403 중 하나이거나, 성공 텍스트 감지
                                            delete_success = False
                                            if detected or (delete_response and delete_response.status in [200, 302, 303, 204, 403]):
                                                delete_success = True
                                            if delete_success:
                                                log_info("[delete_post] [RESULT] 삭제 성공 판정")
                                                print("[delete_post] [RESULT] 삭제 성공 판정")
                                                return True
                                            else:
                                                log_info("[delete_post] [RESULT] 삭제 실패 판정")
                                                print("[delete_post] [RESULT] 삭제 실패 판정")
                                                return False
                                        except Exception as click_exc:
                                            log_error(f"[delete_post] 삭제 확인 버튼 클릭 실패: {click_exc}")
                                            
                                            return False
                                        try:
                                            await self.page.wait_for_load_state('networkidle', timeout=10000)
                                        except Exception as e:
                                            log_info(f"[delete_post] wait_for_load_state 예외: {e}")
                                        delete_confirm_time = _time.time()
                                        # 최대 10초 동안 1초 간격으로 삭제 성공 패턴 polling
                                        poll_success = False
                                        poll_count = 0
                                        last_page_content = None
                                        delete_success_patterns = [
                                            "삭제된 게시물", "존재하지 않는 게시물", "없는 게시물", "삭제되었습니다", "삭제 처리되었습니다",
                                            "삭제가 완료되었습니다", "삭제하신 게시물이 존재하지 않습니다", "해당 게시물을 찾을 수 없습니다",
                                            "삭제 또는 이동된 게시물입니다", "삭제된 글입니다"
                                        ]
                                        for poll_count in range(1, 11):
                                            await asyncio.sleep(1)
                                            await self.page.reload()
                                            await asyncio.sleep(0.5)
                                            last_page_content = await self.page.content()
                                            if any(pattern in last_page_content for pattern in delete_success_patterns):
                                                poll_success = True
                                                log_info(f"[delete_post] polling {poll_count}: 삭제 성공 패턴 감지 (즉시 break)")
                                                print(f"\033[96m[delete_post] polling {poll_count}: 삭제 성공 패턴 감지\033[0m")
                                                break
                                            else:
                                                log_info(f"[delete_post] polling {poll_count}: 삭제 성공 패턴 미감지")
                                                print(f"\033[93m[delete_post] polling {poll_count}: 삭제 성공 패턴 미감지\033[0m")
                                        verify_start_time = _time.time()
                                        log_info(f"[delete_post] 삭제 확인~검증 대기 시간: {verify_start_time - delete_confirm_time:.2f}s, polling 횟수: {poll_count}, polling 결과: {'성공' if poll_success else '타임아웃'}")
                                        # polling 마지막 page_content를 아래 검증 로직에서 재활용
                                        page_content = last_page_content if last_page_content is not None else await self.page.content()
                                        if poll_success:
                                            log_info("[delete_post] polling 성공 후 추가 대기 (3초)")
                                            await asyncio.sleep(3)
                                        await asyncio.sleep(0.5)

                                    else:
                                        log_error("[delete_post] 삭제 확인 버튼을 찾지 못함 (최종 삭제 단계)")
                                        
                                        return False
                                # 삭제 후 실제 삭제 여부 검증
                                await self.page.reload()
                                await asyncio.sleep(1)
                                page_content = await self.page.content()
                                delete_success_patterns = [
                                    "삭제된 게시물", "존재하지 않는 게시물", "없는 게시물", "삭제되었습니다", "삭제 처리되었습니다",
                                    "삭제가 완료되었습니다", "삭제하신 게시물이 존재하지 않습니다", "해당 게시물을 찾을 수 없습니다",
                                    "삭제 또는 이동된 게시물입니다", "삭제된 글입니다"
                                ]
                                # 1차: 삭제 패턴 체크
                                deleted = any(pattern in page_content for pattern in delete_success_patterns)
                                # 2차: 실제로 접근해서 본문이 남아있는지 재확인 (최대 3회 polling)
                                is_deleted = False
                                content_area = None
                                from bs4 import BeautifulSoup
                                for verify_attempt in range(1, 4):
                                    await asyncio.sleep(1.5)
                                    log_info(f"[delete_post] 게시글 삭제 검증 재접근 시도 {verify_attempt}/3")
                                    await self.page.goto(post['link'], timeout=20000)
                                    await asyncio.sleep(1)
                                    verify_content = await self.page.content()
                                    is_deleted = any(p in verify_content for p in delete_success_patterns)
                                    soup = BeautifulSoup(verify_content, 'html.parser')
                                    content_area = soup.select_one('.gallview, .write_div, .write_content')
                                    # 삭제 버튼이 또 있으면 반복적으로 삭제 시도
                                    delete_btn_retry = None
                                    for selector in [
                                        'button.btn_grey.cancle',
                                        "button:has-text('삭제')",
                                        "input[type=button][value=삭제]"
                                    ]:
                                        delete_btn_retry = await self.page.query_selector(selector)
                                        if delete_btn_retry:
                                            break
                                    if delete_btn_retry:
                                        log_info(f"[delete_post] 게시글 재접근 {verify_attempt}회차: 삭제 버튼 발견, 반복 삭제 시도")
                                        try:
                                            await delete_btn_retry.click()
                                            log_info(f"[delete_post] 재삭제 버튼 클릭 성공: {selector}")
                                            await asyncio.sleep(1)
                                            # 삭제 확인 버튼도 다시 시도
                                            if '/board/delete/' in self.page.url:
                                                confirm_btn_retry = await self.page.query_selector("input[type=submit][value=삭제], button:has-text('삭제')")
                                                if confirm_btn_retry:
                                                    await confirm_btn_retry.click()
                                                    log_info("[delete_post] 재삭제 확인 버튼 클릭 성공 (최종)")
                                                    try:
                                                        await self.page.wait_for_load_state('networkidle', timeout=10000)
                                                    except Exception as e:
                                                        log_info(f"[delete_post] 재삭제 wait_for_load_state 예외: {e}")
                                                    log_info("[delete_post] 재삭제 후 추가 대기 (4초)")
                                                    await asyncio.sleep(4)
                                                    # 재시도 후 바로 다음 검증으로 넘어감
                                                    continue
                                        except Exception as re_del_e:
                                            log_info(f"[delete_post] 재삭제 버튼 클릭 예외: {re_del_e}")
                                    if (is_deleted or not content_area):
                                        log_info(f"[delete_post] 게시글 검증 {verify_attempt}회차: 삭제 성공 패턴 감지 또는 본문 없음")
                                        break
                                    else:
                                        log_info(f"[delete_post] 게시글 검증 {verify_attempt}회차: 본문 영역 존재, 삭제 미확인")

                                elapsed = _time.time() - _start_time
                                # 확인~검증 대기 시간은 위에서 이미 계산한 verify_start_time - delete_confirm_time 사용
                                confirm_verify_time = 0.0
                                try:
                                    confirm_verify_time = verify_start_time - delete_confirm_time
                                except Exception:
                                    pass
                                if (deleted or is_deleted) and not content_area:
                                    msg = f"[delete_post] [SUCCESS] Post deleted and not accessible: {post['title']} (총소요: {elapsed:.2f}s, 확인~검증: {confirm_verify_time:.2f}s)"
                                    log_info(msg)
                                    print(f"\033[92m{msg}\033[0m")
                                    log_task_end('delete_post', module='DCCleaner')
                                    return True
                                else:
                                    msg = f"[delete_post] [FAIL] Post still exists or accessible after deletion attempt: {post['title']} at {self.page.url} (총소요: {elapsed:.2f}s, 확인~검증: {confirm_verify_time:.2f}s)"
                                    log_error(msg)
                                    print(f"\033[91m{msg}\033[0m")
                                    
                                    log_task_end('delete_post', module='DCCleaner')
                                    return False
                            except Exception as click_e:
                                log_error(f"[delete_post] 삭제 버튼 클릭 예외: {click_e}")
                                # detach 등 예외 발생 시 재탐색
                                continue
                    except Exception as e:
                        log_error(f"[delete_post] 삭제 버튼 탐색 예외: {e}")
                        continue
                # 삭제 버튼 없으면 메타 삭제 시도
                content = await self.page.content()
                import re
                m = re.search(r"goDelete\('([^']+)'\)", content)
                meta_delete_url = m.group(1) if m else None
                if meta_delete_url:
                    try:
                        response = await self.page.request.post(meta_delete_url)
                        log_info(f"[delete_post] 직접 삭제 요청 결과: {response.status}")
                        if response.status == 200:
                            return True
                        else:
                            continue
                    except Exception as e:
                        log_error(f"[delete_post] 직접 삭제 요청 예외: {e}", exc_info=sys.exc_info())
                        continue
                else:
                    log_info(f"[delete_post] 삭제 버튼/삭제 URL 모두 탐색 실패.")
                    continue
            except Exception as e:
                log_error(f"[delete_post] 예외 발생 (attempt {attempt}): {e}", exc_info=sys.exc_info())
                
                if attempt == max_retry:
                    return False
                # 페이지 복구 후 재시도
                try:
                    self.page = await self.context.new_page()
                except Exception as e2:
                    log_error(f"[delete_post] 페이지 복구 실패: {e2}", exc_info=sys.exc_info())
                    return False
        return False

    async def close_resources(self):
        from dc_logger import log_info
        log_info('[CLEANUP] 리소스 정리 시작', module='DCCleaner')
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            log_info(f'[CLEANUP] 리소스 정리 중 예외: {e}', module='DCCleaner')
        log_info('[CLEANUP] 리소스 정리 완료', module='DCCleaner')

    async def cleanup(self, hours_ago: float = 1.0):
        pass

    async def run_delete_loop(self, posts):
        from dc_logger import log_info
        total_attempt = len(posts)
        success_count = 0
        fail_count = 0
        for post in posts:
            # 브라우저/페이지가 닫힌 경우 루프 조기 종료
            if not self.browser or not self.page:
                print("\033[91m[FAIL] 브라우저나 페이지가 닫혀 더 이상 삭제를 진행할 수 없습니다.\033[0m")
                log_info(f"[delete_post] 브라우저나 페이지가 닫혀 더 이상 삭제를 진행할 수 없습니다.", module="DCCleaner")
                break
            try:
                result = await self.delete_post(post)
                if result:
                    success_count += 1
                    print(f"\033[92m[SUCCESS] Deleted: {post['title']} | {post.get('link', '')}\033[0m")
                    log_info(f"[delete_post] SUCCESS: {post['title']} | {post.get('link', '')}", module="DCCleaner")
                else:
                    fail_count += 1
                    print(f"\033[91m[FAIL] Failed to delete: {post['title']} | {post.get('link', '')}\033[0m")
                    log_info(f"[delete_post] FAIL: {post['title']} | {post.get('link', '')}", module="DCCleaner")
            except Exception as e:
                fail_count += 1
                err_msg = str(e)
                print("\033[91m[FAIL] Unhandled exception in delete_post: {}\033[0m".format(e))
                log_info(f"[delete_post] FAIL (Exception): {post['title']} | {post.get('link', '')} | {e}", module="DCCleaner")
                with open('error_log.txt', 'a', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {post['title']} | {getattr(self.page, 'url', 'unknown')} | {type(e).__name__}: {e}\n")
                # TargetClosedError 또는 page가 닫혔다는 메시지가 포함되면 루프 중단
                if "TargetClosedError" in err_msg or "context or browser has been closed" in err_msg or "browser has been closed" in err_msg:
                    print("\033[91m[FAIL] 브라우저가 닫혀 삭제 루프를 중단합니다.\033[0m")
                    log_info(f"[delete_post] 브라우저가 닫혀 삭제 루프를 중단합니다.", module="DCCleaner")
                    break
        print(f"\033[94m[INFO] 모든 삭제 시도 완료. 총 시도: {total_attempt}, 성공: {success_count}, 실패: {fail_count}\033[0m")
        log_info(f"[delete_post] 모든 삭제 시도 완료. 총 시도: {total_attempt}, 성공: {success_count}, 실패: {fail_count}", module="DCCleaner")

        try:
            await self.init_browser()
            await self.login()
            
            posts = await self.get_posts_from_gallog(hours_ago)
            print(f"Found {len(posts)} posts older than {hours_ago} hours")
            
            for post in posts:
                success = await self.delete_post(post)
                if success:
                    print(f"Successfully deleted: {post['title']}")
                else:
                    print(f"Failed to delete: {post['title']}")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            if self.browser:
                await self.browser.close()

async def main():
    cleaner = DCCleaner()
    await cleaner.init_browser()
    await cleaner.login()
    posts = await cleaner.get_posts_from_gallog(hours_ago=1.0)
    await cleaner.run_delete_loop(posts)
    if cleaner.browser:
        await cleaner.browser.close()

if __name__ == "__main__":
    async def safe_main():
        cleaner = DCCleaner()
        try:
            await cleaner.init_browser()
            await cleaner.login()
            total_deleted = 0
            batch_num = 1
            while True:
                try:
                    # 더 많은 게시물을 한 번에 삭제 (최대한 오래된 글까지)
                    posts = await cleaner.get_posts_from_gallog(hours_ago=10000.0)
                    if not posts:
                        print("No more posts to delete.")
                        break
                    print(f"[Batch {batch_num}] Found {len(posts)} posts to delete.")
                    for post in posts:
                        try:
                            success = await cleaner.delete_post(post)
                            if success:
                                print(f"[Batch {batch_num}] Successfully deleted: {post['title']}")
                                total_deleted += 1
                            else:
                                print(f"[Batch {batch_num}] Failed to delete: {post['title']}")
                        except Exception as post_err:
                            print(f"[Batch {batch_num}] Error deleting post: {post['title']} | {post_err}")
                    print(f"[Batch {batch_num}] Batch completed. Total deleted so far: {total_deleted}")
                    batch_num += 1
                except Exception as batch_err:
                    print(f"[Batch {batch_num}] Error in batch: {batch_err}")
                    # 예외 발생 시에도 루프를 중단하지 않고 다음 반복 진행
                    batch_num += 1
            print(f"\n[RESULT] 실행 종료 - 이번 실행에서 총 {total_deleted}개의 게시물을 삭제했습니다.")
        finally:
            await cleaner.close_resources()
    try:
        asyncio.run(safe_main())
    except RuntimeError as e:
        if str(e) != 'Event loop is closed':
            raise
        # Windows에서 발생하는 종료 시 RuntimeError 무시
    except Exception as e:
        print(f"[ERROR] 프로그램 종료 중 예외 발생: {e}")
    finally:
        import sys
        sys.exit(0)
