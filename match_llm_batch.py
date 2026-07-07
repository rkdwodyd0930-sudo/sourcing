import json
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "Qwen/Qwen3.5-4B"

print("[READY] 로컬 디스크에서 토크나이저 및 Qwen 모델 로드 중...")

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

def extract_attributes_single(product_name: str) -> dict:
    """
    배치 파싱 오류 시 안전장치(Fallback)로 작동하는 개별 상품 속성 추출 함수
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


def extract_attributes_batch(product_names: list[str]) -> list[dict]:
    """
    여러 개의 상품명을 리스트 형태로 묶어서(Batch) 한 번의 프롬프트로 전달하고,
    출력 또한 JSON 배열 형태로 받아오는 개선된 속성 추출 함수
    """
    system_instruction = (
        "너는 이커머스 상품 속성 추출 전문가야. 주어진 상품명 목록(JSON 배열)의 각 상품명에서 브랜드, 용량, 단위, 수량을 추출하여, 입력된 순서대로 대응되는 JSON 배열 형식으로만 답해.\n\n"
        "[대원칙]\n"
        "1. 용량 단위는 g, ml, 팩, 개 등으로 통일해. (kg은 g으로, L는 ml로 환산)\n"
        "2. 반드시 구매자가 최종적으로 받게 되는 '총 팩/개수(Total Quantity)'를 계산해야 해.\n"
        "3. 'A+B개' 또는 'A + B개' 형태의 덧셈 수식이 등장하면 이를 반드시 더한 최종 합산 값을 quantity로 줘.\n"
        "4. '36입, 1개' 또는 '20개, 1개'처럼 묶음 단위 뒤에 ', 1개'가 붙는 경우, 뒤의 1개는 무시하고 실제 대량 묶음 개수(36 또는 20)를 quantity로 줘.\n"
        "5. 면도기+면도날 세트나 참치 6개+고추참치 12개처럼 서로 다른 상품이 섞여 규격화가 안 되는 혼합 상품은 is_valid_for_comparison을 false로 줘.\n"
        "6. 입력 데이터가 JSON 배열이므로, 출력 또한 반드시 입력 리스트의 개수와 순서가 정확히 일치하는 동일한 크기의 JSON 배열이어야 해. 추가적인 텍스트나 설명은 절대 하지 마.\n\n"
        "[예시 체인]\n"
        "입력:\n"
        "[\n"
        "  \"앱솔루트 명작 분유 2단계 800g, 3개\",\n"
        "  \"스팸 클래식 340g 10+10개, 1개\",\n"
        "  \"CJ 햇반 윤기가득쌀밥 210g 36입 1개, 36개\"\n"
        "]\n\n"
        "출력:\n"
        "[\n"
        "  {\"is_valid_for_comparison\": true, \"brand\": \"매일유업\", \"capacity\": 800, \"unit\": \"g\", \"quantity\": 3},\n"
        "  {\"is_valid_for_comparison\": true, \"brand\": \"스팸\", \"capacity\": 340, \"unit\": \"g\", \"quantity\": 20},\n"
        "  {\"is_valid_for_comparison\": true, \"brand\": \"CJ\", \"capacity\": 210, \"unit\": \"g\", \"quantity\": 36}\n"
        "]"
    )
    
    input_str = json.dumps(product_names, ensure_ascii=False, indent=2)
    print(f"\n[LLM BATCH INPUT] (Count: {len(product_names)})")
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"입력:\n{input_str}\n출력:"}
    ]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    # 1개 상품명당 평균 120토큰 내외 생성 허용
    max_tokens = max(200, len(product_names) * 120)
    
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=max_tokens,
        temperature=0.3,  # 배치 응답 포맷 안정성을 위해 낮춤
        top_p=0.95,
        top_k=20,
        min_p=0,
    )
    
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 
    content = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
    print(f"[LLM BATCH RESPONSE]:\n{content}")
    
    try:
        results = json.loads(content)
        if isinstance(results, list) and len(results) == len(product_names):
            return results
        else:
            print(f"[WARN] 결과 개수({len(results) if isinstance(results, list) else 'Not List'})와 입력 개수({len(product_names)}) 불일치. 개별 Fallback 모드로 실행합니다.")
    except json.JSONDecodeError:
        print("[WARN] JSON 디코딩 실패. 개별 Fallback 모드로 실행합니다.")
        
    # Fallback 처리
    fallback_results = []
    for name in product_names:
        fallback_results.append(extract_attributes_single(name))
    return fallback_results


def clean_price(price_str: str) -> int:
    """ '28,800원' 형태의 문자열 가격을 순수 정수(int)로 변환합니다. """
    return int(price_str.replace(",", "").replace("원", "").strip())


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
    print(f"[INFO] 전체 상품 목록에서 고유 상품명 {len(unique_names)}개 수집 완료.")
    
    # 2. 고유 상품명들을 청크 크기 단위로 쪼개어 배치로 LLM 전달
    CHUNK_SIZE = 10
    product_attributes_map = {}
    
    print(f"[START] 배치 처리 시작 (청크 크기: {CHUNK_SIZE})")
    for i in range(0, len(unique_names), CHUNK_SIZE):
        chunk = unique_names[i : i + CHUNK_SIZE]
        print(f"\n[BATCH] [{i // CHUNK_SIZE + 1}번째 배치] {len(chunk)}개 상품명 속성 추출 중...")
        
        chunk_results = extract_attributes_batch(chunk)
        
        for name, attr in zip(chunk, chunk_results):
            product_attributes_map[name] = attr

    # 3. 수집된 속성 지도를 기반으로 매칭 및 최저가 비교 1:1 로컬 연산 수행
    final_matched_results = []
    print("\n[PROCESS] 매칭 및 가격 연산 적용 시작...")
    
    for item in input_data:
        st11_name = item["11st_name"]
        st11_attr = product_attributes_map.get(st11_name)
        
        if not st11_attr:
            print(f"[WARN] {st11_name}의 속성 데이터가 유실되었습니다. 개별 보정합니다.")
            st11_attr = extract_attributes_single(st11_name)
            
        valid_coupang_list = []
        
        for cp_cand in item["coupang_matches"]:
            cp_name = cp_cand["name"]
            cp_attr = product_attributes_map.get(cp_name)
            
            if not cp_attr:
                cp_attr = extract_attributes_single(cp_name)
                
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
