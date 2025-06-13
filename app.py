import requests
import json
import schedule
import time
import threading
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify

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

@app.route('/')
def dashboard():
    """메인 페이지"""
    if os.environ.get('DISABLED') == 'true':
        return '<h1>🔧 서비스 일시 중지됨</h1>'
    
    return jsonify({
        "status": "running",
        "message": "네이버 카페 닉네임 수집 서비스",
        "version": "v2.0 (안정화 완료)",
        "endpoints": {
            "main": "/",
            "status": "/api/status",
            "nicknames": "/nicknames", 
            "collect": "/collect-now",
            "health": "/health"
        },
        "features": [
            "자동 닉네임 수집 (1시간마다)",
            "수동 수집 기능",
            "수집 통계 제공",
            "API 엔드포인트 제공"
        ]
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
    """멤버 순위 조회 API (Browserless 연결 후 사용 예정)"""
    return app.response_class(
        response=json.dumps({
            "message": "멤버 순위 기능은 Browserless 연결 후 사용 가능합니다",
            "status": "준비중",
            "rankings": member_rankings,
            "next_steps": [
                "1. Browserless 서비스 배포 완료",
                "2. Playwright 기능 연동",
                "3. 네이버 로그인 및 순위 수집 기능 활성화"
            ]
        }, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

@app.route('/health')
def health_check():
    """헬스 체크"""
    response = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "naver-cafe-nickname-collector",
        "version": "2.0",
        "uptime": "running",
        "environment": {
            "port": os.environ.get("PORT", "5000"),
            "browserless_domain": "SET" if os.environ.get('BROWSERLESS_PUBLIC_DOMAIN') else "NOT_SET",
            "browserless_token": "SET" if os.environ.get('BROWSERLESS_TOKEN') else "NOT_SET",
            "naver_username": "SET" if os.environ.get('NAVER_USERNAME') else "NOT_SET",
            "naver_password": "SET" if os.environ.get('NAVER_PASSWORD') else "NOT_SET"
        }
    }
    return app.response_class(
        response=json.dumps(response, ensure_ascii=False, indent=2),
        status=200,
        mimetype='application/json; charset=utf-8'
    )

if __name__ == "__main__":
    print("🚀 네이버 카페 닉네임 수집 서비스 시작 v2.0")
    print("📋 기능: 닉네임 자동수집, API 제공, 통계 관리")
    
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
    
    app.run(host="0.0.0.0", port=port, debug=False)
