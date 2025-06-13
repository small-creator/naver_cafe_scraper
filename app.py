# ========== 기존 app.py에서 이 부분들만 수정하세요 ==========

# 1. 상단 import 부분은 그대로 유지
import requests
import json
import schedule
import time
import threading
import asyncio
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
from playwright.async_api import async_playwright

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 한글 제대로 출력

# 데이터 저장용 (그대로 유지)
collected_nicknames = []
member_rankings = {'posts': [], 'comments': [], 'last_updated': None}

# 네이버 카페 설정 (그대로 유지)
CAFE_ID = "30169141"  # 강동맘 카페 ID

# ========== 여기서부터 NaverCafeManager 클래스만 교체 ==========
class NaverCafeManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        
        # Browserless 설정 - Railway 환경변수에서 가져오기
        self.browserless_public_domain = os.environ.get('BROWSERLESS_PUBLIC_DOMAIN', '')
        self.browserless_token = os.environ.get('BROWSERLESS_TOKEN', '')
        
        # 연결 URL 구성
        if self.browserless_public_domain:
            self.playwright_endpoint = f"wss://{self.browserless_public_domain}/playwright?token={self.browserless_token}"
            self.http_endpoint = f"https://{self.browserless_public_domain}"
        else:
            self.playwright_endpoint = None
            self.http_endpoint = None
        
    async def start_browser(self, headless=True):
        """Browserless 서비스에 연결"""
        try:
            self.playwright = await async_playwright().start()
            
            # 방법 1: 직접 Playwright WebSocket 연결 (권장)
            if self.playwright_endpoint:
                print(f"Browserless 연결 중: {self.playwright_endpoint}")
                
                try:
                    self.browser = await self.playwright.chromium.connect_over_cdp(
                        self.playwright_endpoint
                    )
                    print("✅ Browserless 연결 성공!")
                    
                except Exception as e:
                    print(f"❌ Browserless 연결 실패: {e}")
                    # 로컬 브라우저로 fallback
                    return await self.start_browser_local(headless)
            
            else:
                # 로컬 브라우저 사용
                return await self.start_browser_local(headless)
            
            # 컨텍스트 및 페이지 생성
            await self.setup_browser_context()
            return True
            
        except Exception as e:
            print(f"브라우저 시작 실패: {e}")
            return await self.start_browser_local(headless)
    
    async def start_browser_local(self, headless=True):
        """로컬 브라우저 사용 (fallback)"""
        try:
            print("🔄 로컬 브라우저 사용")
            
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            await self.setup_browser_context()
            print("✅ 로컬 브라우저 연결 성공!")
            return True
            
        except Exception as e:
            print(f"❌ 로컬 브라우저 실패: {e}")
            return False
    
    async def setup_browser_context(self):
        """브라우저 컨텍스트 및 페이지 설정"""
        self.context = await self.browser.new_context(
            viewport={'width': 1024, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        self.page = await self.context.new_page()

    # ========== 나머지 메서드들은 기존과 동일하게 유지 ==========
    async def login_naver(self, username, password):
        """네이버 로그인 (기존 코드 그대로)"""
        try:
            await self.page.goto('https://nid.naver.com/nidlogin.login')
            await self.page.wait_for_selector('#id', timeout=10000)
            
            await self.page.fill('#id', username)
            await asyncio.sleep(1)
            await self.page.fill('#pw', password)
            await asyncio.sleep(1)
            
            await self.page.click('#log\\.login')
            await asyncio.sleep(3)
            
            current_url = self.page.url
            
            # 추가 인증 대기
            if 'auth' in current_url or 'login' in current_url:
                print("추가 인증이 필요합니다. 대기 중...")
                timeout_count = 0
                while timeout_count < 30:  # 최대 1분 대기
                    await asyncio.sleep(2)
                    current_url = self.page.url
                    if 'naver.com' in current_url and 'login' not in current_url and 'auth' not in current_url:
                        break
                    timeout_count += 1
                        
            if 'naver.com' in current_url and 'login' not in current_url:
                print("로그인 성공!")
                return True
            else:
                print("로그인 실패")
                return False
                
        except Exception as e:
            print(f"로그인 오류: {e}")
            return False

    async def get_post_rankings(self, start_date=None):
        """게시글 멤버 순위 가져오기 (기존 코드 그대로)"""
        # ... 기존 코드 그대로 복사 ...
        try:
            if not start_date:
                today = datetime.now()
                if today.month == 1:
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    last_month = today.replace(month=today.month - 1, day=1)
                start_date = last_month.strftime('%Y-%m-%d')
            
            api_url = (
                f"https://cafe.stat.naver.com/api/cafe/{CAFE_ID}/rank/memberCreate"
                f"?service=CAFE&timeDimension=MONTH&startDate={start_date}"
                f"&memberId=%EB%A9%A4%EB%B2%84&exclude=member%2Cboard%2CdashBoard"
            )
            
            await self.page.goto(api_url)
            await asyncio.sleep(2)
            
            json_data = await self.page.evaluate('''() => {
                try {
                    const pre = document.querySelector('pre');
                    if (pre) {
                        return JSON.parse(pre.textContent);
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            }''')
            
            if json_data:
                return self.parse_post_stats(json_data)
            else:
                return []
                
        except Exception as e:
            print(f"게시글 순위 조회 오류: {e}")
            return []
    
    def parse_post_stats(self, data):
        """게시글 API 응답 데이터 파싱 (기존 코드 그대로)"""
        # ... 기존 parse_post_stats 메서드 그대로 복사 ...
        try:
            collected_members = []
            
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                
                if 'statData' in result and isinstance(result['statData'], list) and len(result['statData']) > 0:
                    stat_data = result['statData'][0]['data']
                    rows = stat_data.get('rows', {})
                    
                    if isinstance(rows, dict):
                        member_ids = rows.get('v', [])
                        counts = rows.get('cnt', [])
                        ranks = rows.get('rank', [])
                        member_infos_nested = rows.get('memberInfos', [[]])
                        
                        member_infos = member_infos_nested[0] if member_infos_nested and len(member_infos_nested) > 0 else []
                        
                        for i in range(min(len(member_ids), 5)):  # 상위 5명
                            try:
                                member_id = member_ids[i] if i < len(member_ids) else ''
                                count = counts[i] if i < len(counts) else 0
                                rank = ranks[i] if i < len(ranks) else i + 1
                                
                                member_info = None
                                for info in member_infos:
                                    if info and info.get('idNo') == member_id:
                                        member_info = info
                                        break
                                
                                if member_info and member_info.get('nickName'):
                                    nick_name = member_info.get('nickName', '')
                                    member_level = member_info.get('memberLevelName', '')
                                    
                                    # 제외 조건
                                    should_exclude = (
                                        nick_name == '수산나' or 
                                        member_level == '제휴업체'
                                    )
                                    
                                    if should_exclude:
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'post_count': count,
                                        'memberLevel': member_level
                                    }
                                    
                                    collected_members.append(member_data)
                                
                            except Exception as e:
                                continue
            
            return collected_members[:5]  # 최대 5명
            
        except Exception as e:
            print(f"게시글 데이터 파싱 오류: {e}")
            return []

    async def get_comment_rankings(self, start_date=None):
        """댓글 멤버 순위 가져오기 (기존 코드 그대로)"""
        # ... 기존 get_comment_rankings 메서드 그대로 복사 ...
        try:
            if not start_date:
                today = datetime.now()
                if today.month == 1:
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    last_month = today.replace(month=today.month - 1, day=1)
                start_date = last_month.strftime('%Y-%m-%d')
            
            api_url = (
                f"https://cafe.stat.naver.com/api/cafe/{CAFE_ID}/rank/memberComment"
                f"?service=CAFE&timeDimension=MONTH&startDate={start_date}"
                f"&memberId=%EB%A9%A4%EB%B2%84&exclude=member%2Cboard%2CdashBoard"
            )
            
            await self.page.goto(api_url)
            await asyncio.sleep(2)
            
            json_data = await self.page.evaluate('''() => {
                try {
                    const pre = document.querySelector('pre');
                    if (pre) {
                        return JSON.parse(pre.textContent);
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            }''')
            
            if json_data:
                return self.parse_comment_stats(json_data)
            else:
                return []
                
        except Exception as e:
            print(f"댓글 순위 조회 오류: {e}")
            return []

    def parse_comment_stats(self, data):
        """댓글 API 응답 데이터 파싱 (기존 코드 그대로)"""
        # ... 기존 parse_comment_stats 메서드 그대로 복사 ...
        try:
            collected_members = []
            
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                
                if 'statData' in result and isinstance(result['statData'], list) and len(result['statData']) > 0:
                    stat_data = result['statData'][0]['data']
                    rows = stat_data.get('rows', {})
                    
                    if isinstance(rows, dict):
                        member_ids = rows.get('v', [])
                        counts = rows.get('cnt', [])
                        ranks = rows.get('rank', [])
                        member_infos_nested = rows.get('memberInfos', [[]])
                        
                        member_infos = member_infos_nested[0] if member_infos_nested and len(member_infos_nested) > 0 else []
                        
                        for i in range(min(len(member_ids), 3)):  # 상위 3명
                            try:
                                member_id = member_ids[i] if i < len(member_ids) else ''
                                count = counts[i] if i < len(counts) else 0
                                rank = ranks[i] if i < len(ranks) else i + 1
                                
                                member_info = None
                                for info in member_infos:
                                    if info and info.get('idNo') == member_id:
                                        member_info = info
                                        break
                                
                                if member_info and member_info.get('nickName'):
                                    nick_name = member_info.get('nickName', '')
                                    member_level = member_info.get('memberLevelName', '')
                                    
                                    # 제외 조건
                                    should_exclude = (
                                        nick_name == '수산나' or 
                                        member_level == '제휴업체'
                                    )
                                    
                                    if should_exclude:
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'comment_count': count,
                                        'memberLevel': member_level
                                    }
                                    
                                    collected_members.append(member_data)
                                
                            except Exception as e:
                                continue
            
            return collected_members[:3]  # 최대 3명
            
        except Exception as e:
            print(f"댓글 데이터 파싱 오류: {e}")
            return []

    async def close(self):
        """브라우저 종료 (기존 코드 그대로)"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            pass

# ========== 나머지 모든 함수와 Flask 라우트들은 그대로 유지 ==========

# fetch_member_rankings 함수 (그대로 유지)
async def fetch_member_rankings():
    # ... 기존 코드 그대로 ...

# run_async_task 함수 (그대로 유지)
def run_async_task(coro):
    # ... 기존 코드 그대로 ...

# fetch_nicknames 함수 (그대로 유지)
def fetch_nicknames():
    # ... 기존 코드 그대로 ...

# run_scheduler 함수 (그대로 유지)
def run_scheduler():
    # ... 기존 코드 그대로 ...

# ========== Flask 라우트들 모두 그대로 유지 ==========
@app.route('/')
def dashboard():
    # ... 기존 코드 그대로 ...

@app.route('/api/status')
def api_status():
    # ... 기존 코드 그대로 ...

# ... 나머지 모든 라우트들 그대로 ...

if __name__ == "__main__":
    # ... 기존 코드 그대로 ...
