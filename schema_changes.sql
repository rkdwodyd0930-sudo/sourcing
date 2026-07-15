-- ==========================================
-- DB 큐 파이프라인 적용을 위한 스키마 변경 SQL
-- ==========================================

-- 1. 상품 매칭 테이블에 파이프라인 단계 상태(status) 컬럼 추가
-- 기본값은 'PENDING_CRAWL' (11번가 소싱 후 크롤링 대기)
ALTER TABLE matched_products 
ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'PENDING_CRAWL';

-- 2. 쿠팡 크롤러가 수집한 후보군 상품군(최대 5개)을 임시 보관할 JSONB 컬럼 추가
-- LLM 매칭 워커는 이 데이터를 읽어가 매칭 판단을 수행함
ALTER TABLE matched_products 
ADD COLUMN IF NOT EXISTS temp_candidates JSONB;

-- 2.5. 기존 DDL에서 누락되었으나 파이썬 코드에서 사용 중인 쿠팡 매칭 이미지 컬럼 추가
ALTER TABLE matched_products 
ADD COLUMN IF NOT EXISTS matched_coupang_image VARCHAR(2000);

-- 2.7. 카테고리별 실시간 수집 및 노출 순서를 나타내기 위한 display_order 컬럼 추가
ALTER TABLE matched_products 
ADD COLUMN IF NOT EXISTS display_order INT;

-- 3. 큐 스캔 성능 최적화를 위해 status 컬럼에 부분 인덱스(Partial Index) 추가
-- 완료된 데이터('COMPLETED')를 제외한 대기 데이터만 효율적으로 인덱싱함
CREATE INDEX IF NOT EXISTS idx_matched_products_pipeline_queue 
ON matched_products(status) 
WHERE status IN ('PENDING_CRAWL', 'PENDING_MATCH');

-- 3.5. 노출용 상품 정렬 및 필터링 인덱스 추가 (display_order가 등록된 활성 상품 대상)
CREATE INDEX IF NOT EXISTS idx_matched_products_active_display 
ON matched_products(category_id, display_order) 
WHERE display_order IS NOT NULL;

-- 4. 기존 완료된(is_matched가 결정된) 데이터가 있다면 'COMPLETED' 상태로 일괄 전환
UPDATE matched_products 
SET status = 'COMPLETED' 
WHERE status = 'PENDING_CRAWL' AND (is_matched IS TRUE OR is_matched IS FALSE);
