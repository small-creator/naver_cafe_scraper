import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

# 환경변수에서 네이버 로그인 정보 가져오기
NAVER_ID = os.getenv("NAVER_ID", "your_naver_id")
NAVER_PASSWORD = os.getenv("NAVER_PASSWORD", "your_password")

# 카페 ID 설정
CAFE_ID = os.getenv("CAFE_ID", "30169141")  # gokangmom 카페 ID

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
                print("\n[알림] 추가 인증이 필요합니다!")
                print("브라우저에서 2단계 인증을 완료해주세요...")
                print("인증이 완료되면 자동으로 다음 단계로 진행됩니다.")
                
                # 사용자가 수동으로 인증을 완료할 때까지 대기
                while True:
                    await asyncio.sleep(2)
                    current_url = self.page.url
                    if 'naver.com' in current_url and 'login' not in current_url and 'auth' not in current_url:
                        print("✓ 인증이 완료되었습니다!")
                        break
                        
            # 로그인 성공 확인
            if 'naver.com' in current_url and 'login' not in current_url:
                print("✓ 네이버 로그인 성공!")
                
                # 간단한 로그인 상태 확인
                try:
                    await asyncio.sleep(2)
                    page_title = await self.page.title()
                    print(f"페이지 제목: {page_title}")
                    
                    # URL이 naver.com이고 login이 없으면 성공으로 간주
                    print("✓ 로그인 상태 확인 완료!")
                    return True
                        
                except Exception as e:
                    print(f"로그인 상태 확인 중 오류: {e}")
                    # 오류가 발생해도 URL 기준으로 성공 판단
                    print("✓ URL 기준으로 로그인 성공으로 판단")
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
        """카페 댓글 통계 API에서 멤버 순위 정보 가져오기"""
        try:
            # 기본값: 전달 1일부터
            if not start_date:
                today = datetime.now()
                # 전달 계산
                if today.month == 1:
                    # 1월인 경우 작년 12월
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    # 전달
                    last_month = today.replace(month=today.month - 1, day=1)
                
                start_date = last_month.strftime('%Y-%m-%d')
            
            print(f"카페 댓글 통계 수집 중... (기준일: {start_date} - 전달 데이터)")
            
            # 댓글 API URL 생성
            api_url = (
                f"https://cafe.stat.naver.com/api/cafe/{CAFE_ID}/rank/memberComment"
                f"?service=CAFE&timeDimension=MONTH&startDate={start_date}"
                f"&memberId=%EB%A9%A4%EB%B2%84&exclude=member%2Cboard%2CdashBoard"
            )
            
            print(f"댓글 API URL: {api_url}")
            
            # API 요청
            response = await self.page.goto(api_url)
            await asyncio.sleep(2)
            
            # JSON 응답 파싱
            content = await self.page.content()
            
            # JSON 데이터 추출 시도
            try:
                # 페이지에서 JSON 데이터 찾기
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
                    print("✓ 댓글 API 응답 수신 성공!")
                    return self.parse_comment_stats(json_data)
                else:
                    print("❌ 댓글 JSON 데이터를 찾을 수 없습니다.")
                    print("페이지 내용:", content[:500])
                    return None
                    
            except Exception as e:
                print(f"댓글 JSON 파싱 오류: {e}")
                print("페이지 내용:", content[:500])
                return None
                
        except Exception as e:
            print(f"카페 댓글 통계 수집 중 오류 발생: {e}")
            return None

    def parse_comment_stats(self, data):
        """댓글 API 응답 데이터를 파싱하여 멤버 순위 정보 추출 (4위까지)"""
        try:
            stats = {
                'comments': [],
                'collected_at': datetime.now().isoformat()
            }
            
            print("댓글 API 응답 구조 분석 중...")
            
            # 네이버 카페 통계 API 구조: result.statData[0].data
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                
                if 'statData' in result and isinstance(result['statData'], list) and len(result['statData']) > 0:
                    stat_data = result['statData'][0]['data']
                    
                    print("댓글 통계 데이터 구조:")
                    print(f"- rows 타입: {type(stat_data.get('rows'))}")
                    
                    rows = stat_data.get('rows', {})
                    if isinstance(rows, dict):
                        # 멤버 ID 리스트
                        member_ids = rows.get('v', [])
                        # 댓글 작성 횟수 리스트
                        counts = rows.get('cnt', [])
                        # 순위 리스트
                        ranks = rows.get('rank', [])
                        # 멤버 정보 리스트
                        member_infos_nested = rows.get('memberInfos', [[]])
                        
                        print(f"- 멤버 수: {len(member_ids)}")
                        print(f"- 댓글 작성 횟수 수: {len(counts)}")
                        print(f"- 순위 수: {len(ranks)}")
                        
                        # memberInfos는 이중 리스트로 되어 있음
                        member_infos = member_infos_nested[0] if member_infos_nested and len(member_infos_nested) > 0 else []
                        print(f"- 멤버 정보 수: {len(member_infos)}")
                        
                        # 각 멤버의 정보를 조합 (상위 3명까지, 제외 조건 적용)
                        collected_members = []
                        excluded_count = 0  # 제외된 멤버 수
                        
                        for i in range(len(member_ids)):
                            # 이미 3명을 수집했으면 중단
                            if len(collected_members) >= 3:
                                break
                                
                            try:
                                member_id = member_ids[i] if i < len(member_ids) else ''
                                count = counts[i] if i < len(counts) else 0
                                rank = ranks[i] if i < len(ranks) else i + 1
                                
                                # 해당 멤버의 정보 찾기
                                member_info = None
                                for info in member_infos:
                                    if info and info.get('idNo') == member_id:
                                        member_info = info
                                        break
                                
                                if member_info and member_info.get('nickName'):
                                    # 제외 조건 확인
                                    nick_name = member_info.get('nickName', '')
                                    member_level = member_info.get('memberLevelName', '')
                                    
                                    # 제외 대상인지 확인
                                    should_exclude = (
                                        nick_name == '수산나' or 
                                        member_level == '제휴업체'
                                    )
                                    
                                    if should_exclude:
                                        print(f"제외: {rank}위. {nick_name} ({member_info.get('userId', 'No ID')}) - {count}개 댓글 (사유: {member_level if member_level == '제휴업체' else '수산나'})")
                                        excluded_count += 1
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'comment_count': count
                                    }
                                    
                                    collected_members.append(member_data)
                                    
                                    print(f"{rank}위. {nick_name} ({member_info.get('userId', 'No ID')}) - {count}개 댓글")
                                
                            except Exception as e:
                                print(f"댓글 멤버 {i} 처리 중 오류: {e}")
                                continue
                        
                        stats['comments'] = collected_members
                        print(f"✓ 상위 3명의 댓글 작성 순위 수집 완료 (제외된 멤버: {excluded_count}명)")
                    
                    else:
                        print("댓글 rows 데이터가 예상한 구조가 아닙니다.")
                        
                else:
                    print("댓글 statData가 없거나 빈 배열입니다.")
                    
            else:
                print("예상한 댓글 API 응답 구조가 아닙니다.")
            
            return stats
            
        except Exception as e:
            print(f"댓글 데이터 파싱 중 오류 발생: {e}")
            import traceback
            print("상세 오류 정보:")
            traceback.print_exc()
            return None

    async def get_cafe_stats(self, start_date=None):
        """카페 통계 API에서 멤버 순위 정보 가져오기"""
        try:
            # 기본값: 전달 1일부터
            if not start_date:
                today = datetime.now()
                # 전달 계산
                if today.month == 1:
                    # 1월인 경우 작년 12월
                    last_month = today.replace(year=today.year - 1, month=12, day=1)
                else:
                    # 전달
                    last_month = today.replace(month=today.month - 1, day=1)
                
                start_date = last_month.strftime('%Y-%m-%d')
            
            print(f"카페 통계 수집 중... (기준일: {start_date} - 전달 데이터)")
            
            # API URL 생성
            api_url = (
                f"https://cafe.stat.naver.com/api/cafe/{CAFE_ID}/rank/memberCreate"
                f"?service=CAFE&timeDimension=MONTH&startDate={start_date}"
                f"&memberId=%EB%A9%A4%EB%B2%84&exclude=member%2Cboard%2CdashBoard"
            )
            
            print(f"API URL: {api_url}")
            
            # API 요청
            response = await self.page.goto(api_url)
            await asyncio.sleep(2)
            
            # JSON 응답 파싱
            content = await self.page.content()
            
            # JSON 데이터 추출 시도
            try:
                # 페이지에서 JSON 데이터 찾기
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
                    print("✓ API 응답 수신 성공!")
                    
                    # 디버깅을 위한 전체 응답 출력
                    print("=== API 응답 전체 구조 ===")
                    print(json.dumps(json_data, ensure_ascii=False, indent=2))
                    print("========================")
                    
                    return self.parse_member_stats(json_data)
                else:
                    print("❌ JSON 데이터를 찾을 수 없습니다.")
                    print("페이지 내용:", content[:500])
                    return None
                    
            except Exception as e:
                print(f"JSON 파싱 오류: {e}")
                print("페이지 내용:", content[:500])
                return None
                
        except Exception as e:
            print(f"카페 통계 수집 중 오류 발생: {e}")
            return None
    
    def parse_member_stats(self, data):
        """API 응답 데이터를 파싱하여 멤버 순위 정보 추출"""
        try:
            stats = {
                'posts': [],    # 게시글 작성 순위
                'comments': [], # 댓글 작성 순위
                'collected_at': datetime.now().isoformat()
            }
            
            print("API 응답 구조 분석 중...")
            
            # 네이버 카페 통계 API 구조: result.statData[0].data
            if isinstance(data, dict) and 'result' in data:
                result = data['result']
                
                if 'statData' in result and isinstance(result['statData'], list) and len(result['statData']) > 0:
                    stat_data = result['statData'][0]['data']
                    
                    print("통계 데이터 구조:")
                    print(f"- rows 타입: {type(stat_data.get('rows'))}")
                    
                    rows = stat_data.get('rows', {})
                    if isinstance(rows, dict):
                        # 멤버 ID 리스트
                        member_ids = rows.get('v', [])
                        # 작성 횟수 리스트
                        counts = rows.get('cnt', [])
                        # 순위 리스트
                        ranks = rows.get('rank', [])
                        # 멤버 정보 리스트
                        member_infos_nested = rows.get('memberInfos', [[]])
                        
                        print(f"- 멤버 수: {len(member_ids)}")
                        print(f"- 작성 횟수 수: {len(counts)}")
                        print(f"- 순위 수: {len(ranks)}")
                        
                        # memberInfos는 이중 리스트로 되어 있음
                        member_infos = member_infos_nested[0] if member_infos_nested and len(member_infos_nested) > 0 else []
                        print(f"- 멤버 정보 수: {len(member_infos)}")
                        
                        # 각 멤버의 정보를 조합 (상위 5명까지, 제외 조건 적용)
                        collected_members = []
                        excluded_count = 0  # 제외된 멤버 수
                        
                        for i in range(len(member_ids)):
                            # 이미 5명을 수집했으면 중단
                            if len(collected_members) >= 5:
                                break
                                
                            try:
                                member_id = member_ids[i] if i < len(member_ids) else ''
                                count = counts[i] if i < len(counts) else 0
                                rank = ranks[i] if i < len(ranks) else i + 1
                                
                                # 해당 멤버의 정보 찾기
                                member_info = None
                                for info in member_infos:
                                    if info and info.get('idNo') == member_id:
                                        member_info = info
                                        break
                                
                                if member_info and member_info.get('nickName'):
                                    # 제외 조건 확인
                                    nick_name = member_info.get('nickName', '')
                                    member_level = member_info.get('memberLevelName', '')
                                    
                                    # 제외 대상인지 확인
                                    should_exclude = (
                                        nick_name == '수산나' or 
                                        member_level == '제휴업체'
                                    )
                                    
                                    if should_exclude:
                                        print(f"제외: {rank}위. {nick_name} ({member_info.get('userId', 'No ID')}) - {count}개 작성 (사유: {member_level if member_level == '제휴업체' else '수산나'})")
                                        excluded_count += 1
                                        continue
                                    
                                    member_data = {
                                        'rank': rank,
                                        'userId': member_info.get('userId', ''),
                                        'nickName': nick_name,
                                        'post_count': count
                                    }
                                    
                                    collected_members.append(member_data)
                                    
                                    print(f"{rank}위. {nick_name} ({member_info.get('userId', 'No ID')}) - {count}개 작성")
                                
                            except Exception as e:
                                print(f"멤버 {i} 처리 중 오류: {e}")
                                continue
                        
                        stats['posts'] = collected_members
                        print(f"✓ 상위 5명의 게시글 작성 순위 수집 완료 (제외된 멤버: {excluded_count}명)")
                    
                    else:
                        print("rows 데이터가 예상한 구조가 아닙니다.")
                        
                else:
                    print("statData가 없거나 빈 배열입니다.")
                    
            else:
                print("예상한 API 응답 구조가 아닙니다.")
            
            return stats
            
        except Exception as e:
            print(f"데이터 파싱 중 오류 발생: {e}")
            import traceback
            print("상세 오류 정보:")
            traceback.print_exc()
            return None
    
    async def save_stats(self, stats, filename=None):
        """통계 정보를 JSON 파일로 저장"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'cafe_member_stats_{timestamp}.json'
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"통계 정보가 {filename}에 저장되었습니다.")
            return True
        except Exception as e:
            print(f"파일 저장 중 오류 발생: {e}")
            return False

# 메인 실행 함수
async def main():
    login_manager = NaverLogin()
    
    try:
        # 브라우저 시작 (Railway에서는 headless=True로 실행)
        await login_manager.start_browser(headless=True)
        
        print("=" * 50)
        print("네이버 로그인 프로그램")
        print("=" * 50)
        
        # 로그인 정보 확인
        if not NAVER_ID or NAVER_ID == "your_naver_id":
            print("⚠️  환경변수 NAVER_ID를 설정해주세요!")
            return
        
        if not NAVER_PASSWORD or NAVER_PASSWORD == "your_password":
            print("⚠️  환경변수 NAVER_PASSWORD를 설정해주세요!")
            return
        
        print(f"아이디: {NAVER_ID}")
        print("비밀번호: " + "*" * len(NAVER_PASSWORD))
        print("\n로그인을 시도합니다...")
        
        # 로그인 실행
        success = await login_manager.login_naver(NAVER_ID, NAVER_PASSWORD)
        
        if success:
            print("\n🎉 로그인이 완료되었습니다!")
            print("브라우저를 확인해보세요.")
            
            # 카페 통계 수집
            print("\n" + "="*50)
            print("카페 멤버 활동 통계 수집 시작 (전달 데이터)")
            print("="*50)
            
            # 전달 게시글 통계 수집
            print("\n1. 게시글 작성 순위 수집 중...")
            post_stats = await login_manager.get_cafe_stats()
            
            # 전달 댓글 통계 수집
            print("\n2. 댓글 작성 순위 수집 중...")
            comment_stats = await login_manager.get_cafe_comment_stats()
            
            # 결과 통합
            combined_stats = {
                'posts': post_stats['posts'] if post_stats else [],
                'comments': comment_stats['comments'] if comment_stats else [],
                'collected_at': datetime.now().isoformat()
            }
            
            if post_stats or comment_stats:
                print("\n📊 월간 활동 순위 결과:")
                
                # 게시글 작성 순위 출력
                if combined_stats['posts']:
                    print(f"\n📝 게시글 작성 순위 (상위 5명):")
                    for member in combined_stats['posts']:
                        print(f"  {member['rank']}위. {member['nickName']} ({member['userId']}) - {member['post_count']}개")
                
                # 댓글 작성 순위 출력
                if combined_stats['comments']:
                    print(f"\n💬 댓글 작성 순위 (상위 3명):")
                    for member in combined_stats['comments']:
                        print(f"  {member['rank']}위. {member['nickName']} ({member['userId']}) - {member['comment_count']}개")
                
                # 결과 저장
                await login_manager.save_stats(combined_stats)
                
            else:
                print("❌ 통계 수집에 실패했습니다.")
                print("카페 관리자 권한이 있는지 확인해주세요.")
            
            # 사용자가 확인할 수 있도록 잠시 대기 (Railway에서는 주석 처리)
            # input("\n엔터키를 누르면 프로그램이 종료됩니다...")
            print("\n프로그램 실행이 완료되었습니다.")
        else:
            print("\n❌ 로그인에 실패했습니다.")
            print("아이디/비밀번호를 확인해주세요.")
            
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n프로그램 실행 중 오류 발생: {e}")
    finally:
        # 브라우저 종료
        await login_manager.close()

if __name__ == "__main__":
    # 프로그램 실행
    asyncio.run(main())
