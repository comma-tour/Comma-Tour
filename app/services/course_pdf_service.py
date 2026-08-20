import requests

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image as ReportLabImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing

from app.core.config import settings

from app.services.course_map_service import generate_course_map_image


FONT_DIR = Path(r"C:\Windows\Fonts")
REGULAR_FONT_PATH = FONT_DIR / "malgun.ttf"
BOLD_FONT_PATH = FONT_DIR / "malgunbd.ttf"

REGULAR_FONT_NAME = "MalgunGothic"
BOLD_FONT_NAME = "MalgunGothicBold"

BRAND_GREEN = colors.HexColor("#1F6B4A")
BRAND_GREEN_LIGHT = colors.HexColor("#EAF4EF")
TEXT_DARK = colors.HexColor("#1F2933")
TEXT_MUTED = colors.HexColor("#667085")
BORDER_LIGHT = colors.HexColor("#DCE5E0")
BACKGROUND_LIGHT = colors.HexColor("#F7FAF8")


def _register_fonts() -> None:
    if not REGULAR_FONT_PATH.exists():
        raise RuntimeError(
            "한글 PDF 생성을 위한 맑은 고딕 폰트를 찾을 수 없습니다."
        )

    pdfmetrics.registerFont(
        TTFont(
            REGULAR_FONT_NAME,
            str(REGULAR_FONT_PATH),
        )
    )

    if BOLD_FONT_PATH.exists():
        pdfmetrics.registerFont(
            TTFont(
                BOLD_FONT_NAME,
                str(BOLD_FONT_PATH),
            )
        )


def _download_image(
    image_url: str | None,
) -> BytesIO | None:
    if not image_url:
        return None

    try:
        response = requests.get(
            image_url,
            timeout=10,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        )

        if not content_type.startswith("image/"):
            return None

        return BytesIO(response.content)

    except Exception:
        return None


def _create_qr_code(
    url: str,
    size: float = 28 * mm,
) -> Drawing:
    qr_code = qr.QrCodeWidget(url)

    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]

    drawing = Drawing(
        size,
        size,
        transform=[
            size / width,
            0,
            0,
            size / height,
            0,
            0,
        ],
    )

    drawing.add(qr_code)

    return drawing


