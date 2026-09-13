"""
프론트엔드(frontend/app/components/KakaoCourseMap.tsx)와 100% 동일한 지도 이미지를
PDF에 넣기 위한 서비스.

카카오 스태틱맵 HTTP API는 번호가 매겨진 초록색 핀이나 실제 경로(Polyline)를
프론트엔드와 똑같이 그려낼 방법이 없다(문서화되지 않은 API라 커스텀 마커/경로
스타일을 신뢰성 있게 재현할 수 없음). 대신 헤드리스 브라우저(Chromium)에서
프론트엔드와 같은 카카오맵 JS SDK + CustomOverlay + Polyline 코드를 그대로
실행시켜 화면을 캡처한다. 이렇게 하면 마커 모양, 색상, 경로선 스타일이 프론트엔드와
픽셀 단위로 동일하다.

단점: PDF 한 장을 만들 때마다 브라우저를 띄우므로 카카오 스태틱맵 API 호출보다
느리고(수 초), 서버 메모리/CPU 부담이 크다. 배포 환경(Dockerfile)에 Chromium과
그 실행에 필요한 시스템 라이브러리가 설치되어 있어야 하고, 컨테이너 메모리도
넉넉히(예: 512MB 이상) 잡아줘야 한다.
"""

import json
import logging
from io import BytesIO

from playwright.sync_api import sync_playwright

from app.core.config import settings

logger = logging.getLogger(__name__)

# frontend/app/globals.css 의 .kakao-course-marker 규칙 및 --green/--ink 변수를 그대로 옮김.
_MARKER_CSS = """
  html, body { margin: 0; padding: 0; background: #e8efeb; }
  #map { width: __WIDTH__px; height: __HEIGHT__px; }
  .kakao-course-marker {
    display: flex;
    align-items: center;
    gap: 6px;
    transform: translateY(-4px);
    white-space: nowrap;
    font-family: "Noto Sans KR", sans-serif;
  }
  .kakao-course-marker span {
    width: 30px;
    height: 30px;
    display: grid;
    place-items: center;
    border: 3px solid white;
    border-radius: 50%;
    background: #0d7144;
    color: white;
    font-size: 11px;
    font-weight: 800;
    box-shadow: 0 3px 8px #173c2866;
  }
  .kakao-course-marker b {
    padding: 5px 8px;
    border-radius: 5px;
    background: white;
    color: #1d2b24;
    font-size: 11px;
    font-weight: normal;
    box-shadow: 0 2px 7px #0002;
  }
"""


def _is_valid_point(item: dict) -> bool:
    mapx = item.get("mapx")
    mapy = item.get("mapy")
    return isinstance(mapx, (int, float)) and isinstance(mapy, (int, float))


def _build_html(route: list[dict], path: list[dict], width: int, height: int) -> str:
    # 스크립트 콘텐츠 안에 "</script>" 문자열이 섞여 파싱이 깨지는 것을 방지.
    route_json = json.dumps(route, ensure_ascii=False).replace("</", "<\\/")
    path_json = json.dumps(path, ensure_ascii=False).replace("</", "<\\/")
    css = _MARKER_CSS.replace("__WIDTH__", str(width)).replace("__HEIGHT__", str(height))

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>{css}</style>
</head>
<body>
<div id="map"></div>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={settings.KAKAO_JS_API_KEY}&autoload=false"></script>
<script>
  window.__mapReady = false;
  window.__mapError = null;

  try {{
    var ROUTE = {route_json};
    var PATH = {path_json};

    kakao.maps.load(function () {{
      try {{
        var container = document.getElementById('map');
        var first = ROUTE[0];
        // frontend KakaoCourseMap.tsx 와 동일한 옵션 (level: 7 시작 후 setBounds로 재조정).
        var map = new kakao.maps.Map(container, {{
          center: new kakao.maps.LatLng(first.mapy, first.mapx),
          level: 7,
        }});

        // 타일 로딩이 끝나면 캡처 준비 완료. 혹시 이벤트가 안 잡히는 경우를 대비해
        // 타임아웃 폴백도 함께 둔다.
        var fallbackTimer = setTimeout(function () {{
          window.__mapReady = true;
        }}, 4000);
        kakao.maps.event.addListener(map, 'tilesloaded', function () {{
          clearTimeout(fallbackTimer);
          window.__mapReady = true;
        }});

        var bounds = new kakao.maps.LatLngBounds();

        ROUTE.forEach(function (spot) {{
          var position = new kakao.maps.LatLng(spot.mapy, spot.mapx);
          bounds.extend(position);

          var marker = document.createElement('div');
          marker.className = 'kakao-course-marker';
          var number = document.createElement('span');
          number.textContent = String(spot.order);
          var label = document.createElement('b');
          label.textContent = spot.tAtsNm;
          marker.appendChild(number);
          marker.appendChild(label);

          new kakao.maps.CustomOverlay({{
            map: map,
            position: position,
            content: marker,
            yAnchor: 1.2,
          }});
        }});

        var path = PATH.map(function (p) {{
          return new kakao.maps.LatLng(p.mapy, p.mapx);
        }});

        if (path.length > 1) {{
          path.forEach(function (p) {{ bounds.extend(p); }});
          new kakao.maps.Polyline({{
            map: map,
            path: path,
            strokeWeight: 6,
            strokeColor: '#0d7144',
            strokeOpacity: 0.85,
            strokeStyle: 'solid',
          }});
        }}

        map.setBounds(bounds, 70, 90, 70, 40);
      }} catch (innerError) {{
        window.__mapError = String(innerError);
        window.__mapReady = true;
      }}
    }});
  }} catch (outerError) {{
    window.__mapError = String(outerError);
    window.__mapReady = true;
  }}
</script>
</body>
</html>"""


def render_course_map_image(
    route: list[dict],
    path: list[dict] | None = None,
    *,
    width: int = 1000,
    height: int = 600,
    timeout_ms: int = 15000,
) -> BytesIO | None:
    """프론트엔드와 동일한 카카오맵(번호 핀 + 경로선)을 헤드리스 브라우저로 캡처한다.

    실패하면(카카오 JS 키 미설정, 브라우저 미설치, 네트워크 오류 등) None을 반환한다.
    호출부(course_pdf_service._draw_map_card)는 None일 때 자체 fallback 일러스트를 그린다.
    """
    clean_route = [
        {
            "order": item.get("order"),
            "tAtsNm": item.get("tAtsNm") or "",
            "mapx": item["mapx"],
            "mapy": item["mapy"],
        }
        for item in route
        if _is_valid_point(item)
    ]
    if not clean_route:
        return None

    clean_path = [
        {"mapx": p["mapx"], "mapy": p["mapy"]}
        for p in (path or [])
        if _is_valid_point(p)
    ]

    if not settings.KAKAO_JS_API_KEY:
        logger.error("KAKAO_JS_API_KEY가 설정되지 않아 지도 스크린샷을 생성할 수 없습니다.")
        return None

    html = _build_html(clean_route, clean_path, width, height)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(html, wait_until="domcontentloaded")

                page.wait_for_function(
                    "window.__mapReady === true", timeout=timeout_ms
                )

                map_error = page.evaluate("window.__mapError")
                if map_error:
                    logger.error("카카오맵 렌더링 중 오류: %s", map_error)
                    return None

                map_element = page.query_selector("#map")
                if map_element is None:
                    return None

                png_bytes = map_element.screenshot(type="png")
            finally:
                browser.close()
    except Exception:
        logger.exception("코스 지도 스크린샷 생성 실패")
        return None

    return BytesIO(png_bytes)
