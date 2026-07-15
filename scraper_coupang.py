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
import shutil

# 캐시 파일 및 TTL 설정 (queue_pipeline 내부 격리)
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crawling_cache_coupang.json")
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
CACHE_TTL_SECONDS = 43200  # 12시간 (12 * 3600)

def log(message):
    print(f"👉 [쿠팡 스마트 크롤러] {message}", file=sys.stderr)

class CoupangBlockedException(Exception):
    """쿠팡에서 차단(Access Denied, 사용권한 제한 등)을 감지했을 때 발생하는 예외"""
    pass

class CoupangSmartPersistentScraper:
    def __init__(self, profile_dir=None):
        if profile_dir is None:
            self.profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_profile")
        else:
            self.profile_dir = profile_dir
        self.init_driver()

    def init_driver(self):
        """
        크롬 옵션을 설정하고 드라이버 인스턴스를 기동합니다.
        데이터 사용량 및 백그라운드 트래픽을 방지하여 안정성과 속도를 확보합니다.
        """
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        
        # --- [초강력 데이터 절약 및 탐지 우회 옵션 세트] ---
        # 1. 이미지 로딩 강제 차단
        options.add_argument('--blink-settings=imagesEnabled=false')
        
        # 2. 백그라운드 네트워크 통신 원천 차단 (크롬 자동 업데이트, 컴포넌트 다운로드 등 차단 - 핵심!)
        options.add_argument('--disable-background-networking')
        
        # 3. 구글 계정 및 서비스 동기화 차단 (백그라운드 동기화 패킷 제거)
        options.add_argument('--disable-sync')
        
        # 4. 기본 번들 앱 및 익스텐션 로딩 차단
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-extensions')
        
        # 5. 오디오 및 비디오 디코딩 리소스 다운로드 차단
        options.add_argument('--mute-audio')
        options.add_argument('--disable-features=AudioServiceOutOfProcess')
        
        # 필요 시 헤드리스 설정을 추가할 수 있습니다.
        # options.add_argument('--headless')
        
        log(f"[*] Persistent 프로필을 사용하여 브라우저 초기화 중: {self.profile_dir}")
        self.driver = uc.Chrome(options=options)

    def recreate_driver_with_clean_profile(self, cooldown_min=600, cooldown_max=900):
        """
        차단이 감지되었을 때 브라우저를 완전히 끄고 하드디스크의 프로필 폴더 자체를 
        물리적으로 통째로 강제 삭제(세탁)한 뒤 완전히 새로운 크롬을 다시 기동하여 복구합니다.
        """
        log("\n[FACTORY RESET] 물리적 프로필 삭제 및 브라우저 재기동 수행 중...")
        try:
            # 1. 기존 드라이버 종료 (디바이스/파일 락 해제)
            log("-> 파일 락 해제를 위해 현재 크롬 브라우저 종료 중...")
            self.driver.quit()
            time.sleep(3) # 파일 락 해제 및 프로세스 완전 종료 대기
            
            # 2. 하드디스크 상의 프로필 폴더 강제 삭제 (찌꺼기 100% 완전 소멸)
            log(f"-> 프로필 디렉토리 강제 삭제 중: {self.profile_dir}")
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            
            # 10~15분 대기 (IP Reputation 쿨다운)
            sleep_time = random.uniform(cooldown_min, cooldown_max)
            log(f"-> IP 평판 회복을 위해 {sleep_time:.2f}초 대기 중...")
            time.sleep(sleep_time)

            # 3. 새로운 크롬 재기동 및 클린 웜업 실행
            log("-> 완전히 새로운 크롬 브라우저 인스턴스 기동 중...")
            self.init_driver()
            self.warm_up()
            log("[FACTORY RESET SUCCESS] 새로운 세션으로 브라우저 재기동 완료.")
            
        except Exception as e:
            log(f"[FACTORY RESET ERROR] 물리적 초기화 중 실패: {e}")

    def warm_up(self):
        """
        최초 구동 시 또는 차단 감지 후 물리적 세탁이 끝난 뒤
        새로운 신선한 신뢰 세션을 받기 위해 구글 경유로 쿠팡 메인에 접근합니다.
        """
        log("\n[WARM-UP] Google 리퍼러를 통한 세션 웜업 수행 중...")
        try:
            log("-> 구글 메인 페이지 접속 중...")
            self.driver.get("https://www.google.com")
            time.sleep(2)
            
            log("-> 구글 검색결과 클릭을 모방하여 쿠팡 메인 접속 중...")
            trigger_link_js = """
            const a = document.createElement('a');
            a.id = 'organic_google_link';
            a.href = 'https://www.coupang.com';
            a.innerText = 'Coupang';
            document.body.appendChild(a);
            a.click();
            """
            self.driver.execute_script(trigger_link_js)
            
            # 보안 토큰들이 정상적으로 생성되고 기록될 때까지 대기
            warm_up_wait = random.uniform(1, 3)
            log(f"-> 보안 쿠키 등록 대기 중 ({warm_up_wait:.2f}초)...")
            time.sleep(warm_up_wait)
            log("[WARM-UP SUCCESS] Persistent 세션 웜업 완료.")
            
        except Exception as e:
            log(f"[WARM-UP ERROR] 웜업 단계 실패: {e}")

    def simulate_human_action(self):
        """
        보안 장비의 감점 점수를 완화하기 위해 가볍게 화면을 스크롤하며 인간 체류 행동을 모사합니다.
        """
        try:
            log("-> 쿨다운 중 인간 행동 스크롤 모사...")
            self.driver.execute_script("window.scrollTo({top: document.body.scrollHeight / 3, behavior: 'smooth'});")
            time.sleep(random.uniform(1, 3))
            self.driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'});")
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            log(f"[SCROLL ERROR] 스크롤 모사 실패: {e}")

    def check_block(self) -> bool:
        """
        현재 페이지가 차단되었는지 감지합니다.
        """
        try:
            page_title = self.driver.title.strip() if self.driver.title else "No Title"
            html = self.driver.page_source
        except Exception:
            return False
            
        # 차단 감지 (1. 일반적인 Access Denied/403 타이틀, 2. 쿠팡 자체적인 사용권한 제한 안내 페이지)
        if "Access Denied" in page_title or "차단" in page_title or "403" in page_title:
            return True
        if "사용권한" in html or "사용권한이 제한된 페이지" in html or "요청하신 페이지의 사용권한이 없습니다" in html:
            return True
        if "sec-if-cpt-container" in html or "akamai-protected-by" in html or "akamai-logo" in html:
            return True
        return False

    def close(self):
        log("\n[*] 브라우저 세션 종료 중...")
        self.driver.quit()

