import json
import os
import urllib.request
import urllib.error

# 사용하고자 하는 Ollama 모델명 지정 (미리 'ollama pull 모델명'을 통해 다운로드해두어야 합니다.)
OLLAMA_MODEL = "qwen3.5:4b"
OLLAMA_URL = "http://localhost:11434/api/chat"

def call_ollama_api(messages: list) -> str:
    """
    Ollama 로컬 API 서버와 통신하는 함수
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.0  # 생각 모드 억제 및 규칙 강제
        }
    }
    
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            return res_json["message"]["content"].strip()
    except urllib.error.URLError as e:
        print(f"[ERROR] Ollama 서버에 연결할 수 없습니다. 서버가 켜져 있는지 확인해 주세요. ({e})")
        raise e
    except Exception as e:
        print(f"[ERROR] Ollama API 호출 중 예상치 못한 오류 발생: {e}")
        raise e

def extract_attributes_single_ollama(product_name: str) -> dict:
    """
    상품명을 개별(1:1)로 하나씩 Ollama에 보내 속성을 추출하는 함수 (터미널 실시간 출력 포함)
    """
    system_instruction = (
        "[CRITICAL] DO NOT write any reasoning process, thought steps, or <think> tags. You must output ONLY the raw JSON object.\n\n"
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
    
    print(f"\n[INPUT] 상품명: {product_name}")
    try:
        content = call_ollama_api(messages)
        print(f"[OLLAMA OUTPUT]: {content}")
        return json.loads(content)
    except json.JSONDecodeError:
        print("[WARN] JSON 디코딩 실패. 기본 빈 객체를 반환합니다.")
        return {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}
    except Exception as e:
        print(f"[WARN] API 통신 또는 알 수 없는 에러 발생: {e}")
        return {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}

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
    total_count = len(unique_names)
    print(f"[INFO] 전체 상품 목록에서 고유 상품명 {total_count}개 수집 완료.")
    
    # 2. 고유 상품명을 하나씩 순차적으로 처리 및 터미널 출력
    product_attributes_map = {}
    print(f"[START] 1:1 순차 속성 추출 시작 (총 {total_count}개)...")
    
    for i, name in enumerate(unique_names):
        print(f"\n-------------------------------------------")
        print(f"[PROGRESS] [{i + 1} / {total_count}]")
        attr = extract_attributes_single_ollama(name)
        product_attributes_map[name] = attr

    # 3. 수집된 속성 지도를 기반으로 매칭 및 최저가 비교 1:1 로컬 연산 수행
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
