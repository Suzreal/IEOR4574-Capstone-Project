import os
import requests
from dotenv import load_dotenv

# Load .env from current project folder
load_dotenv(dotenv_path="/Users/grantgg/Desktop/restaurant-ai-demo/.env")

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
print("DEBUG GOOGLE_MAPS_API_KEY:", bool(API_KEY), "(True means key is loaded)")

if not API_KEY:
    raise RuntimeError("GOOGLE_MAPS_API_KEY not loaded from .env")

# ---------- Test 1: Geocoding ----------
address = "Times Square, New York"
geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
geo_params = {"address": address, "key": API_KEY}

print("\n=== Geocoding Test ===")
geo_resp = requests.get(geo_url, params=geo_params, timeout=10)
print("HTTP status code:", geo_resp.status_code)
geo_data = geo_resp.json()
print("Geocoding API status:", geo_data.get("status"))
print("Geocoding error_message:", geo_data.get("error_message"))
if geo_data.get("results"):
    first = geo_data["results"][0]
    print("Formatted address:", first.get("formatted_address"))
    loc = first["geometry"]["location"]
    lat, lng = loc["lat"], loc["lng"]
    print("Lat, Lng:", lat, lng)
else:
    print("No results from Geocoding.")

# ---------- Test 2: Places Nearby Search ----------
print("\n=== Places Nearby Search Test ===")
if geo_data.get("results"):
    loc = geo_data["results"][0]["geometry"]["location"]
    lat, lng = loc["lat"], loc["lng"]
else:
    raise RuntimeError("Cannot run Places test because Geocoding had no results.")

places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
places_params = {
    "location": f"{lat},{lng}",
    "radius": 5000,  # 5 km
    "type": "restaurant",
    "keyword": "Japanese restaurant",
    "key": API_KEY,
}

places_resp = requests.get(places_url, params=places_params, timeout=10)
print("HTTP status code:", places_resp.status_code)
places_data = places_resp.json()
print("Places API status:", places_data.get("status"))
print("Places error_message:", places_data.get("error_message"))

results = places_data.get("results", [])
print("Number of places returned:", len(results))
for r in results[:5]:
    print("-", r.get("name"), "| rating:", r.get("rating"), "| addr:", r.get("vicinity"))