def handle_alert(driver):
    try:
        alert = driver.switch_to.alert
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
        log(f"💾 캐시 영속화 완료 (총 {len(cache_data)}개 검색어)")
    except Exception as e:
        log(f"⚠️ 캐시 저장 실패: {e}")

def scrape_coupang_for_keyword(scraper, keyword):
    driver = scraper.driver
    encoded_keyword = urllib.parse.quote(keyword)
    search_url = f"https://www.coupang.com/np/search?q={encoded_keyword}"
    
    log(f"🔎 쿠팡 검색 페이지 이동: {search_url}")
    driver.get(search_url)
    
    time.sleep(random.uniform(1.8, 3.2))
    handle_alert(driver)
    
    # 1. 차단 여부 먼저 검사
    if scraper.check_block():
        raise CoupangBlockedException()
        
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#product-list, ul#product-list"))
        )
    except Exception as e:
        # WebDriverWait 실패 시 차단 여부 재검증
        if scraper.check_block():
            raise CoupangBlockedException()
        log(f"⚠️ 검색 결과 목록 로드 타임아웃 (차단 아님): {e}")
        return []
        
    card_elements = driver.find_elements(By.CSS_SELECTOR, "ul#product-list li")
    
    matches = []
    for card in card_elements:
        try:
            try:
                card.find_element(By.CSS_SELECTOR, "span[class*='RankMark']")
            except:
                continue # 광고 상품 스킵
                
            link_el = card.find_element(By.CSS_SELECTOR, "a")
            href = link_el.get_attribute("href") or ""
            
            try:
                name_el = card.find_element(By.CSS_SELECTOR, "[class*='productNameV2']")
            except:
                try:
                    name_el = card.find_element(By.CSS_SELECTOR, ".ProductUnit_productNameV2__cV9cw")
                except:
                    name_el = link_el
            name = name_el.get_attribute("textContent").strip()
            
            price = "판매가 없음"
            try:
                price_els = card.find_elements(By.CSS_SELECTOR, "[class*='priceArea'] span")
                for p_el in price_els:
                    p_txt = p_el.get_attribute("textContent").strip()
                    if "원" in p_txt and not p_txt.startswith("("):
                        price = p_txt
                        break
            except:
                pass
            
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
            
            if len(matches) >= 5:
                break
        except Exception:
            pass
            
    log(f"✔️ '{keyword[:15]}...' 검색 완료 (본상품 {len(matches)}개 수집)")
    return matches

