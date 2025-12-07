import pandas as pd
import requests
import json

DATA_PATH = "manhattan_restaurants.csv" 
MODEL_NAME = "gemma3:12b"
OLLAMA_URL = "http://localhost:11434/api/chat" 


df = pd.read_csv(DATA_PATH)

# Basic data cleaning
df["ZIPCODE"] = df["ZIPCODE"].fillna(0).astype(int).astype(str)
df["CUISINE_DESCRIPTION"] = df["CUISINE_DESCRIPTION"].astype(str)
df["RESTAURANT"] = df["RESTAURANT"].astype(str)
df["STREET"] = df["STREET"].astype(str)
df["BUILDING"] = df["BUILDING"].astype(str)
df["PHONE"] = df["PHONE"].astype(str)
df["CRITICALFLAG"] = df["CRITICALFLAG"].astype(str)


# =============================
#  Simple intent check
# =============================

def looks_like_restaurant_query(user_query: str) -> bool:
    """
    Simple heuristic: check for food/restaurant/cuisine words.
    If this returns False, we ask the user for a clearer restaurant prompt.
    """
    q = user_query.lower()

    restaurant_words = [
        "restaurant", "restaur", "resturant", "restruant",
        "food", "eat", "dinner", "lunch", "breakfast",
        "brunch", "supper", "meal", "place to eat", "where to eat",
        "recommend", "recommendation", "recommendations"
    ]

    cuisine_words = [
        "chinese", "japanese", "korean", "thai", "italian", "french", "mexican",
        "indian", "sushi", "noodle", "ramen", "dim sum", "pizza", "burger",
        "steakhouse", "cafe", "coffee", "bakery"
    ]

    return any(w in q for w in (restaurant_words + cuisine_words))



#Candidate filtering to keep prompt size reasonable

def filter_candidates(user_query: str, max_candidates: int = 40) -> pd.DataFrame:
    """
    Heuristic filter:
    - Match cuisine words in the query to CUISINE_DESCRIPTION.
    - Narrow by ZIP codes based on location keywords.
    - Limit to max_candidates rows.
    Always returns a DataFrame (never None).
    """
    q = user_query.lower()
    candidates = df.copy()

    # --- 1) Cuisine filter based on cuisine description ---
    cuisine_mask = pd.Series(False, index=candidates.index)

    for cuisine in candidates["CUISINE_DESCRIPTION"].unique():
        c_low = str(cuisine).lower()
        # crude match: if cuisine name (or first token) appears in query
        if c_low.split("/")[0] in q or c_low in q:
            cuisine_mask |= (candidates["CUISINE_DESCRIPTION"] == cuisine)

    if cuisine_mask.any():
        candidates = candidates[cuisine_mask]

    # --- 2) Location filter by ZIP code keywords ---
    zip_by_keyword = {
        # Times Square area
        "times square": ["10036", "10018", "10019"],
        "time square":  ["10036", "10018", "10019"],

        # Midtown West
        "midtown west":   ["10018", "10019", "10036"],
        "hell's kitchen": ["10018", "10019", "10036"],
        "hells kitchen":  ["10018", "10019", "10036"],
        "theater district": ["10018", "10019", "10036"],

        # Midtown East
        "midtown east":   ["10016", "10017", "10022"],
        "grand central":  ["10016", "10017", "10022"],
        "united nations": ["10017", "10022"],

        # Generic "midtown" = east + west
        "midtown": ["10016", "10017", "10018", "10019", "10022", "10036"],

        # Columbia University / Morningside Heights / UWS
        "columbia university": ["10027", "10025"],
        "morningside heights": ["10027", "10025"],
        "upper west side":     ["10023", "10024", "10025"],
        "uws":                 ["10023", "10024", "10025"],
    }

    zip_mask = pd.Series(True, index=candidates.index)
    for keyword, zips in zip_by_keyword.items():
        if keyword in q:
            zip_mask = candidates["ZIPCODE"].isin(zips)
            break

    candidates = candidates[zip_mask]

    # --- 3) Fallback if over-filtered ---
    if candidates.empty:
        candidates = df.copy()

    # --- 4) Limit candidate count ---
    if len(candidates) > max_candidates:
        candidates = candidates.sample(max_candidates, random_state=42)

    return candidates

# pompt builder

