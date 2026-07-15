import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import json
import time
import os

# 캐시 파일 및 디렉토리 설정 (queue_pipeline 내부로 격리)
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crawling_cache_11st.json")
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
CACHE_TTL_SECONDS = 43200  # 12시간 (12 * 3600)

def log(message):
    print(f"👉 [11번가 크롤러] {message}", file=sys.stderr)

def handle_alert(driver):
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        log(f"⚠️ 경고창 발견: {alert_text}")
        alert.accept()
        return True
    except:
        return False

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"⚠️ 캐시 로드 실패: {e}")
    return {}

def save_cache(cache_data: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
        log(f"💾 캐시 영속화 완료 (총 {len(cache_data)}개 상품)")
    except Exception as e:
        log(f"⚠️ 캐시 저장 실패: {e}")

def extract_options(driver, product_url):
    log(f"🔗 상세 페이지 접속: {product_url}")
    driver.get(product_url)
    
    time.sleep(0.5)
    if handle_alert(driver):
        return []
        
    accordion_items = driver.find_elements(By.CSS_SELECTOR, "em.accordion_item, .accordion_item")
    accordion_texts = [el.get_attribute("textContent").strip() for el in accordion_items]
    
    if any("옵션 2" in txt or "옵션2" in txt for txt in accordion_texts):
        log("❌ 다중 옵션 상품 -> options = []")
        return []
        
    has_opt1 = any("옵션 1" in txt or "옵션1" in txt for txt in accordion_texts)
    if not has_opt1:
        triggers = driver.find_elements(By.CSS_SELECTOR, ".c_product_select a, .c_product_select, button.c-product-option__select")
        trigger_texts = [el.get_attribute("textContent").strip() for el in triggers]
        has_opt1 = any("선택" in txt or "옵션" in txt for txt in trigger_texts)
        
    if not has_opt1:
        log("❌ 옵션이 없는 단일 상품 -> options = []")
        return []
        
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
            
    log(f"👉 상세 추출 완료: {len(options)}개 옵션 확보")
    return options

def start_scraping(target_url=None, category_id="processed_food"):
    LIMIT = 10
    cache_data = load_cache()
    
    # target_url이 주어지지 않았을 경우 기본 가공식품 베스트 URL 사용
    if not target_url:
        target_url = "https://www.11st.co.kr/page/best?metaCtgrNo=167009&dispCtgr1No=1001338&categoryNo=167020&dispCtgrLevel=1&dispCtgrNo=1001338&dispCtgrCd=042016"
        
    log(f"🚀 스텔스 크롬 브라우저 초기화 (수집 제한 개수: {LIMIT}개, 카테고리: {category_id})")
    options = uc.ChromeOptions()
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--headless')
    
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    options.page_load_strategy = 'eager'
    
    driver = uc.Chrome(options=options)
    
    try:
        # STEP 1: 베스트 목록 페이지 접속
        log(f"11번가 베스트 페이지({category_id}) 접속 중: {target_url}")
        driver.get(target_url)
        
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
        
        products_list = []
        seen_links = set()
        
        for card in cards:
            try:
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
                
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "div.c-card-item__name dd")
                except:
                    title_el = link_el
                title = title_el.get_attribute("textContent").strip()
                if title.startswith("상품명"):
                    title = title[3:].strip()
                
                price_el = card.find_element(By.CSS_SELECTOR, "dd.c-card-item__price span.value")
                price = price_el.get_attribute("textContent").strip() + "원"

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
            except Exception:
                pass
                
        target_products = products_list[:LIMIT]
        log(f"📋 수집 대상 기본 상품 개수: {len(target_products)}개")
        
        # STEP 3: 상세 페이지 순회하며 옵션 수집 (캐시 적용)
        now = time.time()
        for idx, item in enumerate(target_products):
            link = item["link"]
            cached_info = cache_data.get(link)
            
            # 캐시가 있고 유효기간이 12시간 이내인 경우 크롤링 스킵 (Cache Hit)
            if cached_info and (now - cached_info.get("timestamp", 0) < CACHE_TTL_SECONDS):
                log(f"[CACHE HIT] [{idx+1}/{len(target_products)}] '{item['name'][:18]}...' -> 상세 수집 생략 (캐시 재활용)")
                item["options"] = cached_info["options"]
                if cached_info.get("img_url") and not item.get("img_url"):
                    item["img_url"] = cached_info["img_url"]
            else:
                # 캐시가 없거나 만료된 경우 상세 크롤링 실행 (Cache Miss)
                log(f"[CACHE MISS/EXPIRED] [{idx+1}/{len(target_products)}] '{item['name'][:18]}...' -> 상세 페이지 크롤링 실행")
                try:
                    options = extract_options(driver, link)
                    item["options"] = options
                    
                    # 새로운 정보를 캐시에 기록
                    cache_data[link] = {
                        "options": options,
                        "img_url": item["img_url"],
                        "timestamp": now
                    }
                except Exception as e:
                    log(f"❌ '{item['name'][:18]}...' 옵션 추출 중 에러: {e}")
                    item["options"] = []
                    
        # 캐시 파일 갱신 저장
        save_cache(cache_data)
                
        # STEP 4: JSON 파일 저장
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_filename = os.path.join(current_dir, "data", f"products_11st_temp_{category_id}.json")
        log(f"💾 최종 데이터 JSON 파일 저장 중 ({output_filename})...")
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(target_products, f, ensure_ascii=False, indent=4)
            
        log(f"✨ 11번가 캐시 수집 및 저장 완료! ({category_id})")
        
    except Exception as e:
        log(f"❌ 치명적 에러 발생: {str(e)}")
    finally:
        driver.quit()

if __name__ == '__main__':
    start_scraping()
