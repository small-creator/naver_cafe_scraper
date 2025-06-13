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

# 데이터 저장용
collected_nicknames = []
member_rankings = {'posts': [], 'comments': [], 'last_updated': None}

# 네이버 카페 설정
CAFE_ID = "30169141"  # 강동맘 카페 ID

class NaverCafeManager:
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        self.playwright = None
        
    async def start_browser(self, headless=True):
        """브라우저 시작"""
        try:
            self.playwright = await async_playwright().start()
            
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            self.context = await self.browser.new_context(
                viewport={'width': 1024, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            self.page = await self.context.new_page()
            return True
        except Exception as e:
            print(f"브라우저 시작 실패: {e}")
            return False
    
    async def login_naver(self, username, password):
        """네이버 로그인"""
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
                while True:
                    await asyncio.sleep(2)
                    current_url = self.page.url
                    if 'naver.com' in current_url and 'login' not in current_url and 'auth' not in current_url:
                        break
                        
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
            print(f"게시글 순위 조회 오류: {e}")
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
            print(f"댓글 순위 조회 오류: {e}")
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
            pass

# 비동기 작업을 위한 함수들
async def fetch_member_rankings():
    """멤버 순위 조회 (비동기)"""
    global member_rankings
    
    naver_manager = NaverCafeManager()
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 멤버 순위 조회 시작...")
        
        # 브라우저 시작
        if not await naver_manager.start_browser(headless=True):
            print("브라우저 시작 실패")
            return False
        
        # 환경변수에서 로그인 정보 가져오기 (실제 사용시 설정 필요)
        username = os.environ.get('NAVER_USERNAME', '')
        password = os.environ.get('NAVER_PASSWORD', '')
        
        if not username or not password:
            print("네이버 로그인 정보가 설정되지 않았습니다")
            return False
        
        # 로그인
        if not await naver_manager.login_naver(username, password):
            print("로그인 실패")
            return False
        
        # 게시글 순위 조회
        post_rankings = await naver_manager.get_post_rankings()
        
        # 댓글 순위 조회
        comment_rankings = await naver_manager.get_comment_rankings()
        
        # 결과 저장
        member_rankings['posts'] = post_rankings
        member_rankings['comments'] = comment_rankings
        member_rankings['last_updated'] = datetime.now().isoformat()
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 멤버 순위 조회 완료")
        print(f"게시글 순위: {len(post_rankings)}명, 댓글 순위: {len(comment_rankings)}명")
        
        return True
        
    except Exception as e:
        print(f"멤버 순위 조회 오류: {e}")
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
        print(f"비동기 작업 실행 오류: {e}")
        return False
    finally:
        try:
            loop.close()
        except:
            pass

# 기존 닉네임 수집 함수
def fetch_nicknames():
    """네이버 카페에서 닉네임 5개 수집"""
    global collected_nicknames
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 닉네임 수집 시작...")
        
        # API 호출
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
                
                # 새로운 데이터 저장
                new_entry = {
                    'nicknames': nicknames,
                    'collected_at': datetime.now().isoformat(),
                    'count': len(nicknames)
                }
                
                collected_nicknames.append(new_entry)
                
                # 최근 10개 기록만 유지
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
    """스케줄러 실행 함수"""
    # 1시간마다 닉네임 수집
    schedule.every().hour.do(fetch_nicknames)
    
    # 매일 오전 9시에 멤버 순위 조회 (관리자 로그인 필요)
    # schedule.every().day.at("09:00").do(lambda: run_async_task(fetch_member_rankings()))
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==================== 웹 대시보드 라우트 ====================

@app.route('/')
def dashboard():
    """메인 대시보드 페이지"""
    if os.environ.get('DISABLED') == 'true':
        return '<h1>🔧 서비스 일시 중지됨</h1>'
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """대시보드용 상태 API"""
    total_collections = len(collected_nicknames)
    last_collection = collected_nicknames[-1] if collected_nicknames else None
    
    # 통계 계산
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
            "member_rankings": member_rankings
        }, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/api/rankings')
def get_rankings():
    """멤버 순위 조회 API"""
    return app.response_class(
        response=json.dumps(member_rankings, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/fetch-rankings')
def fetch_rankings_manual():
    """수동으로 멤버 순위 조회"""
    try:
        success = run_async_task(fetch_member_rankings())
        
        if success:
            return app.response_class(
                response=json.dumps({
                    "success": True,
                    "message": "멤버 순위 조회 완료!",
                    "rankings": member_rankings
                }, ensure_ascii=False, indent=2),
                status=200,
                mimetype='application/json; charset=utf-8'
            )
        else:
            return app.response_class(
                response=json.dumps({
                    "success": False,
                    "message": "멤버 순위 조회 실패"
                }, ensure_ascii=False, indent=2),
                status=200,
                mimetype='application/json; charset=utf-8'
            )
    except Exception as e:
        return app.response_class(
            response=json.dumps({
                "success": False,
                "message": f"오류 발생: {str(e)}"
            }, ensure_ascii=False, indent=2),
            status=500,
            mimetype='application/json; charset=utf-8'
        )

# ==================== 기존 API 라우트 ====================

@app.route('/nicknames')
def get_latest_nicknames():
    """최근 수집된 닉네임 조회"""
    if collected_nicknames:
        latest = collected_nicknames[-1]
        response = {
            "success": True,
            "nicknames": latest['nicknames'],
            "collected_at": latest['collected_at'],
            "count": latest['count']
        }
        return app.response_class(
            response=json.dumps(response, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
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
    """수동으로 즉시 수집"""
    success = fetch_nicknames()
    
    if success and collected_nicknames:
        latest = collected_nicknames[-1]
        response = {
            "success": True,
            "message": "수집 완료!",
            "nicknames": latest['nicknames'],
            "count": latest['count']
        }
        return app.response_class(
            response=json.dumps(response, ensure_ascii=False, indent=2),
            status=200,
            mimetype='application/json; charset=utf-8'
        )
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

@app.route('/health')
def health_check():
    """헬스 체크"""
    response = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

if __name__ == "__main__":
    import os
    
    # 첫 실행
    print("🚀 네이버 카페 닉네임 수집 서비스 시작")
    fetch_nicknames()
    
    # 스케줄러를 별도 스레드에서 실행
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Flask 앱 실행
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
