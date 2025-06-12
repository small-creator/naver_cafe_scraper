# 네이버 카페 닉네임 수집기

네이버 카페에서 자동으로 닉네임을 수집하는 Flask 웹 서비스입니다.

## 🚀 기능

- 1시간마다 자동으로 닉네임 5개 수집
- REST API 엔드포인트 제공
- 수동 수집 기능
- 수집 기록 저장 및 조회

## 📡 API 엔드포인트

- `GET /` - 서비스 정보
- `GET /nicknames` - 최근 수집된 닉네임
- `GET /all-nicknames` - 모든 수집 기록
- `GET /collect-now` - 수동 수집 실행
- `GET /health` - 헬스 체크

## 🛠️ 로컬 실행

```bash
pip install -r requirements.txt
python app.py
```

## 🌐 배포

Render.com에 자동 배포됩니다.

## 📊 사용 예시

```bash
# 최신 닉네임 조회
curl https://your-app.onrender.com/nicknames

# 수동 수집
curl https://your-app.onrender.com/collect-now
```