import requests
import re
from pathlib import Path
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm

COMMONS_API_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
BHL_BASE_URL = "https://www.biodiversitylibrary.org"

# Input category
category_name = "Abbildungen zur Naturgeschichte Brasiliens"
category_name = category_name.replace("_", " ").replace("Category:", "").strip()
def get_files_in_category(category_name):
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmtype": "file",
        "cmlimit": "max",
        "format": "json"
    }
    try:
        r = requests.get(COMMONS_API_ENDPOINT, params=params)
        data = r.json()
        files = data.get("query", {}).get("categorymembers", [])
        return [file["title"].replace("File:", "") for file in files]
    except Exception:
        return []

def get_commons_wikitext(filename):
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": "File:" + filename,
        "rvslots": "*",
        "rvprop": "content",
        "formatversion": "2",
        "format": "json"
    }
    try:
        r = requests.get(COMMONS_API_ENDPOINT, params=params)
        data = r.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages or "missing" in pages[0]:
            return ""
        return pages[0]["revisions"][0]["slots"]["main"]["content"]
    except Exception:
        return ""

def parse_bhl_template(wikitext):
    if not wikitext:
        return {field: "" for field in ["pageid", "titleid", "pagetypes", "date", "author", "names"]}
    m = re.search(r'(?s)\{\{BHL\s*\|.*?\}\}', wikitext)
    if not m:
        return {field: "" for field in ["pageid", "titleid", "pagetypes", "date", "author", "names"]}
    bhl_block = m.group(0)
    field_names = ["pageid", "titleid", "pagetypes", "date", "author", "names"]
    results = {}
    for field in field_names:
        regex = r"\|\s*{}\s*=\s*(.*?)\n".format(field)
        fm = re.search(regex, bhl_block)
        if fm:
            value = fm.group(1).strip()
            value = re.sub(r"\}\}.*", "", value).strip()
            if field == "names":
             # Example: | names = NameFound:Dicholophus cristatus NameConfirmed:Dicholophus cristatus  
             # Regex to get the scientific name after NameFound)
                try:
                    value = re.search(r"NameFound:([A-Za-z ]+)NameConfirmed", value).group(1)
                except AttributeError:
                    try:
                     value = re.search(r"NameFound:([A-Za-z ]+)", value).group(1)
                    except AttributeError:
                        value = value
            results[field] = value
        else:
            results[field] = ""
    return results

def find_publication_from_category(category_name):
    query = f"""
    SELECT ?item ?itemLabel ?publicationDate
    WHERE
    {{
      ?item wdt:P373 "{category_name}" .
      ?item wdt:P4327 ?bhl_bib_id .
      OPTIONAL {{ ?item wdt:P577 ?publicationDate. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 1
    """
    try:
        r = requests.get(
            WIKIDATA_SPARQL_ENDPOINT,
            params={'query': query, 'format': 'json'}
        )
        data = r.json()
        results = data.get("results", {}).get("bindings", [])
        if results:
            qid = results[0].get("item", {}).get("value", "").split("/")[-1]
            label = results[0].get("itemLabel", {}).get("value", "")
            publication_date = results[0].get("publicationDate", {}).get("value", "").split("T")[0]
            return qid, label, publication_date
    except Exception:
        pass
    return "", "", ""

def scrape_bhl_details(bhl_url):
    try:
        r = requests.get(bhl_url)
        soup = BeautifulSoup(r.text, "html.parser")
        holding_institution = soup.find("h5", text="Holding Institution:").find_next("p").text.strip()
        sponsor = soup.find("h5", text="Sponsor:").find_next("p").text.strip()
        return holding_institution, sponsor
    except Exception:
        return "", ""

def generate_data(category_name):
    files = get_files_in_category(category_name)
    publication_qid, publication_title, inception_date = find_publication_from_category(category_name)
    rows = []
    
    url_printed = False
    for file in tqdm(files):
        wikitext = get_commons_wikitext(file)
        bhl_data = parse_bhl_template(wikitext)
        instance_of = bhl_data["pagetypes"]
        biblio_id = bhl_data["titleid"]

        if not url_printed:
            bhl_url = f"{BHL_BASE_URL}/bibliography/{biblio_id}"
            print(f"Visit the BHL page for this category: {bhl_url}")
            collection, sponsor = scrape_bhl_details(bhl_url)
            print(f"Detected Collection: {collection}")
            print(f"Detected Sponsor: {sponsor}")
            if not collection or not sponsor:
                collection = input("Enter the Collection (if not auto-detected): ").strip()
                sponsor = input("Enter the Sponsor (if not auto-detected): ").strip()
            illustrator = input("Enter the Illustrator QID: ").strip()
            url_printed = True

        row = {
            "File": file or "",
            "BHL Page ID": bhl_data["pageid"] or "",
            "Instance of": instance_of or "",
            "Published In": publication_title or "",
            "Published In QID": publication_qid or "",
            "Collection": collection or "",
            "Sponsor": sponsor or "",
            "Bibliography ID": biblio_id or "",
            "Illustrator": illustrator or "",
            "Inception": inception_date or "",
            "Names": bhl_data["names"] or "",
        }
        rows.append(row)
    
    return rows

# Main logic
data = generate_data(category_name)
HERE = Path(__file__).parent
output_path = HERE
output_path.mkdir(parents=True, exist_ok=True)
output_file = output_path / f"{category_name.replace(' ', '_')}.tsv"

df = pd.DataFrame(data)
df.to_csv(output_file, sep="\t", index=False)

print(f"Data written to: {output_file}")
