import html
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from app.core.config import settings
from app.services.course_map_service import generate_course_map_image


FONT_DIR = Path(r"C:\Windows\Fonts")
REGULAR_FONT_PATH = FONT_DIR / "malgun.ttf"
BOLD_FONT_PATH = FONT_DIR / "malgunbd.ttf"

REGULAR_FONT_NAME = "MalgunGothic"
BOLD_FONT_NAME = "MalgunGothicBold"

APP_DIR = Path(__file__).resolve().parents[1]
LOGO_PATH = APP_DIR / "assets" / "comma-tour-logo.png"
SECTION_LOGO_CANDIDATES = [
    APP_DIR / "assets" / "comma-mark.png",
]

# frontend globals.css + 확정 시안 기준
BRAND_GREEN = colors.HexColor("#0D7144")
BRAND_GREEN_DARK = colors.HexColor("#075634")
BRAND_GREEN_MID = colors.HexColor("#169653")
BRAND_MINT = colors.HexColor("#E8F5ED")
BRAND_MINT_SOFT = colors.HexColor("#F3FAF5")
BRAND_MINT_PALE = colors.HexColor("#F8FCF9")
PAGE_BG = colors.HexColor("#FBFDFC")
TEXT_DARK = colors.HexColor("#1D2B24")
TEXT_MUTED = colors.HexColor("#636D68")
TEXT_LIGHT = colors.HexColor("#8B9690")
BORDER = colors.HexColor("#CFE4D6")
DIVIDER = colors.HexColor("#DDEAE2")
HEADER_BG = colors.HexColor("#F0F8F2")
FOOTER_BG = colors.HexColor("#EFF8F2")
MAP_FALLBACK = colors.HexColor("#E9F4ED")
SEA_FALLBACK = colors.HexColor("#D9EEF5")

CONGESTION_STYLES = {
    "LOW": ("여유", colors.HexColor("#187448"), colors.HexColor("#E8F7EF")),
    "MEDIUM": ("보통", colors.HexColor("#846813"), colors.HexColor("#F8F1DA")),
    "HIGH": ("혼잡", colors.HexColor("#C66C00"), colors.HexColor("#FFF4E3")),
    "VERY_HIGH": ("매우 혼잡", colors.HexColor("#C52F38"), colors.HexColor("#FFF0F0")),
    "UNKNOWN": ("정보 없음", TEXT_MUTED, colors.HexColor("#F1F3F2")),
}


def _bold_font_name() -> str:
    return BOLD_FONT_NAME if BOLD_FONT_PATH.exists() else REGULAR_FONT_NAME


def _register_fonts() -> None:
    if not REGULAR_FONT_PATH.exists():
        raise RuntimeError("한글 PDF 생성을 위한 맑은 고딕 폰트를 찾을 수 없습니다.")
    pdfmetrics.registerFont(TTFont(REGULAR_FONT_NAME, str(REGULAR_FONT_PATH)))
    if BOLD_FONT_PATH.exists():
        pdfmetrics.registerFont(TTFont(BOLD_FONT_NAME, str(BOLD_FONT_PATH)))


def _download_image(image_url: str | None) -> BytesIO | None:
    if not image_url:
        return None
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").startswith("image/"):
            return None
        return BytesIO(response.content)
    except Exception:
        return None


def _safe_text(value: str | None) -> str:
    return html.escape(value or "")


def _truncate(text: str | None, max_chars: int) -> str:
    if not text:
        return ""
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def _create_qr_code(url: str, size: float) -> Drawing:
    qr_code = qr.QrCodeWidget(url)
    bounds = qr_code.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(
        size,
        size,
        transform=[size / width, 0, 0, size / height, 0, 0],
    )
    drawing.add(qr_code)
    return drawing


def _draw_round_rect(c, x, y, w, h, *, fill, stroke=BORDER, radius=4 * mm, line_width=0.7):
    c.saveState()
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(line_width)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)
    c.restoreState()


