import os
import sys
import json
import time
import random
import logging
import shutil
from datetime import datetime
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

# 파일 경로 및 로컬 모듈 자동 인식을 위한 경로 추가
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

# .env 파일 로드 설정 (개발 및 운영 환경 DB 계정 주입용)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CURRENT_DIR, ".env"))
except ImportError:
    pass


# 1, 2단계 로컬 모듈 동적 임포트 및 3단계 매칭 파일 존재 확인
MODULES_AVAILABLE = False
try:
    import scraper_11st
    import scraper_coupang
    # 기존 Qwen LLM 모델 로드가 임포트 시 즉시 발생하는 문제를 예방하기 위해
    # match_llm_official은 상단에서 임포트하지 않고, 파일 존재 유무만 확인 후 실행 시점에 Lazy Import 합니다.
    if os.path.exists(os.path.join(CURRENT_DIR, "match_llm_official.py")):
        MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ [임포트 경고] 크롤러 및 매칭 모듈 임포트 실패: {e}")
    print("⚠️ 1, 2, 3단계 통합 파이프라인의 백그라운드 호출이 제한될 수 있습니다.")

# PostgreSQL DB 접속 드라이버 (psycopg 3) 확인
DB_AVAILABLE = False
try:
    import psycopg
    from psycopg.rows import dict_row
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ [라이브러리 경고] 'psycopg' (psycopg 3) 패키지가 설치되지 않았습니다. DB 저장 로직은 Mock 모드로 동작합니다.")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PriceMatchBackend")

# 데이터베이스 연결 정보 설정 (환경변수 또는 기본 로컬 디버그용 계정 정보)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# 글로벌 상태 관리용 객체
class PipelineStatus:
    def __init__(self):
        self.is_updating = False
        self.last_updated = None

status_tracker = PipelineStatus()


def get_db_connection():
    """ PostgreSQL 연결 객체를 생성하여 반환합니다. """
    if not DB_AVAILABLE:
        return None
    try:
        # psycopg 3에서는 dbname 및 timeout 인수를 사용합니다.
        conn = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            timeout=3
        )
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed (Host: {DB_HOST}, DB: {DB_NAME}): {e}")
        return None


def init_last_updated_from_db():
    """ 서버 시작 시 DB에서 가장 최근에 저장된 데이터의 수정 시각을 긁어와 last_updated를 초기화합니다. """
    conn = get_db_connection()
    if not conn:
        logger.warning("⚠️ Database connection unavailable during startup. Initializing last_updated to current time.")
        status_tracker.last_updated = datetime.now().isoformat()
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(updated_at) FROM matched_products;")
            result = cur.fetchone()
            if result and result[0]:
                status_tracker.last_updated = result[0].isoformat()
                logger.info(f"💾 DB로부터 최근 동기화 시각 로딩 완료: {status_tracker.last_updated}")
            else:
                status_tracker.last_updated = datetime.now().isoformat()
    except Exception as e:
        logger.error(f"⚠️ DB 최근 동기화 시간 조회 실패: {e}")
        status_tracker.last_updated = datetime.now().isoformat()
    finally:
        conn.close()


