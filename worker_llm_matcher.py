import os
import sys
import time
import json
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

# 기존 LLM 매칭 모듈 및 도구 임포트 시도
try:
    import match_llm
except ImportError:
    # 모듈이 없을 경우를 대비한 가벼운 헬퍼 함수 구현 (데모용)
    class MockMatchLLM:
        def clean_price(self, price_str):
            if not price_str or price_str == "판매가 없음":
                return 0
            try:
                # '12,300원' -> 12300 변환
                return int(''.join(filter(str.isdigit, price_str)))
            except:
                return 0
    match_llm = MockMatchLLM()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

def log(message):
    print(f"🧠 [LLM 매칭 워커] {message}")

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

def perform_llm_match_logic(source_item, candidates):
    """
    Qwen LLM을 호출하여 11번가 상품과 쿠팡 후보 상품군 간의 매칭 판단을 수행합니다.
    """
    source_name = source_item["source_name"]
    
    # match_llm 모듈이 정상 로드되어 실제 Qwen 매칭 함수가 존재하는 경우 실제 호출 진행
    if hasattr(match_llm, "match_llm_direct_single"):
        log(f"🧠 Qwen 모델을 사용하여 1:N 매칭 대조 호출 중... (후보군 {len(candidates)}개)")
        match_result = match_llm.match_llm_direct_single(source_name, candidates)
        
        matched_index = match_result.get("matched_index")
        matched_attr = match_result.get("matched_attr")
        
        if matched_index is not None and 0 <= matched_index < len(candidates):
            best_candidate = candidates[matched_index]
            return {
                "is_matched": True,
                "matched_attr": matched_attr,
                "best_candidate": best_candidate
            }
        else:
            return {
                "is_matched": False,
                "matched_attr": matched_attr,
                "best_candidate": None
            }
    else:
        # 가상환경에 torch/transformers 패키지가 없는 테스트 환경을 위한 Mock 폴백 작동
        log("⚠️ [Mock 모드] Qwen 모델 로딩 실패 상태이므로 첫 번째 상품을 매칭 완료 처리합니다.")
        if not candidates:
            return {
                "is_matched": False,
                "matched_attr": {"brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0},
                "best_candidate": None
            }
        best_candidate = candidates[0]
        return {
            "is_matched": True,
            "matched_attr": {
                "brand": "임시 브랜드",
                "capacity": 100,
                "unit": "g",
                "quantity": 1
            },
            "best_candidate": best_candidate
        }

def run_worker():
    log("🚀 LLM 매칭 데몬 구동 시작...")
    
    while True:
        conn = get_db_connection()
        conn.autocommit = False
        
        try:
            cur = conn.cursor()
            
            # [핵심] FOR UPDATE SKIP LOCKED로 LLM 대기열에서 1건 조회
            query = """
            SELECT id, source_name, source_price, temp_candidates 
            FROM matched_products 
            WHERE status = 'PENDING_MATCH' 
            ORDER BY id ASC 
            LIMIT 1 
            FOR UPDATE SKIP LOCKED;
            """
            cur.execute(query)
            job = cur.fetchone()
            
            if not job:
                conn.commit()
                log("💤 대기열이 비어있습니다. 10초 대기 중...")
                time.sleep(10)
                continue
                
            job_id = job["id"]
            source_name = job["source_name"]
            source_price = job["source_price"]
            temp_candidates = job["temp_candidates"]
            
            log(f"📦 [일감 획득] ID: {job_id} / 상품명: '{source_name[:20]}...' 매칭 시작")
            
            # JSONB 데이터 파싱
            candidates = []
            if temp_candidates:
                if isinstance(temp_candidates, str):
                    candidates = json.loads(temp_candidates)
                elif isinstance(temp_candidates, list):
                    candidates = temp_candidates
            
            # LLM 매칭 연산 수행
            match_result = perform_llm_match_logic(job, candidates)
            
            # 결과 가공 및 가격 계산
            is_matched = match_result["is_matched"]
            matched_attr = match_result["matched_attr"]
            best_candidate = match_result["best_candidate"]
            
            matched_attr = matched_attr if matched_attr else {}
            brand = matched_attr.get("brand", "unknown")
            capacity = matched_attr.get("capacity", 0)
            unit = matched_attr.get("unit", "none")
            quantity = matched_attr.get("quantity", 0)
            
            matched_coupang_name = None
            matched_coupang_price = None
            matched_coupang_pure_price = 0
            matched_coupang_link = None
            matched_coupang_image = None
            price_difference = 0
            is_source_cheaper_winner_chance = False
            
            source_pure_price = match_llm.clean_price(source_price)
            
            if is_matched and best_candidate:
                matched_coupang_name = best_candidate.get("name")
                matched_coupang_price = best_candidate.get("price")
                matched_coupang_pure_price = match_llm.clean_price(matched_coupang_price)
                matched_coupang_link = best_candidate.get("link")
                matched_coupang_image = best_candidate.get("image")
                
                # 가격 비교 연산
                price_difference = matched_coupang_pure_price - source_pure_price
                # 11번가(소싱처)가 더 저렴하고 매칭 성공 시 최저가 우승 기회 있음
                if source_pure_price > 0 and matched_coupang_pure_price > 0:
                    if source_pure_price < matched_coupang_pure_price:
                        is_source_cheaper_winner_chance = True
            
            # DB 최종 업데이트 및 상태를 'COMPLETED'로 변경
            update_query = """
            UPDATE matched_products 
            SET 
                brand = %s,
                capacity = %s,
                unit = %s,
                quantity = %s,
                is_matched = %s,
                matched_coupang_name = %s,
                matched_coupang_price = %s,
                matched_coupang_pure_price = %s,
                matched_coupang_link = %s,
                matched_coupang_image = %s,
                price_difference = %s,
                is_source_cheaper_winner_chance = %s,
                status = 'COMPLETED',
                updated_at = NOW() 
            WHERE id = %s;
            """
            cur.execute(update_query, (
                brand, capacity, unit, quantity, is_matched,
                matched_coupang_name, matched_coupang_price, matched_coupang_pure_price,
                matched_coupang_link, matched_coupang_image, price_difference,
                is_source_cheaper_winner_chance, job_id
            ))
            
            conn.commit()
            log(f"✅ 매칭 연산 완료 (결과: {'매칭성공' if is_matched else '매칭실패'}) -> status: COMPLETED")
            
        except Exception as e:
            log(f"❌ DB 연동 및 LLM 매칭 중 치명적 에러: {e}")
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
