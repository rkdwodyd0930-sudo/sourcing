import os
import sys
import time
import random
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

# scraper_coupang_smart.py에서 스마트 스크래퍼 모듈 재사용
from scraper_coupang import CoupangSmartPersistentScraper, scrape_coupang_for_keyword, CoupangBlockedException

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def log(message):
    print(f"🕷️ [쿠팡 크롤링 워커] {message}", file=sys.stderr)

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

def run_worker():
    log("🚀 쿠팡 크롤러 데몬 구동 시작...")
    
    # 스마트 스크래퍼 초기화 (최초 1회 브라우저 웜업)
    # 워커 시작 시 1회만 브라우저를 띄워두고 무한 루프를 돌며 브라우저를 재사용합니다.
    scraper = CoupangSmartPersistentScraper()
    try:
        scraper.warm_up()
    except Exception as e:
        log(f"⚠️ 초기 웜업 오류 (계속 진행): {e}")

    selenium_search_idx = 0

    while True:
        conn = get_db_connection()
        conn.autocommit = False # 트랜잭션 제어를 위해 autocommit 비활성화
        
        try:
            cur = conn.cursor()
            
            # [핵심] FOR UPDATE SKIP LOCKED를 이용해 대기열에서 1건의 데이터를 중복 없이 락을 걸고 가져옴
            # 이 쿼리 덕분에 여러 대의 크롤러 프로세스가 동시에 돌아도 데이터 충돌이 전혀 발생하지 않습니다.
            query = """
            SELECT id, source_name 
            FROM matched_products 
            WHERE status = 'PENDING_CRAWL' 
            ORDER BY id ASC 
            LIMIT 1 
            FOR UPDATE SKIP LOCKED;
            """
            cur.execute(query)
            job = cur.fetchone()
            
            if not job:
                # 처리할 작업이 없다면 트랜잭션을 끝내고 대기
                conn.commit()
                log("💤 대기열이 비어있습니다. 10초 대기 중...")
                time.sleep(10)
                continue
                
            job_id = job["id"]
            keyword = job["source_name"]
            
            log(f"📦 [일감 획득] ID: {job_id} / 키워드: '{keyword}' 크롤링 시작")
            
            # --- [우회 전략: 8회 수집 시마다 롱 쿨다운 및 스크롤 모사 적용] ---
            if selenium_search_idx > 0 and selenium_search_idx % 8 == 0:
                cooldown_time = random.uniform(2.0, 5.0)
                log(f"☕ 8회 수집 완료. 쿨다운 휴식 및 행동 모사 중 ({cooldown_time:.2f}초)...")
                scraper.simulate_human_action()
                time.sleep(cooldown_time / 2)
                scraper.simulate_human_action()
                time.sleep(cooldown_time / 2)
            
            # 쿠팡 검색 크롤링 수행
            try:
                candidates = scrape_coupang_for_keyword(scraper, keyword)
                selenium_search_idx += 1
                
                # 성공 시: 임시 후보군을 저장하고 상태를 'PENDING_MATCH' (LLM 매칭 대기)로 업그레이드
                import json
                update_query = """
                UPDATE matched_products 
                SET temp_candidates = %s, status = 'PENDING_MATCH', updated_at = NOW() 
                WHERE id = %s;
                """
                cur.execute(update_query, (json.dumps(candidates, ensure_ascii=False), job_id))
                conn.commit()
                log(f"✅ 수집 완료 (후보군 {len(candidates)}개) -> LLM 매칭 대기열로 이동")
                
                time.sleep(random.uniform(2.0, 4.0))
                
            except CoupangBlockedException:
                # 차단당했을 때: 
                # 1. 일단 현재 락을 해제하기 위해 트랜잭션을 Rollback합니다. (다른 워커가 시도할 수 있도록 데이터 반환)
                conn.rollback()
                log(f"⚠️ [차단 감지] 현재 작업을 반환하고 세션 세탁(Reboot)을 시작합니다. (ID: {job_id})")
                
                # 2. 브라우저를 재부팅하고 10~15분 동안 물리적으로 IP 쿨다운을 기다립니다.
                scraper.recreate_driver_with_clean_profile()
                
            except Exception as e:
                # 크롤링 중 일반 에러(셀레늄 에러 등) 발생 시: FAILED 상태로 설정하고 커밋
                log(f"❌ 크롤링 에러 발생 (ID: {job_id}): {e}")
                update_query = """
                UPDATE matched_products 
                SET status = 'FAILED', updated_at = NOW() 
                WHERE id = %s;
                """
                cur.execute(update_query, (job_id,))
                conn.commit()
                
        except Exception as e:
            log(f"❌ DB 연동 치명적 에러: {e}")
            if conn:
                conn.rollback()
            time.sleep(5)
            
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    try:
        run_worker()
    except KeyboardInterrupt:
        log("👋 워커 중단됨.")
