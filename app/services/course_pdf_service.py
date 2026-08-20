from io import BytesIO
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


FONT_DIR = Path(r"C:\Windows\Fonts")
REGULAR_FONT_PATH = FONT_DIR / "malgun.ttf"
BOLD_FONT_PATH = FONT_DIR / "malgunbd.ttf"

REGULAR_FONT_NAME = "MalgunGothic"
BOLD_FONT_NAME = "MalgunGothicBold"


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
        fontSize=20,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "CommaTourSubtitle",
        parent=styles["Normal"],
        fontName=REGULAR_FONT_NAME,
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=16,
    )

    heading_style = ParagraphStyle(
        "CommaTourHeading",
        parent=styles["Heading2"],
        fontName=(
            BOLD_FONT_NAME
            if BOLD_FONT_PATH.exists()
            else REGULAR_FONT_NAME
        ),
        fontSize=13,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "CommaTourBody",
        parent=styles["BodyText"],
        fontName=REGULAR_FONT_NAME,
        fontSize=9.5,
        leading=15,
        spaceAfter=4,
    )

    story = []

    course = shared_course["course"]
    route = course["route"]

    story.append(
        Paragraph(
            "CommaTour",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "여유로운 여행 코스",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            (
                f"관광지 수: {course['spotCount']}곳<br/>"
                f"전체 이동거리: "
                f"{course['totalDistanceKm']:.2f} km"
            ),
            body_style,
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm,
        )
    )

    for item in route:
        story.append(
            Paragraph(
                f"{item['order']}. {item['tAtsNm']}",
                heading_style,
            )
        )

        details = []

        if item.get("category"):
            details.append(
                f"카테고리: {item['category']}"
            )

        if item.get("address"):
            details.append(
                f"주소: {item['address']}"
            )

        if item.get("cnctrRate7dAvg") is not None:
            details.append(
                (
                    "향후 7일 평균 관광 집중률: "
                    f"{item['cnctrRate7dAvg']:.2f}"
                )
            )

        details.append(
            f"혼잡 단계: {item['congestionLevel']}"
        )

        if details:
            story.append(
                Paragraph(
                    "<br/>".join(details),
                    body_style,
                )
            )

        if item.get("summary"):
            story.append(
                Paragraph(
                    item["summary"],
                    body_style,
                )
            )

        story.append(
            Spacer(
                1,
                5 * mm,
            )
        )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    story.append(
        Paragraph(
            f"공유 ID: {shared_course['shareId']}",
            body_style,
        )
    )

    document.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes