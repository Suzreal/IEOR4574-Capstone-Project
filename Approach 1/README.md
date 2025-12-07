# IEOR4574-Capstone-Project


AI Engineering Capstone - NYC Restaurant Recommendation on Ollama Local Model.


Please run the following line in the terminal:

**The environment needs around 10GB of storage to create as it required the installation of local LLM**

-   Install Ollama from the official installer, then

    - `ollama serve`

    - `ollama pull gemma3:12b`

- Required python package: 

    - `pandas>=2.0.0`
    - `requests>=2.31.0`



`
Please run python ollama_model.py
`

- This might takes around 30s-1min to run.



Dataset origin: https://data.cityofnewyork.us/Health/restaurant-data-set-2/f6tk-2b7a/about_data

Dataset contains the following column after cleaning:
-   ‘CAMIS': unique identifier of each restaurant 
-   'RESTAURANT': restaurant name
-   'BUILDING', 'STREET', 'ZIPCODE': the 3 columns contain address information
-   'PHONE': phone number
-   'CUISINE_DESCRIPTION': cuisine genres
-   'CRITICALFLAG': if this restaurant is in a critical food safety condition




Example output:

Prompt: `Please give me some restaurant recommendation near Chinatown`

`NOM WAH TEA, DIM SUM PARLOR:
  Address: 13 DOYERS STREET, Manhattan, NY 10013
  Phone: 2129626047
  Warning: ⚠️ Food safety notice: This restaurant has a CRITICAL violation flag.

CAFE EVERGREEN:
  Address: 1367 1 AVENUE, Manhattan, NY 10021
  Phone: 2127443266
  Warning: No critical food safety violations flagged in the latest record.

ROYAL SEAFOOD CAFE:
  Address: 103 MOTT STREET, Manhattan, NY 10013
  Phone: 2129667199
  Warning: No critical food safety violations flagged in the latest record.

SHANGHAI ASIAN CUISINE:
  Address: 14A ELIZABETH STREET, Manhattan, NY 10013
  Phone: 2129645640
  Warning: ⚠️ Food safety notice: This restaurant has a CRITICAL violation flag.

PARISI BAKERY:
  Address: 198 MOTT STREET, Manhattan, NY 10012
  Phone: 2122266378
  Warning: ⚠️ Food safety notice: This restaurant has a CRITICAL violation flag.`


# Issues targeted and solved during the process:

- As showen during presentation, when the location infromation is unclear, the model does not provide good recommendation.

    - The 'CAFE EVERGREEN' above is way far beyond 'walking distance'.
    - Provide a small location zipcode match to LLM so it has better knowledge of what restaurants to recommend
    -`zip_by_keyword =
        "times square": ["10036", "10018", "10019"],
        "time square":  ["10036", "10018", "10019"],
        "midtown west":   ["10018", "10019", "10036"],
        "hell's kitchen": ["10018", "10019", "10036"],
        "hells kitchen":  ["10018", "10019", "10036"],
        "theater district": ["10018", "10019", "10036"],
        "midtown east":   ["10016", "10017", "10022"],
        "grand central":  ["10016", "10017", "10022"],
        "united nations": ["10017", "10022"],
        "midtown": ["10016", "10017", "10018", "10019", "10022", "10036"],
        "columbia university": ["10027", "10025"],
        "morningside heights": ["10027", "10025"],
        "upper west side":     ["10023", "10024", "10025"],
        "uws":                 ["10023", "10024", "10025"]`

- The ambiguous words in prompt will fail the program:

    - Example: miss spellling the word `restaurant`, providing a list of check, and an extra check if the prompt cannot be recognized, LLM will ask the user for a clearer restaurant prompt.
    - `    restaurant_words = [
        "restaurant", "restaur", "resturant", "restruant",
        "food", "eat", "dinner", "lunch", "breakfast",
        "brunch", "supper", "meal", "place to eat", "where to eat",
        "recommend", "recommendation", "recommendations"
    ]`

- So we switched to the updated version(final product)


# Example use

<img width="805" height="630" alt="image" src="https://github.com/user-attachments/assets/65af660c-1875-42a4-a1f1-ab36ef472530" />
