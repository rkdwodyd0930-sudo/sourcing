import os
import sys
import json
import logging
import subprocess
from datetime import datetime
from typing import Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)

# .env 환경 변수 주입
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(CURRENT_DIR, ".env"))
except ImportError:
    pass

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("QueuePipelineAPIServer")

# DB 접속 환경 변수
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

# PostgreSQL 연결 지원 라이브러리 검사
DB_AVAILABLE = False
try:
    import psycopg
    from psycopg.rows import dict_row
    DB_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ 'psycopg' 패키지가 없습니다. DB 연동이 불가능합니다.")

def get_db_connection():
    if not DB_AVAILABLE:
        return None
    try:
        return psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=3
        )
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return None

def get_last_updated_time() -> str:
    """ DB에서 최근 업데이트 시각을 확인하여 반환 """
    conn = get_db_connection()
    if not conn:
        return datetime.now().isoformat()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(updated_at) FROM matched_products;")
            result = cur.fetchone()
            if result and result[0]:
                return result[0].isoformat()
    except Exception as e:
        logger.error(f"⚠️ DB 최근 동기화 시각 조회 실패: {e}")
    finally:
        conn.close()
    return datetime.now().isoformat()

def load_categories_config() -> List[Dict[str, str]]:
    """ DB 카테고리 마스터 테이블에서 수집 채널을 동적 로드 """
    categories_list = []
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT category_id, category_name, mall_name, target_url FROM categories;")
                categories_list = cur.fetchall()
        except Exception as e:
            logger.error(f"⚠️ DB 카테고리 설정 로드 실패: {e}")
        finally:
            conn.close()
            
    if not categories_list:
        categories_list = [{
            "category_id": "processed_food",
            "category_name": "11번가 가공식품 베스트 (기본값)",
            "mall_name": "11st",
            "target_url": "https://www.11st.co.kr/page/best?metaCtgrNo=167009&dispCtgr1No=1001338&categoryNo=167020&dispCtgrLevel=1&dispCtgrNo=1001338&dispCtgrCd=042016"
        }]
    return categories_list

def is_crawler_running() -> bool:
    """ DB에 PENDING_CRAWL이나 PENDING_MATCH인 일감이 있으면 작업이 구동 중인 것으로 판별 """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM matched_products WHERE status IN ('PENDING_CRAWL', 'PENDING_MATCH');")
            count = cur.fetchone()[0]
            return count > 0
    except Exception as e:
        logger.error(f"⚠️ 작업 감지 에러: {e}")
        return False
    finally:
        conn.close()

def run_sourcing_producer_subprocess():
    """ 11번가 소싱 데이터 등록기(producer_11st.py)를 비동기 서브프로세스로 기동 """
    script_path = os.path.join(CURRENT_DIR, "producer_11st.py")
    if not os.path.exists(script_path):
        logger.error(f"❌ 소싱 등록기 스크립트를 찾을 수 없습니다: {script_path}")
        return

    logger.info("🚀 [Subprocess] 11번가 수집 및 큐 적재 프로세스(producer_11st.py) 실행 시작...")
    subprocess.Popen([sys.executable, script_path])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 스타트업 로그
    logger.info("🔥 비동기 DB 큐 파이프라인 API 서버 기동 완료.")
    yield

app = FastAPI(
    title="비동기 DB 큐 파이프라인 API 서버 (프로토타입)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173","https://onback-sourcing.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/products")
async def get_products(category: str = None, mall: str = None):
    """
    [React 연동용 최신 제품 목록 조회 API]
    * DB 데이터를 조회하여 React 전송용 DTO 객체로 가공해 즉시 반환합니다.
    """
    products = []
    conn = get_db_connection()
    
    if conn:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                query = """
                    SELECT 
                        id, source_mall as "source_mall", source_link as "11st_link", 
                        source_name as "11st_name", source_price as "11st_price", 
                        source_pure_price as "st11_pure_price", source_image as "11st_image", 
                        brand, capacity, unit, quantity, is_matched, status, display_order,
                        matched_coupang_name, matched_coupang_price, matched_coupang_pure_price, matched_coupang_link, 
                        matched_coupang_image, price_difference, is_source_cheaper_winner_chance as "is_11st_cheaper_winner_chance",
                        last_checked_at, updated_at
                    FROM matched_products 
                    WHERE display_order IS NOT NULL
                """
                params = []
                if category:
                    query += " AND category_id = %s"
                    params.append(category)
                if mall:
                    query += " AND source_mall = %s"
                    params.append(mall)
                
                query += " ORDER BY display_order ASC;"
                
                cur.execute(query, params)
                products = cur.fetchall()
                
                for p in products:
                    if p.get("last_checked_at"):
                        p["last_checked_at"] = p["last_checked_at"].isoformat()
                    if p.get("updated_at"):
                        p["updated_at"] = p["updated_at"].isoformat()
                    
                    if p.get("is_matched"):
                        p["final_coupang_target"] = {
                            "name": p.get("matched_coupang_name"),
                            "price": p.get("matched_coupang_price"),
                            "link": p.get("matched_coupang_link"),
                            "image": p.get("matched_coupang_image")  
                        }
                    else:
                        p["final_coupang_target"] = None
        except Exception as e:
            logger.error(f"⚠️ DB 조회 중 예외 발생: {e}")
        finally:
            conn.close()
            
    # DB 조회 불가 시 로컬 JSON 파일 Fallback 백업 구동
    if not products:
        target_cat_id = category if category else "processed_food"
        matched_file_path = os.path.join(CURRENT_DIR, "data", f"data_final_matched_{target_cat_id}.json")
        if os.path.exists(matched_file_path):
            try:
                with open(matched_file_path, "r", encoding="utf-8") as f:
                    products = json.load(f)
            except Exception as e:
                logger.error(f"⚠️ {matched_file_path} 파일 파싱 중 오류: {e}")

    return {
        "last_updated": get_last_updated_time(),
        "is_updating": is_crawler_running(), # DB 상에 남은 대기 작업 여부로 반환
        "categories": load_categories_config(),
        "products": products
    }

@app.post("/api/products/trigger")
async def trigger_pipeline_manually(background_tasks: BackgroundTasks):
    if is_crawler_running():
        raise HTTPException(
            status_code=400,
            detail="이미 현재 백그라운드에서 크롤링 및 LLM 매칭 작업이 진행 중에 있습니다."
        )
    
    # 비동기로 별도 프로세스 실행 (소싱 시작)
    background_tasks.add_task(run_sourcing_producer_subprocess)
    return {
        "status": "triggered",
        "message": "백그라운드에서 11번가 소싱 데이터 등록기(producer_11st.py)가 가동되었습니다."
    }

@app.get("/api/pipeline/status")
async def get_pipeline_status():
    """
    [대기열 실시간 모니터링용 API]
    각 상태별 건수를 반환합니다.
    """
    conn = get_db_connection()
    if not conn:
        return {"status": "DB_UNAVAILABLE", "counts": {}}
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT status, COUNT(*) as count 
                FROM matched_products 
                GROUP BY status;
            """)
            rows = cur.fetchall()
            counts = {row["status"]: row["count"] for row in rows}
            return {
                "status": "OK",
                "counts": counts
            }
    except Exception as e:
        return {"status": "ERROR", "detail": str(e)}
    finally:
        conn.close()

if __name__ == "__main__":
    import uvicorn
    # 8000번 포트로 구동
    logger.info("🔥 독립형 비동기 API 서버 구동 (포트: 8000)")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
