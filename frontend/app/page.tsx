"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, Check, ChevronRight, Clock3, Compass, MapPin, Menu, RefreshCw, Route, Search, Sparkles, X } from "lucide-react";

type Spot = {
  // TODO(BE): 백엔드 응답 필드(tAtsNm, rlteTatsNm 등)는 API 변환 함수에서
  // 이 프론트엔드 공통 모델로 매핑합니다. API 원본 필드명을 JSX에 직접 사용하지 않습니다.
  id: number;
  name: string;
  address: string;
  description: string;
  category: string;
  rate: number;
  image: string;
};

/**
 * EDIT(UI): 홈 검색 결과에 보이는 임시 관광지 데이터입니다.
 * 문구/주소/집중률/사진을 바꾸려면 아래 값을 수정하세요.
 * 실제 연동 후에는 삭제하고 GET /api/spots 검색 결과로 대체합니다.
 * TODO(BE): 상세정보 응답에 id, 명소명, 주소, 소개문구, 이미지 URL,
 * cnctrRate7dAvg가 모두 포함되어야 합니다.
 */
const spots: Spot[] = [
  { id: 1, name: "해운대해수욕장", address: "부산광역시 해운대구 해운대해변로 264", description: "푸른 바다를 따라 걷기 좋은 부산의 대표 해변입니다.", category: "자연 · 해변", rate: 78, image: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=80" },
  { id: 2, name: "경주 불국사", address: "경상북도 경주시 불국로 385", description: "신라 시대의 대표 사찰로 천년의 이야기를 만납니다.", category: "역사 · 사찰", rate: 62, image: "https://images.unsplash.com/photo-1578469645742-46cae010e5d4?auto=format&fit=crop&w=900&q=80" },
  { id: 3, name: "제주 성산일출봉", address: "제주특별자치도 서귀포시 성산읍", description: "바다 위로 떠오르는 일출과 아름다운 능선을 감상해요.", category: "자연 · 명승", rate: 28, image: "https://images.unsplash.com/photo-1578469645742-46cae010e5d4?auto=format&fit=crop&w=900&q=80" },
];

/**
 * EDIT(UI): 추천 화면 확인을 위한 임시 데이터입니다.
 * TODO(BE): recommend() 응답의 recommendations를 Spot[]으로 변환해 이 배열 대신 사용합니다.
 * 이미지/주소/소개문구는 recommend() 원본에 없으므로 백엔드에서 관광지 기본정보를
 * 결합해서 내려주거나 별도의 상세정보 API를 호출해야 합니다.
 */
const recommendations: Spot[] = [
  { id: 11, name: "송정해수욕장", address: "부산 해운대구", description: "부드러운 파도와 여유로운 산책로가 있는 해변", category: "자연 · 해변 · 해수욕장", rate: 42, image: "https://images.unsplash.com/photo-1473116763249-2faaef81ccda?auto=format&fit=crop&w=700&q=80" },
  { id: 12, name: "청사포", address: "부산 해운대구", description: "등대와 바다열차가 어우러지는 작은 포구", category: "자연 · 해양 · 해안경관", rate: 31, image: "https://images.unsplash.com/photo-1494783367193-149034c05e8f?auto=format&fit=crop&w=700&q=80" },
  { id: 13, name: "기장 일광해수욕장", address: "부산 기장군", description: "잔잔한 수면과 넓은 모래사장이 편안한 해변", category: "자연 · 해변 · 해수욕장", rate: 45, image: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=700&q=80" },
  { id: 14, name: "죽성성당", address: "부산 기장군", description: "푸른 바다를 배경으로 선 그림 같은 작은 성당", category: "문화 · 역사 · 건축물", rate: 26, image: "https://images.unsplash.com/photo-1548625361-ec8533b9b9f4?auto=format&fit=crop&w=700&q=80" },
  { id: 15, name: "오시리아 해안산책로", address: "부산 기장군", description: "바닷바람을 맞으며 천천히 걷기 좋은 산책로", category: "자연 · 해양 · 산책로", rate: 24, image: "https://images.unsplash.com/photo-1498623116890-37e912163d5d?auto=format&fit=crop&w=700&q=80" },
];

// EDIT(UI): 혼잡 단계 기준과 화면 문구를 바꾸는 곳입니다. 최종 기준은 백엔드와 합의해야 합니다.
function crowd(rate: number) {
  if (rate >= 70) return { text: "매우 혼잡", className: "very" };
  if (rate >= 50) return { text: "혼잡", className: "busy" };
  if (rate >= 30) return { text: "보통", className: "normal" };
  return { text: "여유", className: "calm" };
}

function Steps({ step }: { step: number }) {
  return <ol className="steps" aria-label="서비스 진행 단계">{["과밀 관광지", "유사 명소 추천", "코스 생성"].map((label, i) => <li className={step >= i + 1 ? "active" : ""} key={label}><span>{step > i + 1 ? <Check size={13} /> : i + 1}</span><small>{label}</small></li>)}</ol>;
}

function Brand() {
  return <div className="brand"><span className="comma">●</span><strong>쉼표투어</strong></div>;
}

function Header({ step }: { step: number }) {
  return <header><Brand /><Steps step={step} /><button className="icon-button" aria-label="메뉴 열기"><Menu /></button></header>;
}

function Gauge({ rate }: { rate: number }) {
  const state = crowd(rate);
  return <div className={`gauge ${state.className}`} style={{ "--rate": `${rate * 3.6}deg` } as React.CSSProperties}><div><strong>{rate}%</strong><small>{state.text}</small></div></div>;
}

export default function Home() {
  // TODO(BE): API 연동 시 spots/recommendations를 서버 상태로 분리하고
  // loading, error, empty 상태를 실제 요청 결과에 맞춰 관리합니다.
  const [step, setStep] = useState(1);
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [selectedBase, setSelectedBase] = useState<Spot>(spots[0]);
  const [selected, setSelected] = useState<number[]>([11, 12]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"region" | "name">("region");

  // TODO(BE): 현재는 브라우저에서 임시 데이터를 필터링합니다.
  // 지역/관광지명/검색어를 GET /api/spots의 query parameter로 전달하도록 교체합니다.
  const results = useMemo(() => searched ? spots.filter(s => s.name.includes(query) || s.address.includes(query)) : spots, [query, searched]);

  // TODO(BE): 코스 순서, 거리, 이동시간은 향후 POST /api/courses 응답을 사용해야 합니다.
  const course = recommendations.filter(s => selected.includes(s.id));

  // TODO(BE): setTimeout은 UI 시연용입니다. 아래 흐름으로 교체합니다.
  // 1) 선택 관광지 id를 POST /api/recommend에 전달
  // 2) congestedSpot과 recommendations 응답을 상태에 저장
  // 3) 실패 시 에러 메시지/재시도 버튼을 표시하고 finally에서 loading 해제
  const goRecommend = (spot: Spot) => {
    setSelectedBase(spot); setLoading(true); setStep(2);
    window.setTimeout(() => setLoading(false), 850);
  };

  return <main><div className="shell"><Header step={step} />
    {step === 1 && <section className="page-section">
      {/* EDIT(UI): 홈 화면의 제목과 설명 문구를 수정 */}
      <div className="hero-copy"><p className="eyebrow"><Sparkles size={16} /> 오늘의 여행에 쉼표 하나</p><h1>붐비는 곳에서 한 걸음 벗어나,<br /><em>나만의 여유</em>를 찾아보세요.</h1><p>관광지의 예상 집중률을 확인하고, 비슷하지만 더 여유로운 장소를 추천받아 보세요.</p></div>
      <div className="search-panel">
        <div className="tabs"><button className={tab === "region" ? "active" : ""} onClick={() => setTab("region")}>지역으로 검색</button><button className={tab === "name" ? "active" : ""} onClick={() => setTab("name")}>관광지명 검색</button></div>
        <div className="search-row">{tab === "region" && <><select aria-label="시/도 선택"><option>시/도 선택</option><option>부산광역시</option><option>경상북도</option><option>제주특별자치도</option></select><select aria-label="시군구 선택"><option>시/군/구 선택</option><option>해운대구</option><option>경주시</option><option>서귀포시</option></select></>}<label className="search-input"><Search size={18} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="관광지명을 입력하세요" onKeyDown={e => e.key === "Enter" && setSearched(true)} />{query && <button aria-label="검색어 지우기" onClick={() => setQuery("")}><X size={16} /></button>}</label><button className="primary" onClick={() => setSearched(true)}>검색</button></div>
        {tab === "name" && query && !searched && <div className="suggestions">{spots.filter(s => s.name.includes(query)).map(s => <button key={s.id} onClick={() => { setQuery(s.name); setSearched(true); }}><MapPin size={15} />{s.name}<small>{s.address}</small></button>)}</div>}
      </div>
      <div className="section-title"><div><span>SEARCH RESULT</span><h2>검색 결과 <small>{results.length}건</small></h2></div></div>
      {/* EDIT(UI): 카드 사진은 spot.image, 문구는 spot.name/address/description에서 바뀝니다. */}
      {results.length ? <div className="result-list">{results.map(spot => { const state = crowd(spot.rate); return <article className="result-card" key={spot.id}><img src={spot.image} alt={`${spot.name} 전경`} /><div className="spot-info"><div className="category">{spot.category}</div><h3>{spot.name}</h3><p className="address"><MapPin size={14} />{spot.address}</p><p>{spot.description}</p></div><div className="rate-block"><Gauge rate={spot.rate} /><span className={`status ${state.className}`}>{state.text}</span></div><button className="recommend-button" onClick={() => goRecommend(spot)}>유사 명소 추천 보기 <ChevronRight size={17} /></button></article>})}</div> : <div className="empty"><Search size={42} /><h3>검색 결과가 없습니다</h3><p>다른 키워드나 지역으로 다시 검색해 보세요.</p><button className="secondary" onClick={() => { setQuery(""); setSearched(false); }}>다시 검색하기</button></div>}
    </section>}

    {step === 2 && <section className="page-section"><button className="back" onClick={() => setStep(1)}><ArrowLeft size={17} /> 검색 결과로</button><div className="base-spot"><img src={selectedBase.image} alt={`${selectedBase.name} 전경`} /><div><small>기준 관광지</small><h2>{selectedBase.name}</h2><p>{selectedBase.address}</p></div><div className="base-rate"><span>현재 집중률</span><strong>{selectedBase.rate}%</strong><b className="status very">{crowd(selectedBase.rate).text}</b></div></div>
      <div className="recommend-heading"><div><span>AI RECOMMENDATION</span><h1>비슷한 매력, 더 여유로운 장소</h1><p>최대 5곳을 선택해 나만의 코스를 만들 수 있어요.</p></div><b>{selected.length} / 5곳 선택</b></div>
      {/* TODO(BE): recommendations 상수를 실제 추천 API 응답 상태로 교체하는 영역입니다. */}
      {loading ? <div className="loading-state"><div className="spinner" /><h3>유사한 명소를 찾고 있어요...</h3><p>AI 추천 모델을 준비하고 있습니다. 잠시만 기다려주세요.</p><div className="skeleton-row">{[1,2,3].map(i => <div className="skeleton" key={i} />)}</div></div> : <div className="recommend-grid">{recommendations.map((spot, index) => { const on = selected.includes(spot.id); const diff = selectedBase.rate - spot.rate; return <article className={`recommend-card ${on ? "selected" : ""}`} key={spot.id}><button className="select-check" aria-label={`${spot.name} ${on ? "선택 해제" : "선택"}`} onClick={() => setSelected(v => on ? v.filter(id => id !== spot.id) : v.length < 5 ? [...v, spot.id] : v)}>{on && <Check size={16} />}</button><span className="rank">추천 {index + 1}</span><img src={spot.image} alt={`${spot.name} 전경`} /><div className="card-body"><span className="category">{spot.category}</span><h3>{spot.name}</h3><p className="address"><MapPin size={14} />{spot.address}</p><div className="mini-rate"><span>집중률 <strong>{spot.rate}%</strong></span><b className={`status ${crowd(spot.rate).className}`}>{crowd(spot.rate).text}</b></div><p className="difference">기준 명소보다 <strong>{diff}% 더 여유로워요</strong></p><button className={on ? "selected-button" : "secondary"} onClick={() => setSelected(v => on ? v.filter(id => id !== spot.id) : [...v, spot.id])}>{on ? <><Check size={16} /> 선택됨</> : "선택"}</button></div></article>})}</div>}
      <div className="sticky-cta"><span>선택된 명소 <strong>{selected.length}곳</strong></span><button className="primary" disabled={!selected.length} onClick={() => setStep(3)}>선택한 명소로 코스 만들기 <Route size={18} /></button></div>
    </section>}

    {step === 3 && <section className="page-section"><button className="back" onClick={() => setStep(2)}><ArrowLeft size={17} /> 추천 명소 수정</button><div className="course-title"><span>YOUR PAUSE ROUTE</span><h1>여유를 잇는 나만의 코스</h1><p>붐비는 순간을 피해 천천히 둘러보는 부산 바다 여행이에요.</p></div><div className="summary"><div><MapPin /><span>방문 명소<strong>{course.length}곳</strong></span></div><div><Route /><span>예상 거리<strong>{Math.max(8, course.length * 6.2).toFixed(1)}km</strong></span></div><div><Clock3 /><span>예상 시간<strong>{course.length + 1}시간 30분</strong></span></div><div><Compass /><span>코스 난이도<strong>여유</strong></span></div></div>
      {/* TODO(BE/MAP): 현재 지도는 CSS 미리보기  mapx/mapy 좌표와 코스 API의
          정렬된 경유지/경로 데이터를 받아 카카오맵 또는 네이버지도 컴포넌트로 교체 */}
      <div className="course-layout"><div className="map-view" aria-label="코스 지도 미리보기"><div className="map-road road-one" /><div className="map-road road-two" />{course.map((spot, i) => <div className={`map-marker marker-${i + 1}`} key={spot.id}>{i + 1}<span>{spot.name}</span></div>)}<div className="map-label">바다를 따라 이어지는 여유로운 경로</div></div><aside className="timeline"><h2>코스 상세</h2>{course.map((spot, i) => <article key={spot.id}><span className="number">{i + 1}</span><img src={spot.image} alt={`${spot.name} 전경`} /><div><h3>{spot.name}</h3><p>{spot.category}</p><b className={`status ${crowd(spot.rate).className}`}>집중률 {spot.rate}% · {crowd(spot.rate).text}</b></div><button aria-label={`${spot.name} 코스에서 제외`} onClick={() => setSelected(v => v.filter(id => id !== spot.id))}><X size={17} /></button></article>)}</aside></div>
      <div className="course-actions"><button className="secondary" onClick={() => { setSelected([]); setStep(2); }}><RefreshCw size={17} /> 다시 추천받기</button><button className="secondary" onClick={() => setStep(2)}>코스 수정하기</button><button className="primary" disabled>공유 · 저장 (준비 중)</button></div>
    </section>}
    <footer><Brand /><p>여유를 찾는 여행, 쉼표 하나.</p><small>© 2026 Comma Tour</small></footer>
  </div></main>;
}