def save_results_to_db():
    """ 3단계 매칭 결과 파일(data_final_matched.json)을 파싱하여 PostgreSQL DB에 Upsert합니다. """
    conn = get_db_connection()
    if not conn:
        logger.warning("⚠️ DB 연결이 불가능하여 PostgreSQL 저장을 생략하고 JSON 파일 업데이트로 갈음합니다.")
        return

    matched_file_path = os.path.join(CURRENT_DIR, "data_final_matched.json")
    products_11st_path = os.path.join(CURRENT_DIR, "products_11st.json")

    if not os.path.exists(matched_file_path):
        logger.error(f"❌ 매칭 결과 JSON 파일이 존재하지 않아 DB에 반영할 수 없습니다: {matched_file_path}")
        return

    # [1단계] 이미지 URL 유실 방지를 위해 products_11st.json에서 이미지 매핑 수집
    # (2단계 쿠팡 스크래퍼 저장 시 11번가 이미지 주소가 누락되는 현상 대응)
    img_map = {}
    if os.path.exists(products_11st_path):
        try:
            with open(products_11st_path, "r", encoding="utf-8") as f:
                data_11st = json.load(f)
                for item in data_11st:
                    link = item.get("link")
                    if link:
                        img_map[link] = item.get("img_url", "")
            logger.info(f"🖼️ 11번가 상품 이미지 매핑 로딩 완료 ({len(img_map)}개)")
        except Exception as e:
            logger.error(f"⚠️ products_11st.json 이미지 파싱 중 오류: {e}")

    try:
        with open(matched_file_path, "r", encoding="utf-8") as f:
            matched_data = json.load(f)

        with conn.cursor() as cur:
            for item in matched_data:
                st11_link = item.get("11st_link")
                if not st11_link:
                    continue

                st11_name = item.get("11st_name", "")
                st11_price = item.get("11st_price", "0원")
                
                # 정수형 11번가 가격 추출
                st11_pure_price = 0
                if MODULES_AVAILABLE:
                    try:
                        import match_llm_official
                        st11_pure_price = match_llm_official.clean_price(st11_price)
                    except Exception:
                        pass
                
                st11_image = img_map.get(st11_link, "")

                # LLM 추출 속성(brand, capacity, unit, quantity) 바인딩 및 예외 처리
                matched_attr = item.get("matched_attr", {})
                if not isinstance(matched_attr, dict):
                    matched_attr = {}

                brand = matched_attr.get("brand", "unknown")
                
                try:
                    capacity = int(matched_attr.get("capacity", 0))
                except (ValueError, TypeError):
                    capacity = 0
                
                unit = matched_attr.get("unit", "none")
                
                try:
                    quantity = int(matched_attr.get("quantity", 0))
                except (ValueError, TypeError):
                    quantity = 0

                is_matched = item.get("is_matched", False)

                # 매칭된 쿠팡 정보 파싱
                final_coupang_target = item.get("final_coupang_target")
                matched_coupang_name = None
                matched_coupang_price = None
                matched_coupang_pure_price = None
                matched_coupang_link = None

                if final_coupang_target and is_matched:
                    matched_coupang_name = final_coupang_target.get("name")
                    matched_coupang_price = final_coupang_target.get("price")
                    if matched_coupang_price and MODULES_AVAILABLE:
                        try:
                            import match_llm_official
                            matched_coupang_pure_price = match_llm_official.clean_price(matched_coupang_price)
                        except Exception:
                            pass
                    matched_coupang_link = final_coupang_target.get("link")

                price_difference = item.get("price_difference", 0)
                is_11st_cheaper_winner_chance = item.get("is_11st_cheaper_winner_chance", False)

                # PostgreSQL Upsert (ON CONFLICT DO UPDATE) 쿼리 실행
                upsert_query = """
                INSERT INTO matched_products (
                    st11_link, st11_name, st11_price, st11_pure_price, st11_image,
                    brand, capacity, unit, quantity, is_matched,
                    matched_coupang_name, matched_coupang_price, matched_coupang_pure_price, matched_coupang_link,
                    price_difference, is_11st_cheaper_winner_chance, last_checked_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, NOW(), NOW()
                )
                ON CONFLICT (st11_link) DO UPDATE SET
                    st11_name = EXCLUDED.st11_name,
                    st11_price = EXCLUDED.st11_price,
                    st11_pure_price = EXCLUDED.st11_pure_price,
                    st11_image = EXCLUDED.st11_image,
                    brand = EXCLUDED.brand,
                    capacity = EXCLUDED.capacity,
                    unit = EXCLUDED.unit,
                    quantity = EXCLUDED.quantity,
                    is_matched = EXCLUDED.is_matched,
                    matched_coupang_name = EXCLUDED.matched_coupang_name,
                    matched_coupang_price = EXCLUDED.matched_coupang_price,
                    matched_coupang_pure_price = EXCLUDED.matched_coupang_pure_price,
                    matched_coupang_link = EXCLUDED.matched_coupang_link,
                    price_difference = EXCLUDED.price_difference,
                    is_11st_cheaper_winner_chance = EXCLUDED.is_11st_cheaper_winner_chance,
                    last_checked_at = NOW(),
                    updated_at = NOW();
                """
                cur.execute(upsert_query, (
                    st11_link, st11_name, st11_price, st11_pure_price, st11_image,
                    brand, capacity, unit, quantity, is_matched,
                    matched_coupang_name, matched_coupang_price, matched_coupang_pure_price, matched_coupang_link,
                    price_difference, is_11st_cheaper_winner_chance
                ))
        conn.commit()
        logger.info(f"✅ DB 데이터 동기화 및 Upsert 성공 (반영 개수: {len(matched_data)}개)")
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ DB Upsert 중 트랜잭션 롤백 에러: {e}")
    finally:
        conn.close()