def start_scraping(category_id="processed_food"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    input_filename = os.path.join(current_dir, "data", f"products_11st_{category_id}.json")
    output_filename = os.path.join(current_dir, "data", f"products_coupang_{category_id}.json")
    
    if not os.path.exists(input_filename):
        log(f"❌ 11번가 상품 데이터 파일이 존재하지 않습니다: {input_filename}")
        return
        
    with open(input_filename, "r", encoding="utf-8") as f:
        products_11st = json.load(f)
        
    products_11st = products_11st[:10]
    
    log(f"📋 [{category_id}] 총 {len(products_11st)}개의 11번가 상품명을 로드했습니다.")
    cache_data = load_cache()
    
    now = time.time()
    need_selenium = False
    
    for item in products_11st:
        name_11st = item["name"]
        cached_info = cache_data.get(name_11st)
        if not cached_info or (now - cached_info.get("timestamp", 0) >= CACHE_TTL_SECONDS):
            need_selenium = True
            break
            
    scraper = None
    if need_selenium:
        log("🚀 스텔스 크롬 브라우저 초기화 중...")
        scraper = CoupangSmartPersistentScraper()
        try:
            scraper.warm_up()
        except Exception as e:
            log(f"⚠️ 쿠팡 초기 세션 활성화 에러: {e}")
    else:
        log(f"✨ [{category_id}] 모든 검색 대상이 캐시에 보관 중입니다.")

    final_results = []
    selenium_search_idx = 0
    
    try:
        for idx, item in enumerate(products_11st):
            name_11st = item["name"]
            cached_info = cache_data.get(name_11st)
            
            if cached_info and (now - cached_info.get("timestamp", 0) < CACHE_TTL_SECONDS):
                coupang_matches = cached_info["coupang_matches"]
            else:
                if scraper:
                    if selenium_search_idx > 0 and selenium_search_idx % 8 == 0:
                        cooldown_time = random.uniform(2.0, 5.0)
                        scraper.simulate_human_action()
                        time.sleep(cooldown_time)
                    
                    max_retries = 2
                    coupang_matches = []
                    for attempt in range(max_retries):
                        try:
                            coupang_matches = scrape_coupang_for_keyword(scraper, name_11st)
                            selenium_search_idx += 1
                            break
                        except CoupangBlockedException:
                            if attempt < max_retries - 1:
                                scraper.recreate_driver_with_clean_profile()
                                continue
                            else:
                                scraper.recreate_driver_with_clean_profile()
                                coupang_matches = []
                        except Exception:
                            coupang_matches = []
                            break
                            
                    cache_data[name_11st] = {
                        "coupang_matches": coupang_matches,
                        "timestamp": now
                    }
                    time.sleep(random.uniform(2.0, 4.0))
                else:
                    coupang_matches = []
            
            final_results.append({
                "11st_name": name_11st,
                "11st_price": item["price"],
                "11st_link": item["link"],
                "11st_image": item.get("img_url", ""),
                "coupang_matches": coupang_matches
            })
            
        save_cache(cache_data)
        
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        log(f"❌ 작업 진행 중 오류 발생: {e}")
    finally:
        if scraper:
            scraper.close()

if __name__ == '__main__':
    start_scraping()
