import csv
import logging
from wikibaseintegrator import wbi_login, WikibaseIntegrator, wbi_enums
from wikibaseintegrator.wbi_config import config as wbi_config
from wikibaseintegrator.models import Qualifiers, References, Reference
from wikibaseintegrator.datatypes import (
    Item,
    ExternalID,
    Time,
    URL
)
from login import *
from helper import get_media_info_id, generate_custom_edit_summary

wbi_config['MEDIAWIKI_API_URL'] = 'https://commons.wikimedia.org/w/api.php'
wbi_config['SPARQL_ENDPOINT_URL'] = 'https://query.wikidata.org/sparql'
wbi_config['WIKIBASE_URL'] = 'https://commons.wikimedia.org'

# Set a custom user agent (important if editing Wikimedia projects)
wbi_config['USER_AGENT'] = 'TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana)'

INSTANCE_OF_DICT = {
    "Illustration": "Q178659",
}
INSTITUTIONS_DICT = {
    "Smithsonian Libraries and Archives": "Q1609326",
    "Smithsonian Institution": "Q131626",
    "Missouri Botanical Garden, Peter H. Raven Library": "Q53530601",
    "Missouri Botanical Garden": "Q1852803"
}

TEST=False

def main(csv_path):

    logging.basicConfig(level=logging.INFO)

    login_instance = wbi_login.Login(
        user=USERNAME,
        password=PASSWORD,
        mediawiki_api_url=wbi_config['MEDIAWIKI_API_URL']
    )
    wbi = WikibaseIntegrator(login=login_instance)
    edit_summary = generate_custom_edit_summary(test_edit=TEST) 

    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            file_name = row.get("File", "").strip()
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

            new_statements = []
            add_instance_claim(row, new_statements)
            add_published_in_claim(row, new_statements)
            add_collection_claim(row, new_statements)
            add_digital_sponsor_claim(row, new_statements)
            add_bhl_id_claim(row, new_statements)
            add_illustrator_claim(row, new_statements)
            add_inception_claim(row, new_statements)

            if new_statements:
                media.claims.add(new_statements, action_if_exists= wbi_enums.ActionIfExists.MERGE_REFS_OR_APPEND)
                try:
                    media.write(summary=edit_summary)
                    logging.info(f"Successfully updated {file_name} with SDC data.")
                except Exception as e:
                    logging.error(f"Failed to write SDC for {file_name}: {e}")
            else:
                logging.info(f"No SDC data to add for {file_name}, skipping...")


def add_inception_claim(row, new_statements):
    inception_str = row.get("Inception", "").strip()
    if inception_str:
                # Inception should be a year, e.g., "1900"
                # 9 is the precision for year
        if len(inception_str) != 4:
                    # Get first 4 
            inception_str = inception_str[:4]
        formatted_string = f"+{inception_str}-01-01T00:00:00Z"
        claim_inception = Time(
                    prop_nr="P571",
                    time=formatted_string,
                    precision=wbi_enums.WikibaseTimePrecision.YEAR
                )
        qualifiers = Qualifiers()
        qualifiers.add(
                    Item(
                        prop_nr="P1480",
                        value="Q110290992"  # "no later than"
                    )
                )
        qualifiers.add(
                    Item(
                        prop_nr="P518",
                        value="Q112134971"  # "analog work"
                    )
                )
        claim_inception.qualifiers = qualifiers
                # reference: P887 = Q110393725 ("inferred from publication date")
        references = References()
        ref_obj = Reference()
        ref_obj.add(
                    Item(
                        prop_nr="P887",
                        value="Q110393725"
                    )
                )
        references.add(ref_obj)
        claim_inception.references = references
        new_statements.append(claim_inception)

def add_illustrator_claim(row, new_statements):
    illustrator = row.get("Illustrator", "").strip()
    if illustrator:
        qual_p3831 = Item(
                    prop_nr="P3831",
                    value="Q644687"  # "illustrator"
                )
        qual_p518 = Item(
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

def add_bhl_id_claim(row, new_statements):
    bhl_page_id = row.get("BHL Page ID", "").strip()
    if bhl_page_id:
        claim_bhl = ExternalID(
                    prop_nr="P687",
                    value=bhl_page_id
                )
        new_statements.append(claim_bhl)

def add_digital_sponsor_claim(row, new_statements):
    sponsor = row.get("Sponsor", "").strip()
            
    if sponsor:
        if sponsor in INSTITUTIONS_DICT:
            sponsor = INSTITUTIONS_DICT[sponsor]
        qual_p3831 = Item(
                    prop_nr="P3831",
                    value="Q131344184"  # digitization sponsor
                )
        qualifiers = Qualifiers()
        qualifiers.add(qual_p3831)
        references = References()
        bib_id = row.get("Bibliography ID", "").strip()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"                                        ))
            references.add(ref_obj)
        claim_sponsor = Item(
                    prop_nr="P859",
                    value=sponsor,
                    qualifiers=qualifiers,
                    references=references
                )
        new_statements.append(claim_sponsor)

def add_collection_claim(row, new_statements):
    collection = row.get("Collection", "").strip()
    if collection:
        if collection in INSTITUTIONS_DICT:
            collection = INSTITUTIONS_DICT[collection]
        qual_p3831 = Item(
                    prop_nr="P3831",
                    value="Q131597993"  # "holding institution"
                )
        qualifiers = Qualifiers()
        qualifiers.add(qual_p3831)
        bib_id = row.get("Bibliography ID", "").strip()
        references = References()
        if bib_id:
            ref_obj = Reference()
            ref_obj.add(URL(prop_nr="P854", value=f"https://www.biodiversitylibrary.org/bibliography/{bib_id}"                                        ))
            references.add(ref_obj)

        claim_collection = Item(
                    prop_nr="P195",
                    value=collection,
                    qualifiers=qualifiers,
                    references=references
                )
        new_statements.append(claim_collection)

def add_instance_claim(row, new_statements):
    instance_of = row.get("Instance of", "").strip()
    if instance_of:
        if instance_of in INSTANCE_OF_DICT:
            instance_of = INSTANCE_OF_DICT[instance_of]
        claim_instance_of = Item(
                    prop_nr="P31",
                    value=instance_of
                )
        new_statements.append(claim_instance_of)

def add_published_in_claim(row, new_statements):
    published_in = row.get("Published In QID", "").strip()
    if published_in:
        qual_p518 = Item(
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

if __name__ == "__main__":
    main("/home/lubianat/Documents/wiki_related/bhl_sdc_exploration/reconciliation_bot/Beitrag_zur_Flora_Brasiliens.tsv")
