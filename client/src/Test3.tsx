import React, { useState, useEffect, useCallback } from 'react';
import type { ProductItem } from './types/product';

interface CategoryConfig {
  category_id: string;
  category_name: string;
  mall_name: string;
  target_url: string;
}

export default function Test3() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<CategoryConfig[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('processed_food');
  const [filter, setFilter] = useState<'all' | 'winner'>('all');
  
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // 1. API 데이터 페치
  const fetchProducts = useCallback(async (category: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`http://localhost:8000/api/products?category=${category}`);
      if (!response.ok) {
        throw new Error('네트워크 요청이 응답을 거부했습니다.');
      }
      const data = await response.json();
      setProducts(data.products || []);
      setCategories(data.categories || []);
      setLastUpdated(data.last_updated || '');
      setIsUpdating(data.is_updating || false);
    } catch (err: any) {
      setError(err.message || '네트워크 장애가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProducts(selectedCategory);
  }, [selectedCategory, fetchProducts]);

  // 2. 수집 상태 폴링
  useEffect(() => {
    let timer: number;
    if (isUpdating) {
      timer = window.setInterval(async () => {
        try {
          const response = await fetch(`http://localhost:8000/api/products?category=${selectedCategory}`);
          if (response.ok) {
            const data = await response.json();
            setIsUpdating(data.is_updating);
            if (!data.is_updating) {
              setProducts(data.products || []);
              setLastUpdated(data.last_updated || '');
              clearInterval(timer);
            }
          }
        } catch (e) {
          console.error(e);
        }
      }, 5000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isUpdating, selectedCategory]);

  // 3. 수동 트리거
  const triggerManualUpdate = async () => {
    if (isUpdating) return;
    if (!window.confirm('AI 비교 엔진을 강제 기동하시겠습니까?')) return;

    try {
      const response = await fetch('http://localhost:8000/api/products/trigger', { method: 'POST' });
      if (response.ok) {
        setIsUpdating(true);
      } else {
        const errData = await response.json();
        alert(`실패: ${errData.detail}`);
      }
    } catch (e) {
      alert('통신 실패');
    }
  };

  const filteredProducts = products.filter((item) => {
    if (filter === 'winner') return item.is_matched && item.is_11st_cheaper_winner_chance;
    return true;
  });

  const totalCount = products.length;
  const matchedCount = products.filter((p) => p.is_matched).length;
  const winnerCount = products.filter((p) => p.is_matched && p.is_11st_cheaper_winner_chance).length;

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 p-6 md:p-8 font-sans antialiased selection:bg-zinc-900 selection:text-white">
      <div className="max-w-7xl mx-auto">
        
        {/* 상단 씬 헤드 라인 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-zinc-200 pb-6 mb-8 gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">
              Sourcing & Price Matching Panel
            </h1>
            <p className="text-xs text-zinc-500 mt-1 uppercase tracking-widest font-mono">
              verified by local llm (qwen-4b)
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {isUpdating ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
                AI 분석 실행 중
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-zinc-100 text-zinc-600 border border-zinc-200">
                🟢 감시 가동 중
              </span>
            )}
            
            <span className="text-xs text-zinc-500 font-mono">
              Updated: {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : 'N/A'}
            </span>

            <button
              onClick={triggerManualUpdate}
              disabled={isUpdating}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg border transition-all duration-200 ${
                isUpdating 
                  ? 'bg-zinc-100 text-zinc-400 border-zinc-200 cursor-not-allowed' 
                  : 'bg-zinc-950 text-white hover:bg-zinc-800 border-zinc-950 hover:shadow-sm'
              }`}
            >
              즉시 수집
            </button>
          </div>
        </div>

        {/* 심플 대시보드 */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-8 border-b border-zinc-200 pb-8">
          <div>
            <p className="text-xs text-zinc-400 uppercase font-medium">수집 제품군</p>
            <p className="text-2xl font-semibold mt-1">{totalCount}개</p>
          </div>
          <div>
            <p className="text-xs text-zinc-400 uppercase font-medium">1:N 규격 일치율</p>
            <p className="text-2xl font-semibold mt-1 text-zinc-800">
              {totalCount ? ((matchedCount/totalCount)*100).toFixed(0) : 0}% 
              <span className="text-xs text-zinc-400 font-normal ml-2">({matchedCount}개 매칭)</span>
            </p>
          </div>
          <div className="col-span-2 md:col-span-1">
            <p className="text-xs text-zinc-400 uppercase font-medium">소싱 위너 찬스</p>
            <p className="text-2xl font-semibold mt-1 text-emerald-600">{winnerCount}개 기회</p>
          </div>
        </div>

        {/* 필터 세트 */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
          {/* 가로 스크롤형 카테고리 셀렉터 */}
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <button
                key={cat.category_id}
                onClick={() => setSelectedCategory(cat.category_id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all duration-200 ${
                  selectedCategory === cat.category_id
                    ? 'bg-zinc-900 text-white border-zinc-900 shadow-sm'
                    : 'bg-white text-zinc-600 border-zinc-200 hover:border-zinc-300'
                }`}
              >
                {cat.category_name}
              </button>
            ))}
          </div>

          <div className="flex bg-zinc-200/60 p-0.5 rounded-lg border border-zinc-200 text-xs">
            <button 
              onClick={() => setFilter('all')} 
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${filter === 'all' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500'}`}
            >
              전체 보기
            </button>
            <button 
              onClick={() => setFilter('winner')} 
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${filter === 'winner' ? 'bg-white text-zinc-900 shadow-xs' : 'text-zinc-500'}`}
            >
              🏆 위너만 ({winnerCount})
            </button>
          </div>
        </div>

        {/* 로딩 / 에러 바운더리 */}
        {loading ? (
          <div className="py-24 text-center border border-dashed border-zinc-300 bg-white rounded-xl">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-2 border-zinc-900 border-t-transparent mb-3"></div>
            <p className="text-zinc-400 text-xs">데이터 정렬 중...</p>
          </div>
        ) : error ? (
          <div className="py-16 text-center bg-white border border-red-100 rounded-xl px-4">
            <p className="text-red-500 text-sm font-semibold">⚠️ {error}</p>
            <button onClick={() => fetchProducts(selectedCategory)} className="mt-4 px-3 py-1.5 bg-zinc-900 text-white text-xs font-semibold rounded-lg">다시 연결</button>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-24 text-center border border-dashed border-zinc-200 bg-white rounded-xl">
            <p className="text-zinc-400 text-xs">수집 리스트가 비어 있습니다.</p>
          </div>
        ) : (
          /* 매거진 룩: 격자형 그리드 정렬 (한 화면에 더 많이 배치) */
          <main className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProducts.map((item, index) => (
              <div key={index} className="bg-white rounded-xl border border-zinc-200/80 hover:border-zinc-400 transition-all duration-300 overflow-hidden flex flex-col justify-between hover:shadow-lg">
                
                <div>
                  {/* 카드 헤더: 50% 분할 이미지 레이아웃 */}
                  <div className="grid grid-cols-2 border-b border-zinc-100 bg-zinc-50/50 h-36">
                    
                    {/* 왼쪽: 쿠팡 이미지 슬롯 */}
                    <div className="relative flex items-center justify-center p-3 border-r border-zinc-100 h-full">
                      {item.is_matched && item.final_coupang_target ? (
                        <>
                          <span className="absolute top-2 left-2 text-[8px] font-black bg-zinc-900 text-white px-1 py-0.5 rounded-xs tracking-wider z-10">COUPANG</span>
                          {item.final_coupang_target.image ? (
                            <img src={item.final_coupang_target.image} alt="쿠팡" className="w-full h-full object-contain mix-blend-multiply" />
                          ) : (
                            <span className="text-[10px] text-zinc-400">No Image</span>
                          )}
                        </>
                      ) : (
                        <span className="text-[10px] text-zinc-300 font-mono">EXCLUDED</span>
                      )}
                    </div>

                    {/* 오른쪽: 소싱처 이미지 슬롯 */}
                    <div className="relative flex items-center justify-center p-3 h-full">
                      <span className="absolute top-2 left-2 text-[8px] font-black bg-zinc-300 text-zinc-700 px-1 py-0.5 rounded-xs tracking-wider z-10">
                        {item.source_mall ? item.source_mall.toUpperCase() : 'SOURCE'}
                      </span>
                      {item["11st_image"] ? (
                        <img src={item["11st_image"]} alt="소싱처" className="w-full h-full object-contain mix-blend-multiply" />
                      ) : (
                        <span className="text-[10px] text-zinc-400">No Image</span>
                      )}
                    </div>
                  </div>

                  {/* 카드 바디 */}
                  <div className="p-5">
                    {/* 상품 뱃지 및 상태바 */}
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[9px] font-mono text-zinc-400">#{(index + 1).toString().padStart(3, '0')}</span>
                      <div>
                        {item.is_matched ? (
                          item.is_11st_cheaper_winner_chance ? (
                            <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-sm border border-emerald-100">🏆 WINNER</span>
                          ) : (
                            <span className="text-[10px] font-bold text-zinc-500 bg-zinc-100 px-2 py-0.5 rounded-sm border border-zinc-200">📊 COUPANG CHEAP</span>
                          )
                        ) : (
                          <span className="text-[10px] text-zinc-400 bg-zinc-50 px-2 py-0.5 rounded-sm">FILTERED</span>
                        )}
                      </div>
                    </div>

                    {/* 기준 상품명 */}
                    <h3 className="font-semibold text-sm text-zinc-900 tracking-tight line-clamp-2 h-10 mb-4" title={item["11st_name"]}>
                      {item["11st_name"]}
                    </h3>

                    {/* 가격 지표 비교 */}
                    <div className="bg-zinc-50 p-3 rounded-lg border border-zinc-100 mb-3 flex flex-col gap-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400 font-medium">소싱 원가:</span>
                        <span className="font-bold text-zinc-800">{item["11st_price"]}</span>
                      </div>
                      
                      {item.is_matched && item.final_coupang_target ? (
                        <>
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400 font-medium">쿠팡 최저가:</span>
                            <span className="font-bold text-zinc-800">{item.final_coupang_target.price}</span>
                          </div>
                          
                          <div className="flex items-center justify-between text-xs border-t border-zinc-200/50 pt-2 font-semibold">
                            <span className="text-zinc-500">가격 변동폭:</span>
                            <span className={item.is_11st_cheaper_winner_chance ? 'text-emerald-600' : 'text-zinc-800'}>
                              {item.is_11st_cheaper_winner_chance ? '🔻' : '🔺'} {Math.abs(item.price_difference || 0).toLocaleString()}원
                            </span>
                          </div>
                        </>
                      ) : (
                        <div className="text-[10px] text-zinc-400 text-center py-2 border-t border-zinc-200/50 font-mono">
                          NOT MATCHED
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 카드 푸터: 링크 및 메타 태그 */}
                <div className="px-5 pb-5 pt-0 mt-auto border-t border-zinc-100/60 pt-3">
                  {/* 링크 매핑 */}
                  <div className="flex items-center justify-between mb-3 text-[10px] font-medium text-zinc-500">
                    <a href={item["11st_link"]} target="_blank" rel="noreferrer" className="hover:text-zinc-900 underline">
                      소싱처 판매처 ↗
                    </a>
                    {item.is_matched && item.final_coupang_target && (
                      <a href={item.final_coupang_target.link} target="_blank" rel="noreferrer" className="hover:text-zinc-900 underline">
                        쿠팡 판매처 ↗
                      </a>
                    )}
                  </div>

                  {/* LLM 규격 라벨 */}
                  {item.is_matched && item.matched_attr ? (
                    <div className="flex flex-wrap gap-1 text-[9px] text-zinc-400 font-mono">
                      <span className="bg-zinc-100 px-1.5 py-0.5 rounded-sm">브랜드: {item.matched_attr.brand}</span>
                      <span className="bg-zinc-100 px-1.5 py-0.5 rounded-sm">{item.matched_attr.capacity}{item.matched_attr.unit} x {item.matched_attr.quantity}개</span>
                    </div>
                  ) : (
                    <div className="text-[9px] text-zinc-300 font-mono">
                      No metadata attributes available
                    </div>
                  )}
                </div>

              </div>
            ))}
          </main>
        )}
      </div>
    </div>
  );
}
