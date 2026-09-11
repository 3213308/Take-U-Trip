# app/adapters/real/weather.py
"""和风天气 Real Adapter"""

import logging
import httpx
from app.adapters.base import BaseWeatherAdapter

logger = logging.getLogger(__name__)

GEO_URL = "np7mdc6wkx.re.qweatherapi.com"
WEATHER_URL = "np7mdc6wkx.re.qweatherapi.com"


class QWeatherAdapter(BaseWeatherAdapter):
    def __init__(self, api_key: str, api_host: str):
        self.api_key = api_key
        self.base = f"https://{api_host}"

    async def _get_location_id(self, city: str) -> str | None:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base}/geo/v2/city/lookup",
                params={"location": city, "key": self.api_key},
            )
            data = r.json()
            if data.get("code") == "200" and data.get("location"):
                return data["location"][0]["id"]
            return None

    async def get_weather(self, city: str, date_range: tuple[str, str]) -> list[dict]:
        location_id = await self._get_location_id(city)
        if not location_id:
            return []
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base}/v7/weather/3d",
                params={"location": location_id, "key": self.api_key},
            )
            data = r.json()
        if data.get("code") != "200":
            logger.warning("和风天气 API 返回错误: %s", data)
            return []
        result = []
        for d in data.get("daily", []):
            result.append({
                "date": d["fxDate"],
                "weather": d["textDay"],
                "temp_high": int(d["tempMax"]),
                "temp_low": int(d["tempMin"]),
                "wind": f"{d['windDirDay']}{d['windScaleDay']}级",
                "rain_probability": int(d.get("pop", 0)),
            })
        return result
