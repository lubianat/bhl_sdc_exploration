import requests
import re
from tqdm import tqdm
from html import unescape
import os
import yaml
import urllib.parse
import time  # For adding a slight delay between requests

# Adjust as needed for politeness
REQUEST_DELAY = 0.1  # seconds

# Identify your script/tool so Wikimedia ops can see who is making requests
HEADERS = {
    "User-Agent": "MyBHLSearchBot/1.0 (tiagolubiana@gmail.com)"
}

CONTINUE_CACHE_FILE = "continue_cache.yaml"                         

def fetch_and_filter_files(base_url,
                           bhl_output_file="biodivlibrary_results.yaml",
                           non_bhl_output_file="non_bhl_results.yaml"):
    """
    Fetch and filter files from Commons search results.

    :param base_url: Full query URL (endpoint + query parameters)
    :param bhl_output_file: Path for storing files that match the BHL pattern
    :param non_bhl_output_file: Path for storing files that do NOT match
    :return: A tuple (bhl_results, non_bhl_results)
    """

    # Dictionary to store continuation parameters for *this* run
    continue_params = {}

    # We'll keep two separate lists for results:
    # 1. BHL matches
    # 2. Non-BHL (false positives)
    bhl_results = []
    non_bhl_results = []
    
    has_more_results = True
    processed_count = 0  # How many pages have we processed so far?
    pbar = None          # We'll create this after first response (when we know totalhits)

    # If an output file already exists for BHL, load previously saved matches
    if os.path.exists(bhl_output_file):
        with open(bhl_output_file, "r") as f:
            existing_data = yaml.safe_load(f)
            if existing_data:
                bhl_results = existing_data

    # If an output file already exists for NON-BHL, load previously saved false positives
    if os.path.exists(non_bhl_output_file):
        with open(non_bhl_output_file, "r") as f:
            existing_data = yaml.safe_load(f)
            if existing_data:
                non_bhl_results = existing_data

    while has_more_results:
        # Build query parameters for the request, merging in continue_params

        query_params = {}
        for k, v in continue_params.items():
            if k != "continue":
                query_params[k] = v

        # Make the request (with custom headers!)
        response = requests.get(base_url, params=query_params, headers=HEADERS)
        
        # Polite delay to avoid hammering the API
        time.sleep(REQUEST_DELAY)
        
        if response.status_code != 200:
            print("Error fetching data:", response.status_code)
            break
        
        data = response.json()

        # Initialize the progress bar once, using 'totalhits' (if provided)
        if pbar is None:
            totalhits = data.get("query", {}).get("searchinfo", {}).get("totalhits") or 0
            pbar = tqdm(total=totalhits, desc="Processing all pages", unit="page")

        # Get pages from the response
        pages = data.get("query", {}).get("pages", {})
        for page_id, file_data in pages.items():
            snippet = file_data.get("snippet", "")
            # Clean up HTML in the snippet
            snippet = unescape(re.sub(r"<.*?>", "", snippet))
            title = file_data.get("title")
            # Check if "biodiversitylibrary.org" or "biodivlibrary" is in the snippet or in the title
            # or if https://doi.org/10.5962/bhl.title or  "61021753@N02" (the flickr id) 
            # or "Biodiversity  Heritage Library Flickr" or "This work is from the Biodiversity Heritage Library"
            # or "BHL Collection" or "author name string: Biodiversity Heritage Library"
            # or "DescriptionHortus Eystettensis" (a particular book in BHL)
            if (re.search(r"\bbiodiversitylibrary\.org\b", snippet, re.IGNORECASE) or
                re.search(r"\bbiodivlibrary\b", snippet, re.IGNORECASE) or
                re.search(r"https://doi\.org/10\.5962/bhl\.title", snippet, re.IGNORECASE) or
                re.search(r"61021753@N02", snippet, re.IGNORECASE) or
                re.search(r"Biodiversity  Heritage Library Flickr", snippet, re.IGNORECASE) or
                re.search(r"This work is from the Biodiversity Heritage Library", snippet, re.IGNORECASE) or
                re.search(r"BHL Collection", snippet, re.IGNORECASE) or
                re.search(r"author name string: Biodiversity Heritage", snippet, re.IGNORECASE) or
                re.search(r"DescriptionHortus Eystettensis", snippet, re.IGNORECASE) or
                re.search(r"\bbiodiversitylibrary\.org\b", title, re.IGNORECASE) or
                re.search(r"\bbiodivlibrary\b", title, re.IGNORECASE) or
                re.search(r"https://doi\.org/10\.5962/bhl\.title", title, re.IGNORECASE) or
                re.search(r"61021753@N02", title, re.IGNORECASE)):
                
                
                # This is a BHL match
                encoded_title = urllib.parse.quote(file_data.get("title"))
                bhl_results.append({
                    "title": file_data.get("title"),
                    "snippet": snippet,
                    "commons_url": f"https://commons.wikimedia.org/wiki/{encoded_title}"
                })
            else:
                # This is a NON-BHL (false positive)
                encoded_title = urllib.parse.quote(file_data.get("title"))
                non_bhl_results.append({
                    "title": file_data.get("title"),
                    "snippet": snippet,
                    "commons_url": f"https://commons.wikimedia.org/wiki/{encoded_title}"
                })

            processed_count += 1
            # Update the overall progress bar by 1
            if pbar:
                pbar.update(1)

        # Save current progress to both files
        with open(bhl_output_file, "w") as f:
            yaml.dump(bhl_results, f, default_flow_style=False)

        with open(non_bhl_output_file, "w") as f:
            yaml.dump(non_bhl_results, f, default_flow_style=False)

        # Check if there's a 'continue' field in the response
        if "continue" in data:
            next_cont = data["continue"]
            cont_tuple = tuple(sorted(next_cont.items()))
            # Debug: print the new continuation data
            print(f"DEBUG: new continue params: {next_cont}")

            # Actually update the continue_params so the next loop will request the new batch
            continue_params = next_cont
        else:
            has_more_results = False

        # Check for 'batchcomplete'
        if "batchcomplete" in data:
            print("Batch complete. (No more properties for this batch.)")

    # Close the progress bar
    if pbar:
        pbar.close()

    print(f"\nProcessing complete.")
    print(f"- BHL matches found: {len(bhl_results)}")
    print(f"- Non-BHL (false positives): {len(non_bhl_results)}")
    print(f"- Pages scanned: {processed_count}")

    return bhl_results, non_bhl_results


# Example usage:
base_api_url = (
    "https://commons.wikimedia.org/w/api.php?"
    "action=query&format=json&uselang=en&generator=search&gsrsearch="
    "filetype%3Abitmap|drawing%20-fileres%3A0%20biodiversitylibrary.org%20"
    "-incategory%3A%22Files%20from%20the%20Biodiversity%20Heritage%20Library%22%20"
    "-incategory%3A%22Biodiversity%20Heritage%20Library%22%20"
    "&gsrlimit=50&gsrinfo=totalhits|suggestion&gsrprop=size|wordcount|timestamp|snippet"
    "&prop=info|imageinfo|entityterms&inprop=url&gsrnamespace=6&iiprop=url|size|mime"
    "&iiurlheight=180&wbetterms=label"
)

output_file_path_bhl = "biodivlibrary_results.yaml"
output_file_path_non_bhl = "non_bhl_results.yaml"

# Now fetch and filter files
bhl_files, non_bhl_files = fetch_and_filter_files(
    base_api_url,
    bhl_output_file=output_file_path_bhl,
    non_bhl_output_file=output_file_path_non_bhl
)