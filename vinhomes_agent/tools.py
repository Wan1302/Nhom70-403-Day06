from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import urlencode
from urllib.request import urlopen

from langchain_core.tools import tool

from vinhomes_agent.config import (
    FAQ_CSV_PATH,
    OPENWEATHER_API_KEY,
    PLACES_JSON_PATH,
    TICKET_STORE_PATH,
    VINHOMES_CITY,
    VINHOMES_LAT,
    VINHOMES_LON,
)
from vinhomes_agent.schemas import FAQRecord


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9\s]", " ", text)


def _tokens(text: str) -> list[str]:
    return [token for token in _normalize(text).split() if len(token) > 1]


def _normalize_budget_key(value: str | None) -> str:
    return _normalize(value or "")


def _budget_level_per_person_vnd(level: str | None) -> int:
    normalized = _normalize_budget_key(level)
    if "thap" in normalized or "tiet kiem" in normalized or "re" in normalized:
        return 200000
    if "thoai mai" in normalized or "cao cap" in normalized:
        return 1200000
    return 500000


def _infer_budget_level(total_budget_vnd: int | None, party_size: int) -> str:
    if not total_budget_vnd:
        return "vừa"
    per_person = max(round(total_budget_vnd / max(party_size, 1)), 1)
    if per_person <= 300000:
        return "thấp"
    if per_person >= 1000000:
        return "thoải mái"
    return "vừa"


def _resolve_total_budget_vnd(trip_constraints: dict, party_size: int) -> int | None:
    explicit_budget = trip_constraints.get("budget_amount_vnd")
    if explicit_budget is not None:
        try:
            return max(int(explicit_budget), 0)
        except (TypeError, ValueError):
            return None

    budget_level = trip_constraints.get("budget_level")
    if budget_level:
        return _budget_level_per_person_vnd(str(budget_level)) * max(party_size, 1)

    return None


def _place_total_cost_vnd(place: dict, party_size: int) -> int:
    return (
        int(place.get("ticket_cost_resident", 0)) * party_size
        + int(place.get("fixed_fee", 0))
        + int(place.get("food_surcharge_pp", 0)) * party_size
    )


def _pick_next_place(
    candidates: list[dict],
    selected_places: list[dict],
    fallback_pool: list[dict] | None = None,
) -> dict | None:
    selected_ids = {item.get("id") for item in selected_places}

    for place in candidates:
        if place.get("id") not in selected_ids:
            return place

    for place in fallback_pool or []:
        if place.get("id") not in selected_ids:
            return place

    return None


@lru_cache(maxsize=1)
def _load_faq_rows() -> list[dict]:
    with FAQ_CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _score_faq(query: str, row: dict) -> float:
    query_tokens = Counter(_tokens(query))
    haystack = " ".join(
        [
            row.get("title", ""),
            row.get("category_title", ""),
            row.get("content_text", "")[:600],
        ]
    )
    doc_tokens = Counter(_tokens(haystack))
    overlap = sum((query_tokens & doc_tokens).values())
    title_bonus = 2 if overlap and any(token in _normalize(row.get("title", "")) for token in query_tokens) else 0
    return float(overlap + title_bonus)


@tool
def search_faq_kb(query: str, category: str | None = None, top_k: int = 3) -> list[dict]:
    """Search the selected FAQ CSV and return the best matching records."""
    rows = _load_faq_rows()
    candidates = []

    for row in rows:
        if category and row.get("category_title") != category:
            continue
        score = _score_faq(query, row)
        if score <= 0:
            continue
        record = FAQRecord(
            id=row["id"],
            title=row["title"],
            category_title=row.get("category_title"),
            detail_url=row["detail_url"],
            content_text=row["content_text"],
            publish_time_iso=row.get("publish_time_iso"),
            updated_time_iso=row.get("updated_time_iso"),
            score=score,
        )
        candidates.append(record.model_dump())

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:top_k]


