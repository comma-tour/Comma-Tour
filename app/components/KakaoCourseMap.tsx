"use client";

import { useEffect, useRef, useState } from "react";
import type { CourseData } from "../../lib/api";

type KakaoLatLng = object;
type KakaoBounds = { extend: (point: KakaoLatLng) => void };
type KakaoMap = { setBounds: (bounds: KakaoBounds) => void };

type KakaoMapsSdk = {
  load: (callback: () => void) => void;
  LatLng: new (latitude: number, longitude: number) => KakaoLatLng;
  LatLngBounds: new () => KakaoBounds;
  Map: new (
    container: HTMLElement,
    options: { center: KakaoLatLng; level: number },
  ) => KakaoMap;
  CustomOverlay: new (options: {
    map: KakaoMap;
    position: KakaoLatLng;
    content: HTMLElement;
    yAnchor: number;
  }) => object;
  Polyline: new (options: {
    map: KakaoMap;
    path: KakaoLatLng[];
    strokeWeight: number;
    strokeColor: string;
    strokeOpacity: number;
    strokeStyle: string;
  }) => object;
};

declare global {
  interface Window {
    kakao?: { maps: KakaoMapsSdk };
  }
}

const SCRIPT_ID = "kakao-map-sdk";
let sdkPromise: Promise<KakaoMapsSdk> | null = null;

function loadKakaoSdk(apiKey: string) {
  if (window.kakao?.maps) {
    return new Promise<KakaoMapsSdk>((resolve) =>
      window.kakao?.maps.load(() => resolve(window.kakao!.maps)),
    );
  }

  if (sdkPromise) return sdkPromise;

  sdkPromise = new Promise<KakaoMapsSdk>((resolve, reject) => {
    const finishLoading = () => {
      if (!window.kakao?.maps) {
        reject(new Error("카카오 지도 SDK를 불러오지 못했습니다."));
        return;
      }
      window.kakao.maps.load(() => resolve(window.kakao!.maps));
    };

    const existingScript = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", finishLoading, { once: true });
      existingScript.addEventListener("error", () => reject(new Error("카카오 지도 SDK 요청에 실패했습니다.")), { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.async = true;
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(apiKey)}&autoload=false`;
    script.addEventListener("load", finishLoading, { once: true });
    script.addEventListener("error", () => reject(new Error("카카오 지도 SDK 요청에 실패했습니다.")), { once: true });
    document.head.appendChild(script);
  });

  return sdkPromise;
}

function isCoordinateValid(mapx: number, mapy: number) {
  return Number.isFinite(mapx) && Number.isFinite(mapy);
}

export default function KakaoCourseMap({ course }: { course: CourseData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const apiKey = process.env.NEXT_PUBLIC_KAKAO_MAP_KEY?.trim();
    const route = course.route.filter((spot) => isCoordinateValid(spot.mapx, spot.mapy));

    if (!apiKey) {
      setError("카카오맵 JavaScript 키를 설정해 주세요.");
      return;
    }
    if (!route.length) {
      setError("지도에 표시할 관광지 좌표가 없습니다.");
      return;
    }

    let cancelled = false;
    setError("");

    loadKakaoSdk(apiKey)
      .then((maps) => {
        if (cancelled || !containerRef.current) return;

        const first = route[0];
        const map = new maps.Map(containerRef.current, {
          center: new maps.LatLng(first.mapy, first.mapx),
          level: 7,
        });
        const bounds = new maps.LatLngBounds();

        route.forEach((spot) => {
          const position = new maps.LatLng(spot.mapy, spot.mapx);
          bounds.extend(position);

          const marker = document.createElement("div");
          marker.className = "kakao-course-marker";
          const number = document.createElement("span");
          number.textContent = String(spot.order);
          const label = document.createElement("b");
          label.textContent = spot.tAtsNm;
          marker.append(number, label);

          new maps.CustomOverlay({ map, position, content: marker, yAnchor: 1.2 });
        });

        const path = course.path
          .filter((point) => isCoordinateValid(point.mapx, point.mapy))
          .map((point) => new maps.LatLng(point.mapy, point.mapx));

        if (path.length > 1) {
          path.forEach((point) => bounds.extend(point));
          new maps.Polyline({
            map,
            path,
            strokeWeight: 6,
            strokeColor: "#0d7144",
            strokeOpacity: 0.85,
            strokeStyle: "solid",
          });
        }

        map.setBounds(bounds);
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "지도를 표시하지 못했습니다.");
        }
      });

    return () => {
      cancelled = true;
      if (containerRef.current) containerRef.current.replaceChildren();
    };
  }, [course]);

  return (
    <div className="map-view kakao-map-view">
      <div ref={containerRef} className="kakao-map-canvas" aria-label="카카오맵 코스 경로" />
      {error && <div className="map-error" role="alert">{error}</div>}
      {!error && <div className="map-label">실제 경로 기준 {course.totalDistanceKm.toFixed(1)}km</div>}
    </div>
  );
}
