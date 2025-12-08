import os
import requests
from urllib.parse import quote_plus

from flask import Flask, render_template, request
from dotenv import load_dotenv
from openai import OpenAI

# ==========================
# Load environment variables
# ==========================
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

MILES_TO_METERS = 1609.34

# Cuisine keyword mapping for Google Places text search
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

CUISINE_LABELS = {
    "chinese": "Chinese",
    "french": "French",
    "southeast_asian": "Southeast Asian",
    "japanese": "Japanese",
    "korean": "Korean",
    "spanish": "Spanish",
    "mexican": "Mexican",
    "italian": "Italian",
}


# =====================================
# 1. Geocoding
# =====================================
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
    if data.get("status") != "OK":
        print("Geocoding error:", data)
        return None, None, None

    result = data["results"][0]
    loc = result["geometry"]["location"]
    lat, lng = loc["lat"], loc["lng"]

    city = None
    for comp in result.get("address_components", []):
        if "locality" in comp.get("types", []):
            city = comp.get("long_name")
            break

    return lat, lng, city


# =====================================
# 2. Google Places (v1) Text Search
# =====================================
def search_restaurants(lat, lng, cuisine_key, radius_meters):
    keyword = CUISINE_KEYWORDS.get(cuisine_key, "")

    url = "https://places.googleapis.com/v1/places:searchText"

    body = {
        "textQuery": keyword,
        "maxResultCount": 20,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": min(radius_meters, 50000),
            }
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.name,places.displayName,places.rating,"
            "places.userRatingCount,places.formattedAddress,places.photos"
        ),
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print("Places Text Search error:", repr(e))
        return []

    data = resp.json()
    if "error" in data:
        print("Places Text Search API error:", data["error"])
        return []

    restaurants = []

    for p in data.get("places", []):
        name_obj = p.get("displayName") or {}
        name_text = name_obj.get("text") or ""

        if not name_text:
            continue

        rating = p.get("rating", 0.0)
        user_ratings_total = p.get("userRatingCount", 0)
        address = p.get("formattedAddress", "")

        # v1 id (e.g. "places/ChIJ..."), used later for details
        place_resource_name = p.get("id") or p.get("name")

        photo_url = ""
        photos = p.get("photos", [])
        if photos:
            photo_name = photos[0].get("name")
            if photo_name:
                photo_url = (
                    f"https://places.googleapis.com/v1/{photo_name}/media"
                    f"?maxWidthPx=800&key={GOOGLE_API_KEY}"
                )

        query = quote_plus(f"{name_text} {address}")
        maps_url = f"https://www.google.com/maps/search/?api=1&query={query}"

        restaurants.append(
            {
                "name": name_text,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
                "address": address,
                "place_id": place_resource_name,
                "maps_url": maps_url,
                "photo_url": photo_url,
            }
        )

    restaurants.sort(
        key=lambda x: (x["rating"], x["user_ratings_total"]), reverse=True
    )
    return restaurants[:5]


# =====================================
# 3. Google Places Details: extra context
# =====================================
def fetch_place_context(place_id: str) -> dict:
    """
    Fetch extra context for a restaurant from Google Places Details API (v1).
    We use types and editorial summary when available.
    """
    if not place_id:
        return {}

    if not place_id.startswith("places/"):
        place_path = f"places/{place_id}"
    else:
        place_path = place_id

    url = f"https://places.googleapis.com/v1/{place_path}"
    params = {
        "fields": "types,primaryType,primaryTypeDisplayName,editorialSummary"
    }
    headers = {
        "X-Goog-Api-Key": GOOGLE_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=6)
        resp.raise_for_status()
    except Exception as e:
        print("Places details error:", repr(e))
        return {}

    data = resp.json() or {}
    ctx = {}

    ctx["types"] = data.get("types", [])
    ctx["primary_type"] = data.get("primaryType")
    ctx["primary_type_display"] = (
        data.get("primaryTypeDisplayName", {}) or {}
    ).get("text")
    editorial = data.get("editorialSummary", {})
    ctx["editorial_summary"] = editorial.get("text")

    return ctx


