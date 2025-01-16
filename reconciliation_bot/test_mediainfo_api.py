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
wbi_config['USER_AGENT'] = 'TiagoLubiana (https://meta.wikimedia.org/wiki/User:TiagoLubiana) a'

wbi = WikibaseIntegrator()
media = wbi.mediainfo.get('M16431477')
print(media.claims)
# Retrieve the first "depicts" (P180) claim
print(media.claims.get('P180')[0].mainsnak.datavalue['value']['id'])