def build_prompt(user_query: str, candidates: pd.DataFrame) -> str:
    """
    Build a prompt that:
    - Explains the task
    - Provides structured restaurant info
    - Asks for exactly top 5 recommendations
    """
    lines = []

    lines.append("You are a restaurant recommendation assistant for Manhattan, NYC.")
    lines.append("You will receive:")
    lines.append("1) A user request (location, cuisine, preferences).")
    lines.append("2) A list of candidate restaurants from a Manhattan dataset.")
    lines.append("")
    lines.append("Your job:")
    lines.append("- Pick the BEST 5 restaurants for the user.")
    lines.append("- Prefer candidates that match the location and cuisine hints.")
    lines.append("- If multiple match, prioritize good variety and interesting options.")
    lines.append("- If the list has fewer than 5, recommend as many as possible.")
    lines.append("")
    lines.append("User request:")
    lines.append(user_query)
    lines.append("")
    lines.append("Here are the candidate restaurants (each with an ID):")

    # candidates has already been reset_index in recommend_restaurants
    for i, row in candidates.iterrows():
        address = f"{row['BUILDING']} {row['STREET']}, Manhattan, NY {row['ZIPCODE']}"
        line = (
            f"- ID {i}: {row['RESTAURANT']} | "
            f"Cuisine: {row['CUISINE_DESCRIPTION']} | "
            f"Address: {address} | "
            f"InspectionFlag: {row['CRITICALFLAG']}"
        )
        lines.append(line)

    lines.append("")
    lines.append(
        "Please answer in this JSON-like format (no extra commentary, "
        "no explanations outside the JSON array):\n"
        "[\n"
        "  {\n"
        '    \"id\": <candidate ID>,\n'
        '    \"name\": \"<restaurant name>\",\n'
        '    \"why\": \"<1-2 sentence explanation>\",\n'
        '    \"address\": \"<address string>\"\n'
        "  },\n"
        "  ... up to 5 entries total ...\n"
        "]"
    )

    return "\n".join(lines)


# call local model

def call_ollama_chat(prompt: str) -> str:
    """
    Call Ollama chat endpoint with gemma3:12b.
    Make sure `ollama serve` is running locally.
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful restaurant recommendation assistant."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,  
    }

    resp = requests.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]




# Parse JSON-like model output


def parse_llm_json(response: str):
    """
    Try to extract a JSON array from the model output.
    Handles cases like ```json ... ``` or extra text.
    """
    s = response.strip()

    if s.startswith("```"):
        first_newline = s.find("\n")
        if first_newline != -1:
            s_inner = s[first_newline + 1 :]
            end_fence = s_inner.rfind("```")
            if end_fence != -1:
                s_inner = s_inner[:end_fence]
            s = s_inner.strip()

    # Try direct JSON parse
    try:
        return json.loads(s)
    except Exception:
        # Fallback: try from first '[' to last ']'
        start = s.find("[")
        end = s.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                return None
        return None


# clean output format

def print_pretty_recommendations(items, candidates: pd.DataFrame):
    """
    items: list of dicts from LLM (id, name, why, address, ...)
    candidates: DataFrame with reset_index 0..N-1
    """
    if not isinstance(items, list) or len(items) == 0:
        print("I couldn't parse any recommendations from the model output.")
        return

    print("Great, here are the top 5 recommended restaurants:\n")

    for item in items[:5]:
        # Get candidate ID safely
        try:
            rid = int(item.get("id"))
        except Exception:
            continue

        if not (0 <= rid < len(candidates)):
            continue

        row = candidates.iloc[rid]

        name = item.get("name", row["RESTAURANT"])
        address = f"{row['BUILDING']} {row['STREET']}, Manhattan, NY {row['ZIPCODE']}"
        phone = row["PHONE"]

        critical_flag = row["CRITICALFLAG"].strip().lower()
        if critical_flag.startswith("critical"):
            warning = "⚠️ Food safety notice: This restaurant has a CRITICAL violation flag."
        else:
            warning = "No critical food safety violations flagged in the latest record."

        print(f"{name}:")
        print(f"  Address: {address}")
        print(f"  Phone: {phone}")
        print(f"  Warning: {warning}")
        print()  # blank line between restaurants


# Main recommendation function

def recommend_restaurants(user_query: str, max_candidates: int = 40):
    if not looks_like_restaurant_query(user_query):
        print(
            "It looks like your message may not be a restaurant recommendation request.\n"
            "Please provide more details like where you are in Manhattan and what kind of food you want.\n"
            "For example:\n"
            "  - \"I'm near Times Square and want some Chinese food\"\n"
            "  - \"I'm in SoHo looking for a casual Italian restaurant\"\n"
        )
        return

    candidates = filter_candidates(user_query, max_candidates=max_candidates)
    candidates = candidates.reset_index(drop=True)
    prompt = build_prompt(user_query, candidates)
    raw_response = call_ollama_chat(prompt)
    items = parse_llm_json(raw_response)

    print_pretty_recommendations(items, candidates)


if __name__ == "__main__":
    user_query = input("Tell me what you're looking for (location + cuisine/preferences):\n> ")
    recommend_restaurants(user_query)
