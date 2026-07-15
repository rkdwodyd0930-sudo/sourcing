import os
import sys
import json
import time
import psycopg
from psycopg.rows import dict_row

# 로컬 디렉토리 경로만 sys.path에 추가하여 완벽 격리 독립 실행 지원
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

# .env 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CURRENT_DIR, ".env"))
except ImportError:
    pass

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def log(message):
    print(f"📥 [11번가 프로듀서] {message}")

def get_db_connection():
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=dict_row,
        connect_timeout=3
    )

def clean_price(price_str: str) -> int:
    if not price_str or price_str == "판매가 없음":
        return 0
    try:
        return int(''.join(filter(str.isdigit, price_str)))
    except:
        return 0

def run_sourcing_and_register(category_id):
    conn = get_db_connection()
    registered_count = 0
    
    try:
        with conn.cursor() as cur:
            # 1. 타깃 URL 조회를 위해 categories 테이블 검사
            cur.execute("SELECT category_id, target_url FROM categories WHERE category_id = %s;", (category_id,))
            row = cur.fetchone()
            
            if not row:
                log(f"❌ categories 테이블에 '{category_id}' 카테고리가 없습니다. 수집을 스킵합니다.")
                return
            
            target_url = row["target_url"]
            if not target_url:
                log(f"⚠️ '{category_id}' 카테고리에 등록된 target_url이 비어있습니다. 수집을 스킵합니다.")
                return
            
            # 2. 실제 11번가 크롤러 모듈(scraper_11st_cached)을 실행하여 실시간 크롤링 수행
            log(f"🔎 11번가 실시간 크롤링을 수행합니다. (카테고리: {category_id}, 타깃 URL: {target_url})")
            import scraper_11st
            scraper_11st.start_scraping(target_url=target_url, category_id=category_id)
            
            # 3. 크롤러가 생성한 임시 결과 파일을 읽기 전용 본파일 명으로 복제
            temp_path = os.path.join(CURRENT_DIR, "data", f"products_11st_temp_{category_id}.json")
            target_path = os.path.join(CURRENT_DIR, "data", f"products_11st_{category_id}.json")
            
            if os.path.exists(temp_path):
                import shutil
                shutil.copyfile(temp_path, target_path)
                log(f"📋 products_11st_{category_id}.json 파일 복제 완료.")
            else:
                log("⚠️ 크롤러가 신규 JSON 파일을 생성하지 못했습니다. 기존 백업 파일이 있다면 대체 사용합니다.")
                
            if not os.path.exists(target_path):
                log("❌ 수집 결과 JSON 파일이 존재하지 않아 DB 등록 작업을 취소합니다.")
                return
                
            with open(target_path, "r", encoding="utf-8") as f:
                products = json.load(f)
                
            # 4. 이번 배치 시작 전, 기존 카테고리 상품들의 display_order를 NULL로 일괄 비워줌 (탈락 상품 격리)
            cur.execute("UPDATE matched_products SET display_order = NULL WHERE category_id = %s;", (category_id,))
            conn.commit()
            
            log(f"📋 [{category_id}] {len(products)}개의 상품 데이터를 로드했습니다. DB 등록을 진행합니다...")
            
            for idx, item in enumerate(products):
                source_link = item.get("link")
                if not source_link:
                    continue
                    
                source_name = item.get("name", "")
                source_price = item.get("price", "0원")
                source_pure_price = clean_price(source_price)
                source_image = item.get("img_url", "")
                display_order = idx + 1 # 1위, 2위, 3위...
                
                # 중복 상품 등록 방지 및 새로운 수집 데이터 등록 (UPSERT)
                upsert_query = """
                INSERT INTO matched_products (
                    source_mall, source_link, source_name, source_price, source_pure_price, source_image, category_id, status, display_order, updated_at
                ) VALUES (
                    '11st', %s, %s, %s, %s, %s, %s, 'PENDING_CRAWL', %s, NOW()
                )
                ON CONFLICT (source_link) DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    source_price = EXCLUDED.source_price,
                    source_pure_price = EXCLUDED.source_pure_price,
                    source_image = EXCLUDED.source_image,
                    category_id = EXCLUDED.category_id,
                    display_order = EXCLUDED.display_order,
                    status = CASE 
                        WHEN matched_products.source_price <> EXCLUDED.source_price OR matched_products.status = 'FAILED' THEN 'PENDING_CRAWL'::varchar
                        ELSE matched_products.status 
                    END,
                    updated_at = NOW();
                """
                cur.execute(upsert_query, (
                    source_link, source_name, source_price, source_pure_price, source_image, category_id, display_order
                ))
                registered_count += 1
                
        conn.commit()
        log(f"✅ DB 등록 완료! [{category_id}] 총 {registered_count}개의 실시간 수집 데이터가 'PENDING_CRAWL' 큐로 적재되었습니다.")
        
    except Exception as e:
        conn.rollback()
        log(f"❌ DB 작업 실패: {e}")
    finally:
        conn.close()

def get_all_sourcing_categories(mall_name="11st") -> list:
    """ DB에서 특정 쇼핑몰(기본값 11st)의 모든 카테고리 ID 리스트를 조회 """
    categories_list = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT category_id FROM categories WHERE mall_name = %s OR mall_name = '11번가';", 
                (mall_name,)
            )
            rows = cur.fetchall()
            categories_list = [row["category_id"] for row in rows]
        conn.close()
    except Exception as e:
        print(f"❌ DB 카테고리 목록 조회 실패: {e}")
        
    return categories_list

if __name__ == "__main__":
    # 11st에 등록된 모든 카테고리를 조회하여 루프 실행
    target_categories = get_all_sourcing_categories("11st")
    
    if not target_categories:
        log("⚠️ DB에 수집 대상으로 등록된 11번가 카테고리가 없어 작업을 종료합니다.")
    else:
        log(f"🚀 총 {len(target_categories)}개의 11번가 카테고리 수집을 순차 가동합니다: {target_categories}")
        for cat_id in target_categories:
            log(f"▶️ 카테고리 수집 시작: {cat_id}")
            run_sourcing_and_register(category_id=cat_id)
            # 각 카테고리 수집 사이에 가볍게 딜레이를 두어 부하 최소화
            time.sleep(2)
        log("🏁 모든 11번가 카테고리 수집 완료.")