def _draw_paragraph(c, text, x, y_top, w, h, style):
    paragraph = Paragraph(text, style)
    _, ph = paragraph.wrap(w, h)
    ph = min(ph, h)
    paragraph.drawOn(c, x, y_top - ph)
    return ph


def _draw_cover(c, image_buffer: BytesIO, x, y, w, h, radius=3 * mm):
    reader = ImageReader(image_buffer)
    iw, ih = reader.getSize()
    if not iw or not ih:
        return
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx = x + (w - dw) / 2
    dy = y + (h - dh) / 2

    c.saveState()
    path = c.beginPath()
    path.roundRect(x, y, w, h, radius)
    c.clipPath(path, stroke=0, fill=0)
    c.drawImage(reader, dx, dy, width=dw, height=dh, mask="auto")
    c.restoreState()


def _draw_image_fallback(c, x, y, w, h):
    c.saveState()
    path = c.beginPath()
    path.roundRect(x, y, w, h, 3 * mm)
    c.clipPath(path, stroke=0, fill=0)
    c.setFillColor(colors.HexColor("#DDEEE3"))
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#B8D8C3"))
    c.rect(x, y, w, h * 0.38, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#F4FAF6"))
    c.circle(x + w * 0.35, y + h * 0.66, h * 0.16, stroke=0, fill=1)
    c.restoreState()


def _draw_logo(c, center_x, y_top, max_w=55 * mm, max_h=15 * mm):
    if not LOGO_PATH.exists():
        c.setFont(_bold_font_name(), 24)
        c.setFillColor(TEXT_DARK)
        c.drawCentredString(center_x, y_top - 8 * mm, "쉼표투어")
        return

    reader = ImageReader(str(LOGO_PATH))
    iw, ih = reader.getSize()
    scale = min(max_w / iw, max_h / ih)
    w, h = iw * scale, ih * scale
    c.drawImage(
        reader,
        center_x - w / 2,
        y_top - h,
        width=w,
        height=h,
        mask="auto",
    )


def _draw_header(c, page_w, page_h):
    header_h = 31 * mm
    y = page_h - header_h
    c.setFillColor(HEADER_BG)
    c.rect(0, y, page_w, header_h, stroke=0, fill=1)

    # 나뭇잎 없이도 시안처럼 헤더를 꽉 채우는 부드러운 지형 실루엣
    c.saveState()
    c.setFillColor(colors.HexColor("#E2F1E6"))
    p = c.beginPath()
    p.moveTo(0, y)
    p.curveTo(page_w * 0.18, y + 11 * mm, page_w * 0.31, y + 2 * mm, page_w * 0.47, y + 4 * mm)
    p.curveTo(page_w * 0.60, y + 7 * mm, page_w * 0.72, y + 15 * mm, page_w * 0.82, y + 6 * mm)
    p.curveTo(page_w * 0.90, y + 1 * mm, page_w * 0.95, y + 5 * mm, page_w, y + 8 * mm)
    p.lineTo(page_w, y)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.restoreState()

    _draw_logo(c, page_w / 2, page_h - 6 * mm, max_w=54 * mm, max_h=14 * mm)
    c.setFillColor(BRAND_GREEN)
    c.setFont(_bold_font_name(), 9.2)
    c.drawCentredString(page_w / 2, y + 6.3 * mm, "여유를 찾는 여행, 쉼표 하나.")
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.8)
    c.line(0, y, page_w, y)


