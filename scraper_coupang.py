import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import json
import time
import os
import urllib.parse
import random

def log(message):
    print(f"👉 [진행상황] {message}", file=sys.stderr)

def handle_alert(driver):
    try:
        alert = driver.switch_to.alert
        alert.accept()
        return True
    except:
        return False

def scrape_coupang_for_keyword(driver, keyword):
    """
    제시된 키워드로 쿠팡을 검색하고 상위 5개의 본상품 데이터를 가져옵니다.
    """
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://www.coupang.com/np/search?q={encoded_keyword}"
    
    log(f"🔎 쿠팡 검색 이동: {search_url}")
    driver.get(search_url)
    
    # 봇 차단 우회를 위해 검색마다 랜덤 대기 부여
    time.sleep(random.uniform(1.8, 3.2))
    handle_alert(driver)
    
    # product-list 가 나타날 때까지 대기
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#product-list, ul#product-list"))
        )
    except Exception as e:
        log(f"⚠️ 검색결과 목록 로드 타임아웃: {e}")
        return []
        
    # 상품 아이템 리스트 추출
    # ProductUnit_productUnit__Qd6sv 클래스명을 포함하거나 리스트 내부의 li 태그들을 타겟팅합니다.
    card_elements = driver.find_elements(By.CSS_SELECTOR, "ul#product-list li")
    
    matches = []
    for card in card_elements:
        try:
            # 1. 광고 상품 제외 필터링 (클래스명에 RankMark 가 들어간 span 유무 확인)
            try:
                rank_mark = card.find_element(By.CSS_SELECTOR, "span[class*='RankMark']")
            except:
                # RankMark 가 없으면 광고 상품으로 간주하고 스킵
                continue
                
            # 2. 링크 엘리먼트 파싱 (a 태그)
            link_el = card.find_element(By.CSS_SELECTOR, "a")
            href = link_el.get_attribute("href") or ""
            
            # 3. 상품명 추출 (ProductUnit_productNameV2__cV9cw 등)
            try:
                name_el = card.find_element(By.CSS_SELECTOR, "[class*='productNameV2']")
            except:
                try:
                    name_el = card.find_element(By.CSS_SELECTOR, ".ProductUnit_productNameV2__cV9cw")
                except:
                    name_el = link_el
            name = name_el.get_attribute("textContent").strip()
            
            # 4. 가격 추출
            price = "판매가 없음"
            try:
                # priceArea 내부의 모든 span 요소를 리스트로 가져옵니다.
                price_els = card.find_elements(By.CSS_SELECTOR, "[class*='priceArea'] span")
                for p_el in price_els:
                    p_txt = p_el.get_attribute("textContent").strip()
                    
                    # 조건 1: 텍스트에 '원'이 포함되어 있어야 합니다. (할인 등의 문구 제외)
                    # 조건 2: 괄호 '('로 시작하지 않아야 합니다. (예: '(100g당 1,585원)' 같은 단위 가격 제외)
                    if "원" in p_txt and not p_txt.startswith("("):
                        price = p_txt
                        break # 원하는 진짜 판매가를 찾았으므로 루프를 종료합니다.
            except:
                # 에러 발생 시 처리할 백업 로직도 위와 동일한 방식으로 구성 가능
                pass
            
            # 5. 이미지 URL 추출
            img_url = ""
            try:
                img_el = card.find_element(By.CSS_SELECTOR, "img")
                img_url = img_el.get_attribute("data-src") or img_el.get_attribute("data-original") or img_el.get_attribute("src") or ""
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
            except:
                pass
                
            matches.append({
                "name": name,
                "price": price,
                "link": href,
                "image": img_url
            })
            
            # 상위 5개 수집 시 중단
            if len(matches) >= 5:
                break
        except Exception as e:
            pass
            
    log(f"✔️ '{keyword[:15]}...' 검색 완료 (본상품 {len(matches)}개 수집)")
    return matches

def start_scraping():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_filename = os.path.join(current_dir, "products_11st.json")
    output_filename = os.path.join(current_dir, "products_coupang.json")
    
    if not os.path.exists(input_filename):
        log(f"❌ 11번가 상품 데이터 파일이 존재하지 않습니다: {input_filename}")
        return
        
    with open(input_filename, "r", encoding="utf-8") as f:
        products_11st = json.load(f)
        
    # 💡 [테스트 팁] 원본 JSON 파일을 수정하지 않고 1개만 테스트하려면 아래 주석(#)을 해제하세요.
    products_11st = products_11st[:3]
    
    log(f"📋 총 {len(products_11st)}개의 11번가 상품명을 로드했습니다.")
    
    # 크롬 헤드리스 및 탐지 우회 옵션 설정
    options = uc.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    # options.add_argument('--disable-popup-blocking')
    # options.add_argument('--headless') # 백그라운드 구동
    
    # 봇 차단 최소화를 위해 이미지 및 알림 로딩 차단
    # prefs = {
    #     "profile.managed_default_content_settings.images": 2,
    #     "profile.default_content_setting_values.notifications": 2
    # }
    # options.add_experimental_option("prefs", prefs)
    # options.page_load_strategy = 'eager'
    
    # 쿠팡 우회용 User-Agent 지정
    # options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    log("🚀 스텔스 크롬 브라우저 초기화 중...")
    driver = uc.Chrome(options=options)
    
    final_results = []
    
    try:
        # 최초 쿠팡 메인 세션 생성 대기
        log("쿠팡 세션 사전 활성화 중...")
        driver.get("https://www.coupang.com/")
        time.sleep(3.0)
        handle_alert(driver)
        
        for idx, item in enumerate(products_11st):
            name_11st = item["name"]
            log(f"\n🔄 [{idx + 1}/{len(products_11st)}] 11번가 상품명: '{name_11st[:30]}...' 매칭 검색")
            
            coupang_matches = scrape_coupang_for_keyword(driver, name_11st)
            
            final_results.append({
                "11st_name": name_11st,
                "11st_price": item["price"],
                "11st_link": item["link"],
                "coupang_matches": coupang_matches
            })
            
            # 한 번 더 긴 랜덤 대기 주입으로 연속 탐색 우회
            time.sleep(random.uniform(2.0, 4.0))
            
        # JSON 결과 보존
        log(f"💾 최종 데이터 JSON 파일 저장 중 ({output_filename})...")
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=4)
            
        log("✨ 쿠팡 매칭 상품 수집 및 저장이 완료되었습니다!")
        
    except Exception as e:
        log(f"❌ 작업 진행 중 오류 발생: {e}")
    finally:
        driver.quit()

if __name__ == '__main__':
    start_scraping()
