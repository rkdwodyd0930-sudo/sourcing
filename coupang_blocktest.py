import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import json
import time
import urllib.parse
import random  # 널널한 랜덤 대기를 위해 추가

def log(message):
    print(f"👉 [진행상황] {message}", file=sys.stderr)

def scrape_multiple_coupang(keywords):
    log("스텔스 크롬 브라우저 초기화 중...")
    options = uc.ChromeOptions()
    # options.add_argument('--headless=new')
    options.add_argument('--window-size=1920,1080')
    # options.add_argument('--disable-popup-blocking')
    # options.add_argument('--disable-gpu') 
    # options.add_argument('--no-sandbox')
    
    driver = uc.Chrome(options=options)
    log("브라우저 실행 완료!")
    
    all_results = {} # 모든 키워드의 결과를 담을 딕셔너리
    
    try:
        # [중요] 최초 1회만 쿠팡 홈에 접속해서 기본 세션을 굽습니다.
        log("쿠팡 메인 페이지 순수 접속 중...")
        # driver.get("https://www.coupang.com/")
        # time.sleep(3.0) 

        # 전달받은 여러 키워드를 루프 돌며 연속 검색합니다.
        for index, keyword in enumerate(keywords):
            log(f"\n🔄 [{index + 1}/{len(keywords)}] '{keyword}' 검색 시작...")
            
            encoded_keyword = urllib.parse.quote(keyword)
            coupang_search_url = f"https://www.coupang.com/np/search?component=&q={encoded_keyword}&channel=user"
            
            log(f"쿠팡 검색 URL로 이동합니다...")
            driver.get(coupang_search_url)
            
            # 검색 결과 로딩 대기
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "search-product"))
                )
                log(f"✅ '{keyword}' 페이지 로딩 성공! (차단 안 됨)")


            except Exception as timeout_error:
                log(f"❌ '{keyword}' 페이지 로딩 실패 (차단되었거나 상품 없음): {str(timeout_error)}")
                all_results[keyword] = {"error": "Timeout or Blocked"}
            
            # --- [핵심] Rate Limit 우회를 위한 널널한 랜덤 대기 시간 ---
            if index < len(keywords) - 1: # 마지막 키워드가 아닐 때만 대기
                sleep_time = random.uniform(2.5, 4.5) # 2.5초 ~ 4.5초 사이의 무작위 시간
                log(f"😴 봇 탐지 방지를 위해 {sleep_time:.2f}초간 휴식합니다...")
                time.sleep(sleep_time)

        # 모든 검색이 정상적으로 끝나면 최종 결과를 JSON으로 출력 (Node.js 송신용)
        log("\n🎉 모든 키워드 검색 완료! 데이터를 출력합니다.")
        print(json.dumps(all_results, ensure_ascii=False))

    except Exception as e:
        log(f"❌ 치명적 에러 발생: {str(e)}")
        print(json.dumps({"error": str(e)}))
    finally:
        log("10초 후 브라우저를 종료합니다.")
        time.sleep(10)
        driver.quit()

if __name__ == '__main__':
    # Node.js에서 인자값으로 키워드 리스트를 보낼 수도 있고, 
    # 터미널 단독 테스트를 위해 기본 연속 테스트 세트를 지정해둡니다.
    if len(sys.argv) > 1:
        # Node.js에서 콤마(,)로 구분해서 보냈다고 가정: 예) "키보드,마우스,모니터"
        target_keywords = sys.argv[1].split(',')
    else:
        # 터미널에서 그냥 python scraper.py 칠 때 실행될 테스트 목록
        target_keywords = [
        '기계식 키보드', '게이밍 마우스', 'C타입 케이블', 
        '무선 헤드셋', '모니터 암', '장패드', 
        '블루투스 스피커', 'HDMI 케이블', '웹캠'
    ]
        
    scrape_multiple_coupang(target_keywords)