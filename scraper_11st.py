import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import json
import time
import os

def log(message):
    print(f"👉 [진행상황] {message}", file=sys.stderr)

def handle_alert(driver):
    """
    브라우저에 Alert 경고창이 떠 있는지 확인하고 발견되면 닫습니다.
    """
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        log(f"⚠️ 경고창 발견: {alert_text}")
        alert.accept()
        return True
    except:
        return False

def extract_options(driver, product_url):
    """
    상품 상세 페이지에 접속하여 옵션을 추출합니다.
    """
    log(f"🔗 상세 페이지 접속: {product_url}")
    driver.get(product_url)
    
    time.sleep(0.5) # 성능 최적화: 이미지/CSS가 차단되어 0.5초면 로딩 완료
    if handle_alert(driver):
        return []
        
    # 1. 아코디언 요소를 통해 옵션 개수 판별
    accordion_items = driver.find_elements(By.CSS_SELECTOR, "em.accordion_item, .accordion_item")
    accordion_texts = [el.get_attribute("textContent").strip() for el in accordion_items]
    
    # 옵션 2 이상이 감지되면 다중 옵션이므로 빈 배열 처리
    if any("옵션 2" in txt or "옵션2" in txt for txt in accordion_texts):
        log("❌ 다중 옵션 상품 -> options = []")
        return []
        
    # 단일 옵션(옵션 1) 혹은 일반 상품 선택 트리거가 존재하는지 판단
    has_opt1 = any("옵션 1" in txt or "옵션1" in txt for txt in accordion_texts)
    if not has_opt1:
        triggers = driver.find_elements(By.CSS_SELECTOR, ".c_product_select a, .c_product_select, button.c-product-option__select")
        trigger_texts = [el.get_attribute("textContent").strip() for el in triggers]
        has_opt1 = any("선택" in txt or "옵션" in txt for txt in trigger_texts)
        
    if not has_opt1:
        log("❌ 옵션이 없는 단일 상품 -> options = []")
        return []
        
    # 2. 클릭 없이 DOM 상에 렌더링된 옵션 버튼들 바로 수집 (hidden 상태도 textContent로 추출 가능)
    option_selectors = [
        "ul.dropdown_list li button.c_product_btn_select",
        "div.dropdown_list button",
        ".c-product-option__list button",
        "button.c_product_btn_select",
        "button[data-log-actionid-label='option_select']"
    ]
    
    option_elements = []
    for selector in option_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            valid_elements = [el for el in elements if el.get_attribute("textContent").strip()]
            if valid_elements:
                option_elements = valid_elements
                break
        except:
            pass
            
    options = []
    for el in option_elements:
        try:
            txt = el.get_attribute("textContent").strip()
            if txt:
                lines = [line.strip() for line in txt.split("\n") if line.strip()]
                cleaned_txt = " / ".join(lines)
                cleaned_txt = cleaned_txt.replace(" / 선택하기", "").replace(" / 선택", "")
                if cleaned_txt and cleaned_txt != "닫기":
                    options.append(cleaned_txt)
        except:
            pass
            
    log(f"👉 추출 완료: {len(options)}개 옵션 확보")
    return options

def start_scraping():
    LIMIT = 3
    
    log(f"🚀 스텔스 크롬 브라우저 초기화 (수집 제한 개수: {LIMIT}개)")
    options = uc.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--headless') # 렌더링 속도 향상을 위한 헤드리스 모드 활성화
    
    # 성능 극대화를 위한 이미지 로딩 배제
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    options.page_load_strategy = 'eager'
    
    driver = uc.Chrome(options=options)
    
    try:
        # STEP 1: 베스트 가공식품 목록 페이지 접속
        target_11st_url = "https://www.11st.co.kr/page/best?metaCtgrNo=167009&dispCtgr1No=1001338&categoryNo=167020&dispCtgrLevel=1&dispCtgrNo=1001338&dispCtgrCd=042016"
        log("11번가 가공식품 베스트 페이지 접속 중...")
        driver.get(target_11st_url)
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".c-card-item, .c_card_item, a.c-card-item__anchor"))
        )
        
        log("베스트 상품 목록 스크롤 다운 로딩 중...")
        for i in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.2)
            
        # STEP 2: 상품 목록 파싱
        log("상품 링크 및 기본 정보 수집 중...")
        cards = driver.find_elements(By.CSS_SELECTOR, "div.c-card-item")
        log(f"발견된 기본 카드 엘리먼트 수: {len(cards)}")
        
        products_list = []
        seen_links = set()
        
        for card in cards:
            try:
                # 1. 링크 엘리먼트 추출 및 광고(data-log-actionid-area != product_list) 필터링
                link_el = card.find_element(By.CSS_SELECTOR, "a.c-card-item__anchor")
                area_attr = link_el.get_attribute("data-log-actionid-area") or ""
                if area_attr != "product_list":
                    continue
                    
                link = link_el.get_attribute("href")
                if not link:
                    continue
                clean_link = link.split("?")[0]
                if clean_link in seen_links:
                    continue
                seen_links.add(clean_link)
                
                # 2. 제목 추출
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "div.c-card-item__name dd")
                except:
                    title_el = link_el
                title = title_el.get_attribute("textContent").strip()
                if title.startswith("상품명"):
                    title = title[3:].strip()
                
                # 3. 가격 추출
                price_el = card.find_element(By.CSS_SELECTOR, "dd.c-card-item__price span.value")
                price = price_el.get_attribute("textContent").strip() + "원"

                # 4. 이미지 URL 추출
                img_url = ""
                try:
                    img_el = card.find_element(By.CSS_SELECTOR, "span.c-lazyload img")
                    img_url = img_el.get_attribute("data-src") or img_el.get_attribute("data-original") or img_el.get_attribute("src") or ""
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                except:
                    pass
                
                products_list.append({
                    "name": title,
                    "price": price,
                    "link": clean_link,
                    "img_url": img_url,
                    "options": []
                })
                
                if len(products_list) >= LIMIT: 
                    break
            except Exception as e:
                pass
                
        target_products = products_list[:LIMIT]
        log(f"📋 수집 대상 기본 상품 개수: {len(target_products)}개")
        
        # STEP 3: 상세 페이지 순회하며 옵션 수집
        for idx, item in enumerate(target_products):
            log(f"[{idx+1}/{len(target_products)}] '{item['name'][:20]}...' 옵션 분석 시작")
            try:
                options = extract_options(driver, item["link"])
                item["options"] = options
            except Exception as e:
                log(f"❌ '{item['name'][:20]}...' 옵션 추출 중 예상치 못한 에러: {e}")
                item["options"] = []
                
        # STEP 4: JSON 파일 저장
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_filename = os.path.join(current_dir, "products_11st.json")
        log(f"💾 최종 데이터 JSON 파일 저장 중 ({output_filename})...")
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(target_products, f, ensure_ascii=False, indent=4)
            
        log("✨ 모든 수집 작업 완료!")
        
    except Exception as e:
        log(f"❌ 치명적 에러 발생: {str(e)}")
    finally:
        driver.quit()

if __name__ == '__main__':
    start_scraping()