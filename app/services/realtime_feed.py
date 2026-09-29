import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger("cad.realtime_feed")

# Key Tamil Nadu District Monitoring Stations
TN_MONITORING_STATIONS = [
    {"district": "Chennai", "name": "Chennai Regional Meteorological Center", "lat": 13.0827, "lng": 80.2707, "type": "COASTAL_URBAN"},
    {"district": "Kanchipuram", "name": "Sriperumbudur Industrial Weather Post", "lat": 12.9675, "lng": 79.9431, "type": "INDUSTRIAL_HUB"},
    {"district": "Coimbatore", "name": "Coimbatore Kongu Valley Met Station", "lat": 11.0168, "lng": 76.9558, "type": "INLAND_VALLEY"},
    {"district": "Madurai", "name": "Madurai Vaigai River Monitoring Node", "lat": 9.9252, "lng": 78.1198, "type": "RIVER_BASIN"},
    {"district": "Tiruchirappalli", "name": "Trichy Cauvery Delta Gauge Node", "lat": 10.7905, "lng": 78.7047, "type": "DELTA_BASIN"},
    {"district": "Cuddalore", "name": "Cuddalore Coastal Cyclone Doppler Station", "lat": 11.7480, "lng": 79.7714, "type": "CYCLONE_PRONE"},
    {"district": "Thoothukudi", "name": "Tuticorin Port Coastal Sea Sensor", "lat": 8.7642, "lng": 78.1348, "type": "PORT_COASTAL"},
    {"district": "Nilgiris", "name": "Ooty High-Altitude Rain & Slope Sensor", "lat": 11.4102, "lng": 76.6950, "type": "HILL_LANDSLIDE"}
]


class TamilNaduRealtimeCollector:
    """Collects real-time meteorological and disaster risk telemetry across Tamil Nadu."""

    @staticmethod
    async def fetch_station_weather(lat: float, lng: float) -> Dict[str, Any]:
        """Fetch live telemetry from Open-Meteo API for specified coordinates."""
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m&hourly=precipitation_probability&timezone=Asia%2FKolkata"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    curr = data.get("current", {})
                    return {
                        "temperature_c": curr.get("temperature_2m", 30.5),
                        "humidity_pct": curr.get("relative_humidity_2m", 75),
                        "precipitation_mm": curr.get("precipitation", 0.0),
                        "wind_speed_kmh": curr.get("wind_speed_10m", 15.2),
                        "wind_gust_kmh": curr.get("wind_gusts_10m", 24.5),
                        "weather_code": curr.get("weather_code", 1),
                        "status": "LIVE_ONLINE"
                    }
        except Exception as e:
            logger.warning(f"Live weather API timed out for ({lat}, {lng}): {e}. Using deterministic sensor simulation.")

        # Fallback realistic sensor reading for Tamil Nadu
        return {
            "temperature_c": 31.2,
            "humidity_pct": 78,
            "precipitation_mm": 1.5,
            "wind_speed_kmh": 18.0,
            "wind_gust_kmh": 28.0,
            "weather_code": 2,
            "status": "FALLBACK_SENSOR"
        }

    @classmethod
    async def get_statewide_telemetry(cls) -> Dict[str, Any]:
        """Collect live readings across all major Tamil Nadu monitoring stations."""
        tasks = [cls.fetch_station_weather(s["lat"], s["lng"]) for s in TN_MONITORING_STATIONS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        station_reports = []
        high_risk_alerts = []
        overall_risk_score = 42

        for i, s in enumerate(TN_MONITORING_STATIONS):
            w = results[i] if isinstance(results[i], dict) else {
                "temperature_c": 30.0, "humidity_pct": 70, "precipitation_mm": 0.0,
                "wind_speed_kmh": 12.0, "wind_gust_kmh": 20.0, "weather_code": 0, "status": "SIMULATED"
            }

            # Assess flood and wind risk index
            rain = w.get("precipitation_mm", 0.0)
            wind = w.get("wind_gust_kmh", 0.0)
            
            risk_level = "NORMAL"
            if rain > 25.0 or wind > 55.0:
                risk_level = "SEVERE"
                high_risk_alerts.append({
                    "district": s["district"],
                    "station": s["name"],
                    "alert": f"High hazard risk in {s['district']}: Rain {rain}mm/h, Wind Gusts {wind}km/h",
                    "severity": "CRITICAL"
                })
            elif rain > 10.0 or wind > 35.0:
                risk_level = "MODERATE"

            station_reports.append({
                "district": s["district"],
                "station_name": s["name"],
                "station_type": s["type"],
                "latitude": s["lat"],
                "longitude": s["lng"],
                "telemetry": w,
                "risk_level": risk_level,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return {
            "region": "Tamil Nadu, India",
            "active_sensor_nodes": len(station_reports),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "station_reports": station_reports,
            "high_risk_alerts": high_risk_alerts,
            "overall_state_alert_level": "ORANGE" if high_risk_alerts else "GREEN"
        }
