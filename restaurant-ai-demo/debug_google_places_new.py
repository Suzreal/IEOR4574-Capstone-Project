import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path="/Users/grantgg/Desktop/restaurant-ai-demo/.env")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
print("DEBUG GOOGLE_MAPS_API_KEY:", bool(API_KEY), "(True means key is loaded)")

if not API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY not loaded from .env")

# First get coordinates with Geocoding
geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
geo_params = {"address": "Times Square, New York", "key": API_KEY}

print("\n=== Geocoding Test ===")
geo_resp = requests.get(geo_url, params=geo_params, timeout=10)
print("HTTP status code:", geo_resp.status_code)
geo_data = geo_resp.json()
print("Geocoding API status:", geo_data.get("status"))
print("Geocoding error_message:", geo_data.get("error_message"))

if not geo_data.get("results"):
    raise RuntimeError("Geocoding returned no results.")

loc = geo_data["results"][0]["geometry"]["location"]
lat, lng = loc["lat"], loc["lng"]
print("Lat, Lng:", lat, lng)

# Now test Places API (New)
print("\n=== Places API (New) Nearby Search Test ===")

url = "https://places.googleapis.com/v1/places:searchNearby"
body = {
    "includedTypes": ["restaurant"],
    "maxResultCount": 20,
    "locationRestriction": {
        "circle": {
            "center": {"latitude": lat, "longitude": lng},
            "radius": 5000,  # 5 km
        }
    },
    "keyword": "Japanese restaurant",
}

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": (
        "places.displayName,places.rating,places.userRatingCount,"
        "places.formattedAddress,places.location,places.id"
    ),
}

resp = requests.post(url, json=body, headers=headers, timeout=10)
print("HTTP status code:", resp.status_code)
data = resp.json()
print("Top-level keys:", list(data.keys()))
print("Error field (if any):", data.get("error"))

places = data.get("places", [])
print("Number of places returned:", len(places))
for p in places[:5]:
    name = (p.get("displayName") or {}).get("text")
    rating = p.get("rating")
    addr = p.get("formattedAddress")
    print("-", name, "| rating:", rating, "| addr:", addr)
