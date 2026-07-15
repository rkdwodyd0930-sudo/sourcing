-- [확장형] 다중 쇼핑몰 및 수집 채널 대응 최저가 매칭 테이블 스키마 DDL

-- 1. 수집 채널 (카테고리/기획전 탭) 마스터 테이블
CREATE TABLE IF NOT EXISTS categories (
    category_id VARCHAR(100) PRIMARY KEY,        -- 표준 카테고리/채널 식별 ID (예: '11st_food', 'ohou_deal')
    category_name VARCHAR(200) NOT NULL,          -- 화면 표시용 이름 (예: '11번가 가공식품', '오늘의집 오늘의딜')
    mall_name VARCHAR(50) NOT NULL,               -- 수집 대상 쇼핑몰 코드 (예: '11st', 'ohou', 'gmarket')
    target_url VARCHAR(1000) NOT NULL,            -- 해당 쇼핑몰의 크롤링 대상 타깃 URL 주소
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 통합 매칭 결과 테이블 (특정 쇼핑몰에 종속되지 않는 범용 필드로 설계)
CREATE TABLE IF NOT EXISTS matched_products (
    id SERIAL PRIMARY KEY,
    source_mall VARCHAR(50) NOT NULL,             -- 수집 출처 쇼핑몰 (예: '11st', 'ohou', 'gmarket')
    source_link VARCHAR(1000) UNIQUE NOT NULL,    -- 소싱 상품 고유 링크 (Upsert 고유 식별 키)
    source_name VARCHAR(1000) NOT NULL,            -- 소싱 상품명
    source_price VARCHAR(100) NOT NULL,           -- 소싱 표시 가격 (예: "38,900원")
    source_pure_price INT NOT NULL,               -- 소싱 정수 가격 (예: 38900)
    source_image VARCHAR(2000),                    -- 소싱 상품 이미지 URL
    category_id VARCHAR(100) REFERENCES categories(category_id) ON DELETE SET NULL, -- 소속 채널/카테고리 (연관관계)
    
    -- LLM 추출 표준 속성 (어느 쇼핑몰이든 공통 규격)
    brand VARCHAR(500),                            -- LLM 브랜드
    capacity INT,                                  -- LLM 용량(규격) 수치
    unit VARCHAR(100),                             -- LLM 단위 (g, ml, 개 등)
    quantity INT,                                  -- LLM 수량
    
    -- 비교 매칭 마켓(쿠팡) 데이터
    is_matched BOOLEAN DEFAULT FALSE,              -- 매칭 성공 여부
    matched_coupang_name VARCHAR(1000),            -- 매칭된 쿠팡 상품명
    matched_coupang_price VARCHAR(100),            -- 매칭된 쿠팡 표시 가격
    matched_coupang_pure_price INT,                -- 매칭된 쿠팡 정수 가격
    matched_coupang_link VARCHAR(2000),            -- 매칭된 쿠팡 링크 URL
    
    -- 가격 차이 분석
    price_difference INT DEFAULT 0,                -- 가격 차이 (쿠팡가 - 소싱처가)
    is_source_cheaper_winner_chance BOOLEAN DEFAULT FALSE, -- 소싱처 상품이 쿠팡보다 싼지 여부 (WINNER 찬스)
    
    last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 데이터 검색 가속화 및 그룹 필터링을 위한 복합 인덱스
CREATE INDEX IF NOT EXISTS idx_matched_products_mall_cat ON matched_products (source_mall, category_id);
CREATE INDEX IF NOT EXISTS idx_matched_products_is_matched ON matched_products (is_matched);
CREATE INDEX IF NOT EXISTS idx_matched_products_winner ON matched_products (is_source_cheaper_winner_chance);


-- [초기 데이터 주입 예시 코드 - 필요 시 DB 클라이언트에서 실행하세요]
-- INSERT INTO categories (category_id, category_name, mall_name, target_url) VALUES 
-- ('11st_processed_food', '11번가 가공식품 베스트', '11st', 'https://www.11st.co.kr/page/best?metaCtgrNo=167009&dispCtgr1No=1001338&categoryNo=167020&dispCtgrLevel=1&dispCtgrNo=1001338&dispCtgrCd=042016'),
-- ('ohou_today_deal', '오늘의집 오늘의딜', 'ohou', 'https://ohou.se/store/today_deals')
-- ON CONFLICT (category_id) DO NOTHING;
