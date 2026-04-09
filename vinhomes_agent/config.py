from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
FAQ_CSV_PATH = DATA_DIR / "vinhomes_faq_selected.csv"
TICKET_STORE_PATH = DATA_DIR / "mock_tickets.jsonl"
SESSION_STORE_PATH = DATA_DIR / "chat_sessions.json"
PLACES_JSON_PATH = DATA_DIR / "vinhomes_places.json"
FEEDBACK_STORE_PATH = DATA_DIR / "chat_feedback.jsonl"

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# OpenWeatherMap — https://openweathermap.org/api/one-call-3
# Mừng đăng ký miễn phí tại: https://home.openweathermap.org/users/sign_up
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# Tọa độ Vinhomes Ocean Park Gia Lâm, Hà Nội
VINHOMES_LAT  = 20.9826
VINHOMES_LON  = 105.9397
VINHOMES_CITY = "Vinhomes Ocean Park Gia Lâm, Hà Nội"
