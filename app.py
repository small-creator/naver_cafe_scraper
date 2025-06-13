import requests
import json
import schedule
import time
import threading
import asyncio
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify

# Playwright import with error handling
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
    print("✅ Playwright 모듈 로드 성공")
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright 모듈이 없습니다. 멤버 순위 기능은 비활성화됩니다.")

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 전역 변수
collected_nicknames = []
member_rankings = {'posts': [], 'comments': [], 'last_updated': None}
CAFE_ID = "30169141"

def fetch_nicknames():
    """네이버 카페에서 닉네임 수집"""
    global collected_nicknames
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 닉네임 수집 시작...")
        
        api_url = "https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/30169141/menus/79/articles"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://cafe.naver.com/'
        }
        
        params = {'pageSize': 15}
        response = requests.get(api_url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            nicknames = []
            
            if 'result' in data and 'articleList' in data['result']:
                article_list = data['result']['articleList']
                
                for article_data in article_list:
                    if (isinstance(article_data, dict) and 
                        'item' in article_data and 
                        'writerInfo' in article_data['item']):
                        
                        writer_info = article_data['item']['writerInfo']
                        nickname = writer_info.get('nickName')
                        
                        if nickname and nickname not in nicknames:
                            nicknames.append(nickname)
                            if len(nicknames) >= 5:
                                break
                
                new_entry = {
                    'nicknames': nicknames,
                    'collected_at': datetime.now().isoformat(),
                    'count': len(nicknames)
                }
                
                collected_nicknames.append(new_entry)
                
                if len(collected_nicknames) > 10:
                    collected_nicknames.pop(0)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ {len(nicknames)}개 닉네임 수집 완료")
                return True
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 수집 실패")
        return False
        
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 오류: {e}")
        return False

def run_scheduler():
    """스케줄러 실행"""
    schedule.every().hour.do(fetch_nicknames)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==================== Browserless NaverCafeManager 클래스 ====================
class NaverCafeManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        
        # Browserless 설정
        self.browserless_domain = os.environ.get('BROWSERLESS_PUBLIC_DOMAIN', '')
        self.browserless_token = os.environ.get('BROWSERLESS_TOKEN', '')
        
        if self.browserless_domain:
            self.playwright_endpoint = f"wss://{self.browserless_domain}/playwright?token={self.browserless_token}"
        else:
            self.playwright_endpoint = None
        
    async def start_browser(self):
        """Browserless 서비스에 연결"""
        if not PLAYWRIGHT_AVAILABLE:
            print("❌ Playwright 모듈이 설치되지 않았습니다")
            return False
            
        try:
            self.playwright = await async_playwright().start()
            
            if self.playwright_endpoint:
                print(f"🔗 Browserless 연결 중: {self.browserless_domain}")
                
                try:
                    self.browser = await self.playwright.chromium.connect_over_cdp(
                        self.playwright_endpoint
                    )
                    print("✅ Browserless 연결 성공!")
                    
                except Exception as e:
                    print(f"❌ Browserless 연결 실패: {e}")
                    print("🔄 로컬 브라우저로 fallback...")
                    return await self.start_local_browser()
            else:
                print("🔄 Browserless 설정이 없어 로컬 브라우저 사용")
                return await self.start_local_browser()
            
            # 컨텍스트 설정
            await self.setup_browser_context()
            return True
            
        except Exception as e:
            print(f"❌ 브라우저 시작 실패: {e}")
            return False
    
    async def start_local_browser(self):
        """로컬 브라우저 사용 (fallback)"""
        try:
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            await self.setup_browser_context()
            print("✅ 로컬 브라우저 시작 성공")
            return True
        except Exception as e:
            print(f"❌ 로컬 브라우저 시작 실패: {e}")
            return False
    
    async def setup_browser_context(self):
        """브라우저 컨텍스트 설정"""
        self.context = await self.browser.new_context(
            viewport={'width': 1024, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()

    async def login_naver(self, username, password):
        """네이버 로그인"""
        try:
            print("🔐 네이버 로그인 시작...")
            
            await self.page.goto('https://nid.naver.com/nidlogin.login')
            await self.page.wait_for_selector('#id', timeout=10000)
            
            await self.page.fill('#id', username)
            await asyncio.sleep(1)
            await self.page.fill('#pw', password)
            await asyncio.sleep(1)
            
            await self.page.click('#log\\.login')
            await asyncio.sleep(3)
            
            current_url = self.page.url
            
            # 추가 인증 처리
            if 'auth' in current_url or 'login' in current_url:
                print("⏳ 추가 인증 대기 중...")
                timeout_count = 0
                while timeout_count < 30:
                    await asyncio.sleep(2)
                    current_url = self.page.url
                    if 'naver.com' in current_url and 'login' not in current_url and 'auth' not in current_url:
                        break
                    timeout_count += 1
            
            if 'naver.com' in current_url and 'login' not in current_url:
                print("✅ 네이버 로그인 성공!")
                return True
            else:
                print("❌ 네이버 로그인 실패")
                return False
                
        except Exception as e:
            print(f"❌ 로그인 오류: {e}")
            return False

    async def get_post_rankings(self, start_date=None):
        """게시글 멤버 순위 가져오기"""
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
            print(f"❌ 게시글 순위 조회 오류: {e}")
            return []
    
    def parse_post_stats(self, data):
        """게시글 API 응답 데이터 파싱"""
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
                        
                        for i in range(min(len(member_ids), 5)):
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
            
            return collected_members[:5]
            
        except Exception as e:
            print(f"❌ 게시글 데이터 파싱 오류: {e}")
            return []

    async def get_comment_rankings(self, start_date=None):
        """댓글 멤버 순위 가져오기"""
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
            print(f"❌ 댓글 순위 조회 오류: {e}")
            return []

    def parse_comment_stats(self, data):
        """댓글 API 응답 데이터 파싱"""
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
                        
                        for i in range(min(len(member_ids), 3)):
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
            
            return collected_members[:3]
            
        except Exception as e:
            print(f"❌ 댓글 데이터 파싱 오류: {e}")
            return []

    async def close(self):
        """브라우저 종료"""
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
            print(f"브라우저 종료 오류: {e}")

# ==================== 비동기 작업 함수들 ====================
async def fetch_member_rankings():
    """멤버 순위 조회 (비동기)"""
    global member_rankings
    
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright가 설치되지 않아 멤버 순위 조회를 할 수 없습니다")
        return False
    
    naver_manager = NaverCafeManager()
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🏆 멤버 순위 조회 시작...")
        
        # 브라우저 시작
        if not await naver_manager.start_browser():
            print("❌ 브라우저 시작 실패")
            return False
        
        # 환경변수에서 로그인 정보 가져오기
        username = os.environ.get('NAVER_USERNAME', '')
        password = os.environ.get('NAVER_PASSWORD', '')
        
        if not username or not password:
            print("❌ 네이버 로그인 정보가 설정되지 않았습니다")
            return False
        
        # 로그인
        if not await naver_manager.login_naver(username, password):
            print("❌ 로그인 실패")
            return False
        
        # 게시글 순위 조회
        print("📊 게시글 순위 조회 중...")
        post_rankings = await naver_manager.get_post_rankings()
        
        # 댓글 순위 조회
        print("💬 댓글 순위 조회 중...")
        comment_rankings = await naver_manager.get_comment_rankings()
        
        # 결과 저장
        member_rankings['posts'] = post_rankings
        member_rankings['comments'] = comment_rankings
        member_rankings['last_updated'] = datetime.now().isoformat()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 멤버 순위 조회 완료")
        print(f"📊 게시글 순위: {len(post_rankings)}명, 💬 댓글 순위: {len(comment_rankings)}명")
        
        return True
        
    except Exception as e:
        print(f"❌ 멤버 순위 조회 오류: {e}")
        return False
    finally:
        await naver_manager.close()

def run_async_task(coro):
    """비동기 작업을 동기적으로 실행"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    except Exception as e:
        print(f"❌ 비동기 작업 실행 오류: {e}")
        return False
    finally:
        try:
            loop.close()
        except:
            pass

# ==================== Flask 라우트들 ====================

@app.route('/')
def dashboard():
    """메인 페이지"""
    if os.environ.get('DISABLED') == 'true':
        return '<h1>🔧 서비스 일시 중지됨</h1>'
    
    return jsonify({
        "status": "running",
        "message": "네이버 카페 닉네임 수집 서비스",
        "version": "v3.0 (Browserless 통합 완료)",
        "features": {
            "nickname_collection": "✅ 활성화",
            "member_rankings": "✅ 활성화" if PLAYWRIGHT_AVAILABLE else "⚠️ Playwright 필요",
            "browserless_integration": "✅ 준비됨" if os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') else "⚠️ 설정 필요"
        },
        "endpoints": {
            "main": "/",
            "status": "/api/status",
            "nicknames": "/nicknames", 
            "collect": "/collect-now",
            "rankings": "/api/rankings",
            "fetch_rankings": "/fetch-rankings",
            "health": "/health"
        }
    })

@app.route('/api/status')
def api_status():
    """상태 API"""
    total_collections = len(collected_nicknames)
    last_collection = collected_nicknames[-1] if collected_nicknames else None
    
    total_nicknames = sum(entry['count'] for entry in collected_nicknames)
    unique_nicknames = set()
    for entry in collected_nicknames:
        unique_nicknames.update(entry['nicknames'])
    
    return app.response_class(
        response=json.dumps({
            "status": "running",
            "total_collections": total_collections,
            "total_nicknames": total_nicknames,
            "unique_nicknames": len(unique_nicknames),
            "last_collection": last_collection['collected_at'] if last_collection else None,
            "recent_nicknames": last_collection['nicknames'] if last_collection else [],
            "member_rankings": member_rankings,
            "environment_status": {
                "browserless_domain": "SET" if os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') else "NOT_SET",
                "browserless_token": "SET" if os.environ.get('BROWSERLESS_TOKEN') else "NOT_SET",
                "naver_credentials": "SET" if (os.environ.get('NAVER_USERNAME') and os.environ.get('NAVER_PASSWORD')) else "NOT_SET"
            },
            "capabilities": {
                "playwright_available": PLAYWRIGHT_AVAILABLE,
                "can_fetch_rankings": PLAYWRIGHT_AVAILABLE and bool(os.environ.get('NAVER_USERNAME')) and bool(os.environ.get('NAVER_PASSWORD')),
                "browserless_configured": bool(os.environ.get('BROWSERLESS_PUBLIC_DOMAIN')) and bool(os.environ.get('BROWSERLESS_TOKEN'))
            }
        }, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/nicknames')
def get_latest_nicknames():
    """최근 닉네임 조회"""
    if collected_nicknames:
        latest = collected_nicknames[-1]
        response = {
            "success": True,
            "nicknames": latest['nicknames'],
            "collected_at": latest['collected_at'],
            "count": latest['count']
        }
    else:
        response = {
            "success": False,
            "message": "아직 수집된 닉네임이 없습니다",
            "nicknames": []
        }
    
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/all-nicknames')
def get_all_nicknames():
    """모든 수집 기록 조회"""
    response = {
        "success": True,
        "collections": collected_nicknames,
        "total_collections": len(collected_nicknames)
    }
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/collect-now')
def collect_now():
    """수동 수집"""
    success = fetch_nicknames()
    
    if success and collected_nicknames:
        latest = collected_nicknames[-1]
        response = {
            "success": True,
            "message": "수집 완료!",
            "nicknames": latest['nicknames'],
            "count": latest['count']
        }
    else:
        response = {
            "success": False,
            "message": "수집 실패"
        }
    
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/api/rankings')
def get_rankings():
    """멤버 순위 조회 API"""
    return app.response_class(
        response=json.dumps({
            "rankings": member_rankings,
            "playwright_available": PLAYWRIGHT_AVAILABLE,
            "can_fetch_rankings": PLAYWRIGHT_AVAILABLE and bool(os.environ.get('NAVER_USERNAME')) and bool(os.environ.get('NAVER_PASSWORD')),
            "browserless_status": {
                "domain_configured": bool(os.environ.get('BROWSERLESS_PUBLIC_DOMAIN')),
                "token_configured": bool(os.environ.get('BROWSERLESS_TOKEN'))
            },
            "endpoints": {
                "manual_fetch": "/fetch-rankings",
                "rankings_data": "/api/rankings"
            },
            "instructions": "Playwright가 설치된 경우 /fetch-rankings 엔드포인트로 실제 순위를 조회할 수 있습니다."
        }, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/fetch-rankings')
def fetch_rankings_manual():
    """수동으로 멤버 순위 조회"""
    if not PLAYWRIGHT_AVAILABLE:
        return app.response_class(
            response=json.dumps({
                "success": False,
                "message": "Playwright 모듈이 설치되지 않았습니다.",
                "solution": "requirements.txt에 playwright==1.40.0을 추가하고 재배포하세요.",
                "current_requirements": [
                    "Flask==2.3.3",
                    "requests==2.31.0", 
                    "schedule==1.2.0",
                    "gunicorn==21.2.0",
                    "playwright==1.40.0  # ← 이 줄을 추가하세요"
                ]
            }, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
    
    # 환경변수 체크
    if not os.environ.get('NAVER_USERNAME') or not os.environ.get('NAVER_PASSWORD'):
        return app.response_class(
            response=json.dumps({
                "success": False,
                "message": "네이버 로그인 정보가 설정되지 않았습니다.",
                "missing_env_vars": [
                    "NAVER_USERNAME" if not os.environ.get('NAVER_USERNAME') else None,
                    "NAVER_PASSWORD" if not os.environ.get('NAVER_PASSWORD') else None
                ]
            }, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
    
    try:
        print("🚀 수동 멤버 순위 조회 요청 받음")
        success = run_async_task(fetch_member_rankings())
        
        if success:
            return app.response_class(
                response=json.dumps({
                    "success": True,
                    "message": "멤버 순위 조회 완료!",
                    "rankings": member_rankings,
                    "summary": {
                        "posts_count": len(member_rankings.get('posts', [])),
                        "comments_count": len(member_rankings.get('comments', [])),
                        "last_updated": member_rankings.get('last_updated')
                    }
                }, ensure_ascii=False, indent=2),
                status=200,
                mimetype='application/json; charset=utf-8'
            )
        else:
            return app.response_class(
                response=json.dumps({
                    "success": False,
                    "message": "멤버 순위 조회 실패",
                    "possible_causes": [
                        "네이버 로그인 실패",
                        "Browserless 연결 실패", 
                        "카페 API 접근 실패",
                        "네트워크 오류"
                    ]
                }, ensure_ascii=False, indent=2),
                status=200,
                mimetype='application/json; charset=utf-8'
            )
    except Exception as e:
        return app.response_class(
            response=json.dumps({
                "success": False,
                "message": f"오류 발생: {str(e)}",
                "error_type": type(e).__name__
            }, ensure_ascii=False, indent=2),
            status=500,
            mimetype='application/json; charset=utf-8'
        )

@app.route('/health')
def health_check():
    """헬스 체크"""
    response = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "naver-cafe-nickname-collector",
        "version": "3.0",
        "uptime": "running",
        "modules": {
            "flask": "✅ 로드됨",
            "requests": "✅ 로드됨",
            "schedule": "✅ 로드됨",
            "playwright": "✅ 로드됨" if PLAYWRIGHT_AVAILABLE else "❌ 설치 필요"
        },
        "environment": {
            "port": os.environ.get("PORT", "5000"),
            "browserless_domain": "SET" if os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') else "NOT_SET",
            "browserless_token": "SET" if os.environ.get('BROWSERLESS_TOKEN') else "NOT_SET",
            "naver_username": "SET" if os.environ.get('NAVER_USERNAME') else "NOT_SET",
            "naver_password": "SET" if os.environ.get('NAVER_PASSWORD') else "NOT_SET"
        },
        "features": {
            "nickname_collection": "✅ 활성화",
            "auto_scheduling": "✅ 활성화 (1시간마다)",
            "member_rankings": "✅ 준비됨" if PLAYWRIGHT_AVAILABLE else "⚠️ Playwright 설치 필요",
            "browserless_integration": "✅ 설정됨" if (os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') and os.environ.get('BROWSERLESS_TOKEN')) else "⚠️ 설정 필요"
        },
        "data": {
            "total_nickname_collections": len(collected_nicknames),
            "ranking_data_available": bool(member_rankings.get('last_updated')),
            "last_ranking_update": member_rankings.get('last_updated', 'None')
        }
    }
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

if __name__ == "__main__":
    print("🚀 네이버 카페 닉네임 수집 서비스 시작 v3.0")
    print("📋 기능: 닉네임 자동수집, 멤버 순위 조회, Browserless 통합")
    
    # 모듈 상태 확인
    print(f"🔧 Playwright: {'✅ 사용 가능' if PLAYWRIGHT_AVAILABLE else '❌ 설치 필요'}")
    print(f"🌐 Browserless: {'✅ 설정됨' if os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') else '⚠️ 설정 필요'}")
    print(f"🔐 네이버 계정: {'✅ 설정됨' if (os.environ.get('NAVER_USERNAME') and os.environ.get('NAVER_PASSWORD')) else '⚠️ 설정 필요'}")
    
    # 초기 수집
    print("📥 초기 닉네임 수집 시작...")
    fetch_nicknames()
    
    # 스케줄러 시작
    print("⏰ 자동 수집 스케줄러 시작 (1시간마다)")
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Flask 앱 실행
    port = int(os.environ.get("PORT", 5000))
    print(f"🌐 Flask 앱 시작 - 포트: {port}")
    print("✅ 서비스 준비 완료!")
    print("🔗 사용 가능한 엔드포인트:")
    print("   • GET  /                  - 서비스 정보")
    print("   • GET  /health            - 헬스 체크")
    print("   • GET  /api/status        - 상태 및 통계") 
    print("   • GET  /nicknames         - 최근 닉네임")
    print("   • GET  /collect-now       - 수동 닉네임 수집")
    print("   • GET  /api/rankings      - 순위 데이터 조회")
    print("   • GET  /fetch-rankings    - 수동 순위 수집")
    
    app.run(host="0.0.0.0", port=port, debug=False)
