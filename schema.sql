-- 11번가 vs 쿠팡 이커머스 최저가 매칭 결과 테이블 DDL
CREATE TABLE IF NOT EXISTS matched_products (
    id SERIAL PRIMARY KEY,
    st11_link VARCHAR(1000) UNIQUE NOT NULL,      -- 11번가 상품 고유 링크 (중복 식별자)
    st11_name VARCHAR(1000) NOT NULL,              -- 11번가 상품명
    st11_price VARCHAR(100) NOT NULL,             -- 11번가 표시 가격 (예: "28,800원")
    st11_pure_price INT NOT NULL,                 -- 11번가 정수형 실제 가격 (예: 28800)
    st11_image VARCHAR(2000),                      -- 11번가 상품 이미지 URL
    brand VARCHAR(500),                            -- LLM 추출 브랜드
    capacity INT,                                  -- LLM 추출 규격(용량)
    unit VARCHAR(100),                             -- LLM 추출 단위
    quantity INT,                                  -- LLM 추출 수량
    is_matched BOOLEAN DEFAULT FALSE,              -- 매칭 성공 여부
    matched_coupang_name VARCHAR(1000),            -- 매칭된 쿠팡 상품명
    matched_coupang_price VARCHAR(100),            -- 매칭된 쿠팡 표시 가격
    matched_coupang_pure_price INT,                -- 매칭된 쿠팡 정수형 실제 가격
    matched_coupang_link VARCHAR(2000),            -- 매칭된 쿠팡 상품 링크
    price_difference INT DEFAULT 0,                -- 가격 차이 (쿠팡가 - 11번가)
    is_11st_cheaper_winner_chance BOOLEAN DEFAULT FALSE, -- 11번가가 더 저렴한지 여부
    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 매칭 체크 시각
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성 (조회 속도 향상을 위한 인덱스 추가)
CREATE INDEX IF NOT EXISTS idx_matched_products_is_matched ON matched_products (is_matched);
CREATE INDEX IF NOT EXISTS idx_matched_products_cheaper ON matched_products (is_11st_cheaper_winner_chance);
