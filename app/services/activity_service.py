import requests
from fastapi import Request
from user_agents import parse
from sqlalchemy.orm import Session
from app.models import Activity, User, Location

from typing import Optional

class ActivityService:
    @staticmethod
    def get_client_ip(request: Request) -> str:
        # Check headers first for proxy, fallback to client.host
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "127.0.0.1"

    @staticmethod
    async def get_geolocation(ip_address: str, lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
        """Fetch location using IP or coordinates (Reverse Geocoding)."""
        # If coordinates are provided, prioritize reverse geocoding to get the exact city/country
        if lat is not None and lon is not None:
            geo_data = await ActivityService.reverse_geocode(lat, lon)
            if geo_data.get("status") == "success":
                return {
                    "city": geo_data.get("city"),
                    "country": geo_data.get("country"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "status": "success"
                }

        # Default fallback (Tactical HQ)
        default_geo = {
            "city": "Internal Network", 
            "country": "Corporate HQ", 
            "latitude": 0.0, 
            "longitude": 0.0, 
            "countryCode": "INTERNAL",
            "status": "success"
        }
        
        # 1. Private/Localhost IP Check
        private_prefixes = ("127.", "192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", 
                            "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", 
                            "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "::1")
        
        is_internal = any(ip_address.startswith(p) for p in private_prefixes) or ip_address in ("localhost", "0.0.0.0")
        target_ip = "" if is_internal else ip_address

        import httpx
        async with httpx.AsyncClient() as client:
            # Primary: ip-api.com
            try:
                url = f"http://ip-api.com/json/{target_ip}?fields=status,country,countryCode,city,lat,lon"
                resp = await client.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success" and data.get("lat"):
                        lat = float(data.get("lat", 0.0))
                        lon = float(data.get("lon", 0.0))
                        
                        # Validate coordinate ranges (-90 to 90 lat, -180 to 180 lon)
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            import logging
                            logging.getLogger("ueba").warning(f"Invalid coordinates from ip-api: {lat}, {lon}")
                            return default_geo

                        return {
                            "city": data.get("city", "Internal"),
                            "country": data.get("country", "Network"),
                            "countryCode": data.get("countryCode", ""),
                            "latitude": lat,
                            "longitude": lon,
                            "status": "success"
                        }
            except Exception:
                pass # Try secondary fallback

            # Secondary: ipapi.co (JSON)
            try:
                url = f"https://ipapi.co/{target_ip}/json/" if target_ip else "https://ipapi.co/json/"
                resp = await client.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("error") and data.get("latitude"):
                        return {
                            "city": data.get("city", "Internal"),
                            "country": data.get("country_name", "Network"),
                            "countryCode": data.get("country_code", ""),
                            "latitude": float(data.get("latitude", 0.0)),
                            "longitude": float(data.get("longitude", 0.0)),
                            "status": "success"
                        }
            except Exception:
                pass
        
        return default_geo

    @staticmethod
    async def reverse_geocode(lat: float, lon: float) -> dict:
        """Fetch city and country from coordinates using Nominatim (OpenStreetMap)."""
        import httpx
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
            # User-Agent is required by Nominatim's usage policy
            headers = {"User-Agent": "UEBA-Security-Platform/1.0"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    address = data.get("address", {})
                    # Try to get city, town, or village
                    city = address.get("city") or address.get("town") or address.get("village") or address.get("suburb") or "Unknown"
                    country = address.get("country", "Unknown")
                    return {"city": city, "country": country, "status": "success"}
        except Exception as e:
            # We don't want to crash the whole app if the free geocoder is down
            import logging
            logging.getLogger("ueba").warning(f"Reverse geocode failed: {str(e)}")
        return {"city": "Unknown", "country": "Unknown", "status": "failed"}

    @staticmethod
    async def log_activity(db: Session, request: Request, user: User, status: str = "success") -> tuple[Activity, dict]:
        """Extracts context and creates an Activity record (Async)."""
        ip = ActivityService.get_client_ip(request)
        ua_string = request.headers.get("user-agent", "")
        parsed_ua = parse(ua_string)
        
        browser = f"{parsed_ua.browser.family} {parsed_ua.browser.version_string}" if parsed_ua else "Unknown"
        device = f"{parsed_ua.os.family} {parsed_ua.device.family}" if parsed_ua else "Unknown"
        
        # Async geolocation lookup
        geo = await ActivityService.get_geolocation(ip)

        activity_data = {
            "browser": browser,
            "device": device,
            "country": geo.get("country"),
            "city": geo.get("city"),
            "countryCode": geo.get("countryCode")
        }

        # Format location string
        if geo.get("countryCode") == "INTERNAL":
            location_str = "Internal Network"
        else:
            location_str = f"{geo.get('city')}, {geo.get('country')}"

        # Initialize Activity object
        activity = Activity(
            user_id=user.id,
            ip_address=ip,
            browser=browser,
            device=device,
            location=location_str,
            city=geo.get("city"),
            country=geo.get("country"),
            latitude=geo.get("latitude"),
            longitude=geo.get("longitude"),
            status=status,
            device_info=ua_string[:250], # fit to column length
        )

        # Also create an initial Location record for the live tracker/map
        if status == "success" and geo.get("latitude") and geo.get("longitude"):
            from app.models import Location
            from datetime import datetime
            initial_location = Location(
                user_id=user.id,
                latitude=geo.get("latitude"),
                longitude=geo.get("longitude"),
                timestamp=datetime.utcnow()
            )
            db.add(initial_location)

        return activity, activity_data