def run_full_pipeline_task():
    """ 
    [종합 파이프라인 통합 함수]
    1단계(11st) -> 2단계(쿠팡) -> 3단계(Qwen LLM 매칭) -> 4단계(DB 저장)
    단계 사이 마진 대기(Sleep) 및 중복 가동 잠금(Semaphore) 처리 탑재.
    """
    if status_tracker.is_updating:
        logger.warning("⚠️ 이미 백그라운드에서 크롤링/매칭 파이프라인이 돌고 있습니다. 중복 가동을 차단합니다.")
        return

    status_tracker.is_updating = True
    logger.info("🚀 [통합 파이프라인] 전체 작업을 순차적으로 구동하기 시작합니다...")

    try:
        if not MODULES_AVAILABLE:
            raise Exception("11st/Coupang/LLM 매칭 관련 모듈 일부가 임포트되지 않아 실행할 수 없습니다.")

        # ----------------------------------------------------------------------
        # [1단계] 11번가 상품 수집
        # ----------------------------------------------------------------------
        logger.info("👉 [통합 파이프라인] [1단계] 11번가 크롤러 시동 중...")
        scraper_11st.start_scraping()

        # scraper_11st.py가 파일명을 'products_11st_temp.json'로 생성하므로,
        # 2단계 쿠팡 크롤러가 정상적으로 읽을 수 있도록 'products_11st.json' 경로로 복사
        temp_11st_path = os.path.join(CURRENT_DIR, "products_11st_temp.json")
        target_11st_path = os.path.join(CURRENT_DIR, "products_11st.json")
        if os.path.exists(temp_11st_path):
            shutil.copyfile(temp_11st_path, target_11st_path)
            logger.info("📋 1단계 임시 결과 파일을 products_11st.json으로 정상 카피 완료.")
        else:
            logger.warning("⚠️ 1단계 임시 결과 파일(products_11st_temp.json)을 감지하지 못했습니다.")

        # IP 차단 방지를 위한 마진 슬립 (15~25초 무작위 휴지)
        sleep_margin_1 = random.uniform(1, 2)
        logger.info(f"😴 IP 차단 우회를 위해 {sleep_margin_1:.2f}초간 대기 후 2단계로 진행합니다...")
        time.sleep(sleep_margin_1)

        # ----------------------------------------------------------------------
        # [2단계] 쿠팡 매칭 후보군 수집
        # ----------------------------------------------------------------------
        logger.info("👉 [통합 파이프라인] [2단계] 쿠팡 크롤러 시동 중...")
        scraper_coupang.start_scraping()

        # IP 차단 방지를 위한 마진 슬립 (15~25초 무작위 휴지)
        sleep_margin_2 = random.uniform(1,2)
        logger.info(f"😴 {sleep_margin_2:.2f}초간 대기 후 3단계(LLM 매칭)로 진행합니다...")
        time.sleep(sleep_margin_2)

        # ----------------------------------------------------------------------
        # [3단계] Qwen-4B LLM 하드 매칭 필터링
        # ----------------------------------------------------------------------
        logger.info("👉 [통합 파이프라인] [3단계] Qwen-4B 로컬 LLM 속성 검증 매칭 시동 중...")
        import match_llm_official
        match_llm_official.run_matching_pipeline()

        # ----------------------------------------------------------------------
        # [4단계] PostgreSQL 데이터베이스 Upsert 동기화
        # ----------------------------------------------------------------------
        logger.info("👉 [통합 파이프라인] [4단계] 수집 결과를 데이터베이스(PostgreSQL)에 동기화 중...")
        save_results_to_db()

        # 모든 단계 정상 완료 시각 갱신
        status_tracker.last_updated = datetime.now().isoformat()
        logger.info(f"✨ [통합 파이프라인] 전체 1시간 주기 종합 배치 작업이 정상 완료되었습니다. (완료 시각: {status_tracker.last_updated})")

    except Exception as e:
        logger.error(f"❌ [통합 파이프라인] 실행 중 예외 장애 발생: {str(e)}")
    finally:
        status_tracker.is_updating = False


