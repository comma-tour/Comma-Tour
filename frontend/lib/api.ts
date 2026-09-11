const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

export type ApiSpot = {
  spotId: number;
  tAtsNm: string;
  address: string | null;
  imageUrl: string | null;
  summary: string | null;
  cnctrRate7dAvg: number | null;
  congestionLevel: string;
  mapx: number | null;
  mapy: number | null;
};

export type SpotSearchResponse = {
  items: ApiSpot[];
  count: number;
};

export type RecommendationItem = {
  spotId: number;
  rlteTatsNm: string;
  rlteRank: number;
  rlteCtgryLclsNm: string | null;
  rlteCtgryMclsNm: string | null;
  rlteCtgrySclsNm: string | null;
  cnctrRate7dAvg: number | null;
  congestionLevel: string;
  congestionDifference: number | null;
  congestionReductionRate: number | null;
  mapx: number | null;
  mapy: number | null;
  score: number;
  recommendationReason: string;
  address: string | null;
  imageUrl: string | null;
  summary: string | null;
};

export type RecommendationResponse = {
  congestedSpot: {
    spotId: number;
    tAtsNm: string;
    cnctrRate7dAvg: number | null;
    congestionLevel: string;
  };
  recommendations: RecommendationItem[];
};

export type CourseRouteItem = {
  order: number;
  spotId: number;
  tAtsNm: string;
  category: string | null;
  cnctrRate7dAvg: number | null;
  congestionLevel: string;
  address: string | null;
  imageUrl: string | null;
  summary: string | null;
  mapx: number;
  mapy: number;
};

export type CourseData = {
  spotCount: number;
  totalDistanceKm: number;
  totalTravelTimeMinutes: number;
  route: CourseRouteItem[];
  path: Array<{ mapx: number; mapy: number }>;
};

type ApiErrorBody = {
  error?: { message?: string };
  detail?: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorBody;
    throw new Error(
      body.error?.message ?? body.detail ?? `요청에 실패했습니다. (${response.status})`,
    );
  }

  return response.json() as Promise<T>;
}

export function searchSpots(params: {
  keyword?: string;
  sido?: string;
  sigungu?: string;
  limit?: number;
}) {
  const query = new URLSearchParams();
  if (params.keyword) query.set("keyword", params.keyword);
  if (params.sido) query.set("sido", params.sido);
  if (params.sigungu) query.set("sigungu", params.sigungu);
  query.set("limit", String(params.limit ?? 20));
  return request<SpotSearchResponse>(`/api/spots/search?${query}`);
}

export function getRecommendations(spotId: number, limit = 5) {
  return request<RecommendationResponse>("/api/recommendations", {
    method: "POST",
    body: JSON.stringify({ spotId, limit }),
  });
}

export function createCourse(spotIds: number[]) {
  return request<{ course: CourseData }>("/api/courses", {
    method: "POST",
    body: JSON.stringify({ spotIds }),
  });
}

export function shareCourse(spotIds: number[]) {
  return request<{ shareId: string; shareUrl: string }>("/api/courses/share", {
    method: "POST",
    body: JSON.stringify({ spotIds }),
  });
}

export function getSharedCourse(shareId: string) {
  return request<{ shareId: string; course: CourseData }>(
    `/api/courses/shared/${encodeURIComponent(shareId)}`,
  );
}

export function getCoursePdfUrl(shareId: string) {
  return `${API_BASE_URL}/api/courses/shared/${encodeURIComponent(shareId)}/pdf`;
}
