from __future__ import annotations

import os
from typing import Any
import requests


def get_weather(city: str, units: str = "metric") -> dict[str, Any]:
    """Fetch current weather for a city directly using OpenWeather API without demo fallbacks."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {
            "error": "missing_api_key",
            "message": "Thiếu cấu hình OPENWEATHER_API_KEY trong file .env.",
        }

    if not city or not city.strip():
        return {
            "error": "missing_city",
            "message": "Tham số thành phố (city) không được để trống.",
        }

    url = "https://api.openweathermap.org/data/2.5/weather"
    selected_units = units if units in {"metric", "imperial"} else "metric"
    params = {
        "q": city.strip(),
        "appid": api_key.strip(),
        "units": selected_units,
        "lang": "vi",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 401:
            return {
                "error": "unauthorized",
                "message": (
                    "Lỗi truy cập OpenWeather API (401 Unauthorized): "
                    "API Key mới tạo cần khoảng 10-30 phút để hệ thống OpenWeather kích hoạt hoàn tất. "
                    "Vui lòng thử lại sau ít phút."
                ),
            }
            
        if response.status_code == 404:
            return {
                "error": "city_not_found",
                "message": f"Không tìm thấy dữ liệu thời tiết cho thành phố '{city}'. Vui lòng kiểm tra lại tên thành phố.",
            }
            
        if response.status_code != 200:
            return {
                "error": f"http_{response.status_code}",
                "message": f"Lỗi gọi OpenWeather API (HTTP {response.status_code}): {response.text}",
            }

        data = response.json()
        weather_desc = ""
        weather_icon = ""
        if data.get("weather") and len(data["weather"]) > 0:
            weather_desc = data["weather"][0].get("description", "").capitalize()
            weather_icon = data["weather"][0].get("icon", "")

        return {
            "city": data.get("name", city),
            "country": data.get("sys", {}).get("country", ""),
            "temp": round(data.get("main", {}).get("temp", 0), 1),
            "feels_like": round(data.get("main", {}).get("feels_like", 0), 1),
            "humidity": data.get("main", {}).get("humidity", 0),
            "description": weather_desc,
            "icon": weather_icon,
            "wind_speed": data.get("wind", {}).get("speed", 0),
            "units": "°C" if selected_units == "metric" else "°F",
        }
    except requests.RequestException as exc:
        return {
            "error": type(exc).__name__,
            "message": f"Lỗi kết nối mạng tới OpenWeather API: {str(exc)}",
        }