def cleanup_chrome_processes():
    """ 
    서버 종료 시 현재 파이썬 프로세스가 띄운 자식 크롬(chrome) 및 웹드라이버 프로세스를 
    추적하여 강제로 종료(Kill)시켜 좀비 프로세스 방지.
    """
    try:
        import psutil
        current_process = psutil.Process(os.getpid())
        # recursive=True 옵션으로 모든 자손 프로세스(크롬 자식들 포함)를 탐색
        children = current_process.children(recursive=True)
        
        chrome_procs = []
        for child in children:
            try:
                name = child.name().lower()
                # 크롬 브라우저와 셀레늄 웹드라이버(chromedriver) 타겟팅
                if "chrome" in name or "webdriver" in name:
                    chrome_procs.append(child)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not chrome_procs:
            return

        logger.info(f"🧹 남겨진 자식 크롬 좀비 프로세스 {len(chrome_procs)}개 감지. 청소를 시작합니다...")
        
        # 1차 부드러운 종료 시도
        for p in chrome_procs:
            try:
                p.terminate()
            except Exception:
                pass
                
        # 최대 2초 대기 후 아직 살아있는 좀비 프로세스는 강제 킬(Kill)
        gone, alive = psutil.wait_procs(chrome_procs, timeout=2)
        for p in alive:
            try:
                logger.warning(f"💥 종료되지 않은 크롬 프로세스 강제 소멸 시도 (PID: {p.pid})")
                p.kill()
            except Exception:
                pass
                
        logger.info("✨ 크롬 좀비 프로세스 청소가 성공적으로 완료되었습니다.")
    except Exception as e:
        logger.error(f"⚠️ 백그라운드 크롬 정리 작업 중 예외 발생: {e}")


# FastAPI Startup 및 Shutdown 수명주기(lifespan) 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [1] Startup: DB에서 최근 수정 시각으로 전역 변수 초기화
    init_last_updated_from_db()
    
    # [2] 스케줄러 세팅 및 자동 시작
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # 60분(1시간)마다 종합 파이프라인 호출 설정
    scheduler.add_job(
        run_full_pipeline_task,
        trigger="interval",
        minutes=60,
        id="integrated_crawl_and_match_job",
        name="1시간 주기 크롤링 & LLM 매칭 배치",
        next_run_time=datetime.now()
    )
    scheduler.start()
    logger.info("⏰ APScheduler가 백그라운드 배치 프로세스로 등록 및 시작되었습니다. (주기: 1시간)")
    
    yield
    
    # [3] Shutdown: 스케줄러 정상 종료
    scheduler.shutdown(wait=False)
    logger.info("🛑 APScheduler 백그라운드 프로세스가 안전하게 종료되었습니다.")
    
    # [4] Shutdown: 좀비 크롬 드라이버 강제 청소 구동
    cleanup_chrome_processes()



