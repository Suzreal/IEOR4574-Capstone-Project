import os
import requests
from urllib.parse import quote_plus

from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

MILES_TO_METERS = 1609.34

# Cuisine → textQuery mapping
CUISINE_KEYWORDS = {
    "chinese": "Chinese restaurant",
    "french": "French restaurant",
    "southeast_asian": "Southeast Asian restaurant",
    "japanese": "Japanese restaurant",
    "korean": "Korean restaurant",
    "spanish": "Spanish restaurant",
    "mexican": "Mexican restaurant",
    "italian": "Italian restaurant",
}


# ----------------------------
# 1. GEOCODING
# ----------------------------
def geocode_address(address: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
    except Exception as e:
        print("Geocoding request failed:", repr(e))
        return None, None, None

    data = resp.json()
    if data.get("status") != "OK" or not data.get("results"):
        print("Geocoding returned no results:", data)
        return None, None, None

    result = data["results"][0]
    loc = result["geometry"]["location"]
    lat = loc["lat"]
    lng = loc["lng"]

    city = None
    for comp in result.get("address_components", []):
        if "locality" in comp.get("types", []):
            city = comp.get("long_name")
            break

    return lat, lng, city


# ----------------------------
# 2. PLACES API (NEW): SEARCH TEXT + PHOTOS
# ----------------------------
def search_restaurants(lat: float, lng: float, cuisine_key: str, radius_meters: int):
    keyword = CUISINE_KEYWORDS.get(cuisine_key, "")
    if not keyword:
        print("Unknown cuisine key:", cuisine_key)
        return []

    url = "https://places.googleapis.com/v1/places:searchText"

    radius_for_api = min(radius_meters, 50000)

    body = {
        "textQuery": keyword,
        "maxResultCount": 20,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius_for_api,
            }
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.displayName,places.rating,places.userRatingCount,"
            "places.formattedAddress,places.location,places.id,places.photos"
        ),
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print("Places API request failed:", repr(e))
        return []

    data = resp.json()

    if "error" in data:
        print("Places API error:", data["error"])
        return []

    places = data.get("places", [])

    restaurants = []
    for p in places:
        name = (p.get("displayName") or {}).get("text")
        if not name:
            continue

        rating = p.get("rating", 0)
        user_ratings_total = p.get("userRatingCount", 0)
        address = p.get("formattedAddress", "")
        place_internal_id = p.get("id")

        # Photo handling (take first photo if exists)
        photo_url = ""
        photos = p.get("photos") or []
        if photos:
            photo_name = photos[0].get("name")
            if photo_name:
                # Places Photos (New): /v1/{photo_name}/media
                photo_url = (
                    f"https://places.googleapis.com/v1/{photo_name}/media"
                    f"?maxWidthPx=800&key={GOOGLE_API_KEY}"
                )

        query = quote_plus(f"{name} {address}")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"

        restaurants.append(
            {
                "name": name,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
                "address": address,
                "place_id": place_internal_id,
                "maps_url": maps_url,
                "photo_url": photo_url,
            }
        )

    restaurants.sort(
        key=lambda x: (x["rating"], x["user_ratings_total"]), reverse=True
    )

    return restaurants[:5]


# ----------------------------
# 3. AI DISH RECOMMENDATIONS
# ----------------------------
def generate_dish_recommendations(
    restaurant_name: str, cuisine_label: str, city: str | None = None
):
    location_info = f"in {city}" if city else ""
    user_prompt = (
        f"You are a foodie assistant. For the restaurant '{restaurant_name}' "
        f"{location_info}, which mainly serves {cuisine_label} cuisine, "
        "suggest 3 representative signature dishes. "
        "Return them as a short bullet list, each line: "
        "Dish Name – brief description (one sentence)."
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert food and restaurant recommendation assistant.",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_completion_tokens=200,
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print("OpenAI error while generating dishes:", repr(e))
        return "AI dish recommendation failed. Please try again later."


# ----------------------------
# 4. FLASK ROUTES
# ----------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", results=None, error=None)


@app.route("/search", methods=["POST"])
def search():
    address = request.form.get("address", "").strip()
    cuisine_key = request.form.get("cuisine", "").strip()
    radius_miles = request.form.get("radius", "1").strip()

    if not address or not cuisine_key:
        return render_template(
            "index.html",
            results=None,
            error="Please fill in both address and cuisine.",
            address=address,
            cuisine=cuisine_key,
            radius=radius_miles,
        )

    try:
        radius_miles_float = float(radius_miles)
    except ValueError:
        radius_miles_float = 1.0

    radius_meters = int(radius_miles_float * MILES_TO_METERS)

    lat, lng, city = geocode_address(address)
    if lat is None:
        return render_template(
            "index.html",
            results=None,
            error="Failed to parse this address. Please try a more standard address.",
            address=address,
            cuisine=cuisine_key,
            radius=radius_miles_float,
        )

    restaurants = search_restaurants(lat, lng, cuisine_key, radius_meters)

    if not restaurants:
        return render_template(
            "index.html",
            results=[],
            error="No restaurants found. Ensure Places API (New) is enabled.",
            address=address,
            cuisine=cuisine_key,
            radius=radius_miles_float,
        )

    cuisine_label_map = {
        "chinese": "Chinese",
        "french": "French",
        "southeast_asian": "Southeast Asian",
        "japanese": "Japanese",
        "korean": "Korean",
        "spanish": "Spanish",
        "mexican": "Mexican",
        "italian": "Italian",
    }
    cuisine_label = cuisine_label_map.get(cuisine_key, "this")

    for r in restaurants:
        r["dish_recs"] = generate_dish_recommendations(
            r["name"], cuisine_label, city
        )

    return render_template(
        "index.html",
        results=restaurants,
        error=None,
        address=address,
        cuisine=cuisine_key,
        radius=radius_miles_float,
    )


# ----------------------------
# RUN APP
# ----------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