def generate_course_pdf(
    shared_course: dict,
) -> bytes:
    _register_fonts()

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CommaTourTitle",
        parent=styles["Title"],
        fontName=(
            BOLD_FONT_NAME
            if BOLD_FONT_PATH.exists()
            else REGULAR_FONT_NAME
        ),
        fontSize=21,
        leading=27,
        textColor=BRAND_GREEN,
        alignment=TA_LEFT,
        spaceAfter=2,
    )

    subtitle_style = ParagraphStyle(
        "CommaTourSubtitle",
        parent=styles["Normal"],
        fontName=REGULAR_FONT_NAME,
        fontSize=9.5,
        leading=14,
        textColor=TEXT_MUTED,
        alignment=TA_LEFT,
        spaceAfter=10,
    )

    section_style = ParagraphStyle(
        "CommaTourSection",
        parent=styles["Heading2"],
        fontName=(
            BOLD_FONT_NAME
            if BOLD_FONT_PATH.exists()
            else REGULAR_FONT_NAME
        ),
        fontSize=14,
        leading=20,
        textColor=TEXT_DARK,
        spaceBefore=8,
        spaceAfter=8,
    )

    heading_style = ParagraphStyle(
        "CommaTourHeading",
        parent=styles["Heading2"],
        fontName=(
            BOLD_FONT_NAME
            if BOLD_FONT_PATH.exists()
            else REGULAR_FONT_NAME
        ),
        fontSize=12.5,
        leading=18,
        textColor=TEXT_DARK,
        spaceAfter=5,
    )

    body_style = ParagraphStyle(
        "CommaTourBody",
        parent=styles["BodyText"],
        fontName=REGULAR_FONT_NAME,
        fontSize=9.2,
        leading=14,
        textColor=TEXT_DARK,
        spaceAfter=4,
    )

    muted_style = ParagraphStyle(
        "CommaTourMuted",
        parent=body_style,
        textColor=TEXT_MUTED,
        fontSize=8.8,
        leading=13,
    )

    stat_label_style = ParagraphStyle(
        "CommaTourStatLabel",
        parent=body_style,
        fontSize=8,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER,
    )

    stat_value_style = ParagraphStyle(
        "CommaTourStatValue",
        parent=body_style,
        fontName=(
            BOLD_FONT_NAME
            if BOLD_FONT_PATH.exists()
            else REGULAR_FONT_NAME
        ),
        fontSize=12,
        textColor=BRAND_GREEN,
        alignment=TA_CENTER,
    )

    story = []

    course = shared_course["course"]
    route = course["route"]

    share_id = shared_course["shareId"]

    frontend_base_url = (
        settings.FRONTEND_BASE_URL.rstrip("/")
    )

    share_url = (
        f"{frontend_base_url}/course/{share_id}"
    )

    travel_minutes = course.get(
        "totalTravelTimeMinutes",
        0,
    )

    travel_hours, remaining_minutes = divmod(
        travel_minutes,
        60,
    )

    if travel_hours:
        travel_time_text = (
            f"{travel_hours}시간 {remaining_minutes}분"
            if remaining_minutes
            else f"{travel_hours}시간"
        )
    else:
        travel_time_text = f"{remaining_minutes}분"

    # ================================
    # 브랜드 헤더
    # ================================

    story.append(
        Paragraph(
            "쉼표투어",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "여유를 찾는 여행, 쉼표 하나.",
            subtitle_style,
        )
    )

    story.append(
        Spacer(
            1,
            3 * mm,
        )
    )

    # ================================
    # 코스 요약
    # ================================

    story.append(
        Paragraph(
            "나의 여행 코스",
            section_style,
        )
    )

    summary_table = Table(
        [
            [
                Paragraph(
                    "방문 장소",
                    stat_label_style,
                ),
                Paragraph(
                    "총 이동거리",
                    stat_label_style,
                ),
                Paragraph(
                    "예상 이동시간",
                    stat_label_style,
                ),
            ],
            [
                Paragraph(
                    f"{course['spotCount']}곳",
                    stat_value_style,
                ),
                Paragraph(
                    f"{course['totalDistanceKm']:.2f} km",
                    stat_value_style,
                ),
                Paragraph(
                    travel_time_text,
                    stat_value_style,
                ),
            ],
        ],
        colWidths=[
            52 * mm,
            52 * mm,
            52 * mm,
        ],
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    BRAND_GREEN_LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    BORDER_LIGHT,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.4,
                    BORDER_LIGHT,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(summary_table)

    story.append(
        Spacer(
            1,
            7 * mm,
        )
    )

    # ================================
    # 코스 지도
    # ================================

    story.append(
        Paragraph(
            "코스 경로",
            section_style,
        )
    )

    map_image = generate_course_map_image(
        route
    )

    if map_image is not None:
        map_flowable = ReportLabImage(
            map_image,
            width=156 * mm,
            height=86.7 * mm,
        )

        story.append(map_flowable)

        story.append(
            Spacer(
                1,
                7 * mm,
            )
        )

    else:
        story.append(
            Paragraph(
                "지도 이미지를 불러오지 못했습니다.",
                muted_style,
            )
        )

        story.append(
            Spacer(
                1,
                7 * mm,
            )
        )

    # ================================
    # 코스 일정
    # ================================

    story.append(
        Paragraph(
            "코스 일정",
            section_style,
        )
    )

    congestion_labels = {
        "LOW": "여유",
        "MEDIUM": "보통",
        "HIGH": "혼잡",
        "VERY_HIGH": "매우 혼잡",
        "UNKNOWN": "정보 없음",
    }

    for route_index, item in enumerate(route):
        order = item["order"]

        congestion_text = congestion_labels.get(
            item["congestionLevel"],
            item["congestionLevel"],
        )

        rate = item.get(
            "cnctrRate7dAvg"
        )

        if rate is not None:
            congestion_summary = (
                f"{congestion_text} · "
                f"집중률 {rate:.1f}%"
            )
        else:
            congestion_summary = (
                congestion_text
            )

        # 관광지 부가 정보
        detail_parts = []

        if item.get("category"):
            detail_parts.append(
                item["category"]
            )

        if item.get("address"):
            detail_parts.append(
                item["address"]
            )

        details_text = "<br/>".join(
            detail_parts
        )

        # 오른쪽 텍스트 영역
        card_contents = [
            Paragraph(
                f"{order}. {item['tAtsNm']}",
                heading_style,
            ),
            Paragraph(
                congestion_summary,
                muted_style,
            ),
        ]

        if details_text:
            card_contents.append(
                Paragraph(
                    details_text,
                    muted_style,
                )
            )

        if item.get("summary"):
            card_contents.append(
                Spacer(
                    1,
                    2 * mm,
                )
            )

            card_contents.append(
                Paragraph(
                    item["summary"],
                    body_style,
                )
            )

        # 대표 이미지 다운로드
        image_buffer = _download_image(
            item.get("imageUrl")
        )

        # 이미지가 있는 경우
        if image_buffer is not None:
            spot_image = ReportLabImage(
                image_buffer,
                width=42 * mm,
                height=30 * mm,
            )

            card_data = [
                [
                    Paragraph(
                        str(order),
                        stat_value_style,
                    ),
                    spot_image,
                    card_contents,
                ]
            ]

            card_widths = [
                14 * mm,
                46 * mm,
                96 * mm,
            ]

        # 이미지가 없는 경우
        else:
            card_data = [
                [
                    Paragraph(
                        str(order),
                        stat_value_style,
                    ),
                    card_contents,
                ]
            ]

            card_widths = [
                14 * mm,
                142 * mm,
            ]

        card = Table(
            card_data,
            colWidths=card_widths,
        )

        card.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.white,
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.7,
                        BORDER_LIGHT,
                    ),
                    (
                        "BACKGROUND",
                        (0, 0),
                        (0, 0),
                        BRAND_GREEN_LIGHT,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "ALIGN",
                        (0, 0),
                        (0, 0),
                        "CENTER",
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        7,
                    ),
                ]
            )
        )

        story.append(
            KeepTogether(
                [
                    card,
                ]
            )
        )

        # 다음 관광지로 이동 표시
        if route_index < len(route) - 1:
            story.append(
                Paragraph(
                    "↓ &nbsp;&nbsp; 다음 장소로 이동",
                    muted_style,
                )
            )

            story.append(
                Spacer(
                    1,
                    3 * mm,
                )
            )

        else:
            story.append(
                Spacer(
                    1,
                    5 * mm,
                )
            )

    # ================================
    # 공유 정보
    # ================================

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    story.append(
        Paragraph(
            "이 코스를 다시 확인해보세요",
            section_style,
        )
    )

    qr_code = _create_qr_code(
        share_url
    )

    share_info = [
        Paragraph(
            (
                "<b>쉼표투어 공유 코스</b>"
                "<br/><br/>"
                "QR 코드를 스캔하거나 아래 주소로 "
                "접속하면 이 코스를 다시 확인할 수 있습니다."
                "<br/><br/>"
                f"{share_url}"
            ),
            body_style,
        )
    ]

    share_table = Table(
        [
            [
                qr_code,
                share_info,
            ]
        ],
        colWidths=[
            36 * mm,
            120 * mm,
        ],
    )

    share_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    BACKGROUND_LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.7,
                    BORDER_LIGHT,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(
        KeepTogether(
            [
                share_table,
            ]
        )
    )
    document.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes