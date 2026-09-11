from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    spotId: int
    limit: int = Field(default=5, ge=1, le=20)


class CongestedSpotResponse(BaseModel):
    spotId: int
    tAtsNm: str
    cnctrRate7dAvg: float | None = None
    congestionLevel: str


class RecommendationItem(BaseModel):
    spotId: int
    rlteTatsNm: str
    rlteRank: int

    rlteCtgryLclsNm: str | None = None
    rlteCtgryMclsNm: str | None = None
    rlteCtgrySclsNm: str | None = None

    cnctrRate7dAvg: float | None = None
    congestionLevel: str

    congestionDifference: float | None = None
    congestionReductionRate: float | None = None

    mapx: float | None = None
    mapy: float | None = None

    score: float

    recommendationReason: str

    address: str | None = None
    imageUrl: str | None = None
    summary: str | None = None


class RecommendationResponse(BaseModel):
    congestedSpot: CongestedSpotResponse
    recommendations: list[RecommendationItem]