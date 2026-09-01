"use client";
/* eslint-disable @next/next/no-img-element */

import { useState } from "react";
import Image from "next/image";
import { ArrowLeft, Check, ChevronRight, Clock3, Compass, MapPin, Menu, RefreshCw, Route, Search, Sparkles, X } from "lucide-react";
import { ApiSpot, CourseData, RecommendationItem, createCourse, getRecommendations, searchSpots, shareCourse } from "../lib/api";

const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80";

type Spot = { id:number; name:string; address:string; description:string; category:string; rate:number|null; image:string; difference?:number|null };

const fromSearch = (item: ApiSpot): Spot => ({
  id:item.spotId, name:item.tAtsNm, address:item.address ?? "주소 정보 없음",
  description:item.summary ?? "상세 소개가 준비 중입니다.", category:"관광지",
  rate:item.cnctrRate7dAvg, image:item.imageUrl ?? FALLBACK_IMAGE,
});

const fromRecommendation = (item: RecommendationItem): Spot => ({
  id:item.spotId, name:item.rlteTatsNm, address:item.address ?? "주소 정보 없음",
  description:item.summary ?? item.recommendationReason,
  category:[item.rlteCtgryLclsNm,item.rlteCtgryMclsNm,item.rlteCtgrySclsNm].filter(Boolean).join(" · ") || "관광지",
  rate:item.cnctrRate7dAvg, image:item.imageUrl ?? FALLBACK_IMAGE, difference:item.congestionDifference,
});

function crowd(rate:number|null) {
  if (rate === null) return { text:"정보 없음", className:"normal" };
  if (rate >= 70) return { text:"매우 혼잡", className:"very" };
  if (rate >= 50) return { text:"혼잡", className:"busy" };
  if (rate >= 30) return { text:"보통", className:"normal" };
  return { text:"여유", className:"calm" };
}
const message = (error:unknown) => error instanceof Error ? error.message : "요청 처리 중 오류가 발생했습니다.";

function Brand() { return <div className="brand"><Image src="/images/comma-tour-logo.png" width={192} height={72} alt="쉼표투어" priority /></div>; }
function Steps({step}:{step:number}) { return <ol className="steps" aria-label="서비스 진행 단계">{["과밀 관광지","유사 명소 추천","코스 생성"].map((label,i)=><li className={step>=i+1?"active":""} key={label}><span>{step>i+1?<Check size={13}/>:i+1}</span><small>{label}</small></li>)}</ol>; }
function Header({step}:{step:number}) { return <header><Brand/><Steps step={step}/><button className="icon-button" aria-label="메뉴 열기"><Menu/></button></header>; }
function Gauge({rate}:{rate:number|null}) { const state=crowd(rate); const value=Math.max(0,Math.min(rate??0,100)); return <div className={`gauge ${state.className}`} style={{"--rate":`${value*3.6}deg`} as React.CSSProperties}><div><strong>{rate===null?"-":`${Math.round(rate)}%`}</strong><small>{state.text}</small></div></div>; }

