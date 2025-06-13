import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from flask import Flask, jsonify
import threading

# 환경변수에서 네이버 로그인 정보 가져오기
NAVER_ID = os.getenv("NAVER_ID", "your_naver_id")
NAVER_PASSWORD = os.getenv("NAVER_PASSWORD", "your_password")
CAFE_ID = os.getenv("CAFE_ID", "30169141")

# Flask 앱 생성
app = Flask(__name__)

# 결과를 저장할 전역 변수
latest_results = {"status": "not_started", "data": None, "timestamp": None}

class NaverLogin:
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        
    async def start_browser(self, headless=True):
        """브라우저 시작"""
        playwright = await async_playwright().start()
        
        # Railway에서 실행하기 위한 브라우저 옵션
        browser_options = {
            'headless': headless,
            'args': [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-first-run',
                '--disable-extensions',
                '--disable-default-apps'
            ]
        }
        
        # 브라우저 실행
        self.browser = await playwright.chromium.launch(**browser_options)
        
        # 새 컨텍스트 생성 (쿠키, 세션 등을 저장)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 새 페이지 생성
        self.page = await self.context.new_page()
        print("브라우저가 시작되었습니다.")
        
    async def login_naver(self, username, password):
        """네이버 로그인"""
        try:
            print("네이버 로그인 페이지로 이동 중...")
            await self.page.goto('https://nid.naver.com/nidlogin.login')
            
            # 로그인 폼이 로드될 때까지 대기
            await self.page.wait_for_selector('#id', timeout=10000)
            print("로그인 페이지 로드 완료!")
            
            # 아이디 입력
            print("아이디 입력 중...")
            await self.page.fill('#id', username)
            await asyncio.sleep(1)
            
            # 비밀번호 입력
            print("비밀번호 입력 중...")
            await self.page.fill('#pw', password)
            await asyncio.sleep(1)
            
            # 로그인 버튼 클릭
            print("로그인 버튼 클릭...")
            await self.page.click('#log\\.login')
            
            # 로그인 처리 대기
            await asyncio.sleep(3)
            
            # 현재 URL 확인하여 로그인 상태 체크
            current_url = self.page.url
            print(f"현재 URL: {current_url}")
            
            # 2단계 인증이나 추가 인증이 필요한 경우
            if 'auth' in current_url or 'login' in current_url:
                print("추가 인증이 필요합니다. 자동 로그인 실패.")
                return False
                        
            # 로그인 성공 확인
            if 'naver.com' in current_url and 'login' not in current_url:
                print("✓ 네이버 로그인 성공!")
                return True
            else:
                print("✗ 로그인 실패")
                return False
                
        except Exception as e:
            print(f"✗ 로그인 중 오류 발생: {e}")
            return False
    
    async def close(self):
        """브라우저 종료"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            print("브라우저가 종료되었습니다.")
        except Exception as e:
            print(f"브라우저 종료 중 오류: {e}")

    async def get_cafe_comment_stats(self, start_date=None):
        """카페 댓글 통계 수집"""
        try:
            if not start_date:
                today = datetime.now()
                if today.month == 1:
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    last_month = today.replace(month=today.month - 1, day=1)
                start_date = last_month.strftime('%Y-%m-%d')
            
            print(f"댓글 통계 수집 중... (기준일: {start_date})")
            
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
            return None
                
        except Exception as e:
            print(f"댓글 통계 수집 중 오류: {e}")
            return None

    def parse_comment_stats(self, data):
        """댓글 데이터 파싱"""
        try:
            stats = {'comments': [], 'collected_at': datetime.now().isoformat()}
            
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                if 'statData' in result and result['statData']:
                    stat_data = result['statData'][0]['data']
                    rows = stat_data.get('rows', {})
                    
                    if isinstance(rows, dict):
                        member_ids = rows.get('v', [])
                        counts = rows.get('cnt', [])
                        ranks = rows.get('rank', [])
                        member_infos_nested = rows.get('memberInfos', [[]])
                        member_infos = member_infos_nested[0] if member_infos_nested else []
                        
                        collected_members = []
                        for i in range(min(len(member_ids), 3)):  # 상위 3명만
                            try:
                                member_id = member_ids[i]
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
                                    if nick_name == '수산나' or member_level == '제휴업체':
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'comment_count': count
                                    }
                                    collected_members.append(member_data)
                            except Exception as e:
                                continue
                        
                        stats['comments'] = collected_members
            
            return stats
        except Exception as e:
            print(f"댓글 데이터 파싱 오류: {e}")
            return None

    async def get_cafe_stats(self, start_date=None):
        """카페 게시글 통계 수집"""
        try:
            if not start_date:
                today = datetime.now()
                if today.month == 1:
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    last_month = today.replace(month=today.month - 1, day=1)
                start_date = last_month.strftime('%Y-%m-%d')
            
            print(f"게시글 통계 수집 중... (기준일: {start_date})")
            
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
                return self.parse_member_stats(json_data)
            return None
                
        except Exception as e:
            print(f"게시글 통계 수집 중 오류: {e}")
            return None
    
    def parse_member_stats(self, data):
        """게시글 데이터 파싱"""
        try:
            stats = {'posts': [], 'collected_at': datetime.now().isoformat()}
            
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                if 'statData' in result and result['statData']:
                    stat_data = result['statData'][0]['data']
                    rows = stat_data.get('rows', {})
                    
                    if isinstance(rows, dict):
                        member_ids = rows.get('v', [])
                        counts = rows.get('cnt', [])
                        ranks = rows.get('rank', [])
                        member_infos_nested = rows.get('memberInfos', [[]])
                        member_infos = member_infos_nested[0] if member_infos_nested else []
                        
                        collected_members = []
                        for i in range(min(len(member_ids), 5)):  # 상위 5명만
                            try:
                                member_id = member_ids[i]
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
                                    if nick_name == '수산나' or member_level == '제휴업체':
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'post_count': count
                                    }
                                    collected_members.append(member_data)
                            except Exception as e:
                                continue
                        
                        stats['posts'] = collected_members
            
            return stats
        except Exception as e:
            print(f"게시글 데이터 파싱 오류: {e}")
            return None

# 백그라운드에서 크롤링 실행
async def run_crawler():
    global latest_results
    
    try:
        latest_results["status"] = "running"
        latest_results["timestamp"] = datetime.now().isoformat()
        
        login_manager = NaverLogin()
        await login_manager.start_browser(headless=True)
        
        # 환경변수 확인
        if not NAVER_ID or NAVER_ID == "your_naver_id":
            latest_results["status"] = "error"
            latest_results["data"] = "NAVER_ID 환경변수가 설정되지 않았습니다"
            return
        
        if not NAVER_PASSWORD or NAVER_PASSWORD == "your_password":
            latest_results["status"] = "error"
            latest_results["data"] = "NAVER_PASSWORD 환경변수가 설정되지 않았습니다"
            return
        
        # 로그인
        success = await login_manager.login_naver(NAVER_ID, NAVER_PASSWORD)
        
        if success:
            # 통계 수집
            post_stats = await login_manager.get_cafe_stats()
            comment_stats = await login_manager.get_cafe_comment_stats()
            
            combined_stats = {
                'posts': post_stats['posts'] if post_stats else [],
                'comments': comment_stats['comments'] if comment_stats else [],
                'collected_at': datetime.now().isoformat()
            }
            
            latest_results["status"] = "completed"
            latest_results["data"] = combined_stats
        else:
            latest_results["status"] = "error"
            latest_results["data"] = "네이버 로그인에 실패했습니다"
        
        await login_manager.close()
        
    except Exception as e:
        latest_results["status"] = "error"
        latest_results["data"] = str(e)

def run_crawler_sync():
    """동기 함수에서 비동기 크롤러 실행"""
    asyncio.run(run_crawler())

# Flask 라우트
@app.route('/')
def home():
    return jsonify({
        "message": "네이버 카페 크롤러 API",
        "endpoints": {
            "/status": "크롤링 상태 확인",
            "/run": "크롤링 실행",
            "/results": "최신 결과 조회"
        }
    })

@app.route('/status')
def status():
    return jsonify(latest_results)

@app.route('/run')
def run_crawler_endpoint():
    # 백그라운드에서 크롤링 실행
    thread = threading.Thread(target=run_crawler_sync)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "message": "크롤링이 시작되었습니다",
        "status": "started"
    })

@app.route('/results')
def get_results():
    return jsonify(latest_results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
