import json
import os
import sys
import time
from transformers import AutoModelForCausalLM, AutoTokenizer
# import torch

# model_name = "Qwen/Qwen3-0.6B"
# model_name = "Qwen/Qwen3.5-4B"
model_name = "Qwen/Qwen3-4B-Instruct-2507"
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(CURRENT_DIR, "data", "product_attributes_cache.json")
os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
CACHE_TTL_SECONDS = 43200  # 12시간 캐시 유효 기간

print("[READY] 로컬 디스크에서 토크나이저 및 Qwen 모델 로드 중...")

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

DB_AVAILABLE = False
try:
    import psycopg
    from psycopg.rows import dict_row
    DB_AVAILABLE = True
except ImportError:
    pass

def get_db_connection():
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

def load_cache() -> dict:
    """ 로컬 캐시 파일과 DB 매칭 테이블로부터 기매칭된 결과를 로드하여 병합합니다. """
    cache_data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            print(f"[CACHE] 로컬 캐시 파일 {len(cache_data)}개 로드 완료.")
        except Exception as e:
            print(f"[CACHE] 로컬 캐시 파일 읽기 실패: {e}")

    conn = get_db_connection()
    if conn:
        db_count = 0
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                # DB의 기매칭 성공/실패 내역을 1:N 다이렉트 매칭 캐시 형식으로 가공
                cur.execute("""
                    SELECT 
                        source_name, brand, capacity, unit, quantity, is_matched,
                        matched_coupang_name, matched_coupang_link, matched_coupang_price
                    FROM matched_products;
                """)
                for row in cur.fetchall():
                    name = row["source_name"]
                    if name:
                        if row["is_matched"]:
                            cache_data[name] = {
                                "matched_index": 0,
                                "matched_attr": {
                                    "brand": row["brand"],
                                    "capacity": row["capacity"],
                                    "unit": row["unit"],
                                    "quantity": row["quantity"]
                                },
                                "matched_link": row["matched_coupang_link"],
                                "reason": "PostgreSQL 데이터베이스로부터 복원된 최적 매칭 정보입니다.",
                                "timestamp": time.time()
                            }
                        else:
                            cache_data[name] = {
                                "matched_index": None,
                                "matched_attr": None,
                                "reason": "PostgreSQL 데이터베이스로부터 복원된 매칭 실패 정보입니다.",
                                "timestamp": time.time()
                            }
                        db_count += 1
            print(f"[CACHE] PostgreSQL 데이터베이스로부터 {db_count}개 1:N 판정 정보 병합 완료.")
        except Exception as e:
            print(f"[CACHE] DB 캐시 읽기 실패: {e}")
        finally:
            conn.close()

    return cache_data

