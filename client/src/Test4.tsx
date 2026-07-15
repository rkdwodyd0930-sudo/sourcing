import { useState, useEffect, useCallback } from 'react';
import type { ProductItem } from './types/product';

interface CategoryConfig {
  category_id: string;
  category_name: string;
  mall_name: string;
  target_url: string;
}

// ngrok 및 로컬 API 연동을 위한 정적 Base URL 선언 (컴포넌트 바깥 최상단 배치)
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// 쇼핑몰 이름에 따른 로고 이미지 및 텍스트 렌더링 (칩 내부 배치용)
const getMallLogo = (mallName: string, isActive = false) => {
  const name = mallName.toLowerCase();
  const textColor = isActive ? 'text-black' : 'text-slate-700';
  
  if (name.includes('11st') || name.includes('11번가')) {
    return (
      <div className="flex items-center gap-2 select-none">
        <img src="/11st_logo.png" alt="11번가" className="h-2 object-contain" />
        <span className={`font-bold text-xs tracking-tight ${textColor}`}>11번가</span>
      </div>
    );
  }
  if (name.includes('gmarket') || name.includes('지마켓')) {
    const gColor = isActive ? 'text-white' : 'text-[#00A5E3]';
    return (
      <div className="flex items-center gap-1.5 select-none">
        <div className="w-4 h-4 rounded-md bg-[#00A5E3] flex items-center justify-center text-white font-black text-[10px]">G</div>
        <span className={`font-black text-xs tracking-tight ${gColor}`}>Gmarket</span>
      </div>
    );
  }
  if (name.includes('auction') || name.includes('옥션')) {
    const aColor = isActive ? 'text-white' : 'text-[#E02020]';
    return (
      <div className="flex items-center gap-1.5 select-none">
        <div className="w-4 h-4 rounded-md bg-[#E02020] flex items-center justify-center text-white font-black text-[10px]">A</div>
        <span className={`font-black text-xs tracking-tight ${aColor}`}>AUCTION</span>
      </div>
    );
  }
  if (name.includes('smartstore') || name.includes('naver') || name.includes('네이버')) {
    const nColor = isActive ? 'text-white' : 'text-[#03C75A]';
    return (
      <div className="flex items-center gap-1.5 select-none">
        <div className="w-4 h-4 rounded-md bg-[#03C75A] flex items-center justify-center text-white font-black text-[10px]">N</div>
        <span className={`font-black text-xs tracking-tight ${nColor}`}>SmartStore</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5 select-none">
      <div className="w-4 h-4 rounded-md bg-slate-500 flex items-center justify-center text-white font-bold text-[10px]">
        {mallName.substring(0, 1).toUpperCase()}
      </div>
      <span className={`font-black text-xs tracking-tight ${textColor}`}>{mallName}</span>
    </div>
  );
};

// 카테고리 이름 가독성 개선 유틸리티
const cleanCategoryName = (name: string) => {
  return name
    .replace(/11번가/g, '')
    .replace(/베스트500/g, '')
    .replace(/\(기본값\)/g, '')
    .trim();
};

export default function Test4() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<CategoryConfig[]>([]);
  
  // 쇼핑몰 및 카테고리 필터 상태 (전체 쇼핑몰 옵션 제거에 따른 기본값 11st 지정)
  const [selectedMall, setSelectedMall] = useState<string>('11st');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  
  const [filter, setFilter] = useState<'all' | 'winner'>('all');
  
  // 백엔드 메타 정보 상태 관리
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // 1. API로부터 데이터 조회 함수
  const fetchProducts = useCallback(async (mall: string, category: string) => {
    setLoading(true);
    setError(null);
    try {
      let url = `${API_BASE_URL}/api/products`;
      const queryParams: string[] = [];
      
      // mall은 항상 유효한 특정 쇼핑몰 값이 오므로 무조건 파라미터 추가
      queryParams.push(`mall=${encodeURIComponent(mall)}`);
      
      if (category !== 'all') {
        queryParams.push(`category=${encodeURIComponent(category)}`);
      }
      
      if (queryParams.length > 0) {
        url += `?${queryParams.join('&')}`;
      }
      
      const response = await fetch(url, {
        headers: {
          "ngrok-skip-browser-warning": "true"
        }
      });
      if (!response.ok) {
        throw new Error('데이터를 가져오는데 실패했습니다.');
      }
      const data = await response.json();
      
      setProducts(data.products || []);
      setCategories(data.categories || []);
      setLastUpdated(data.last_updated || '');
      setIsUpdating(data.is_updating || false);
    } catch (err: any) {
      setError(err.message || '네트워크 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. 쇼핑몰 또는 카테고리 변경 시 데이터 패칭
  useEffect(() => {
    fetchProducts(selectedMall, selectedCategory);
  }, [selectedMall, selectedCategory, fetchProducts]);

  // 쇼핑몰 변경 시 카테고리를 '전체(all)'로 초기화하여 UI 정합성 유지
  useEffect(() => {
    setSelectedCategory('all');
  }, [selectedMall]);

  // 카테고리 설정 마스터 리스트가 로드되었을 때, 만약 현재 selectedMall이 유효하지 않은 값이면 첫 번째 값으로 보정
  useEffect(() => {
    if (categories.length > 0) {
      const mallNames = Array.from(new Set(categories.map((c) => c.mall_name)));
      if (!mallNames.includes(selectedMall)) {
        setSelectedMall(mallNames[0]);
      }
    }
  }, [categories, selectedMall]);

  // 3. 백그라운드 크롤링 상태값 폴링
  useEffect(() => {
    let timer: number;
    if (isUpdating) {
      timer = window.setInterval(async () => {
        try {
          let url = `${API_BASE_URL}/api/products`;
          const queryParams: string[] = [];
          queryParams.push(`mall=${encodeURIComponent(selectedMall)}`);
          if (selectedCategory !== 'all') {
            queryParams.push(`category=${encodeURIComponent(selectedCategory)}`);
          }
          if (queryParams.length > 0) {
            url += `?${queryParams.join('&')}`;
          }
          
          const response = await fetch(url, {
            headers: {
              "ngrok-skip-browser-warning": "true"
            }
          });
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
          console.error('크롤링 상태 조회 오류:', e);
        }
      }, 5000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isUpdating, selectedMall, selectedCategory]);

  // 4. 수동 수집 강제 트리거 함수
  const triggerManualUpdate = async () => {
    if (isUpdating) return;
    
    if (!window.confirm('전체 크롤러와 Qwen LLM 매칭 파이프라인을 즉시 백그라운드에서 가동하시겠습니까?\n약 수 분의 시간이 소요될 수 있습니다.')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/products/trigger`, {
        method: 'POST',
        headers: {
          "ngrok-skip-browser-warning": "true"
        }
      });
      if (response.ok) {
        setIsUpdating(true);
        alert('백그라운드에서 수집 및 매칭 배치가 강제 트리거되었습니다. 잠시만 기다려 주세요.');
      } else {
        const errData = await response.json();
        alert(`트리거 실패: ${errData.detail || '알 수 없는 오류'}`);
      }
    } catch (e) {
      alert('서버와 통신할 수 없습니다.');
    }
  };

  // 5. 필터링 분기
  const filteredProducts = products.filter((item) => {
    if (filter === 'winner') return item.is_matched && item.is_11st_cheaper_winner_chance;
    return true;
  });

  // 6. 요약 통계 연산
  const totalCount = products.length;
  const matchedCount = products.filter((p) => p.is_matched).length;
  const winnerCount = products.filter((p) => p.is_matched && p.is_11st_cheaper_winner_chance).length;

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-800 font-sans">
      
      {/* 1. 상단 시스템 상태 & 알림 배너 */}
      <div className="flex flex-col md:flex-row md:items-center justify-between bg-indigo-50 border border-indigo-100 p-4 rounded-xl mb-6 max-w-6xl mx-auto gap-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            {isUpdating ? (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
              </>
            ) : (
              <>
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
              </>
            )}
          </span>
          <p className="text-sm font-semibold text-indigo-900">
            {isUpdating 
              ? '🔄 백그라운드에서 크롤링 및 로컬 LLM 1:N 매칭이 실행 중입니다...' 
              : '🟢 시스템 대기 상태 (1시간 주기 자동 업데이트 가동 중)'}
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <p className="text-xs font-bold text-indigo-600 bg-white px-3 py-1.5 rounded-lg shadow-2xs">
            ⏰ 최근 업데이트: {lastUpdated ? new Date(lastUpdated).toLocaleString() : '수집 내역 없음'}
          </p>
          <button
            onClick={triggerManualUpdate}
            disabled={true || isUpdating}
            className="px-3 py-1.5 text-xs font-bold rounded-lg transition-all shadow-2xs bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-300 disabled:text-slate-500 disabled:cursor-not-allowed disabled:pointer-events-auto"
          >
            {isUpdating ? '수집 중...' : '⚡ 즉시 수집'}
          </button>
        </div>
      </div>

      {/* 2. 상단 타이틀 배너 */}
      <header className="mb-8 max-w-6xl mx-auto">
        <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          📊 최저가 매칭 검증 센터 
          <span className="text-sm font-normal text-slate-400 bg-slate-200/60 px-2 py-0.5 rounded-md">Live API Mode</span>
        </h1>
        <p className="text-slate-500 mt-1">다중 쇼핑몰 및 카테고리별 실시간 데이터 모니터링</p>
      </header>

      {/* 3. 대시보드 통계 카드 세트 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">수집 상품 수</p>
          <p className="text-3xl font-extrabold text-slate-800 mt-1">{totalCount}개</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">쿠팡 1:N 매칭 완료</p>
          <p className="text-3xl font-extrabold text-indigo-600 mt-1">
            {matchedCount}개 <span className="text-xs font-normal text-slate-400">({totalCount ? ((matchedCount/totalCount)*100).toFixed(0) : 0}%)</span>
          </p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-xs border-emerald-100 bg-emerald-50/20">
          <p className="text-xs font-bold text-emerald-600 uppercase tracking-wider">🔥 소싱처 위너 찬스</p>
          <p className="text-3xl font-extrabold text-emerald-600 mt-1">{winnerCount}개</p>
        </div>
      </div>

      {/* 4. 카테고리 선택 & 필터 컨트롤 구역 */}
      <div className="max-w-6xl mx-auto mb-6 bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex flex-col gap-5">
        
        {/* 쇼핑몰 선택 영역 (상단) - 전체 쇼핑몰 옵션이 제거됨 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">쇼핑몰 선택</span>
          <div className="flex flex-wrap gap-2">
            {Array.from(new Set(categories.map((c) => c.mall_name))).map((mall) => {
              const isActive = selectedMall === mall;
              return (
                <button
                  key={mall}
                  onClick={() => setSelectedMall(mall)}
                  className={`inline-flex items-center rounded-full transition-all border ${
                    isActive
                      ? 'bg-indigo-600/10 border-indigo-600 shadow-sm'
                      : 'bg-white border-slate-200 hover:bg-slate-50'
                  } px-4 py-2`}
                >
                  {getMallLogo(mall, isActive)}
                </button>
              );
            })}
          </div>
        </div>

        <hr className="border-slate-100" />

        {/* 카테고리 선택 영역 (하단) - 선택된 쇼핑몰의 카테고리만 동적 노출 */}
        <div className="flex flex-col gap-2.5">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">카테고리</span>
          <div className="flex flex-wrap gap-2">
            {/* 전체 카테고리 선택 칩 */}
            <button
              onClick={() => setSelectedCategory('all')}
              className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all border ${
                selectedCategory === 'all'
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              전체
            </button>

            {/* 개별 카테고리 선택 칩들 */}
            {categories
              .filter((c) => c.mall_name === selectedMall)
              .map((cat) => {
                const isActive = selectedCategory === cat.category_id;
                return (
                  <button
                    key={cat.category_id}
                    onClick={() => setSelectedCategory(cat.category_id)}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all border ${
                      isActive
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                        : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    {cleanCategoryName(cat.category_name)}
                  </button>
                );
              })}
          </div>
        </div>

        <hr className="border-slate-100" />

        {/* 위너 필터링 버튼 */}
        <div className="flex justify-between items-center flex-wrap gap-3">
          <span className="text-xs font-medium text-slate-400">
            * 쇼핑몰과 카테고리를 선택해 실시간 최저가를 모니터링하세요.
          </span>
          <div className="flex gap-2">
            <button 
              onClick={() => setFilter('all')} 
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all border ${
                filter === 'all' 
                  ? 'bg-slate-900 text-white border-slate-900 shadow-md shadow-slate-900/10' 
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
              }`}
            >
              전체 상품 리스트
            </button>
            <button 
              onClick={() => setFilter('winner')} 
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-all border ${
                filter === 'winner' 
                  ? 'bg-emerald-600 text-white border-emerald-600 shadow-md shadow-emerald-600/10' 
                  : 'bg-white text-emerald-600 border-emerald-200 hover:bg-emerald-50'
              }`}
            >
              🏆 위너 찬스만 ({winnerCount})
            </button>
          </div>
        </div>
      </div>

      {/* 5. 로딩 / 에러 / 데이터 없음 예외 화면 처리 */}
      {loading ? (
        <div className="max-w-6xl mx-auto py-20 text-center text-slate-400 text-sm font-semibold bg-white rounded-2xl border border-slate-100 shadow-2xs">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-indigo-500 border-t-transparent mb-4"></div>
          <p>카테고리 데이터를 동기화하는 중입니다...</p>
        </div>
      ) : error ? (
        <div className="max-w-6xl mx-auto py-12 px-6 text-center text-rose-600 bg-rose-50 border border-rose-100 rounded-2xl">
          <p className="font-bold mb-2">⚠️ 데이터를 로드할 수 없습니다.</p>
          <p className="text-xs text-rose-500">{error}</p>
          <button 
            onClick={() => fetchProducts(selectedMall, selectedCategory)}
            className="mt-4 px-4 py-2 bg-rose-600 text-white text-xs font-bold rounded-lg hover:bg-rose-700 transition-all"
          >
            다시 시도
          </button>
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="max-w-6xl mx-auto py-20 text-center text-slate-400 text-sm bg-white rounded-2xl border border-slate-100 shadow-2xs">
          <p className="font-semibold text-slate-600">수집된 상품 내역이 없습니다.</p>
          <p className="text-xs text-slate-400 mt-1">백그라운드 스케줄러가 작동 중이거나, 즉시 수집을 실행하여 데이터를 채워 주세요.</p>
        </div>
      ) : (
        /* 6. 리스트 본문 슬롯 */
        <main className="max-w-6xl mx-auto flex flex-col gap-6">
          {filteredProducts.map((item, index) => (
            <div key={index} className="bg-white rounded-2xl shadow-xs border border-slate-100 hover:border-slate-300 transition-all p-6">
              
              {/* 상품 타이틀 및 매칭 성공 여부 태그 */}
              <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-4 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="bg-slate-100 text-slate-700 text-xs font-black px-2 py-0.5 rounded-sm">#{index + 1}</span>
                  <span className="text-base font-bold text-slate-900">{item["11st_name"]}</span>
                </div>
                
                <div>
                  {item.is_matched ? (
                    item.is_11st_cheaper_winner_chance ? (
                      <span className="bg-emerald-100 text-emerald-800 text-xs font-extrabold px-3 py-1.5 rounded-full shadow-xs">
                        🏆 {item.source_mall ? item.source_mall.toUpperCase() : '소싱처'} WINNER
                      </span>
                    ) : (
                      <span className="bg-amber-100 text-amber-800 text-xs font-extrabold px-3 py-1.5 rounded-full shadow-xs">📉 쿠팡 WINNER</span>
                    )
                  ) : (
                    <span className="bg-slate-100 text-slate-400 text-xs font-extrabold px-3 py-1.5 rounded-full">❌ 규격 필터 매칭 불가</span>
                  )}
                </div>
              </div>

              {/* 좌우 이미지 비교 메인 레이아웃 구역 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                
                {/* 왼쪽 섹션: 쿠팡 매칭 최저가 데이터 카드 */}
                <div className="flex gap-4 p-4 rounded-xl border border-sky-100 bg-sky-50/10">
                  {item.is_matched && item.final_coupang_target ? (
                    <>
                      <div className="w-24 h-24 bg-white rounded-lg overflow-hidden flex-shrink-0 border border-slate-200 shadow-2xs">
                        {item.final_coupang_target.image ? (
                          <img src={item.final_coupang_target.image} alt="쿠팡" className="w-full h-full object-cover" loading="lazy" />
                        ) : (
                          <div className="w-full h-full bg-slate-100 flex items-center justify-center text-slate-300 text-[10px]">No Image</div>
                        )}
                      </div>
                      <div className="flex flex-col justify-between flex-1">
                        <div>
                          <span className="text-[10px] font-black bg-sky-500 text-white px-1.5 py-0.5 rounded-sm uppercase tracking-wider">COUPANG MATCH</span>
                          <p className="text-xs text-slate-500 line-clamp-1 mt-1 font-medium">{item.final_coupang_target.name}</p>
                          <p className="text-xl font-black text-slate-800 mt-0.5">{item.final_coupang_target.price}</p>
                        </div>
                        
                        <a href={item.final_coupang_target.link} target="_blank" rel="noreferrer" className="text-xs text-slate-400 hover:text-sky-500 underline transition-colors mt-2">
                          쿠팡 원본 판매 페이지 ↗
                        </a>

                        {/* 매칭 가격 변동폭 리포트 */}
                        <div className={`mt-2 px-3 py-1.5 rounded-lg text-xs font-black flex items-center justify-between ${item.is_11st_cheaper_winner_chance ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                          <span>{item.is_11st_cheaper_winner_chance ? '소싱처가 더 저렴!' : '쿠팡이 더 저렴!'}</span>
                          <span className="font-extrabold text-sm">
                            {Math.abs(item.price_difference || 0).toLocaleString()}원 {item.is_11st_cheaper_winner_chance ? '🔻' : '🔺'}
                          </span>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="w-full flex items-center justify-center text-slate-400 text-xs font-medium bg-slate-100/50 rounded-xl border border-dashed border-slate-200">
                      LLM 규격 필터링으로 걸러진 제외 상품입니다.
                    </div>
                  )}
                </div>

                {/* 오른쪽 섹션: 원본 쇼핑몰 데이터 카드 */}
                <div className="flex gap-4 p-4 rounded-xl border border-orange-100 bg-orange-50/10">
                  <div className="w-24 h-24 bg-white rounded-lg overflow-hidden flex-shrink-0 border border-slate-200 shadow-2xs">
                    {item["11st_image"] ? (
                      <img src={item["11st_image"]} alt="소싱처" className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <div className="w-full h-full bg-slate-100 flex items-center justify-center text-slate-300 text-[10px]">No Image</div>
                    )}
                  </div>
                  <div className="flex flex-col justify-between flex-1">
                    <div>
                      <span className="text-[10px] font-black bg-orange-500 text-white px-1.5 py-0.5 rounded-sm uppercase tracking-wider">
                        {item.source_mall ? item.source_mall.toUpperCase() : 'SOURCE'}
                      </span>
                      <p className="text-xs text-slate-500 line-clamp-1 mt-1 font-medium">{item["11st_name"]}</p>
                      <p className="text-xl font-black text-slate-800 mt-2">{item["11st_price"]}</p>
                    </div>
                    <a href={item["11st_link"]} target="_blank" rel="noreferrer" className="text-xs text-slate-400 hover:text-orange-500 underline transition-colors">
                      {item.source_mall ? item.source_mall.toUpperCase() : 'SOURCE'} 원본 판매 페이지 ↗
                    </a>
                  </div>
                </div>

              </div>

              {/* 하단: LLM 속성 추출 메타 태그 라벨 */}
              {item.is_matched && item.matched_attr && (
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-2 flex-wrap">
                  <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2 py-0.5 rounded-md">브랜드: {item.matched_attr.brand}</span>
                  <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2 py-0.5 rounded-md">규격 용량: {item.matched_attr.capacity}{item.matched_attr.unit}</span>
                  <span className="text-[10px] bg-slate-100 text-slate-500 font-bold px-2 py-0.5 rounded-md">매칭 수량: {item.matched_attr.quantity}개</span>
                </div>
              )}

            </div>
          ))}
        </main>
      )}
    </div>
  );
}
