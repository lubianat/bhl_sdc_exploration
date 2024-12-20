import re
import requests
import click
from tqdm import tqdm
from SPARQLWrapper import SPARQLWrapper, JSON

# Base URLs
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Initialize logs and outputs
quickstatements_1 = []
quickstatements_2 = []
manual_log = []
log_2_files = []

# Fetch subcategories from Commons
def get_subcategories(category, verbose=False):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "subcat",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    subcategories = [cat["title"] for cat in response.get("query", {}).get("categorymembers", [])]
    if verbose:
        print(f"Found {len(subcategories)} subcategories under {category}.")
    # Remove Category: prefix
    subcategories = [sub.replace("Category:", "") for sub in subcategories]
    return subcategories

# Get file count for a category
def get_file_count(category, verbose=False):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    files = response.get("query", {}).get("categorymembers", [])
    if verbose:
        print(f"Found {len(files)} files in {category}.")
    return len(files)

# Fetch Wikidata item by taxon name
def fetch_wikidata_item(taxon_name, verbose=False):
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
        if verbose:
            print(f"Found Wikidata item for {taxon_name}: {item['id']}.")
        return item["id"]
    if verbose:
        print(f"No Wikidata item found for {taxon_name}.")
    return None

# Fetch file names from a category
def get_files_in_category(category, verbose=False):
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": "max",
    }
    response = requests.get(COMMONS_API, params=params).json()
    files = [file["title"].replace("File:", "") for file in response.get("query", {}).get("categorymembers", [])]
    if verbose:
        print(f"Found {len(files)} files in {category}: {files}")
    return files

# Fetch M-ID for a file on Wikimedia Commons
def fetch_m_id(filename, verbose=False):
    params = {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
    }
    response = requests.get(COMMONS_API, params=params).json()
    pages = response.get("query", {}).get("pages", {})
    for page_id, page_data in pages.items():
        if "pageid" in page_data:
            m_id = f"M{page_data['pageid']}"
            if verbose:
                print(f"Found M-ID for {filename}: {m_id}.")
            return m_id
    if verbose:
        print(f"No M-ID found for {filename}.")
    return None

# Check for P18 (image) values in batch
def check_missing_p18(wikidata_ids, verbose=False):
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
    if verbose:
        print(f"Missing P18 for {len(missing_p18)} items: {missing_p18}.")
    return missing_p18

@click.command()
@click.argument('category')
@click.option('--verbose', is_flag=True, help='Enable verbose output for debugging.')
def process_category(category, verbose):
    """CLI tool to process Wikimedia Commons categories recursively."""
    print(f"Processing category: {category}")

    # Initialize progress trackers
    wikidata_ids = []
    commons_quickstatements = []
    p18_quickstatements = []

    # Fetch subcategories recursively
    genera = get_subcategories(category, verbose=verbose)
    if verbose:
        print(f"Top-level category has {len(genera)} subcategories.")

    for genus in tqdm(genera, desc="Processing genera"):
        if "Unidentified" in genus:
            continue
        taxa = get_subcategories(genus, verbose=verbose)
        if genus == "Aphelandra - botanical illustrations":
            break
        for taxon in tqdm(taxa, desc=f"Processing taxa in {genus}", leave=False):
            match = re.match(r"([^\\-]+) - botanical illustrations", taxon)
            if not match:
                if verbose:
                    print(f"Skipping taxon {taxon}: no match for regex.")
                continue

            species_name = match.group(1)
            file_count = get_file_count(taxon, verbose=verbose)

            wikidata_item = fetch_wikidata_item(species_name, verbose=verbose)
            if wikidata_item:
                wikidata_ids.append(wikidata_item)

            files = get_files_in_category(taxon, verbose=verbose)
            if files:
                for file in files:
                    m_id = fetch_m_id(file, verbose=verbose)
                    if m_id:
                        commons_quickstatements.append(
                            f"{m_id}\tP180\t{wikidata_item}\tS887\tQ131478853\n"
                        )

                # Add P18 if missing
                if wikidata_item in check_missing_p18([wikidata_item], verbose=verbose) and file_count == 1:
                    p18_quickstatements.append(
                        f"{wikidata_item}\tP18\t\"{files[0]}\"\tS887\tQ131478853\n"
                    )

    # Save outputs
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
                log_2_files.append(taxon)
            else:
                manual_log.append("https://commons.wikimedia.org/wiki/" + taxon + "\n")

    # Save outputs
    with open("commons_quickstatements.txt", "w") as f:
        for statement in commons_quickstatements:
            f.write(statement)

    with open("p18_quickstatements.txt", "w") as f:
        for statement in p18_quickstatements:
            f.write(statement)

    with open("quickstatements_1.txt", "w") as f:
        f.writelines(quickstatements_1)

    with open("quickstatements_2.txt", "w") as f:
        f.writelines(quickstatements_2)

    with open("manual_log.txt", "w") as f:
        f.writelines(manual_log)

    with open("log_2_files.txt", "w") as f:
        f.writelines(log_2_files)

    print("Processing complete. Outputs saved.")

if __name__ == '__main__':
    process_category()