def save_cache(cache_data: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
        print(f"[CACHE] 최종 {len(cache_data)}개 캐시 데이터 로컬 JSON에 백업 완료.")
    except Exception as e:
        print(f"[CACHE] 로컬 캐시 백업 실패: {e}")

def match_llm_direct_single(st11_name: str, coupang_matches: list) -> dict:
    """ Qwen 모델을 이용해 11st 상품과 여러 쿠팡 후보군을 직접 1:N 최저가 대조 """
    if not coupang_matches:
        return {"matched_index": None, "matched_attr": None, "reason": "쿠팡 비교 후보군이 존재하지 않습니다."}

    # system_instruction = (
    #     "너는 이커머스 상품 매칭 전문가야. 11번가의 기준 상품명 하나와 쿠팡의 비교 대상 후보 상품 목록이 주어졌을 때, "
    #     "브랜드, 용량(규격), 단위, 총 수량이 모두 일치하여 완전히 동일한 상품(동일 SKU)인 대상을 후보 목록에서 찾아내야 해.\n\n"
    #     "[대원칙]\n"
    #     "1. 브랜드: 브랜드명이 완전히 동일하거나, 실질적으로 같은 브랜드여야 해 (예: 'CJ제일제당'과 'CJ', 'Dole'과 '돌'은 동일 브랜드로 취급).\n"
    #     "2. 용량 및 규격: 상품의 단품당 용량이 일치해야 해.\n"
    #     "3. 총 수량(Quantity): 구매자가 최종적으로 받게 되는 '총 개수'가 반드시 일치해야 해.\n"
    #     "4. 패키지 구성: 혼합 구성이거나 맛 종류가 다르면 동일상품이 아님.\n"
    #     "5. 최저가 우선 매칭: 만약 완전히 동일한 상품(동일 SKU) 후보가 여러 개 발견된다면, 그중에서 가격(price)이 가장 저렴한 최저가 후보의 인덱스를 무조건 선택해야 해.\n\n"
    #     "[출력 형식]\n"
    #     "반드시 아래의 JSON 형식으로만 답하고, 다른 설명글은 적지 마.\n"
    #     "{\n"
    #     "  \"matched_index\": 완전히 동일한 상품 중 가격이 가장 저렴한 후보의 인덱스 번호 (0부터 시작, 동일 상품이 없으면 null),\n"
    #     "  \"matched_attr\": {\n"
    #     "    \"brand\": \"추출된 브랜드명 (예: CJ제일제당)\",\n"
    #     "    \"capacity\": 추출된 단품 용량 숫자만 (예: 180),\n"
    #     "    \"unit\": \"추출된 용량 단위 (예: g, ml, 개)\",\n"
    #     "    \"quantity\": 추출된 총 수량 숫자만 (예: 10)\n"
    #     "  },\n"
    #     "  \"reason\": \"일치 여부를 판단한 명확하고 짧은 근거\"\n"
    #     "}"
    # )
    system_instruction = (
        "너는 이커머스 상품 매칭 전문가야. 11번가의 기준 상품명 하나와 쿠팡의 비교 대상 후보 상품 목록이 주어졌을 때, "
        "브랜드, 용량(규격), 단위, 총 수량이 모두 일치하여 완전히 동일한 상품(동일 SKU)인 대상을 후보 목록에서 찾아내야 해.\n\n"
        "[대원칙]\n"
        "1. 브랜드: 브랜드명이 완전히 동일하거나, 실질적으로 같은 브랜드여야 해 (예: 'CJ제일제당'과 'CJ', 'Dole'과 '돌'은 동일 브랜드로 취급).\n"
        "2. 용량 및 규격: 상품의 단품당 용량이 일치해야 해 (예: '180g'과 '180g'은 일치. '210g'과 '216g'처럼 미세한 차이라도 용량이 다르면 일치하지 않는 다른 상품임).\n"
        "3. 총 수량(Quantity): 구매자가 최종적으로 받게 되는 '총 개수'가 반드시 일치해야 해. (예: '180g x 10팩'과 '10개, 180g'은 수량이 10개로 일치. 수량이 다르면 절대 동일상품이 아님).\n"
        "4. 패키지 구성: 혼합 구성이거나 맛 종류가 다르면 동일상품이 아님.\n"
        "5. 최저가 우선 매칭: 만약 완전히 동일한 상품(동일 SKU) 후보가 여러 개 발견된다면, 그중에서 가격(price)이 가장 저렴한 최저가 후보의 인덱스를 무조건 선택해야 해.\n\n"
        "[⚠️ 강력한 제약 및 기각 규칙]\n"
        "- 정보 부재 시 추측 금지: 기준 상품이나 후보 상품 중 한쪽이라도 용량(g, ml 등)이나 수량이 적혀 있지 않다면, 절대 임의로 용량을 상상하거나 추측하여 판정하지 말고 무조건 matched_index를 null로 반환해.\n"
        "- 모음전 배제: 기준 상품명이 슬래시(/)나 쉼표(,) 등으로 여러 종류의 옵션 상품을 나열한 모음전 형태인 경우, 단일 상품 매칭이 불가능하므로 matched_index를 null로 반환해.\n"
        "- 유사 명칭 단어 검증: 브랜드와 핵심 단어가 유사하더라도 끝자리 상품명 형태(예: '초코떡'과 '초코절편')가 명백히 다르면 다른 상품으로 간주해.\n\n"
        "[출력 형식]\n"
        "반드시 아래의 JSON 형식으로만 답하고, 다른 설명글은 적지 마.\n"
        "{\n"
        "  \"matched_index\": 완전히 동일한 상품 중 가격이 가장 저렴한 후보의 인덱스 번호 (0부터 시작, 동일 상품이 없으면 null),\n"
        "  \"matched_attr\": {\n"
        "    \"brand\": \"추출된 브랜드명 (예: CJ제일제당)\",\n"
        "    \"capacity\": 추출된 단품 용량 숫자만 (예: 180),\n"
        "    \"unit\": \"추출된 용량 단위 (예: g, ml, 개)\",\n"
        "    \"quantity\": 추출된 총 수량 숫자만 (예: 10)\n"
        "  } (동일 상품이 없어서 matched_index가 null이면 matched_attr도 null),\n"
        "  \"reason\": \"일치 여부를 판단한 명확하고 짧은 근거 (예: 1번 후보가 180g 10개로 용량 및 수량이 일치하며 최저가임)\"\n"
        "}"
    )

    candidates_text = ""
    for idx, cp_cand in enumerate(coupang_matches):
        candidates_text += f"후보 {idx}: {cp_cand['name']} (가격: {cp_cand['price']})\n"

    prompt = (
        f"기준 상품명 (11번가): {st11_name}\n\n"
        f"쿠팡 후보 목록:\n{candidates_text}\n"
        f"결과 (JSON):"
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": prompt}
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
        max_new_tokens=1000,
        do_sample=True,
        temperature=0.7,
        top_p=0.95,
        top_k=20,
        repetition_penalty=1.0
    )
    
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 
    content = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    file_path = os.path.join(CURRENT_DIR, "data", "raw_llm_output_all.txt")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"=== [상품명: {st11_name}] ===\n")
        f.write(content)
        f.write("\n\n")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"matched_index": None, "matched_attr": None, "reason": "LLM 응답 JSON 파싱 에러"}

