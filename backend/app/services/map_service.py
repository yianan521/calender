"""
Map Service — commute time calculation and departure reminders.
Supports Amap (高德地图) as primary provider, with fallback to direct distance estimation.
"""

import logging
import math
from datetime import datetime, timedelta

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class MapService:
    """Commute time calculator using map API."""

    BASE_URL = "https://restapi.amap.com/v3"

    async def get_commute_info(
        self, origin: str, destination: str
    ) -> dict:
        """Calculate commute time and distance between two locations.

        Returns dict with: commute_minutes, distance_km, routes
        """
        if not settings.map_api_key:
            return self._estimate_direct(origin, destination)

        try:
            # Geocode origin and destination
            origin_coords = await self._geocode(origin)
            dest_coords = await self._geocode(destination)

            if not origin_coords or not dest_coords:
                return self._estimate_direct(origin, destination)

            # Get driving route
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/direction/driving",
                    params={
                        "key": settings.map_api_key,
                        "origin": origin_coords,
                        "destination": dest_coords,
                        "extensions": "base",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1" or not data.get("route", {}).get("paths"):
                return self._estimate_direct(origin, destination)

            path = data["route"]["paths"][0]
            duration_seconds = int(path.get("duration", 0))
            distance_meters = int(path.get("distance", 0))

            steps = []
            for step in path.get("steps", []):
                steps.append({
                    "instruction": step.get("instruction", ""),
                    "road": step.get("road", ""),
                    "distance": step.get("distance", ""),
                    "duration": step.get("duration", ""),
                })

            return {
                "commute_minutes": max(1, math.ceil(duration_seconds / 60)),
                "distance_km": round(distance_meters / 1000, 1),
                "routes": steps[:5],  # first 5 steps
            }

        except Exception as e:
            logger.warning("Map API commute request failed: %s", e)
            return self._estimate_direct(origin, destination)

    async def _geocode(self, address: str) -> str | None:
        """Convert address to coordinates (lng,lat)."""
        if not settings.map_api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/geocode/geo",
                    params={
                        "key": settings.map_api_key,
                        "address": address,
                        "city": settings.map_city,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") == "1" and data.get("geocodes"):
                return data["geocodes"][0].get("location")
            return None
        except Exception:
            return None

    @staticmethod
    def _estimate_direct(origin: str, destination: str) -> dict:
        """Fallback: rough estimate based on distance assumption (30km/h average)."""
        distance_km = 10.0  # default assumption
        commute_minutes = math.ceil(distance_km / 30 * 60)
        return {
            "commute_minutes": commute_minutes,
            "distance_km": distance_km,
            "routes": [],
        }

    def calculate_departure_time(
        self, event_start: datetime, commute_minutes: int, buffer_minutes: int = 10
    ) -> datetime:
        """Calculate when the user should depart to arrive on time."""
        return event_start - timedelta(minutes=commute_minutes + buffer_minutes)

    async def suggest_commute_reminder(
        self,
        origin: str,
        event_title: str,
        event_start: datetime,
        event_location: str,
        buffer_minutes: int = 10,
    ) -> dict:
        """Generate a complete commute reminder suggestion."""
        commute_info = await self.get_commute_info(origin, event_location)
        commute_minutes = commute_info["commute_minutes"]
        departure_time = self.calculate_departure_time(
            event_start, commute_minutes, buffer_minutes
        )

        return {
            "origin": origin,
            "destination": event_location,
            "commute_minutes": commute_minutes,
            "distance_km": commute_info["distance_km"],
            "departure_time": departure_time,
            "event_start": event_start,
            "message": (
                f"前往「{event_title}」预计需要{commute_minutes}分钟"
                f"（约{commute_info['distance_km']}公里），"
                f"建议在{departure_time.strftime('%H:%M')}前出发。"
            ),
            "routes": commute_info.get("routes", []),
        }


map_service = MapService()
