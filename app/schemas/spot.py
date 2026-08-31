from pydantic import BaseModel


class SpotSearchItem(BaseModel):
    spotId: int
    tAtsNm: str
    address: str | None = None
    imageUrl: str | None = None
    summary: str | None = None

    cnctrRate7dAvg: float | None = None
    congestionLevel: str

    mapx: float | None = None
    mapy: float | None = None


class SpotSearchResponse(BaseModel):
    items: list[SpotSearchItem]
    count: int

class SpotCategory(BaseModel):
    large: str | None = None
    medium: str | None = None
    small: str | None = None


class SpotDetailResponse(BaseModel):
    spotId: int
    tAtsNm: str
    address: str | None = None
    imageUrl: str | None = None
    summary: str | None = None

    category: SpotCategory

    cnctrRate7dAvg: float | None = None
    congestionLevel: str

    mapx: float | None = None
    mapy: float | None = None