import React, { useState, useEffect, useCallback } from 'react';
import type { ProductItem } from './types/product';

interface CategoryConfig {
  category_id: string;
  category_name: string;
  mall_name: string;
  target_url: string;
}

export default function Test2() {
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
        throw new Error('데이터를 동기화하지 못했습니다.');
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

  // 2. 수집 상태 폴링 (5초 간격)
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

  // 3. 즉시 수집 트리거
  const triggerManualUpdate = async () => {
    if (isUpdating) return;
    if (!window.confirm('로컬 Qwen-LLM 분석을 포함한 백그라운드 크롤링을 강제 시작하시겠습니까?')) return;

    try {
      const response = await fetch('http://localhost:8000/api/products/trigger', { method: 'POST' });
      if (response.ok) {
        setIsUpdating(true);
      } else {
        const errData = await response.json();
        alert(`실패: ${errData.detail}`);
      }
    } catch (e) {
      alert('서버 응답 없음');
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
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 font-sans antialiased selection:bg-teal-500 selection:text-black">
      
      {/* 백그라운드 글로우 그래픽 데코레이션 */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute top-1/3 right-1/4 w-96 h-96 bg-teal-500/5 rounded-full blur-3xl pointer-events-none"></div>

      <div className="relative z-10 max-w-6xl mx-auto">
        
        {/* 1. 글래스모피즘 상태 배너 */}
        <div className="flex flex-col md:flex-row md:items-center justify-between bg-slate-900/60 backdrop-blur-xl border border-slate-800 p-4 rounded-2xl mb-8 gap-4 shadow-xl">
          <div className="flex items-center gap-3">
            <span className="relative flex h-3.5 w-3.5">
              {isUpdating ? (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-amber-500"></span>
                </>
              ) : (
                <>
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-teal-500"></span>
                </>
              )}
            </span>
            <p className="text-sm font-medium tracking-wide text-slate-300">
              {isUpdating 
                ? '🔄 로컬 AI가 최저가 매칭 및 상품 규격을 분석 중입니다...' 
                : '🟢 실시간 감시 시스템 가동 중 (1시간 주기 갱신)'}
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-400 bg-slate-950/80 px-3 py-1.5 rounded-xl border border-slate-800">
              ⏰ 최근 업데이트: {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '없음'}
            </span>
            <button
              onClick={triggerManualUpdate}
              disabled={isUpdating}
              className={`px-4 py-2 text-xs font-black rounded-xl tracking-wider transition-all duration-300 ${
                isUpdating 
                  ? 'bg-slate-800 text-slate-600 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-teal-500 to-indigo-600 hover:from-teal-400 hover:to-indigo-500 text-white shadow-lg shadow-teal-500/20 active:scale-95'
              }`}
            >
              {isUpdating ? 'RUNNING...' : '⚡ 즉시 수집'}
            </button>
          </div>
        </div>

        {/* 2. 네온 헤더 배너 */}
        <header className="mb-10">
          <h1 className="text-4xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-teal-400">
            METADATA MATCHING
          </h1>
          <p className="text-slate-400 mt-2 text-sm tracking-wide uppercase">AI 기반 다중 이커머스 규격 및 최저가 검증 엔진</p>
        </header>

        {/* 3. 대시보드 메타 카드 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-slate-900/40 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl hover:border-slate-700 transition-all duration-300 group">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest group-hover:text-teal-400 transition-colors">Target Products</p>
            <p className="text-4xl font-black text-white mt-2 tracking-tight">{totalCount} <span className="text-lg font-normal text-slate-500">Items</span></p>
          </div>
          <div className="bg-slate-900/40 backdrop-blur-md border border-slate-800/80 p-6 rounded-2xl shadow-xl hover:border-slate-700 transition-all duration-300 group">
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest group-hover:text-indigo-400 transition-colors">AI Matching Rate</p>
            <p className="text-4xl font-black text-indigo-400 mt-2 tracking-tight">
              {totalCount ? ((matchedCount/totalCount)*100).toFixed(0) : 0}% 
              <span className="text-xs font-normal text-slate-500 ml-2">({matchedCount}개 완매칭)</span>
            </p>
          </div>
          <div className="bg-gradient-to-br from-teal-950/20 to-emerald-950/20 backdrop-blur-md border border-teal-500/20 p-6 rounded-2xl shadow-xl hover:border-teal-500/40 transition-all duration-300 group">
            <p className="text-xs font-bold text-teal-400 uppercase tracking-widest">🏆 Cheaper Sourcing Chance</p>
            <p className="text-4xl font-black text-teal-400 mt-2 tracking-tight">{winnerCount} <span className="text-lg font-normal text-teal-600">Wins</span></p>
          </div>
        </div>

        {/* 4. 필터 콘트롤 세트 */}
        <div className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="flex flex-wrap gap-2.5">
            {categories.map((cat) => (
              <button
                key={cat.category_id}
                onClick={() => setSelectedCategory(cat.category_id)}
                className={`px-4 py-2.5 rounded-xl text-xs font-bold tracking-wider transition-all duration-300 border ${
                  selectedCategory === cat.category_id
                    ? 'bg-white text-black border-white shadow-lg'
                    : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:text-white hover:border-slate-700'
                }`}
              >
                {cat.category_name}
              </button>
            ))}
          </div>

          <div className="flex gap-2 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
            <button 
              onClick={() => setFilter('all')} 
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 ${filter === 'all' ? 'bg-slate-800 text-teal-400' : 'text-slate-500 hover:text-slate-300'}`}
            >
              전체 리스트
            </button>
            <button 
              onClick={() => setFilter('winner')} 
              className={`px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 ${filter === 'winner' ? 'bg-slate-800 text-teal-400' : 'text-slate-500 hover:text-slate-300'}`}
            >
              위너 찬스 ({winnerCount})
            </button>
          </div>
        </div>

        {/* 5. 콘텐츠 영역 */}
        {loading ? (
          <div className="py-24 text-center bg-slate-900/20 border border-slate-900 rounded-3xl backdrop-blur-md">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-teal-500 border-t-transparent mb-4"></div>
            <p className="text-slate-500 text-sm">로컬 DB 데이터 로딩 중...</p>
          </div>
        ) : error ? (
          <div className="py-16 text-center bg-rose-950/20 border border-rose-900/50 rounded-3xl px-6">
            <p className="text-rose-400 font-bold">⚠️ 연결 실패</p>
            <p className="text-xs text-rose-500 mt-2">{error}</p>
            <button onClick={() => fetchProducts(selectedCategory)} className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-500 text-xs font-bold rounded-lg transition-all">재접속 시도</button>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-24 text-center bg-slate-900/20 border border-slate-900 rounded-3xl">
            <p className="text-slate-500 text-sm">해당 조건에 만족하는 수집 상품이 없습니다.</p>
          </div>
        ) : (
          <main className="flex flex-col gap-6">
            {filteredProducts.map((item, index) => (
              <div key={index} className="bg-slate-900/30 backdrop-blur-md rounded-2xl border border-slate-900 hover:border-slate-800 transition-all duration-300 p-6 shadow-xl">
                
                {/* 상단 타이틀 */}
                <div className="flex flex-wrap items-center justify-between gap-4 mb-4 pb-3 border-b border-slate-800/80">
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-black bg-slate-800 text-slate-400 px-2 py-0.5 rounded-sm">#{index + 1}</span>
                    <span className="text-base font-bold text-white tracking-tight">{item["11st_name"]}</span>
                  </div>
                  <div>
                    {item.is_matched ? (
                      item.is_11st_cheaper_winner_chance ? (
                        <span className="bg-teal-500/10 text-teal-400 border border-teal-500/20 text-xs font-bold px-3 py-1.5 rounded-full shadow-xs">🏆 소싱 위너</span>
                      ) : (
                        <span className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-bold px-3 py-1.5 rounded-full shadow-xs">📉 쿠팡 위너</span>
                      )
                    ) : (
                      <span className="bg-slate-800 text-slate-500 text-xs font-bold px-3 py-1.5 rounded-full">❌ 미매칭</span>
                    )}
                  </div>
                </div>

                {/* 상품 비교 듀얼 그리드 (쿠팡이 왼쪽, 11번가가 오른쪽) */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  
                  {/* 왼쪽 섹션: 쿠팡 (COUPANG MATCH) */}
                  <div className="flex gap-4 p-4 rounded-xl border border-slate-800/50 bg-slate-950/60 relative overflow-hidden">
                    {item.is_matched && item.final_coupang_target ? (
                      <>
                        <div className="w-20 h-20 bg-slate-900 rounded-lg overflow-hidden flex-shrink-0 border border-slate-800">
                          {item.final_coupang_target.image ? (
                            <img src={item.final_coupang_target.image} alt="쿠팡" className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-slate-600 text-[10px]">No Image</div>
                          )}
                        </div>
                        <div className="flex flex-col justify-between flex-1">
                          <div>
                            <span className="text-[9px] font-black bg-cyan-600 text-white px-2 py-0.5 rounded-sm uppercase tracking-wider">COUPANG</span>
                            <p className="text-xs text-slate-400 line-clamp-1 mt-1">{item.final_coupang_target.name}</p>
                            <p className="text-lg font-black text-cyan-400 mt-0.5">{item.final_coupang_target.price}</p>
                          </div>
                          <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-900">
                            <a href={item.final_coupang_target.link} target="_blank" rel="noreferrer" className="text-[10px] text-slate-500 hover:text-cyan-400 transition-colors underline">
                              쿠팡 원본 ↗
                            </a>
                            {/* 가격 변동 리포팅 */}
                            <span className={`text-[11px] font-bold ${item.is_11st_cheaper_winner_chance ? 'text-teal-400' : 'text-amber-400'}`}>
                              {item.is_11st_cheaper_winner_chance ? '🔻' : '🔺'} {Math.abs(item.price_difference || 0).toLocaleString()}원
                            </span>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="w-full flex items-center justify-center text-slate-600 text-xs py-8">
                        규격 불일치로 매칭 제외된 대상입니다.
                      </div>
                    )}
                  </div>

                  {/* 오른쪽 섹션: 오리지널 소싱처 (SOURCE) */}
                  <div className="flex gap-4 p-4 rounded-xl border border-slate-800/50 bg-slate-950/60">
                    <div className="w-20 h-20 bg-slate-900 rounded-lg overflow-hidden flex-shrink-0 border border-slate-800">
                      {item["11st_image"] ? (
                        <img src={item["11st_image"]} alt="소싱처" className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-600 text-[10px]">No Image</div>
                      )}
                    </div>
                    <div className="flex flex-col justify-between flex-1">
                      <div>
                        <span className="text-[9px] font-black bg-orange-600 text-white px-2 py-0.5 rounded-sm uppercase tracking-wider">
                          {item.source_mall ? item.source_mall.toUpperCase() : 'SOURCE'}
                        </span>
                        <p className="text-xs text-slate-400 line-clamp-1 mt-1">{item["11st_name"]}</p>
                        <p className="text-lg font-black text-orange-400 mt-0.5">{item["11st_price"]}</p>
                      </div>
                      <a href={item["11st_link"]} target="_blank" rel="noreferrer" className="text-[10px] text-slate-500 hover:text-orange-400 transition-colors underline mt-2">
                        소싱처 원본 ↗
                      </a>
                    </div>
                  </div>

                </div>

                {/* 하단 LLM 메타 태그 */}
                {item.is_matched && item.matched_attr && (
                  <div className="mt-4 pt-3 border-t border-slate-800/40 flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] text-slate-500 bg-slate-950 px-2 py-1 rounded-md border border-slate-900">브랜드: {item.matched_attr.brand}</span>
                    <span className="text-[10px] text-slate-500 bg-slate-950 px-2 py-1 rounded-md border border-slate-900">규격: {item.matched_attr.capacity}{item.matched_attr.unit}</span>
                    <span className="text-[10px] text-slate-500 bg-slate-950 px-2 py-1 rounded-md border border-slate-900">수량: {item.matched_attr.quantity}개</span>
                  </div>
                )}

              </div>
            ))}
          </main>
        )}
      </div>
    </div>
  );
}
