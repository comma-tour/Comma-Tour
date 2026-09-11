"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Download, MapPin, Route } from "lucide-react";
import { CourseData, getCoursePdfUrl, getSharedCourse } from "../../../lib/api";
import KakaoCourseMap from "../../components/KakaoCourseMap";

const FALLBACK_IMAGE =
  "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80";

export default function SharedCoursePage() {
  const { shareId } = useParams<{ shareId: string }>();
  const [course, setCourse] = useState<CourseData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!shareId) return;
    getSharedCourse(shareId)
      .then((response) => setCourse(response.course))
      .catch((requestError: unknown) =>
        setError(
          requestError instanceof Error
            ? requestError.message
            : "공유 코스를 불러오지 못했습니다.",
        ),
      );
  }, [shareId]);

  return (
    <main>
      <div className="shell">
        <section className="page-section shared-course">
          <div className="course-title">
            <span>SHARED PAUSE ROUTE</span>
            <h1>공유받은 쉼표투어 코스</h1>
          </div>
          {error && <div className="api-error" role="alert">{error}</div>}
          {!course && !error && (
            <div className="loading-state"><div className="spinner" /><p>코스를 불러오는 중입니다.</p></div>
          )}
          {course && (
            <>
              <div className="summary">
                <div><MapPin /><span>방문 명소<strong>{course.spotCount}곳</strong></span></div>
                <div><Route /><span>예상 거리<strong>{course.totalDistanceKm.toFixed(1)}km</strong></span></div>
              </div>
              <KakaoCourseMap course={course} />
              <div className="shared-route-list">
                {course.route.map((spot) => (
                  <article key={spot.spotId}>
                    <span>{spot.order}</span>
                    <img src={spot.imageUrl ?? FALLBACK_IMAGE} alt={`${spot.tAtsNm} 전경`} />
                    <div><h2>{spot.tAtsNm}</h2><p>{spot.address ?? spot.category ?? "관광지"}</p></div>
                  </article>
                ))}
              </div>
              <div className="course-actions">
                <Link className="secondary" href="/">새 코스 만들기</Link>
                <a className="primary" href={getCoursePdfUrl(shareId)}><Download size={17} /> PDF 다운로드</a>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