# FastAPI 인스턴스 초기화
app = FastAPI(
    title="11번가 vs 쿠팡 이커머스 최저가 매칭 API 서버 허브",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정: React 개발용 포트(5173) 및 통신 가능 포트 개방
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/products")
async def get_products():
    """
    [React 연동용 최신 제품 목록 조회 API]
    실시간 크롤링을 도는 것이 아닌, 스케줄러가 백그라운드에서 저장해 둔 PostgreSQL 데이터를 초고속(0.01초 이하) 반환합니다.
    PostgreSQL 접속 오류 발생 시에는 'data_final_matched.json' 로컬 파일에서 직접 읽는 Fallback을 탑재하였습니다.
    """
    products = []
    conn = get_db_connection()
    
    if conn:
        try:
            # psycopg 3에서는 dict_row를 row_factory로 전달하여 dict 결과를 받습니다.
            with conn.cursor(row_factory=dict_row) as cur:
                # updated_at을 기준으로 정렬하여 최신 매칭 상품부터 반환
                cur.execute("""
                    SELECT 
                        id, st11_link as "11st_link", st11_name as "11st_name", 
                        st11_price as "11st_price", st11_pure_price as "11st_pure_price",
                        st11_image as "11st_image", brand, capacity, unit, quantity, 
                        is_matched, matched_coupang_name, matched_coupang_price, 
                        matched_coupang_pure_price, matched_coupang_link, 
                        price_difference, is_11st_cheaper_winner_chance,
                        last_checked_at, updated_at
                    FROM matched_products 
                    ORDER BY updated_at DESC;
                """)
                products = cur.fetchall()
                
                # datetime 객체를 프론트엔드 전송용 ISO 문자열로 변환
                for p in products:
                    if p.get("last_checked_at"):
                        p["last_checked_at"] = p["last_checked_at"].isoformat()
                    if p.get("updated_at"):
                        p["updated_at"] = p["updated_at"].isoformat()
        except Exception as e:
            logger.error(f"⚠️ DB 데이터 조회 실패, 로컬 JSON Fallback 구동: {e}")
        finally:
            conn.close()
            
    # DB 조회 데이터가 유실되었거나 DB 미사용 시 로컬 JSON 데이터를 반환하여 개발 단계에서의 연속성 보장
    if not products:
        matched_file_path = os.path.join(CURRENT_DIR, "data_final_matched.json")
        if os.path.exists(matched_file_path):
            try:
                with open(matched_file_path, "r", encoding="utf-8") as f:
                    products = json.load(f)
                logger.info("ℹ️ 로컬 data_final_matched.json 백업 데이터 파일 파싱 완료.")
            except Exception as e:
                logger.error(f"⚠️ data_final_matched.json 백업 파일 파싱 중 오류: {e}")
                products = []

    return {
        "last_updated": status_tracker.last_updated,
        "is_updating": status_tracker.is_updating,
        "products": products
    }


@app.post("/api/products/trigger")
async def trigger_pipeline_manually(background_tasks: BackgroundTasks):
    """
    [프론트엔드 수동 강제 수집 버튼 연동 API]
    API 호출 즉시 백그라운드 태스크(BackgroundTasks) 형태로 전체 크롤러 및 매칭 파이프라인을 기동합니다.
    """
    if status_tracker.is_updating:
        raise HTTPException(
            status_code=400,
            detail="이미 현재 백그라운드에서 크롤링 및 LLM 매칭 파이프라인이 구동 중에 있습니다."
        )
    
    background_tasks.add_task(run_full_pipeline_task)
    return {
        "status": "triggered",
        "message": "백그라운드에서 크롤링 & 매칭 통합 배치 작업이 강제로 시작되었습니다."
    }


if __name__ == "__main__":
    import uvicorn
    # 기본 8000번 포트로 백엔드 API 서비스 시작
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
