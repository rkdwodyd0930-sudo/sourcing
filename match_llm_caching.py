import json
import torch
import os
import sys
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "Qwen/Qwen3.5-4B"
CACHE_FILE = "product_attributes_cache.json"

print("[READY] 로컬 디스크에서 토크나이저 및 Qwen 모델 로드 중...")

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

# ----------------------------------------------------------------------
# [PostgreSQL DB 연동 라이브러리 검사]
# ----------------------------------------------------------------------
DB_AVAILABLE = False
try:
    import psycopg
    from psycopg.rows import dict_row
    DB_AVAILABLE = True
except ImportError:
    pass

def get_db_connection():
    """ PostgreSQL 연결 객체를 생성하여 반환합니다. (main.py 환경설정 공유) """
    if not DB_AVAILABLE:
        return None
    try:
        return psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "ecommerce_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            timeout=3
        )
    except Exception:
        return None

# ----------------------------------------------------------------------
# [캐시 관리 함수]
# ----------------------------------------------------------------------
def load_cache() -> dict:
    """
    로컬 JSON 파일과 PostgreSQL DB에서 이미 파싱된 상품 속성 정보를 로드하여
    단일 메모리 캐시 딕셔너리로 구축합니다.
    """
    cache_data = {}
    
    # 1단계: 로컬 JSON 캐시 파일 로드
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            print(f"[CACHE] 로컬 캐시 파일 {len(cache_data)}개 로드 완료.")
        except Exception as e:
            print(f"[CACHE] 로컬 캐시 파일 읽기 실패: {e}")

    # 2단계: PostgreSQL DB가 사용 가능하면 DB의 기존 매칭 속성들 로드하여 머지
    conn = get_db_connection()
    if conn:
        db_count = 0
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                # 11번가 상품 속성 수집
                cur.execute("SELECT st11_name, brand, capacity, unit, quantity, is_matched FROM matched_products;")
                for row in cur.fetchall():
                    name = row["st11_name"]
                    if name:
                        cache_data[name] = {
                            "is_valid_for_comparison": row["is_matched"],
                            "brand": row["brand"],
                            "capacity": row["capacity"],
                            "unit": row["unit"],
                            "quantity": row["quantity"]
                        }
                        db_count += 1
                        
                # 쿠팡 상품 속성 수집
                cur.execute("""
                    SELECT matched_coupang_name as cp_name, brand, capacity, unit, quantity, is_matched 
                    FROM matched_products 
                    WHERE matched_coupang_name IS NOT NULL;
                """)
                for row in cur.fetchall():
                    name = row["cp_name"]
                    if name:
                        cache_data[name] = {
                            "is_valid_for_comparison": row["is_matched"],
                            "brand": row["brand"],
                            "capacity": row["capacity"],
                            "unit": row["unit"],
                            "quantity": row["quantity"]
                        }
                        db_count += 1
            print(f"[CACHE] PostgreSQL 데이터베이스로부터 {db_count}개 속성 정보 병합 완료.")
        except Exception as e:
            print(f"[CACHE] DB 캐시 읽기 실패: {e}")
        finally:
            conn.close()

    return cache_data

def save_cache(cache_data: dict):
    """ 새로 수집된 상품 속성 정보를 로컬 캐시 JSON 파일에 저장합니다. """
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
        print(f"[CACHE] 최종 {len(cache_data)}개 캐시 데이터 로컬 JSON에 백업 완료.")
    except Exception as e:
        print(f"[CACHE] 로컬 캐시 백업 실패: {e}")


# ----------------------------------------------------------------------
# [Transformers 기반 개별 LLM 속성 추출]
# ----------------------------------------------------------------------
def extract_attributes_single(product_name: str) -> dict:
    """
    Hugging Face Transformers 로컬 모델을 구동하여 1개의 상품 속성을 정밀하게 추출합니다.
    (기존 match_llm_official.py 로직 계승)
    """
    system_instruction = (
        "너는 이커머스 상품 속성 추출 전문가야. 주어진 상품명에서 브랜드, 용량, 단위, 수량을 찾아 지정된 JSON 형식으로만 답해.\n\n"
        "[대원칙]\n"
        "1. 용량 단위는 g, ml, 팩, 개 등으로 통일해. (kg은 g으로, L는 ml로 환산)\n"
        "2. 반드시 구매자가 최종적으로 받게 되는 '총 팩/개수(Total Quantity)'를 계산해야 해.\n"
        "3. 'A+B개' 또는 'A + B개' 형태의 덧셈 수식이 등장하면 이를 반드시 더한 최종 합산 값을 quantity로 줘.\n"
        "4. '36입, 1개' 또는 '20개, 1개'처럼 묶음 단위 뒤에 ', 1개'가 붙는 경우, 뒤의 1개는 무시하고 실제 대량 묶음 개수(36 또는 20)를 quantity로 줘.\n"
        "5. 면도기+면도날 세트나 참치 6개+고추참치 12개처럼 서로 다른 상품이 섞여 규격화가 안 되는 혼합 상품은 is_valid_for_comparison을 false로 줘.\n\n"
        "[예시 체인]\n"
        "입력: 앱솔루트 명작 분유 2단계 800g, 3개\n"
        "출력: {\"is_valid_for_comparison\": true, \"brand\": \"매일유업\", \"capacity\": 800, \"unit\": \"g\", \"quantity\": 3}"
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"입력: {product_name}\n출력:"}
    ]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=200,
        temperature=0.6,
        top_p=0.95,
        top_k=20,
        min_p=0,
    )
    
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 
    content = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}


