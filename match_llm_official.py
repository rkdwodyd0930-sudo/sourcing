import json
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer

# 1. 방금 다운로드한 로컬 폴더 경로 지정 (인터넷 통신 완전 차단)
# LOCAL_MODEL_PATH = "../crawl/qwen3_06b_local"

# print("⏳ 로컬 디스크에서 토크나이저 및 Qwen 모델 로드 중...")

# tokenizer = AutoTokenizer.from_pretrained(LOCAL_MODEL_PATH)
# model = AutoModelForCausalLM.from_pretrained(
#     LOCAL_MODEL_PATH,
#     device_map="auto",
#     dtype="auto"
# )

model_name = "Qwen/Qwen3.5-4B"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)
# tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
# model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-7B-Instruct")
# model_name = "Qwen/Qwen2.5-7B-Instruct-AWQ"
# model = AutoModelForCausalLM.from_pretrained(
#     model_name,
#     torch_dtype="auto",
#     device_map="auto"
# )
# tokenizer = AutoTokenizer.from_pretrained(model_name)


def extract_attributes_with_llm(product_name: str) -> dict:
    # """
    # 공식 문서 퀵스타트 방식으로 개조된 속성 추출 함수 (생각 모드 완전 OFF)
    # """
    # system_instruction = (
    #     "너는 이커머스 상품 속성 추출 전문가야. 주어진 상품명에서 브랜드, 용량, 단위, 수량을 찾아 지정된 JSON 형식으로만 답해.\n"
    #     "[규칙]\n"
    #     "1. 용량 단위는 g, ml, 팩, 개 등으로 통일해. (kg은 g으로, L는 ml로 환산)\n"
    #     "2. 350ml+350ml 처럼 덧셈 수식이 있다면 capacity는 350, quantity는 2로 해석해.\n"
    #     "3. 면도기+면도날 세트처럼 규격화가 안 되는 혼합 상품은 is_valid_for_comparison을 false로 줘.\n\n"
    #     "[예시]\n"
    #     "입력: 앱솔루트 명작 분유 2단계 800g, 3개\n"
    #     "출력: {\"is_valid_for_comparison\": true, \"brand\": \"매일유업\", \"capacity\": 800, \"unit\": \"g\", \"quantity\": 3}"
    # )
    """
    공식 문서 퀵스타트 방식으로 개조된 속성 추출 함수 (묶음/스팸 상품 수량 계산 강화)
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
        "출력: {\"is_valid_for_comparison\": true, \"brand\": \"매일유업\", \"capacity\": 800, \"unit\": \"g\", \"quantity\": 3}\n\n"
        "입력: 스팸 클래식 340g 10+10개, 1개\n"
        "출력: {\"is_valid_for_comparison\": true, \"brand\": \"스팸\", \"capacity\": 340, \"unit\": \"g\", \"quantity\": 20}\n\n"
        "입력: CJ 햇반 윤기가득쌀밥 210g 36입 1개, 36개\n"
        "출력: {\"is_valid_for_comparison\": true, \"brand\": \"CJ\", \"capacity\": 210, \"unit\": \"g\", \"quantity\": 36}\n\n"
        "입력: 동원 라이트스탠다드참치 85g 6개 + 고추참치 85g 12개, 18개\n"
        "출력: {\"is_valid_for_comparison\": false, \"brand\": \"동원\", \"capacity\": 85, \"unit\": \"g\", \"quantity\": 18}"
    )
    print(f" [입력으로 들어간 product_name]: {product_name}")

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"입력: {product_name}\n출력:"}
    ]
    
    # 2. 공식 문서 방식: 챗 템플릿 조립 시 생각 모드를 False로 강제 차단!
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False  # 💡 공식 가이드대로 생각 모드를 완전히 끕니다.
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    # 3. 공식 문서 방식: 텍스트 완성(Generate) 수행
    # 공식 문서가 제안하는 Non-thinking 전용 샘플링 파라미터를 명시적으로 주입합니다.
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=200,       # 32768은 너무 기므로 JSON 길이에 맞게 60으로 제한
        temperature=0.6,         # 공식 권장값 0.7
        top_p=0.95,               # 공식 권장값 0.8
        top_k=20,                # 공식 권장값 20
        min_p=0,              # 공식 권장값 0
        # do_sample=True          # 정량적인 결과 고정을 위해 샘플링 무작위성 제거
    )
    
    # 입력 프롬프트 부분을 떼어내고 순수 답변 ID만 추출
    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist() 
    
    # 4. 공식 문서 방식: 생각 모드가 꺼졌으므로 바로 content만 깔끔하게 디코드
    content = tokenizer.decode(output_ids, skip_special_tokens=True).strip("\n")
    print(f"🤖 [LLM 날것의 답변]: {content}")
    
    # 예외적 포맷 깨짐 방지를 위한 예외 처리
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"is_valid_for_comparison": False, "brand": "unknown", "capacity": 0, "unit": "none", "quantity": 0}

def clean_price(price_str: str) -> int:
    """ '28,800원' 형태의 문자열 가격을 순수 정수(int)로 변환합니다. """
    return int(price_str.replace(",", "").replace("원", "").strip())

def run_matching_pipeline():
    # 2단계(scrape_coupang.py)에서 생성된 가상의 JSON 데이터 세트 (질문자님 예시 반영)
    mock_input_data = [
        {
            "11st_name": "동원 라이트스탠다드참치, 85g, 18개",
            "11st_price": "28,800원",
            "11st_link": "https://www.11st.co.kr/products/8877601502",
            "coupang_matches": [
                {
                    "name": "동원 라이트스탠다드 참치, 85g, 18개",
                    "price": "36,900원",
                    "link": "https://www.coupang.com/vp/products/1"
                },
                {
                    "name": "동원 라이트스탠다드참치 85g 6개 + 고추참치 85g 12개, 18개",
                    "price": "30,700원",
                    "link": "https://www.coupang.com/vp/products/2"
                },
                {
                    "name": "동원참치 라이트 스탠다드, 85g, 18개",
                    "price": "36,330원",
                    "link": "https://www.coupang.com/vp/products/3"
                }
            ]
        },
        {
            "11st_name": "[유귀열 THE귀한] 도가니탕 700g x 5팩",
            "11st_price": "45,000원",
            "11st_link": "https://www.11st.co.kr/products/8877601503",
            "coupang_matches": [
                {
                    "name": "한복선 녹두품은 능이 삼계탕 1kg x 4팩",
                    "price": "39,000원",
                    "link": "https://www.coupang.com/vp/products/4"
                },
                {
                    "name": "유귀열의 The귀한 도가니탕 700g 5팩, 5개",
                    "price": "42,000원",
                    "link": "https://www.coupang.com/vp/products/5"
                }
            ]
        }
    ]
    
    final_matched_results = []
    print("\n🚀 [3단계 파이프라인] 매칭 및 가격 연산 시작...")
    
    INPUT_FILE = "products_coupang.json"
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 에러: '{INPUT_FILE}' 파일이 없습니다. 2단계 크롤러를 먼저 실행해주세요.")
        return
        
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        mock_input_data = json.load(f)

    for item in mock_input_data:
        st11_name = item["11st_name"]
        print(f"\n🔍 분석 중인 11번가 상품: {st11_name}")
        
        # 11번가 속성 추출
        st11_attr = extract_attributes_with_llm(st11_name)
        valid_coupang_list = []
        
        # 쿠팡 후보군 1:1 순회
        for cp_cand in item["coupang_matches"]:
            cp_name = cp_cand["name"]
            cp_attr = extract_attributes_with_llm(cp_name)
            
            # 파이썬 메인 로직 하드 필터링 (브랜드, 용량, 수량, 단위)
            brand_match = (st11_attr["brand"] in cp_attr["brand"]) or (cp_attr["brand"] in st11_attr["brand"])

            if (st11_attr["is_valid_for_comparison"] and cp_attr["is_valid_for_comparison"] and
                brand_match and
                st11_attr["capacity"] == cp_attr["capacity"] and 
                st11_attr["quantity"] == cp_attr["quantity"] and
                st11_attr["unit"] == cp_attr["unit"]):
                
                cp_cand["pure_price"] = clean_price(cp_cand["price"])
                valid_coupang_list.append(cp_cand)
        
        # 최종 교통정리
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
            print(f"✅ 매칭 성공! -> 최저가 쿠팡 상품: {best_coupang_target['name']} ({best_coupang_target['price']})")
        else:
            item["is_matched"] = False
            item["matched_attr"] = st11_attr
            item["final_coupang_target"] = None
            item["is_11st_cheaper_winner_chance"] = False
            item["price_difference"] = 0
            print("❌ 동일 상품 없음 (필터링 완료)")
            
        final_matched_results.append(item)
        
    output_filename = "data_final_matched.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(final_matched_results, f, ensure_ascii=False, indent=4)
        
    print(f"\n🏁 검증 완료! 결과가 '{output_filename}'에 저장되었습니다.")

if __name__ == "__main__":
    run_matching_pipeline()