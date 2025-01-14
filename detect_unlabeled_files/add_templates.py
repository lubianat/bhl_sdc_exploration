#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pywikibot
import yaml
import sys
import os
import pathlib
HERE = pathlib.Path(__file__).parent

TEMPLATE = "{{Biodiversity Heritage Library}}"

def add_bhl_template_if_missing(page_title, site):
    """
    Given the exact file page title on Wikimedia Commons, 
    check if the template is present. If not, insert it 
    before the first [[Category: statement.
    """
    page = pywikibot.Page(site, page_title)
    old_text = page.text
    
    # 1) Check if the template is already present
    if TEMPLATE in old_text:
        print(f"Skipping {page_title} because template is already present.")
        return
    
    # 2) Find the first occurrence of [[Category:
    category_index = old_text.find("[[Category:")
    
    if category_index == -1:
        # No category found, we can decide to append at the end
        new_text = old_text.rstrip() + "\n" + TEMPLATE + "\n"
    else:
        # Insert the template right before the first [[Category:
        new_text = (old_text[:category_index] +
                    TEMPLATE + "\n" +
                    old_text[category_index:])
    
    # 3) Save only if there's a change
    if new_text != old_text:
        page.text = new_text
        try:
            page.save(summary=f"Bot: Adding {TEMPLATE} before first category.")
            print(f"Successfully edited {page_title}.")
        except pywikibot.exceptions.PageSaveRelatedError as e:
            print(f"Error saving {page_title}: {e}")

def main():
    # Make sure we have pywikibot configured for Wikimedia Commons
    site = pywikibot.Site('commons', 'commons')
    # Path to your YAML file"./biodivlibrary_results.yaml"
    yaml_file = HERE / "biodivlibrary_results.yaml"
    
    if not os.path.isfile(yaml_file):
        print(f"Error: YAML file '{yaml_file}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Load the YAML data
    with open(yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Iterate through each item in the YAML
    for item in data:
        # e.g. 'title': 'File:The Mammals of Australia scan ...'
        page_title = item.get("title")
        if not page_title:
            print("Warning: No 'title' found in item, skipping.")
            continue
        
        add_bhl_template_if_missing(page_title, site)

if __name__ == "__main__":
    main()
