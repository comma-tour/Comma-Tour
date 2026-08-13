"""
임베딩 모델 비교용 관광 도메인 평가셋

설계 원칙 (상세 근거는 ai/docs/embedding_model_comparison.md 참고):
    1. 카테고리 다양성 - 4장 4.3절 콘텐츠타입 대분류(관광지/문화시설/축제/레포츠/숙박/쇼핑/음식점)를 최대한 커버
    2. 어휘 중복 최소화 - 같은 주제의 A/B 문장도 동일 단어 반복 없이 다른 표현으로 작성
    3. 문장 풀 재사용 - 20개 문장만 작성, 유사 쌍은 같은 주제 A-B, 비유사 쌍은 다른 주제끼리 교차 매칭
       → 유사/비유사 평가에 같은 문장 풀을 쓰므로 문장 길이·문체 차이가 결과에 섞이지 않음
    4. detailCommon2.overview 문체 모사 - KorService2 실제 소개문구 분포(1~2문장 소개체)에 맞춤
       (※ 최초에는 detailIntro2로 알고 있었으나, 매뉴얼 재확인 결과 실제 소개문구 필드는
       detailCommon2 오퍼레이션의 overview임. matching/mock_korservice.py, matching/embedding.py 참고)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TopicPair:
    topic: str
    sentence_a: str
    sentence_b: str


EVAL_TOPICS: list[TopicPair] = [
    TopicPair(
        topic="해안 절경/일몰",
        sentence_a="탁 트인 해안선과 붉게 물드는 노을이 장관을 이루는 해변으로, 사진 명소로도 유명합니다.",
        sentence_b="일몰 무렵 바다와 하늘이 온통 주황빛으로 물드는 풍경을 감상할 수 있는 해안 산책로입니다.",
    ),
    TopicPair(
        topic="전통 한옥마을",
        sentence_a="기와지붕이 늘어선 골목을 따라 옛 정취를 느끼며 걸을 수 있는 전통 한옥 마을입니다.",
        sentence_b="수백 년 역사를 지닌 고택들이 모여 있어 전통 건축의 아름다움을 체험할 수 있는 마을입니다.",
    ),
    TopicPair(
        topic="전통시장 먹거리",
        sentence_a="다양한 지역 특산물과 길거리 음식을 즐길 수 있는 활기 넘치는 전통 시장입니다.",
        sentence_b="제철 농수산물과 즉석 먹거리로 가득한 재래시장으로, 현지인들도 즐겨 찾는 곳입니다.",
    ),
    TopicPair(
        topic="공원 산책/벚꽃",
        sentence_a="봄이면 벚꽃이 만개해 산책하기 좋은 도심 속 공원입니다.",
        sentence_b="화사한 벚꽃길과 잘 정비된 산책로가 어우러진 시민 휴식 공간입니다.",
    ),
    TopicPair(
        topic="역사 박물관/유적",
        sentence_a="선사시대부터 이어진 유물을 전시한 역사 박물관으로, 지역의 문화사를 한눈에 살펴볼 수 있습니다.",
        sentence_b="고대 유적지에서 발굴된 유물들을 보존·전시하는 문화유산 공간입니다.",
    ),
    TopicPair(
        topic="등산/트레킹",
        sentence_a="완만한 능선을 따라 오르는 등산로가 있어 초보자도 부담 없이 트레킹을 즐길 수 있는 산입니다.",
        sentence_b="다양한 난이도의 산책·등산 코스가 마련되어 있어 남녀노소 즐겨 찾는 산악 명소입니다.",
    ),
    TopicPair(
        topic="지역 축제/공연",
        sentence_a="매년 가을 지역 특산물을 주제로 열리는 축제로, 다채로운 공연과 체험 프로그램이 함께 진행됩니다.",
        sentence_b="전통 음악 공연과 지역 먹거리 부스가 어우러진 계절 축제입니다.",
    ),
    TopicPair(
        topic="리조트 숙박",
        sentence_a="바다 전망을 갖춘 객실과 다양한 부대시설을 갖춘 휴양형 리조트입니다.",
        sentence_b="가족 단위 여행객을 위한 편의시설과 오션뷰 객실을 제공하는 숙박 시설입니다.",
    ),
    TopicPair(
        topic="쇼핑거리",
        sentence_a="최신 유행 의류와 액세서리 매장이 밀집한 젊은 층 인기 쇼핑거리입니다.",
        sentence_b="트렌디한 편집숍과 카페가 늘어선 도심 쇼핑 골목으로 유동인구가 많습니다.",
    ),
    TopicPair(
        topic="향토음식점",
        sentence_a="지역 향토 음식을 대표하는 손맛 깃든 메뉴로 유명한 오래된 식당입니다.",
        sentence_b="대대로 이어져 온 조리법으로 만든 전통 향토요리를 맛볼 수 있는 맛집입니다.",
    ),
]


def get_similar_pairs() -> list[tuple[str, str]]:
    """같은 주제 내 A-B 문장 쌍 (10개) — '유사해야 하는 쌍'"""
    return [(t.sentence_a, t.sentence_b) for t in EVAL_TOPICS]



# (topic_index, 'a'|'b') 쌍을 명시적으로 지정 — 서로 확실히 다른 카테고리끼리만 교차되도록 직접 배치.
# 같은 20개 문장 풀을 재사용해, 유사/비유사 평가 간 문장 길이·문체 편차를 통제한다.
_DISSIMILAR_INDEX_PAIRS: list[tuple[tuple[int, str], tuple[int, str]]] = [
    ((0, "a"), (8, "a")),  # 해안 절경 vs 쇼핑거리
    ((1, "a"), (5, "a")),  # 한옥마을 vs 등산/트레킹
    ((2, "a"), (7, "a")),  # 전통시장 vs 리조트 숙박
    ((3, "a"), (9, "a")),  # 공원 산책/벚꽃 vs 향토음식점
    ((4, "a"), (6, "a")),  # 역사 박물관 vs 지역 축제
    ((0, "b"), (2, "b")),  # 일몰 해변 vs 전통시장
    ((1, "b"), (8, "b")),  # 고택 마을 vs 쇼핑거리
    ((5, "b"), (4, "b")),  # 등산 산책로 vs 유적 박물관
    ((6, "b"), (3, "b")),  # 축제 공연 vs 벚꽃길
    ((7, "b"), (9, "b")),  # 리조트 숙박 vs 향토요리 맛집
]


def get_dissimilar_pairs() -> list[tuple[str, str]]:
    """서로 다른 주제끼리 교차 매칭한 문장 쌍 (10개) — '유사하지 않아야 하는 쌍'"""

    def _resolve(idx: int, side: str) -> str:
        topic = EVAL_TOPICS[idx]
        return topic.sentence_a if side == "a" else topic.sentence_b

    return [
        (_resolve(*first), _resolve(*second)) for first, second in _DISSIMILAR_INDEX_PAIRS
    ]


def get_all_sentences() -> list[str]:
    """평가셋에 등장하는 20개 문장 (임베딩 1회만 계산하고 재사용하기 위함)"""
    sentences: list[str] = []
    for t in EVAL_TOPICS:
        sentences.append(t.sentence_a)
        sentences.append(t.sentence_b)
    return sentences


if __name__ == "__main__":
    print(f"유사 쌍 {len(get_similar_pairs())}개, 비유사 쌍 {len(get_dissimilar_pairs())}개")
