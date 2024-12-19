import re
import requests
import csv
from bs4 import BeautifulSoup
from SPARQLWrapper import SPARQLWrapper, JSON

# Base URLs
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
# SPARQL endpoint for querying Wikidata
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Initialize logs and outputs
quickstatements_1 = []
quickstatements_2 = []
manual_log = []
log_2_files = []

# Fetch subcategories from Commons
category = "Acanthus_-_botanical_illustrations"
def get_subcategories(category):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "subcat",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    return [cat["title"] for cat in response.get("query", {}).get("categorymembers", [])]

# Get file count for a category
def get_file_count(category):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "file",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    files = response.get("query", {}).get("categorymembers", [])
    return len(files)

# Fetch Wikidata item by taxon name
def fetch_wikidata_item(taxon_name):
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "search": taxon_name,
        "language": "en",
        "type": "item",
        "props": "descriptions|aliases",
    }
    response = requests.get(WIKIDATA_API, params=params).json()
    for item in response.get("search", []):
        return item["id"]
    return None

# Generate QuickStatements
# Fetch file names from a category
def get_files_in_category(category):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "file",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    files = response.get("query", {}).get("categorymembers", [])
    return [file["title"].replace("File:", "") for file in files]

# Processing subcategories
subcategories = get_subcategories(category)
# Fetch M-ID for a file on Wikimedia Commons
def fetch_m_id(filename):
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
    }
    response = requests.get(COMMONS_API, params=params).json()
    pages = response.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        if "pageid" in page_data:
            return f"M{page_data['pageid']}"
    return None



# Check for P18 (image) values in batch
def check_missing_p18(wikidata_ids):
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    ids_str = " ".join(f"wd:{qid}" for qid in wikidata_ids)
    query = f"""
    SELECT ?item WHERE {{
        VALUES ?item {{ {ids_str} }}
        FILTER NOT EXISTS {{ ?item wdt:P18 ?image }}
    }}
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    missing_p18 = set()
    for result in results["results"]["bindings"]:
        missing_p18.add(result["item"]["value"].split("/")[-1])  # Extract QID
    return missing_p18

# Processing subcategories
wikidata_ids = []
subcategories = get_subcategories(category)
for subcat in subcategories:
    match = re.match(r"Category:(Saurauia [^\\-]+) - botanical illustrations", subcat)
    if not match:
        continue

    species_name = match.group(1)
    file_count = get_file_count(subcat)

    wikidata_item = fetch_wikidata_item(species_name)
    if wikidata_item:
        wikidata_ids.append(wikidata_item)

# Check which items are missing P18
missing_p18_ids = check_missing_p18(wikidata_ids)

# Extend QuickStatements generation
commons_quickstatements = []
p18_quickstatements = []

for subcat in subcategories:
    match = re.match(r"Category:([^\\-]+) - botanical illustrations", subcat)
    if not match:
        continue

    species_name = match.group(1)
    file_count = get_file_count(subcat)

    wikidata_item = fetch_wikidata_item(species_name)
    if not wikidata_item:
        continue

    files = get_files_in_category(subcat)
    if files:
        for file in files:
            m_id = fetch_m_id(file)
            if m_id:
                # Create QuickStatements for Commons structured data
                commons_quickstatements.append(
                    f"{m_id}\tP180\t{wikidata_item}\tS887\tQ131478853\n"
                )

        # Add P18 if missing
        if wikidata_item in missing_p18_ids and file_count == 1:
            p18_quickstatements.append(
                f"{wikidata_item}\tP18\t\"{files[0]}\"\n"
            )

    # Handle QuickStatements for Wikidata reference illustration
    if file_count == 1 and files:
        quickstatements_1.append(
            f"{wikidata_item}\tP13162\t\"{files[0]}\"\tS887\tQ131478853\n"
        )
    elif file_count == 2 and files:
        quickstatements_2.append(
            f"{wikidata_item}\tP13162\t\"{files[0]}\"\tS887\tQ131478853\n"
            f"{wikidata_item}\tP13162\t\"{files[1]}\"\tS887\tQ131478853\n"
        )
        log_2_files.append(subcat)
    else:
        manual_log.append("https://commons.wikimedia.org/wiki/" + subcat+"\n")

# Save QuickStatements for Wikimedia Commons
with open("commons_quickstatements.txt", "w") as f:
    for statement in commons_quickstatements:
        f.write(statement)

# Save QuickStatements for P18
with open("p18_quickstatements.txt", "w") as f:
    for statement in p18_quickstatements:
        f.write(statement)

# Save other QuickStatements and logs
with open("quickstatements_1.txt", "w") as f:
    f.writelines(quickstatements_1)

with open("quickstatements_2.txt", "w") as f:
    f.writelines(quickstatements_2)

with open("manual_log.txt", "w") as f:
    f.writelines(manual_log)

with open("log_2_files.txt", "w") as f:
    f.writelines(log_2_files)

print("Processing complete. Outputs saved.")