def clean_price(price_str: str) -> int:
    return int(price_str.replace(",", "").replace("원", "").strip())

def run_matching_pipeline(category_id="processed_food"):
    INPUT_FILE = os.path.join(CURRENT_DIR, "data", f"products_coupang_{category_id}.json")
    output_filename = os.path.join(CURRENT_DIR, "data", f"data_final_matched_{category_id}.json")
    
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] '{INPUT_FILE}' 파일이 없습니다.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        input_data = json.load(f)

    cache_data = load_cache()
    now = time.time()
    
    final_matched_results = []
    for idx, item in enumerate(input_data):
        st11_name = item["11st_name"]
        coupang_matches = item["coupang_matches"]
        
        cached_result = cache_data.get(st11_name)
        
        db_matched_target_index = None
        if cached_result and "matched_link" in cached_result:
            for c_idx, cp_cand in enumerate(coupang_matches):
                if cp_cand.get("link") == cached_result["matched_link"]:
                    db_matched_target_index = c_idx
                    break
        
        if cached_result and (now - cached_result.get("timestamp", 0) < CACHE_TTL_SECONDS):
            match_result = cached_result
            if db_matched_target_index is not None:
                match_result["matched_index"] = db_matched_target_index
        else:
            match_result = match_llm_direct_single(st11_name, coupang_matches)
            
            cache_data[st11_name] = {
                "matched_index": match_result.get("matched_index"),
                "matched_attr": match_result.get("matched_attr"),
                "reason": match_result.get("reason"),
                "timestamp": now
            }
            matched_idx = match_result.get("matched_index")
            if matched_idx is not None and 0 <= matched_idx < len(coupang_matches):
                cache_data[st11_name]["matched_link"] = coupang_matches[matched_idx].get("link", "")
                
            time.sleep(0.5)
            
        matched_index = match_result.get("matched_index")
        matched_attr = match_result.get("matched_attr")
        
        if matched_index is not None and 0 <= matched_index < len(coupang_matches):
            best_coupang_target = coupang_matches[matched_index]
            
            st11_pure_price = clean_price(item["11st_price"])
            cp_pure_price = clean_price(best_coupang_target["price"])
            price_diff = cp_pure_price - st11_pure_price
            
            item["is_matched"] = True
            item["matched_attr"] = matched_attr
            item["final_coupang_target"] = {
                "name": best_coupang_target["name"],
                "price": best_coupang_target["price"],
                "link": best_coupang_target["link"],
                "image": best_coupang_target.get("image", "")
            }
            item["is_11st_cheaper_winner_chance"] = price_diff > 0 
            item["price_difference"] = price_diff
        else:
            item["is_matched"] = False
            item["matched_attr"] = None
            item["final_coupang_target"] = None
            item["is_11st_cheaper_winner_chance"] = False
            item["price_difference"] = 0
            
        final_matched_results.append(item)
        
    save_cache(cache_data)
        
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_matched_results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    run_matching_pipeline()
