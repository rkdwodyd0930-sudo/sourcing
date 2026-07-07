import React, { useState } from 'react';
import type { ProductItem } from './types/product';
import mockData from '../mockup.json'; // data.json 구조는 이전과 동일합니다.

export default function Test() {
  // 타입을 ProductItem[] 배열로 선언하여 자동 완성을 활성화합니다.
  const [products] = useState<ProductItem[]>(mockData as ProductItem[]);
  const [filter, setFilter] = useState<'all' | 'winner'>('all');

  // 필터링 분기
  const filteredProducts = products.filter((item) => {
    if (filter === 'winner') return item.is_matched && item.is_11st_cheaper_winner_chance;
    return true;
  });

  // 요약 통계 연산
  const totalCount = products.length;
  const matchedCount = products.filter((p) => p.is_matched).length;
  const winnerCount = products.filter((p) => p.is_matched && p.is_11st_cheaper_winner_chance).length;

  return (
    <div className="min-h-screen bg-slate-50 p-6 text-slate-800 font-sans">
      
      {/* 데이터가 성공적으로 불러와졌을 때 상단에 배치 */}
<div className="flex items-center justify-between bg-indigo-50 border border-indigo-100 p-4 rounded-xl mb-6 max-w-6xl mx-auto">
  <div className="flex items-center gap-2">
    <span className="relative flex h-3 w-3">
      {/* 🔴 깜빡이는 실시간 이펙트 */}
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
    </span>
    <p className="text-sm font-semibold text-indigo-900">
      시스템이 정상 작동 중입니다. (1시간 주기 자동 갱신)
    </p>
  </div>
  <p className="text-xs font-bold text-indigo-600 bg-white px-3 py-1.5 rounded-lg shadow-2xs">
    {/* ⏰ 최근 업데이트: {data.last_updated} */} ⏰ 최근 업데이트: 2024-06-15 14:30
  </p>
</div>
      {/* 상단 타이틀 배너 */}
      <header className="mb-8 max-w-6xl mx-auto">
        <h1 className="text-3xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          📊 최저가 매칭 검증 센터 <span className="text-sm font-normal text-slate-400 bg-slate-200/60 px-2 py-0.5 rounded-md">TypeScript Mode</span>
        </h1>
        <p className="text-slate-500 mt-1">11번가 베스트 1,500개 타겟 스크래핑 데이터 모니터링</p>
      </header>

      {/* 대시보드 통계 카드 세트 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto mb-8">
        <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">수집 상품 수</p>
          <p className="text-3xl font-extrabold text-slate-800 mt-1">{totalCount}개</p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-xs border border-slate-100">
          <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">쿠팡 1:1 매칭 완료</p>
          <p className="text-3xl font-extrabold text-indigo-600 mt-1">
            {matchedCount}개 <span className="text-xs font-normal text-slate-400">({totalCount ? ((matchedCount/totalCount)*100).toFixed(0) : 0}%)</span>
          </p>
        </div>
        <div className="bg-white p-6 rounded-2xl shadow-xs border-emerald-100 bg-emerald-50/20">
          <p className="text-xs font-bold text-emerald-600 uppercase tracking-wider">🔥 11번가 위너 찬스</p>
          <p className="text-3xl font-extrabold text-emerald-600 mt-1">{winnerCount}개</p>
        </div>
      </div>

      {/* 상단 컨트롤 탭 필터 버튼 */}
      <div className="max-w-6xl mx-auto mb-6 flex gap-2">
        <button 
          onClick={() => setFilter('all')} 
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${filter === 'all' ? 'bg-slate-900 text-white shadow-md shadow-slate-900/10' : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'}`}
        >
          전체 상품 리스트
        </button>
        <button 
          onClick={() => setFilter('winner')} 
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${filter === 'winner' ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/10' : 'bg-white text-emerald-600 border border-emerald-200 hover:bg-emerald-50'}`}
        >
          🏆 위너 찬스만 ({winnerCount})
        </button>
      </div>

      {/* 리스트 본문 슬롯 */}
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
                    <span className="bg-emerald-100 text-emerald-800 text-xs font-extrabold px-3 py-1.5 rounded-full shadow-xs">🏆 11번가 WINNER</span>
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
              
              {/* 왼쪽 섹션: 11번가 오리지널 데이터 카드 */}
              <div className="flex gap-4 p-4 rounded-xl border border-orange-100 bg-orange-50/10">
                <div className="w-24 h-24 bg-white rounded-lg overflow-hidden flex-shrink-0 border border-slate-200 shadow-2xs">
                  <img src={item["11st_image"]} alt="11번가" className="w-full h-full object-cover" loading="lazy" />
                </div>
                <div className="flex flex-col justify-between flex-1">
                  <div>
                    <span className="text-[10px] font-black bg-orange-500 text-white px-1.5 py-0.5 rounded-sm uppercase tracking-wider">11STREET</span>
                    <p className="text-xl font-black text-slate-800 mt-2">{item["11st_price"]}</p>
                  </div>
                  <a href={item["11st_link"]} target="_blank" rel="noreferrer" className="text-xs text-slate-400 hover:text-orange-500 underline transition-colors">
                    11번가 원본 판매 페이지 ↗
                  </a>
                </div>
              </div>

              {/* 오른쪽 섹션: 쿠팡 매칭 최저가 데이터 카드 */}
              <div className="flex gap-4 p-4 rounded-xl border border-sky-100 bg-sky-50/10">
                {item.is_matched && item.final_coupang_target ? (
                  <>
                    <div className="w-24 h-24 bg-white rounded-lg overflow-hidden flex-shrink-0 border border-slate-200 shadow-2xs">
                      <img src={item.final_coupang_target.image} alt="쿠팡" className="w-full h-full object-cover" loading="lazy" />
                    </div>
                    <div className="flex flex-col justify-between flex-1">
                      <div>
                        <span className="text-[10px] font-black bg-sky-500 text-white px-1.5 py-0.5 rounded-sm uppercase tracking-wider">COUPANG MATCH</span>
                        <p className="text-xs text-slate-500 line-clamp-1 mt-1 font-medium">{item.final_coupang_target.name}</p>
                        <p className="text-xl font-black text-slate-800 mt-0.5">{item.final_coupang_target.price}</p>
                      </div>
                      
                      {/* 매칭 가격 변동폭 리포트 */}
                      <div className={`mt-2 px-3 py-1.5 rounded-lg text-xs font-black flex items-center justify-between ${item.is_11st_cheaper_winner_chance ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                        <span>{item.is_11st_cheaper_winner_chance ? '11번가가 더 저렴!' : '쿠팡이 더 저렴!'}</span>
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
    </div>
  );
}