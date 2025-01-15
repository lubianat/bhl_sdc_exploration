import csv
import random
import logging

from wikibaseintegrator import wbi_login, WikibaseIntegrator, wbi_enums
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator import datatypes
from wikibaseintegrator.models import Qualifiers, References, Reference

# Data type helpers
from wikibaseintegrator.datatypes import (
    Item,
    ExternalID,
    Time
)
from login import *
import requests

# -------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------
# Point these at Wikimedia Commons if needed:
wbi_config['MEDIAWIKI_API_URL'] = 'https://commons.wikimedia.org/w/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://query.wikidata.org/sparql'
wbi_config['WIKIBASE_URL'] = 'https://commons.wikimedia.org'

# Set a custom user agent (important if editing Wikimedia projects)
wbi_config['USER_AGENT'] = 'TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana)'


def generate_custom_edit_summary():
    # As per https://www.wikidata.org/wiki/Wikidata:Edit_groups/Adding_a_tool
    random_hex = f"{random.randrange(0, 2**48):x}"
    return f"SDC import (BHL Model v0.1.1, manual curation) ([[:toolforge:editgroups-commons/b/CB/{random_hex}|details]])"

def get_media_info_id(file_name):
    """
    Extract the MediaInfo ID (M-ID) for a given Wikimedia Commons file name.

    Args:
        file_name (str): The name of the file on Wikimedia Commons.

    Returns:
        str: The MediaInfo ID (e.g., 'M12345') if found, or an error message.
    """
    # Base URL for MediaWiki API
    API_URL = "https://commons.wikimedia.org/w/api.php"

    if "File:" in file_name:
        file_name = file_name.replace("File:", "")
    # Prepare the request parameters
    params = {
        "action": "query",
        "titles": f"File:{file_name}",
        "prop": "info",
        "format": "json"
    }

    try:
        # Make the API request
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # Extract the page data
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return "Error: No page data found for the file."

        # Get the first (and only) page in the response
        page = next(iter(pages.values()))

        # Extract the MediaInfo ID using the pageid
        if "pageid" in page:
            media_info_id = f"M{page['pageid']}"
            return media_info_id
        else:
            return "Error: MediaInfo ID could not be found for the file."

    except requests.RequestException as e:
        return f"Error: API request failed. {e}"