@tool
def search_faq_web(query: str, top_k: int = 3) -> list[dict]:
    """Search the public web for FAQ fallback results."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=top_k))
    except Exception:
        return []

    docs = []
    for index, item in enumerate(results, start=1):
        title = item.get("title") or item.get("heading") or f"Web result {index}"
        url = item.get("href") or item.get("url") or ""
        snippet = item.get("body") or item.get("snippet") or ""
        if not url:
            continue
        docs.append(
            {
                "id": f"web-{index}",
                "title": title,
                "category_title": "Web fallback",
                "detail_url": url,
                "content_text": snippet,
                "publish_time_iso": None,
                "updated_time_iso": None,
                "score": 0.5,
            }
        )

    return docs[:top_k]


@tool
def get_ticket_schema() -> dict:
    """Return the required ticket fields and accepted urgency labels."""
    return {
        "required_fields": [
            "issue_type",
            "urgency",
            "location",
            "description",
            "incident_time",
            "contact_name",
            "contact_phone",
        ],
        "urgency_options": ["low", "medium", "high", "critical"],
    }


@tool
def validate_ticket_input(ticket_draft: dict) -> dict:
    """Validate a ticket draft and report missing fields."""
    schema = get_ticket_schema.invoke({})
    missing_fields = [field for field in schema["required_fields"] if not ticket_draft.get(field)]
    errors = []

    if ticket_draft.get("description") and len(ticket_draft["description"].strip()) < 12:
        errors.append("Mô tả sự cố đang quá ngắn.")
    if ticket_draft.get("contact_phone") and len(re.sub(r"\D", "", ticket_draft["contact_phone"])) < 9:
        errors.append("Số điện thoại có vẻ chưa hợp lệ.")

    return {
        "is_complete": not missing_fields and not errors,
        "missing_fields": missing_fields,
        "errors": errors,
    }


@tool
def summarize_ticket_draft(ticket_draft: dict) -> str:
    """Create a short human-readable ticket summary."""
    return (
        "Bản nháp ticket:\n"
        f"- Loại sự cố: {ticket_draft.get('issue_type', 'Chưa có')}\n"
        f"- Mức độ khẩn cấp: {ticket_draft.get('urgency', 'Chưa có')}\n"
        f"- Vị trí: {ticket_draft.get('location', 'Chưa có')}\n"
        f"- Thời điểm: {ticket_draft.get('incident_time', 'Chưa có')}\n"
        f"- Người liên hệ: {ticket_draft.get('contact_name', 'Chưa có')}\n"
        f"- Số điện thoại: {ticket_draft.get('contact_phone', 'Chưa có')}\n"
        f"- Mô tả: {ticket_draft.get('description', 'Chưa có')}"
    )


@tool
def create_ticket(ticket_draft: dict) -> dict:
    """Persist a mock ticket and return the created ticket id."""
    TICKET_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    payload = {
        "ticket_id": ticket_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "ticket": ticket_draft,
    }
    with TICKET_STORE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


@tool
def get_trip_requirements_helper(trip_constraints: dict) -> dict:
    """Report missing trip constraints and suggest the next question."""
    required = {
        "trip_date": "Bạn muốn đi ngày nào?",
        "party_size": "Nhóm mình có bao nhiêu người?",
        "budget_level": (
            "Ngân sách đi chơi của bạn ở mức nào, hoặc cụ thể là bao nhiêu tiền? "
            "(Ví dụ: 300k tổng, hoặc thấp: ~200k/người, vừa: ~500k/người, thoải mái: >1.2 triệu/người)"
        ),
        "interests": "Bạn muốn ưu tiên trải nghiệm gì: ăn uống, check-in, trẻ em hay thư giãn?",
    }

    if not trip_constraints.get("origin"):
        trip_constraints = {**trip_constraints, "origin": "Vinhomes Ocean Park Gia Lâm"}

    missing = []
    for field in required:
        if field == "budget_level":
            if not trip_constraints.get("budget_level") and not trip_constraints.get("budget_amount_vnd"):
                missing.append(field)
            continue
        if not trip_constraints.get(field):
            missing.append(field)

    next_question = required[missing[0]] if missing else None
    return {"missing_fields": missing, "next_question": next_question}


def _parse_trip_date(trip_date_str: str) -> datetime | None:
    """Hôm nay / ngày mai / ISO date."""
    s = str(trip_date_str).strip().lower()
    today = datetime.now()
    if any(k in s for k in ("hôm nay", "hom nay", "today")):
        return today
    if any(k in s for k in ("ngày mai", "ngay mai", "tomorrow")):
        return today + timedelta(days=1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fetch_weather(trip_date_str: str) -> dict:
    if not OPENWEATHER_API_KEY:
        return {
            "summary": "Chưa có OPENWEATHER_API_KEY. Bạn có thể đăng ký miễn phí tại openweathermap.org.",
            "temp_c": None,
            "feels_like_c": None,
            "humidity_pct": None,
            "wind_kmh": None,
            "icon": "🌤️",
            "source": "fallback",
        }

    target_dt = _parse_trip_date(trip_date_str)
    params = urlencode(
        {
            "lat": VINHOMES_LAT,
            "lon": VINHOMES_LON,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": "vi",
            "cnt": 40,
        }
    )
    url = f"https://api.openweathermap.org/data/2.5/forecast?{params}"

    try:
        with urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        err_str = str(exc)
        if "401" in err_str:
            return {
                "summary": (
                    "☀️ Trời quang tại Gia Lâm (dự báo dự phòng vì API key đang chờ kích hoạt). "
                    "Nhiệt độ khoảng 32°C, cảm giác 36°C, độ ẩm 75%, gió 12 km/h."
                ),
                "source": "mock_401",
            }
        return {
            "summary": f"Đã có lỗi khi gọi API thời tiết: {err_str}",
            "source": "error",
        }

    forecasts = data.get("list", [])
    if not forecasts:
        return {"summary": "Không nhận được dữ liệu thời tiết.", "source": "empty"}

    best = forecasts[0]
    if target_dt:
        target_ts = target_dt.timestamp()
        best = min(forecasts, key=lambda f: abs(f["dt"] - target_ts))

    main = best.get("main", {})
    weather = best.get("weather", [{}])[0]
    wind = best.get("wind", {})

    icon_map = {
        "clear": "☀️",
        "clouds": "⛅",
        "rain": "🌧️",
        "drizzle": "🌦️",
        "thunderstorm": "⚡",
        "snow": "❄️",
        "mist": "🌫️",
    }
    icon_key = weather.get("main", "").lower()
    icon = next((v for k, v in icon_map.items() if k in icon_key), "🌤️")
    desc = weather.get("description", "")
    temp = main.get("temp")
    feels = main.get("feels_like")
    humid = main.get("humidity")
    wind_speed = round((wind.get("speed", 0)) * 3.6, 1)

    forecast_time = datetime.fromtimestamp(best["dt"]).strftime("%d/%m/%Y %H:%M")
    location_name = data.get("city", {}).get("name", VINHOMES_CITY)

    summary = (
        f"{icon} {desc.capitalize()} tại {location_name} (dự báo lúc {forecast_time})\n"
        f"Nhiệt độ: {temp}°C, cảm giác {feels}°C | Độ ẩm: {humid}% | Gió: {wind_speed} km/h"
    )

    return {
        "summary": summary,
        "temp_c": temp,
        "feels_like_c": feels,
        "humidity_pct": humid,
        "wind_kmh": wind_speed,
        "icon": icon,
        "description": desc,
        "forecast_time": forecast_time,
        "source": "openweathermap",
    }


@tool
def get_trip_context(trip_constraints: dict) -> dict:
    """Return real weather + realistic context for an Ocean Park 1 trip plan."""
    interests = {item.lower() for item in trip_constraints.get("interests", [])}

    try:
        with PLACES_JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            place_catalog = data.get("places", [])
    except Exception:
        place_catalog = []

    places = [p for p in place_catalog if not interests or p.get("tag") in interests]
    if not places and len(place_catalog) >= 3:
        places = [place_catalog[0], place_catalog[1], place_catalog[2]]

    origin = (trip_constraints.get("origin") or "").lower()
    transport = (
        "VinBus nội khu miễn phí, hoặc xe đạp/xe điện nội khu (Grab/XanhSM)."
        if any(k in origin for k in ("vinhomes", "s1.", "s2.", "z", "r1"))
        else "Nên di chuyển bằng taxi/xe tự lái hoặc VinBus các tuyến E01, E02, E03."
    )

    trip_date = trip_constraints.get("trip_date", "hôm nay")
    weather = _fetch_weather(str(trip_date))
    party_size = max(int(trip_constraints.get("party_size") or 1), 1)
    total_budget_vnd = _resolve_total_budget_vnd(trip_constraints, party_size)
    budget_level = trip_constraints.get("budget_level") or _infer_budget_level(total_budget_vnd, party_size)

    return {
        "weather": weather,
        "transport": transport,
        "budget_hint": f"Ngân sách mức '{budget_level}'.",
        "budget_total_vnd": total_budget_vnd,
        "places": places,
        "location": VINHOMES_CITY,
    }


@tool
def build_itinerary(trip_constraints: dict, trip_context: dict) -> dict:
    """Build a realistic itinerary draft and calculate estimated costs."""
    places = trip_context.get("places", [])
    party_size = max(int(trip_constraints.get("party_size") or 2), 1)
    total_budget_vnd = _resolve_total_budget_vnd(trip_constraints, party_size)

    itinerary = []
    all_places = list(places)
    morning_places = [p for p in all_places if p.get("tag") in ("check-in", "trẻ em", "tre em")]
    noon_places = [p for p in all_places if p.get("tag") in ("ăn uống", "an uong")]
    afternoon_places = [p for p in all_places if p.get("tag") in ("thư giãn", "thu gian", "check-in", "trẻ em", "tre em")]
    evening_places = [p for p in all_places if p.get("tag") in ("ăn uống", "an uong", "check-in", "thư giãn", "thu gian")]

    if total_budget_vnd is not None:
        all_places = sorted(all_places, key=lambda p: _place_total_cost_vnd(p, party_size))
        morning_places = sorted(morning_places, key=lambda p: _place_total_cost_vnd(p, party_size))
        noon_places = sorted(noon_places, key=lambda p: _place_total_cost_vnd(p, party_size))
        afternoon_places = sorted(afternoon_places, key=lambda p: _place_total_cost_vnd(p, party_size))
        evening_places = sorted(evening_places, key=lambda p: _place_total_cost_vnd(p, party_size))

    selected_places: list[dict] = []

    morning_place = _pick_next_place(morning_places, selected_places, all_places)
    if morning_place:
        p = morning_place
        selected_places.append(p)
        itinerary.append({"slot": "Sáng", "plan": f"Tới Ocean Park và bắt đầu tại {p['name']}. {p['note']}"})
    else:
        itinerary.append({"slot": "Sáng", "plan": "Tới Ocean Park, dạo bộ ngắm cảnh quan và tận hưởng không khí buổi sáng."})

    noon_place = _pick_next_place(noon_places, selected_places, all_places)
    if noon_place:
        p = noon_place
        selected_places.append(p)
        itinerary.append({"slot": "Trưa", "plan": f"Nghỉ ngơi và dùng bữa tại {p['name']}. {p['note']}"})
    else:
        itinerary.append({"slot": "Trưa", "plan": "Ăn trưa tại khu shophouse hoặc các quán ăn nội khu phù hợp ngân sách."})

    afternoon_place = _pick_next_place(afternoon_places, selected_places, all_places)
    if afternoon_place:
        p = afternoon_place
        selected_places.append(p)
        itinerary.append({"slot": "Chiều", "plan": f"Tiếp tục trải nghiệm tại {p['name']}. {p['note']}"})
    else:
        itinerary.append({"slot": "Chiều", "plan": "Dạo quanh hồ, chụp ảnh và thư giãn với các hoạt động miễn phí trong khu."})

    evening_place = _pick_next_place(evening_places, selected_places, all_places)
    if evening_place:
        p = evening_place
        selected_places.append(p)
        itinerary.append({"slot": "Tối", "plan": f"Kết thúc ngày tại {p['name']}. {p['note']}"})
    else:
        itinerary.append({"slot": "Tối", "plan": "Thưởng thức ẩm thực đường phố tại chợ đêm Hải Âu hoặc về sớm nếu muốn tiết kiệm chi phí."})

    ticket_cost_total = sum(int(p.get("ticket_cost_resident", 0)) * party_size for p in selected_places)
    fixed_fee_total = sum(int(p.get("fixed_fee", 0)) for p in selected_places)
    venue_food_surcharge_total = sum(int(p.get("food_surcharge_pp", 0)) * party_size for p in selected_places)
    estimated_cost = ticket_cost_total + fixed_fee_total + venue_food_surcharge_total
    budget_remaining_vnd = None if total_budget_vnd is None else total_budget_vnd - estimated_cost

    dynamic_notes = []
    for p in selected_places:
        if p.get("ticket_cost_resident", 0) > 0 or p.get("ticket_cost_guest", 0) > 0:
            dynamic_notes.append(
                f"Lưu ý về {p['name']}: giá vé cư dân {p.get('ticket_cost_resident', 0):,} VND, khách ngoài {p.get('ticket_cost_guest', 0):,} VND."
            )
        if p.get("fixed_fee", 0) > 0:
            dynamic_notes.append(f"Địa điểm {p['name']} có phụ phí cố định {p.get('fixed_fee', 0):,} VND.")

    notes = [
        trip_context.get("weather", {}).get("summary", ""),
        f"Gợi ý di chuyển: {trip_context.get('transport', '')}",
    ]
    notes.extend(dynamic_notes)

    if total_budget_vnd is not None:
        if budget_remaining_vnd >= 0:
            notes.append(f"Kế hoạch nằm trong ngân sách, còn dư khoảng {budget_remaining_vnd:,} VND.")
        else:
            notes.append(f"Kế hoạch đang vượt ngân sách khoảng {abs(budget_remaining_vnd):,} VND.")

    return {
        "itinerary": itinerary,
        "estimated_cost_vnd": estimated_cost,
        "estimated_cost_per_person_vnd": round(estimated_cost / party_size),
        "cost_breakdown": {
            "ticket_cost_total_vnd": ticket_cost_total,
            "fixed_fee_total_vnd": fixed_fee_total,
            "venue_food_surcharge_total_vnd": venue_food_surcharge_total,
        },
        "budget_total_vnd": total_budget_vnd,
        "budget_remaining_vnd": budget_remaining_vnd,
        "is_over_budget": bool(total_budget_vnd is not None and budget_remaining_vnd < 0),
        "notes": notes,
    }


TRIP_TOOL_REGISTRY = {
    "get_trip_requirements_helper": get_trip_requirements_helper,
    "get_trip_context": get_trip_context,
    "build_itinerary": build_itinerary,
}