# ----------------------------------------------------------------------
# [캐시 판별 속성 추출]
# ----------------------------------------------------------------------
def extract_attributes_with_cache(product_name: str, cache_data: dict) -> dict:
    """
    상품명이 캐시 데이터에 존재하면 LLM을 태우지 않고 즉시 반환하며,
    존재하지 않는 신규 상품명인 경우에만 로컬 GPU로 LLM을 가동합니다.
    """
    if product_name in cache_data:
        print(f"[CACHE HIT] -> {product_name}")
        return cache_data[product_name]
        
    print(f"[LLM CALL]  -> {product_name}")
    attr = extract_attributes_single(product_name)
    cache_data[product_name] = attr
    return attr


def clean_price(price_str: str) -> int:
    """ '28,800원' 형태의 문자열 가격을 순수 정수(int)로 변환합니다. """
    return int(price_str.replace(",", "").replace("원", "").strip())


# ----------------------------------------------------------------------
# [메인 매칭 파이프라인]
# ----------------------------------------------------------------------
def run_matching_pipeline():
    INPUT_FILE = "products_coupang.json"
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] '{INPUT_FILE}' 파일이 없습니다. 2단계 크롤러를 먼저 실행해주세요.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    # 1. 속성을 추출해야 하는 모든 고유 상품명 수집
    all_names = set()
    for item in input_data:
        all_names.add(item["11st_name"])
        for cp_cand in item["coupang_matches"]:
            all_names.add(cp_cand["name"])
            
    unique_names = list(all_names)
    total_count = len(unique_names)
    print(f"[INFO] 전체 상품 목록에서 고유 상품명 {total_count}개 수집 완료.")
    
    # 2. 캐시 로드
    cache_data = load_cache()
    
    # 3. 1:1 순차적으로 캐시 판별 속성 추출
    product_attributes_map = {}
    print(f"[START] 캐시 필터링 기반 속성 추출 시작...")
    
    for name in unique_names:
        attr = extract_attributes_with_cache(name, cache_data)
        product_attributes_map[name] = attr

    # 4. 새로 업데이트된 메모리 캐시 데이터를 로컬 JSON 캐시에 영속화
    save_cache(cache_data)

    # 5. 수집된 속성 지도를 기반으로 매칭 및 최저가 비교 1:1 로컬 연산 수행
    final_matched_results = []
    print("\n[PROCESS] 매칭 및 가격 연산 적용 시작...")
    
    for item in input_data:
        st11_name = item["11st_name"]
        st11_attr = product_attributes_map.get(st11_name)
        
        if not st11_attr:
            st11_attr = {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}
            
        valid_coupang_list = []
        
        for cp_cand in item["coupang_matches"]:
            cp_name = cp_cand["name"]
            cp_attr = product_attributes_map.get(cp_name)
            
            if not cp_attr:
                cp_attr = {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}
                
            # 브랜드명 포함 관계 비교 (유연한 브랜드 대조)
            brand_match = (st11_attr["brand"] in cp_attr["brand"]) or (cp_attr["brand"] in st11_attr["brand"])

            if (st11_attr["is_valid_for_comparison"] and cp_attr["is_valid_for_comparison"] and
                brand_match and
                st11_attr["capacity"] == cp_attr["capacity"] and 
                st11_attr["quantity"] == cp_attr["quantity"] and
                st11_attr["unit"] == cp_attr["unit"]):
                
                cp_cand["pure_price"] = clean_price(cp_cand["price"])
                valid_coupang_list.append(cp_cand)
        
        # 최저가 교통정리
        if valid_coupang_list:
            best_coupang_target = min(valid_coupang_list, key=lambda x: x["pure_price"])
            st11_pure_price = clean_price(item["11st_price"])
            price_diff = best_coupang_target["pure_price"] - st11_pure_price
            
            item["is_matched"] = True
            item["matched_attr"] = st11_attr
            item["final_coupang_target"] = {
                "name": best_coupang_target["name"],
                "price": best_coupang_target["price"],
                "link": best_coupang_target["link"]
            }
            item["is_11st_cheaper_winner_chance"] = price_diff > 0 
            item["price_difference"] = price_diff
            print(f"[MATCH SUCCESS] -> 최저가 쿠팡 상품: {best_coupang_target['name']} ({best_coupang_target['price']})")
        else:
            item["is_matched"] = False
            item["matched_attr"] = st11_attr
            item["final_coupang_target"] = None
            item["is_11st_cheaper_winner_chance"] = False
            item["price_difference"] = 0
            print(f"[MATCH FAIL] '{st11_name}' 매칭 동일 상품 없음 (필터링 완료)")
            
        final_matched_results.append(item)
        
    output_filename = "data_final_matched.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_matched_results, f, ensure_ascii=False, indent=4)
        
    print(f"\n[FINISHED] 검증 완료! 결과가 '{output_filename}'에 저장되었습니다.")

if __name__ == "__main__":
    run_matching_pipeline()
