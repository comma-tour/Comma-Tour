from pydantic import BaseModel, Field


class CourseRequest(BaseModel):
    spotIds: list[int] = Field(min_length=2, max_length=5)


class CourseRouteItem(BaseModel):
    order: int
    spotId: int
    tAtsNm: str

    category: str | None = None

    cnctrRate7dAvg: float | None = None
    congestionLevel: str

    address: str | None = None
    imageUrl: str | None = None
    summary: str | None = None

    mapx: float
    mapy: float


class CoursePathItem(BaseModel):
    mapx: float
    mapy: float


class CourseData(BaseModel):
    spotCount: int
    totalDistanceKm: float
    totalTravelTimeMinutes: int
    route: list[CourseRouteItem]
    path: list[CoursePathItem]


class CourseResponse(BaseModel):
    course: CourseData

class ShareCourseRequest(BaseModel):
    spotIds: list[int] = Field(min_length=2, max_length=5)


class ShareCourseResponse(BaseModel):
    shareId: str
    shareUrl: str


class SharedCourseResponse(BaseModel):
    shareId: str
    course: CourseData