def main(csv_path):
    # Set up logging for debug
    logging.basicConfig(level=logging.INFO)

    # 1) Login
    login_instance = wbi_login.Login(
        user=USERNAME,
        password=PASSWORD,
        mediawiki_api_url=wbi_config['MEDIAWIKI_API_URL']
    )
    wbi = WikibaseIntegrator(login=login_instance)

    edit_summary = generate_custom_edit_summary() 
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            file_name = row.get("File", "").strip()  # e.g. "Example.jpg"
            if not file_name:
                logging.warning("Skipping row with empty 'File' column.")
                continue
        
            try:
                data = get_media_info_id(file_name)
                mediainfo_id = data
                media = wbi.mediainfo.get(entity_id=mediainfo_id)
            except Exception as e:
                logging.error(f"Could not load MediaInfo for File:{file_name}: {e}")
                continue

            # We'll store all new statements in a list, then media.claims.add(...) them.
            new_statements = []

            # 3) Build statements from columns

            # P31 = instance of
            instance_of = row.get("Instance of", "").strip()
            if instance_of:
                claim_instance_of = Item(
                    prop_nr="P31",
                    value=instance_of
                )
                new_statements.append(claim_instance_of)

            # P1433 = published in
            published_in = row.get("Published In", "").strip()
            if published_in:
                # with qualifier P518 = Q112134971
                qual_p518 = datatypes.Item(
                    prop_nr="P518",
                    value="Q112134971"  # "analog work"
                )
                qualifiers = Qualifiers()
                qualifiers.add(qual_p518)

                claim_published_in = Item(
                    prop_nr="P1433",
                    value=published_in,
                    qualifiers=qualifiers
                )
                new_statements.append(claim_published_in)

            # P195 = collection
            institutions_dict = {
                "Smithsonian Libraries and Archives": "Q1609326",
                "Smithsonian Institution": "Q131626"
            }
            collection = row.get("Collection", "").strip()
            if collection:
                if collection in institutions_dict:
                    collection = institutions_dict[collection]
                # qualifier P3831 = Q131597993 (holding institution)
                qual_p3831 = datatypes.Item(
                    prop_nr="P3831",
                    value="Q131597993"  # "holding institution"
                )
                qualifiers = Qualifiers()
                qualifiers.add(qual_p3831)

                # reference: P854 = row["Bibliography ID"]
                bib_id = row.get("Bibliography ID", "").strip()
                references = References()
                if bib_id:
                    ref_obj = Reference()
                    ref_obj.add(datatypes.URL(prop_nr="P854", value=bib_id))
                    references.add(ref_obj)

                claim_collection = Item(
                    prop_nr="P195",
                    value=collection,
                    qualifiers=qualifiers,
                    references=references
                )
                new_statements.append(claim_collection)

            # P859 = sponsor
            sponsor = row.get("Sponsor", "").strip()
            if sponsor:
                if sponsor in institutions_dict:
                    sponsor = institutions_dict[sponsor]

                qual_p3831 = datatypes.Item(
                    prop_nr="P3831",
                    value="Q131344184"  # digitization sponsor
                )
                qualifiers = Qualifiers()
                qualifiers.add(qual_p3831)

                references = References()
                bib_id = row.get("Bibliography ID", "").strip()


                if bib_id:
                    ref_obj = Reference()
                    ref_obj.add(datatypes.URL(prop_nr="P854", value=bib_id))
                    references.add(ref_obj)

                claim_sponsor = Item(
                    prop_nr="P859",
                    value=sponsor,
                    qualifiers=qualifiers,

                    references=references
                )
                new_statements.append(claim_sponsor)

            # P687 = BHL page ID (external-id)
            bhl_page_id = row.get("BHL Page ID", "").strip()
            if bhl_page_id:
                claim_bhl = ExternalID(
                    prop_nr="P687",
                    value=bhl_page_id
                )
                new_statements.append(claim_bhl)

            # P170 = creator (illustrator)
            illustrator = row.get("Illustrator", "").strip()
            if illustrator:
                qual_p3831 = datatypes.Item(
                    prop_nr="P3831",
                    value="Q644687"  # "illustrator"
                )
                qual_p518 = datatypes.Item(
                    prop_nr="P518",
                    value="Q112134971"  # "analog work"
                )
                qualifiers = Qualifiers()
                qualifiers.add(qual_p518)
                qualifiers.add(qual_p3831)

                claim_creator = Item(
                    prop_nr="P170",
                    value=illustrator,
                    qualifiers=qualifiers
                )
                new_statements.append(claim_creator)

            # P571 = inception (time)
            # plus qualifiers P1480 = Q110290992 ("no later than") and P518 = Q112134971
            # references: P887 = Q110393725 ("inferred from publication date")
            inception_str = row.get("Inception", "").strip()
            if inception_str:
                # Inception is a year, e.g., "1900"
                # 9 is the precision for year
                formatted_string = f"+{inception_str}-01-01T00:00:00Z"
                claim_inception = Time(
                    prop_nr="P571",
                    time=formatted_string,
                    precision=wbi_enums.WikibaseTimePrecision.YEAR
                )
                qualifiers = Qualifiers()
                qualifiers.add(
                    datatypes.Item(
                        prop_nr="P1480",
                        value="Q110290992"  # "no later than"
                    )
                )
                qualifiers.add(
                    datatypes.Item(
                        prop_nr="P518",
                        value="Q112134971"  # "analog work"
                    )
                )
                claim_inception.qualifiers = qualifiers

                # reference: P887 = Q110393725 ("inferred from publication date")
                references = References()
                ref_obj = Reference()
                ref_obj.add(
                    datatypes.Item(
                        prop_nr="P887",
                        value="Q110393725"
                    )
                )
                references.add(ref_obj)

                claim_inception.references = references
                new_statements.append(claim_inception)

            # 4) Add new statements to the media info entity
            if new_statements:
                media.claims.add(new_statements)
                # 5) Write to Commons with a custom edit summary (including an EditGroups link)
                try:
                    media.write(summary=edit_summary)
                    logging.info(f"Successfully updated {file_name} with SDC data.")
                except Exception as e:
                    logging.error(f"Failed to write SDC for {file_name}: {e}")
            else:
                logging.info(f"No SDC data to add for {file_name}, skipping...")


if __name__ == "__main__":
    main("/home/lubianat/Documents/wiki_related/bhl_sdc_exploration/reconciliation_bot/test2.tsv")