# =====================================
# 4. AI Recommended Dishes with context (gpt-5-mini)
# =====================================
def generate_dish_recommendations_for_restaurant(
    restaurant: dict,
    cuisine_label: str,
    city: str | None = None,
):
    name = restaurant.get("name", "this restaurant")
    address = restaurant.get("address", "")
    rating = restaurant.get("rating", None)
    reviews = restaurant.get("user_ratings_total", None)
    place_id = restaurant.get("place_id")

    place_ctx = fetch_place_context(place_id)
    types = place_ctx.get("types", [])
    primary_type = place_ctx.get("primary_type")
    primary_display = place_ctx.get("primary_type_display")
    editorial = place_ctx.get("editorial_summary")

    pieces = []
    if city:
        pieces.append(city)
    if address:
        pieces.append(address)
    location_str = ", ".join(pieces) if pieces else "this city"

    rating_str = ""
    if rating is not None and reviews is not None:
        rating_str = (
            f"It has a Google rating of {rating:.1f} "
            f"based on about {reviews} reviews."
        )
    elif rating is not None:
        rating_str = f"It has a Google rating of {rating:.1f}."

    type_str = ""
    if primary_display:
        type_str = f"It is labeled as a '{primary_display}'."
    elif primary_type:
        type_str = f"It is labeled as type '{primary_type}'."

    if types:
        type_str += f" Extra types: {', '.join(types[:6])}."

    editorial_str = ""
    if editorial:
        editorial_str = f' Google describes it as: "{editorial}"'

    restaurant_desc = (
        f"The restaurant is called '{name}', located in {location_str}. "
        f"{rating_str} {type_str} {editorial_str}"
    )

    base_instruction = (
        "You are a foodie and menu expert.\n\n"
        "I will describe a real restaurant and the user's cuisine preference. "
        "Based on this description and your knowledge of typical menus for this "
        "style of restaurant, suggest 3 likely signature dishes that a user "
        "should try. You may approximate based on common patterns for that "
        "cuisine and type; you do not need to know the exact menu, but avoid "
        "contradicting the description.\n\n"
    )

    user_prompt = (
        base_instruction
        + f"Restaurant description:\n{restaurant_desc}\n\n"
        + f"User cuisine preference: {cuisine_label}.\n\n"
        + "Return your answer as a short bullet list. Each line should be:\n"
        + "Dish name – one-sentence description."
    )

    print("=== OpenAI dish debug ===")
    print("OPENAI_API_KEY prefix:", (OPENAI_API_KEY or "")[:12])
    print("Model: gpt-5-mini")
    print("Restaurant desc for model:", restaurant_desc)

    def extract_text_from_completion(comp):
        msg = comp.choices[0].message
        content = msg.content
        print("message.content type:", type(content))
        print("message.content raw:", repr(content))

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for c in content:
                t = getattr(c, "text", None)
                if t is None and isinstance(c, dict):
                    t = c.get("text")
                if t:
                    parts.append(t)
            return "\n".join(parts).strip()

        return ""

    try:
        # First attempt: full prompt with context
        completion = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert food and restaurant recommendation assistant.",
                },
                {"role": "user", "content": user_prompt},
            ],
            # no max_completion_tokens here – use default so model has room to speak
        )
        print("RAW completion object (full prompt):", completion)
        text = extract_text_from_completion(completion)
        print("Final extracted text (full prompt):", repr(text))

        if text:
            return text

        # Retry with simplified prompt if first attempt was empty
        print(">>> First call returned empty text. Retrying with simplified prompt...")
        simple_prompt = (
            f"Suggest 3 signature dishes for a {cuisine_label} restaurant "
            f"called '{name}'. Return a bullet list; each line is "
            "Dish name – one-sentence description."
        )

        completion2 = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert food and restaurant recommendation assistant.",
                },
                {"role": "user", "content": simple_prompt},
            ],
        )
        print("RAW completion object (simple prompt):", completion2)
        text2 = extract_text_from_completion(completion2)
        print("Final extracted text (simple prompt):", repr(text2))

        if text2:
            return text2

        return "(Model returned empty content for this restaurant, even after retry.)"

    except Exception as e:
        print("OpenAI dish error:", repr(e))
        return "AI dish recommendation failed. Please try again later."


# =====================================
# 5. Flask Routes
# =====================================
@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        results=None,
        error=None,
        address="",
        cuisine="",
        radius=3,
    )


@app.route("/search", methods=["POST"])
def search():
    address = request.form.get("address", "").strip()
    cuisine = request.form.get("cuisine", "")
    radius = float(request.form.get("radius", 3))

    lat, lng, city = geocode_address(address)
    if lat is None:
        return render_template(
            "index.html",
            results=[],
            error="Unable to parse address. Please try another location.",
            address=address,
            cuisine=cuisine,
            radius=radius,
        )

    restaurants = search_restaurants(lat, lng, cuisine, radius * MILES_TO_METERS)

    cuisine_label = CUISINE_LABELS.get(cuisine, "this cuisine style")

    for r in restaurants:
        r["dish_recs"] = generate_dish_recommendations_for_restaurant(
            restaurant=r,
            cuisine_label=cuisine_label,
            city=city,
        )

    return render_template(
        "index.html",
        results=restaurants,
        error=None,
        address=address,
        cuisine=cuisine,
        radius=radius,
    )


# =====================================
# Run App
# =====================================
if __name__ == "__main__":
    app.run(debug=True)
