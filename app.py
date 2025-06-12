import requests
import json
import schedule
import time
import threading
from datetime import datetime
from flask import Flask, jsonify

app = Flask(__name__)

# 수집된 닉네임 저장용
collected_nicknames = []

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
    # 1시간마다 실행
    schedule.every().hour.do(fetch_nicknames)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Flask 라우트들
@app.route('/')
def home():
    """홈페이지"""
    return jsonify({
        "service": "네이버 카페 닉네임 수집기",
        "status": "실행 중",
        "last_collection": collected_nicknames[-1]['collected_at'] if collected_nicknames else "아직 수집되지 않음",
        "total_collections": len(collected_nicknames),
        "endpoints": {
            "latest": "/nicknames",
            "all": "/all-nicknames",
            "manual": "/collect-now"
        }
    })

@app.route('/nicknames')
def get_latest_nicknames():
    """최근 수집된 닉네임 조회"""
    if collected_nicknames:
        latest = collected_nicknames[-1]
        return jsonify({
            "success": True,
            "nicknames": latest['nicknames'],
            "collected_at": latest['collected_at'],
            "count": latest['count']
        })
    else:
        return jsonify({
            "success": False,
            "message": "아직 수집된 닉네임이 없습니다",
            "nicknames": []
        })

@app.route('/all-nicknames')
def get_all_nicknames():
    """모든 수집 기록 조회"""
    return jsonify({
        "success": True,
        "collections": collected_nicknames,
        "total_collections": len(collected_nicknames)
    })

@app.route('/collect-now')
def collect_now():
    """수동으로 즉시 수집"""
    success = fetch_nicknames()
    
    if success and collected_nicknames:
        latest = collected_nicknames[-1]
        return jsonify({
            "success": True,
            "message": "수집 완료!",
            "nicknames": latest['nicknames'],
            "count": latest['count']
        })
    else:
        return jsonify({
            "success": False,
            "message": "수집 실패"
        })

@app.route('/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

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