export default function Home() {
  const [step,setStep]=useState(1);
  const [tab,setTab]=useState<"region"|"name">("region");
  const [query,setQuery]=useState(""); const [sido,setSido]=useState(""); const [sigungu,setSigungu]=useState("");
  const [searched,setSearched]=useState(false); const [results,setResults]=useState<Spot[]>([]);
  const [selectedBase,setSelectedBase]=useState<Spot|null>(null); const [recommendations,setRecommendations]=useState<Spot[]>([]);
  const [selected,setSelected]=useState<number[]>([]); const [course,setCourse]=useState<CourseData|null>(null);
  const [loading,setLoading]=useState(false); const [error,setError]=useState(""); const [shareUrl,setShareUrl]=useState("");

  async function performSearch() {
    const keyword=query.trim();
    if (tab==="name"&&!keyword) return setError("관광지명을 입력해 주세요.");
    if (tab==="region"&&!sido&&!sigungu&&!keyword) return setError("지역 또는 관광지명을 선택해 주세요.");
    setLoading(true); setError(""); setSearched(true);
    try { const data=await searchSpots({keyword:keyword||undefined,sido:tab==="region"?sido||undefined:undefined,sigungu:tab==="region"?sigungu||undefined:undefined}); setResults(data.items.map(fromSearch)); }
    catch(e) { setResults([]); setError(message(e)); } finally { setLoading(false); }
  }
  async function goRecommend(spot:Spot) {
    setSelectedBase(spot); setRecommendations([]); setSelected([]); setError(""); setLoading(true); setStep(2);
    try { const data=await getRecommendations(spot.id); setSelectedBase({...spot,rate:data.congestedSpot.cnctrRate7dAvg}); setRecommendations(data.recommendations.map(fromRecommendation)); }
    catch(e) { setError(message(e)); } finally { setLoading(false); }
  }
  function toggleSpot(id:number) { setSelected(ids=>ids.includes(id)?ids.filter(item=>item!==id):ids.length<5?[...ids,id]:ids); }
  async function buildCourse() {
    if(selected.length<2)return; setLoading(true); setError("");
    try { const data=await createCourse(selected); setCourse(data.course); setShareUrl(""); setStep(3); }
    catch(e) { setError(message(e)); } finally { setLoading(false); }
  }
  async function createShareLink() {
    setLoading(true); setError("");
    try { const data=await shareCourse(selected); setShareUrl(data.shareUrl); await navigator.clipboard?.writeText(data.shareUrl); }
    catch(e) { setError(message(e)); } finally { setLoading(false); }
  }

  return <main><div className="shell"><Header step={step}/>
    {step===1&&<section className="page-section">
      <div className="hero-copy"><p className="eyebrow"><Sparkles size={16}/> 오늘의 여행에 쉼표 하나</p><h1>붐비는 곳에서 한 걸음 벗어나,<br/><em>나만의 여유</em>를 찾아보세요.</h1><p>관광지의 예상 집중률을 확인하고, 비슷하지만 더 여유로운 장소를 추천받아 보세요.</p></div>
      <div className="search-panel"><div className="tabs"><button className={tab==="region"?"active":""} onClick={()=>setTab("region")}>지역으로 검색</button><button className={tab==="name"?"active":""} onClick={()=>setTab("name")}>관광지명 검색</button></div>
        <div className="search-row">{tab==="region"&&<><select aria-label="시/도 선택" value={sido} onChange={e=>{setSido(e.target.value);setSigungu("");}}><option value="">시/도 선택</option><option>부산광역시</option><option>경상북도</option><option>제주특별자치도</option></select><select aria-label="시군구 선택" value={sigungu} onChange={e=>setSigungu(e.target.value)}><option value="">시/군/구 선택</option><option>해운대구</option><option>경주시</option><option>서귀포시</option></select></>}
          <label className="search-input"><Search size={18}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="관광지명을 입력하세요" onKeyDown={e=>e.key==="Enter"&&void performSearch()}/>{query&&<button aria-label="검색어 지우기" onClick={()=>setQuery("")}><X size={16}/></button>}</label><button className="primary" disabled={loading} onClick={()=>void performSearch()}>{loading?"검색 중...":"검색"}</button></div></div>
      {error&&<div className="api-error" role="alert">{error}</div>}
      <div className="section-title"><div><span>SEARCH RESULT</span><h2>검색 결과 <small>{results.length}건</small></h2></div></div>
      {results.length?<div className="result-list">{results.map(spot=>{const state=crowd(spot.rate);return <article className="result-card" key={spot.id}>
        { }<img src={spot.image} alt={`${spot.name} 전경`}/><div className="spot-info"><div className="category">{spot.category}</div><h3>{spot.name}</h3><p className="address"><MapPin size={14}/>{spot.address}</p><p>{spot.description}</p></div><div className="rate-block"><Gauge rate={spot.rate}/><span className={`status ${state.className}`}>{state.text}</span></div><button className="recommend-button" onClick={()=>void goRecommend(spot)}>유사 명소 추천 보기 <ChevronRight size={17}/></button></article>})}</div>
        :<div className="empty"><Search size={42}/><h3>{searched&&!loading?"검색 결과가 없습니다":"관광지를 검색해 보세요"}</h3><p>{searched&&!loading?"다른 키워드나 지역으로 다시 검색해 보세요.":"검색 결과는 백엔드 관광지 API에서 불러옵니다."}</p></div>}
    </section>}

    {step===2&&selectedBase&&<section className="page-section"><button className="back" onClick={()=>{setError("");setStep(1);}}><ArrowLeft size={17}/> 검색 결과로</button>
      <div className="base-spot">{ }<img src={selectedBase.image} alt={`${selectedBase.name} 전경`}/><div><small>기준 관광지</small><h2>{selectedBase.name}</h2><p>{selectedBase.address}</p></div><div className="base-rate"><span>현재 집중률</span><strong>{selectedBase.rate===null?"-":`${Math.round(selectedBase.rate)}%`}</strong><b className={`status ${crowd(selectedBase.rate).className}`}>{crowd(selectedBase.rate).text}</b></div></div>
      <div className="recommend-heading"><div><span>AI RECOMMENDATION</span><h1>비슷한 매력, 더 여유로운 장소</h1><p>2곳 이상, 최대 5곳을 선택해 나만의 코스를 만들 수 있어요.</p></div><b>{selected.length} / 5곳 선택</b></div>{error&&<div className="api-error" role="alert">{error}</div>}
      {loading?<div className="loading-state"><div className="spinner"/><h3>유사한 명소를 찾고 있어요...</h3><p>잠시만 기다려주세요.</p></div>:recommendations.length?<div className="recommend-grid">{recommendations.map((spot,index)=>{const on=selected.includes(spot.id);return <article className={`recommend-card ${on?"selected":""}`} key={spot.id}><button className="select-check" aria-label={`${spot.name} ${on?"선택 해제":"선택"}`} onClick={()=>toggleSpot(spot.id)}>{on&&<Check size={16}/>}</button><span className="rank">추천 {index+1}</span>{ }<img src={spot.image} alt={`${spot.name} 전경`}/><div className="card-body"><span className="category">{spot.category}</span><h3>{spot.name}</h3><p className="address"><MapPin size={14}/>{spot.address}</p><div className="mini-rate"><span>집중률 <strong>{spot.rate===null?"-":`${Math.round(spot.rate)}%`}</strong></span><b className={`status ${crowd(spot.rate).className}`}>{crowd(spot.rate).text}</b></div><p className="difference">{spot.difference==null?"집중률 차이 정보 없음":<strong>{spot.difference.toFixed(1)}% 더 여유로워요</strong>}</p><button className={on?"selected-button":"secondary"} onClick={()=>toggleSpot(spot.id)}>{on?<><Check size={16}/> 선택됨</>:"선택"}</button></div></article>})}</div>:<div className="empty"><Sparkles size={42}/><h3>추천 결과가 없습니다</h3><p>이 관광지보다 여유로운 유사 관광지를 찾지 못했습니다.</p></div>}
      <div className="sticky-cta"><span>선택된 명소 <strong>{selected.length}곳</strong></span><button className="primary" disabled={selected.length<2||loading} onClick={()=>void buildCourse()}>{loading?"코스 생성 중...":<>선택한 명소로 코스 만들기 <Route size={18}/></>}</button></div>
    </section>}

    {step===3&&course&&<section className="page-section"><button className="back" onClick={()=>{setError("");setStep(2);}}><ArrowLeft size={17}/> 추천 명소 수정</button><div className="course-title"><span>YOUR PAUSE ROUTE</span><h1>여유를 잇는 나만의 코스</h1><p>선택한 명소를 이동 경로에 맞게 정렬했습니다.</p></div>
      <div className="summary"><div><MapPin/><span>방문 명소<strong>{course.spotCount}곳</strong></span></div><div><Route/><span>예상 거리<strong>{course.totalDistanceKm.toFixed(1)}km</strong></span></div><div><Clock3/><span>예상 시간<strong>{course.totalTravelTimeMinutes}분</strong></span></div><div><Compass/><span>코스 유형<strong>여유</strong></span></div></div>{error&&<div className="api-error" role="alert">{error}</div>}{shareUrl&&<div className="share-result">공유 링크가 복사되었습니다. <a href={shareUrl}>{shareUrl}</a></div>}
      <div className="course-layout"><div className="map-view" aria-label="코스 지도 미리보기"><div className="map-road road-one"/><div className="map-road road-two"/>{course.route.map((spot,index)=><div className={`map-marker marker-${index+1}`} key={spot.spotId}>{index+1}<span>{spot.tAtsNm}</span></div>)}<div className="map-label">실제 경로 기준 {course.totalDistanceKm.toFixed(1)}km</div></div><aside className="timeline"><h2>코스 상세</h2>{course.route.map(spot=><article key={spot.spotId}><span className="number">{spot.order}</span>{ }<img src={spot.imageUrl??FALLBACK_IMAGE} alt={`${spot.tAtsNm} 전경`}/><div><h3>{spot.tAtsNm}</h3><p>{spot.category??spot.address??"관광지"}</p><b className={`status ${crowd(spot.cnctrRate7dAvg).className}`}>집중률 {spot.cnctrRate7dAvg===null?"-":`${Math.round(spot.cnctrRate7dAvg)}%`} · {crowd(spot.cnctrRate7dAvg).text}</b></div><button aria-label={`${spot.tAtsNm} 코스에서 제외`} onClick={()=>{setSelected(ids=>ids.filter(id=>id!==spot.spotId));setStep(2);}}><X size={17}/></button></article>)}</aside></div>
      <div className="course-actions"><button className="secondary" onClick={()=>{setSelected([]);setStep(2);}}><RefreshCw size={17}/> 다시 추천받기</button><button className="secondary" onClick={()=>setStep(2)}>코스 수정하기</button><button className="primary" disabled={loading} onClick={()=>void createShareLink()}>{loading?"공유 링크 생성 중...":"공유 링크 만들기"}</button></div>
    </section>}
    <footer><Brand/><p>여유를 찾는 여행, 쉼표 하나.</p><small>© 2026 Comma Tour</small></footer>
  </div></main>;
}