def _draw_stat_icon(c, cx, cy, kind):
    c.saveState()
    c.setStrokeColor(BRAND_GREEN)
    c.setFillColor(BRAND_GREEN)
    c.setLineWidth(1.2)
    if kind == "pin":
        c.circle(cx, cy + 1.2 * mm, 2.2 * mm, stroke=1, fill=0)
        c.circle(cx, cy + 1.2 * mm, 0.65 * mm, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(cx - 1.7 * mm, cy - 0.2 * mm)
        p.lineTo(cx, cy - 3.2 * mm)
        p.lineTo(cx + 1.7 * mm, cy - 0.2 * mm)
        c.drawPath(p, stroke=1, fill=0)
    elif kind == "route":
        c.circle(cx - 3 * mm, cy - 1 * mm, 0.9 * mm, stroke=1, fill=0)
        c.circle(cx + 3 * mm, cy + 2.2 * mm, 0.9 * mm, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - 2.2 * mm, cy - 0.7 * mm)
        p.curveTo(cx - 0.5 * mm, cy + 0.2 * mm, cx + 0.3 * mm, cy - 1.7 * mm, cx + 1.2 * mm, cy)
        p.curveTo(cx + 1.7 * mm, cy + 1.2 * mm, cx + 1.7 * mm, cy + 2.2 * mm, cx + 2.2 * mm, cy + 2.2 * mm)
        c.drawPath(p, stroke=1, fill=0)
    else:  # clock
        c.circle(cx, cy, 3.2 * mm, stroke=1, fill=0)
        c.line(cx, cy, cx, cy + 1.8 * mm)
        c.line(cx, cy, cx + 1.5 * mm, cy - 0.7 * mm)
    c.restoreState()


def _draw_brand_mark(c, cx, cy, size=3.2 * mm):
    """쉼표투어 로고의 쉼표 모티프를 섹션 아이콘으로 통일한다."""
    c.saveState()
    c.setFillColor(BRAND_GREEN)
    r = size * 0.55
    c.circle(cx - r * 0.15, cy + r * 0.15, r, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(cx - r * 0.65, cy - r * 0.05)
    p.curveTo(cx - r * 0.85, cy - r * 0.9, cx - r * 0.95, cy - r * 1.25, cx - r * 0.55, cy - r * 1.45)
    p.curveTo(cx + r * 0.05, cy - r * 1.15, cx + r * 0.25, cy - r * 0.75, cx + r * 0.35, cy - r * 0.25)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.restoreState()


def _get_section_logo_path() -> Path | None:
    for path in SECTION_LOGO_CANDIDATES:
        if path.exists():
            return path
    return None


def _draw_section_title(c, x, y, title, icon="dot"):
    """assets에 준비한 쉼표 마크를 우선 사용하고 없으면 벡터 마크로 fallback."""
    logo_path = _get_section_logo_path()
    if logo_path is not None:
        reader = ImageReader(str(logo_path))
        iw, ih = reader.getSize()
        mark_h = 4.0 * mm
        mark_w = mark_h * (iw / ih) if ih else mark_h
        if mark_w > 4.5 * mm:
            scale = 4.5 * mm / mark_w
            mark_w *= scale
            mark_h *= scale
        c.drawImage(reader, x, y - 0.2 * mm, width=mark_w, height=mark_h, mask="auto")
        title_x = x + mark_w + 2.2 * mm
    else:
        _draw_brand_mark(c, x + 1.6 * mm, y + 1.4 * mm, size=2.9 * mm)
        title_x = x + 6 * mm

    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont(_bold_font_name(), 10.2)
    c.drawString(title_x, y, title)

def _draw_summary(c, x, y, w, h, course, travel_text):
    _draw_round_rect(c, x, y, w, h, fill=BRAND_MINT_PALE)
    _draw_section_title(c, x + 5 * mm, y + h - 7 * mm, "코스 요약", "dot")

    # 아이콘 → 라벨 → 수치의 세로 간격을 분리해 겹침을 방지한다.
    body_y = y + 4.5 * mm
    col_w = (w - 10 * mm) / 3
    labels = ["방문 명소", "총 이동거리", "예상 이동시간"]
    values = [f"{course['spotCount']}곳", f"{course['totalDistanceKm']:.1f} km", travel_text]
    kinds = ["pin", "route", "clock"]

    for i in range(3):
        x0 = x + 5 * mm + i * col_w
        cx = x0 + col_w / 2
        if i > 0:
            c.setStrokeColor(DIVIDER)
            c.setLineWidth(0.6)
            c.line(x0, y + 4.5 * mm, x0, y + h - 11 * mm)

        _draw_stat_icon(c, cx, y + h - 14.5 * mm, kinds[i])

        c.setFillColor(TEXT_DARK)
        c.setFont(REGULAR_FONT_NAME, 7.0)
        c.drawCentredString(cx, y + 10.0 * mm, labels[i])

        c.setFillColor(BRAND_GREEN)
        c.setFont(_bold_font_name(), 14.5)
        c.drawCentredString(cx, y + 4.0 * mm, values[i])

def _draw_map_card(c, x, y, w, h, route, distance):
    _draw_round_rect(c, x, y, w, h, fill=BRAND_MINT_PALE)
    _draw_section_title(c, x + 5 * mm, y + h - 7 * mm, "코스 경로", "pin")

    image_x = x + 4 * mm
    image_y = y + 10 * mm
    image_w = w - 8 * mm
    image_h = h - 24 * mm
    map_image = generate_course_map_image(route)
    if map_image is not None:
        _draw_cover(c, map_image, image_x, image_y, image_w, image_h, radius=2.2 * mm)
    else:
        c.saveState()
        path = c.beginPath()
        path.roundRect(image_x, image_y, image_w, image_h, 2.2 * mm)
        c.clipPath(path, stroke=0, fill=0)
        c.setFillColor(MAP_FALLBACK)
        c.rect(image_x, image_y, image_w, image_h, stroke=0, fill=1)
        c.setFillColor(SEA_FALLBACK)
        c.rect(image_x + image_w * 0.72, image_y, image_w * 0.28, image_h, stroke=0, fill=1)
        points = []
        for i in range(max(2, len(route))):
            px = image_x + image_w * (0.12 + 0.17 * i)
            py = image_y + image_h * (0.18 + 0.15 * i)
            points.append((px, py))
        c.setStrokeColor(BRAND_GREEN_MID)
        c.setLineWidth(1.6)
        for a, b in zip(points, points[1:]):
            c.line(a[0], a[1], b[0], b[1])
        for px, py in points:
            c.setFillColor(BRAND_GREEN)
            c.setStrokeColor(colors.white)
            c.setLineWidth(1.2)
            c.circle(px, py, 1.8 * mm, stroke=1, fill=1)
        c.restoreState()

    c.setFillColor(TEXT_LIGHT)
    c.setFont(REGULAR_FONT_NAME, 6.3)
    c.setFillColor(colors.HexColor("#4A4A4A"))
    c.drawString(x + 5 * mm, y + 4.2 * mm, f"※ 실제 경로 기준 {distance:.1f} km")


def _draw_share_card(c, x, y, w, h, share_url):
    """QR/설명/URL과 하단 공유 문구의 균형을 맞춘 공유 카드."""
    _draw_round_rect(c, x, y, w, h, fill=BRAND_MINT_PALE)
    _draw_section_title(c, x + 5 * mm, y + h - 7 * mm, "공유하기", "share")

    # 카드 내부를 상단 콘텐츠 / 하단 CTA로 명확하게 분리한다.
    qr_size = 24.5 * mm
    qr_box = qr_size + 7 * mm
    qr_x = x + 5 * mm
    # 지도 카드와 정확히 같은 높이 중심에 QR을 맞춘다.
    qr_y = y + (h - qr_box) / 2

    _draw_round_rect(
        c, qr_x, qr_y, qr_box, qr_box,
        fill=colors.white, radius=2 * mm, line_width=0.5
    )
    renderPDF.draw(
        _create_qr_code(share_url, qr_size), c,
        qr_x + 3.5 * mm, qr_y + 3.5 * mm,
    )

    copy_x = qr_x + qr_box + 4.5 * mm
    copy_w = max(18 * mm, x + w - 6 * mm - copy_x)

    # 설명 + URL을 하나의 묶음으로 보고 QR 중앙 높이에 맞춘다.
    copy_style = ParagraphStyle(
        "share-copy-v8",
        fontName=_bold_font_name(),
        fontSize=6.7,
        leading=8.8,
        textColor=TEXT_DARK,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    url_box_h = 6.6 * mm
    group_gap = 0.15 * mm
    desc_h = 9.5 * mm
    group_h = desc_h + group_gap + url_box_h
    group_bottom = qr_y + (qr_box - group_h) / 2
    copy_top = group_bottom + group_h

    _draw_paragraph(
        c,
        "아래 QR코드 또는 링크로<br/>코스 페이지를 확인할 수 있습니다.",
        copy_x, copy_top, copy_w, desc_h, copy_style,
    )

    # 설명 바로 아래에 작은 여백만 두고 주소창을 붙인다.
    url_box_y = group_bottom
    c.setFillColor(BRAND_MINT)
    c.setStrokeColor(BORDER)
    c.roundRect(
        copy_x, url_box_y, copy_w, url_box_h, 1.8 * mm,
        stroke=1, fill=1,
    )

    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont(REGULAR_FONT_NAME, 5.25)
    max_url_w = max(5 * mm, copy_w - 6 * mm)
    display_url = share_url
    while (
        len(display_url) > 8
        and pdfmetrics.stringWidth(display_url, REGULAR_FONT_NAME, 5.25) > max_url_w
    ):
        display_url = display_url[:-2] + "…"

    c.drawString(copy_x + 3 * mm, url_box_y + 2.15 * mm, display_url)
    c.linkURL(
        share_url,
        (copy_x, url_box_y, copy_x + copy_w, url_box_y + url_box_h),
        relative=0,
    )

    # CTA는 이전보다 위로 올려 공유 카드 안에서 더 자연스럽게 보이게 한다.
    share_style = ParagraphStyle(
        "share-title-v10",
        fontName=_bold_font_name(),
        fontSize=10.0,
        leading=12.0,
        textColor=BRAND_GREEN_DARK,
        alignment=1,
        wordWrap="CJK",
    )
    cta_h = 8.5 * mm
    cta_y = y + 10.0 * mm
    _draw_paragraph(
        c,
        "이 코스를 친구와 함께 공유해보세요!",
        x + 3 * mm, cta_y, w - 6 * mm, cta_h,
        share_style,
    )


def _draw_category_badge(c, text, x, y, max_w):
    if not text:
        return 0
    font = _bold_font_name()
    size = 6.2
    content = _truncate(text, 12)
    tw = pdfmetrics.stringWidth(content, font, size)
    bw = min(max_w, tw + 5 * mm)
    bh = 5 * mm

    # 기존처럼 둥근 pill을 유지하되, 카드 안에서 독립된 정보 태그로 사용한다.
    c.setFillColor(BRAND_MINT)
    c.setStrokeColor(colors.HexColor("#D9ECDF"))
    c.roundRect(x, y, bw, bh, bh / 2, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#379764"))
    c.setFont(font, size)
    c.drawCentredString(x + bw / 2, y + 1.55 * mm, content)
    return bw


def _draw_congestion_badge(c, level, rate, x, y):
    label, text_color, bg_color = CONGESTION_STYLES.get(level, CONGESTION_STYLES["UNKNOWN"])
    if rate is not None:
        text = f"집중률 {rate:.1f}%  |  {label}"
    else:
        text = label
    font = _bold_font_name()
    size = 6.4
    tw = pdfmetrics.stringWidth(text, font, size)
    bw = tw + 5.2 * mm
    bh = 5.4 * mm
    c.setFillColor(bg_color)
    c.roundRect(x, y, bw, bh, bh / 2, stroke=0, fill=1)
    c.setFillColor(text_color)
    c.setFont(font, size)
    c.drawCentredString(x + bw / 2, y + 1.6 * mm, text)


def _draw_number_circle(c, number, cx, cy):
    c.setFillColor(BRAND_GREEN)
    c.circle(cx, cy, 4.1 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(_bold_font_name(), 8.8)
    c.drawCentredString(cx, cy - 2.9, str(number))


# 사용자 제공 화살표 이미지
ARROW_IMAGE_PATH = r"C:\Users\cholo\commatour\backend\app\assets\arrow.png"


def _draw_down_arrow(c, cx, cy):
    """사용자 제공 arrow.png를 그대로 사용해 아래 방향 화살표를 그린다."""
    c.saveState()

    # 원본 이미지 비율을 유지한다.
    with Image.open(ARROW_IMAGE_PATH) as im:
        img_w, img_h = im.size
    aspect = img_w / float(img_h)

    arrow_h = 8 * mm
    arrow_w = arrow_h * aspect

    # 기존 화살표 중심을 기준으로 약간 아래에 배치.
    x = cx - arrow_w / 2
    y = cy - arrow_h / 2 - 1.5

    c.drawImage(
        ARROW_IMAGE_PATH,
        x, y,
        width=arrow_w,
        height=arrow_h,
        preserveAspectRatio=True,
        mask="auto",
    )
    c.restoreState()


def _draw_top_round_rect(c, x, y, w, h, radius=3 * mm, fill=HEADER_BG):
    """상단 모서리만 둥글고 하단은 직선인 섹션 헤더."""
    c.saveState()
    c.setFillColor(fill)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.7)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x, y + h - radius)
    p.curveTo(x, y + h - radius * 0.45, x + radius * 0.45, y + h, x + radius, y + h)
    p.lineTo(x + w - radius, y + h)
    p.curveTo(x + w - radius * 0.45, y + h, x + w, y + h - radius * 0.45, x + w, y + h - radius)
    p.lineTo(x + w, y)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.restoreState()


def _split_first_line(text, font_name, font_size, max_width):
    """카테고리 pill 오른쪽에 들어갈 첫 줄과 나머지를 분리한다."""
    words = text.split()
    if not words:
        return "", ""
    line = ""
    consumed = 0
    for word in words:
        candidate = word if not line else line + " " + word
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            line = candidate
            consumed += len(word) + (1 if line != word else 0)
        else:
            break
    if not line:
        line = words[0]
        while len(line) > 1 and pdfmetrics.stringWidth(line, font_name, font_size) > max_width:
            line = line[:-1]
        return line, text[len(line):].lstrip()
    return line, text[len(line):].lstrip()


def _draw_schedule_card(c, item, x, y, w, h):
    _draw_round_rect(c, x, y, w, h, fill=colors.white,
                     radius=3 * mm, line_width=0.6)

    number_w = 15 * mm
    image_w = 37 * mm
    info_w = 59 * mm

    for dx in [
        x + number_w,
        x + number_w + image_w,
        x + number_w + image_w + info_w,
    ]:
        c.setStrokeColor(DIVIDER)
        c.setLineWidth(0.5)
        c.line(dx, y + 2 * mm, dx, y + h - 2 * mm)

    _draw_number_circle(c, item["order"], x + number_w / 2, y + h / 2)

    image_x = x + number_w + 2 * mm
    image_y = y + 2 * mm
    image_draw_w = image_w - 4 * mm
    image_draw_h = h - 4 * mm
    image_buffer = _download_image(item.get("imageUrl"))
    if image_buffer is not None:
        _draw_cover(c, image_buffer, image_x, image_y,
                    image_draw_w, image_draw_h, radius=2 * mm)
    else:
        _draw_image_fallback(c, image_x, image_y,
                             image_draw_w, image_draw_h)

    info_x = x + number_w + image_w + 3 * mm
    info_top = y + h - 5.2 * mm
    name = _truncate(item.get("tAtsNm"), 22)
    name_style = ParagraphStyle(
        "spot-name", fontName=_bold_font_name(), fontSize=8.0,
        leading=9.2, textColor=TEXT_DARK, alignment=TA_LEFT,
    )
    _draw_paragraph(c, _safe_text(name), info_x, info_top + 1.0 * mm,
                    info_w - 4 * mm, 9 * mm, name_style)

    c.setFillColor(colors.HexColor("#78837D"))
    c.setFont(REGULAR_FONT_NAME, 5.8)
    c.drawString(info_x, y + h - 12.7 * mm,
                 "⌖ " + _truncate(item.get("address"), 31))

    _draw_congestion_badge(
        c, item.get("congestionLevel", "UNKNOWN"),
        item.get("cnctrRate7dAvg"), info_x, y + 3.3 * mm,
    )

    # 설명 영역은 [소분류] / [설명]의 두 줄 구조로 고정한다.
    summary_x = x + number_w + image_w + info_w + 3 * mm
    summary_w_inner = x + w - 3 * mm - summary_x
    category = item.get("category") or "관광지"

    # 소분류와 설명을 카드 중앙에 맞추되 기존보다 조금 위로 올린다.
    badge_y = y + h - 8.7 * mm
    _draw_category_badge(
        c, category, summary_x, badge_y,
        min(24 * mm, summary_w_inner * 0.48)
    )

    summary = (_truncate(item.get("summary"), 118)
               or "관광지 상세 소개가 준비 중입니다.")
    text_color = TEXT_DARK if item.get("summary") else TEXT_MUTED

    summary_style = ParagraphStyle(
        "spot-summary-v7", fontName=REGULAR_FONT_NAME,
        fontSize=6.2, leading=8.0, textColor=text_color,
        alignment=TA_LEFT, wordWrap="CJK",
    )
    summary_h = max(7 * mm, h - 14.0 * mm)
    _draw_paragraph(
        c, _safe_text(summary), summary_x, badge_y - 1.6 * mm,
        summary_w_inner, summary_h, summary_style,
    )


def generate_course_pdf(shared_course: dict) -> bytes:
    _register_fonts()

    course = shared_course["course"]
    route = course["route"]
    share_id = shared_course["shareId"]
    share_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/course/{share_id}"

    travel_minutes = course.get("totalTravelTimeMinutes", 0)
    hours, minutes = divmod(travel_minutes, 60)
    if hours:
        travel_text = f"{hours}시간 {minutes}분" if minutes else f"{hours}시간"
    else:
        travel_text = f"{minutes}분"

    buffer = BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)

    c.setTitle(f"CommaTour Course {share_id}")
    c.setAuthor("CommaTour")

    # 전체 배경
    c.setFillColor(PAGE_BG)
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)
    _draw_header(c, page_w, page_h)

    margin_x = 9 * mm
    gap = 5 * mm
    content_w = page_w - 2 * margin_x

    # 1) 인트로 + 코스 요약
    intro_top = page_h - 38 * mm
    intro_h = 34 * mm
    left_w = 91 * mm
    right_w = content_w - left_w - gap

    summary_y = intro_top - intro_h

    # 소개 영역을 오른쪽 코스 요약 박스의 수직 중앙에 맞춘다.
    intro_center_y = summary_y + intro_h / 2
    c.setFillColor(BRAND_GREEN)
    c.setFont(_bold_font_name(), 8.0)
    c.drawString(margin_x, intro_center_y + 9.0 * mm, "YOUR PAUSE ROUTE")
    c.setFillColor(TEXT_DARK)
    c.setFont(_bold_font_name(), 19.0)
    c.drawString(margin_x, intro_center_y + 1.0 * mm, "여유를 잇는 나만의 코스")

    intro_style = ParagraphStyle(
        "intro", fontName=REGULAR_FONT_NAME, fontSize=7.5, leading=11.0,
        textColor=TEXT_MUTED, alignment=TA_LEFT,
    )
    _draw_paragraph(
        c,
        "혼잡을 피해 더 여유롭고 매력적인 여행지를<br/>연결한 나만의 맞춤 코스입니다.",
        margin_x,
        intro_center_y - 4.0 * mm,
        left_w - 8 * mm,
        14 * mm,
        intro_style,
    )
    _draw_summary(c, margin_x + left_w + gap, summary_y, right_w, intro_h, course, travel_text)

    # 2) 지도 + 공유 카드: 같은 높이, 같은 baseline
    utility_top = summary_y - 4 * mm
    utility_h = 62 * mm
    map_w = 92 * mm
    share_w = content_w - map_w - gap
    utility_y = utility_top - utility_h

    _draw_map_card(c, margin_x, utility_y, map_w, utility_h, route, course["totalDistanceKm"])
    _draw_share_card(c, margin_x + map_w + gap, utility_y, share_w, utility_h, share_url)

    # 3) 일정 섹션: 시안처럼 가로 전체에 옅은 섹션 바
    schedule_top = utility_y - 4 * mm
    schedule_header_h = 10 * mm
    schedule_header_y = schedule_top - schedule_header_h
    # 소제목에 맞는 폭의 헤더 박스만 두고, 하단 선은 오른쪽 끝까지 연결한다.
    schedule_header_w = 34 * mm
    _draw_top_round_rect(
        c,
        margin_x,
        schedule_header_y,
        schedule_header_w,
        schedule_header_h,
        radius=3 * mm,
        fill=HEADER_BG,
    )
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.7)
    c.line(
        margin_x + schedule_header_w,
        schedule_header_y,
        margin_x + content_w,
        schedule_header_y,
    )
    _draw_section_title(
        c, margin_x + 4 * mm, schedule_top - 6.8 * mm,
        "코스 일정", "calendar"
    )

    route_count = max(1, len(route))
    schedule_bottom = 14 * mm
    cards_top = schedule_top - schedule_header_h - 2.5 * mm
    cards_area_h = cards_top - schedule_bottom
    arrow_gap = 4.4 * mm if route_count > 1 else 0
    card_h = (cards_area_h - arrow_gap * (route_count - 1)) / route_count
    # 5개 기준 약 21mm, 2~4개면 지나치게 커지지 않게 제한
    card_h = min(card_h, 22.5 * mm)
    total_cards_h = card_h * route_count + arrow_gap * (route_count - 1)
    current_y = cards_top - card_h
    card_positions = []

    # 카드를 먼저 모두 그린다.
    for idx, item in enumerate(route):
        card_positions.append(current_y)
        _draw_schedule_card(c, item, margin_x, current_y, content_w, card_h)
        current_y -= card_h + arrow_gap

    # 화살표는 카드 위에 마지막으로 그려 양쪽 카드에 겹치는 부분도
    # 가려지지 않고 항상 보이게 한다.
    for idx in range(route_count - 1):
        arrow_y = card_positions[idx] - arrow_gap / 2
        _draw_down_arrow(c, page_w / 2, arrow_y + 1)

    # footer
    c.setFillColor(FOOTER_BG)
    c.rect(0, 0, page_w, 11 * mm, stroke=0, fill=1)
    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont(_bold_font_name(), 8.0)
    c.drawCentredString(page_w / 2, 6.4 * mm, "쉼표투어")
    c.setFillColor(TEXT_MUTED)
    c.setFont(REGULAR_FONT_NAME, 6.2)
    c.drawCentredString(page_w / 2, 3.1 * mm, "© 2026 Comma Tour. All rights reserved.")
    c.setFillColor(BRAND_GREEN_DARK)
    c.setFont(_bold_font_name(), 7.5)

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes