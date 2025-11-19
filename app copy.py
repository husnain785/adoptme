import requests
from bs4 import BeautifulSoup
import re
import json
import pandas as pd
import os
import time

# --- Configuration ---
base_url = "https://adoptmetradingvalues.com"
detail_template = f"{base_url}/what-is-worth.php?q=&id="
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
# categories = ['foods', 'gifts', 'houses', 'pets', 'petsneons', 'petsvehicles', 'petwear', 'stickers', 'strollers', 'toys', 'vehicles', 'wings']
categories = ['pets']  # Focusing on pets for this run
json_file_path = 'adoptme_values.json'
csv_file_path = 'adoptme_values.csv'

# --- Step 1: Fetch all unique IDs that need to be scraped ---
print("--- Step 1: Fetching all unique item IDs ---")
id_to_category = {}
all_ids_from_site = set()

for cat in categories:
    list_url = f"{base_url}/pet-value-list.php?params={cat}"
    try:
        resp = requests.get(list_url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        ids_found = set()
        for a in soup.find_all('a', href=re.compile(r'id=\d+')):
            match = re.search(r'id=(\d+)', a.get('href'))
            if match:
                id_str = match.group(1)
                ids_found.add(id_str)
                id_to_category[id_str] = cat
                all_ids_from_site.add(id_str)
        print(f"Found {len(ids_found)} IDs in category '{cat}'")
    except requests.exceptions.RequestException as e:
        print(f"Could not fetch category '{cat}': {e}")

print(f"\nFound a total of {len(all_ids_from_site)} unique IDs on the website.")

# --- Step 2: Load existing data and determine what needs to be scraped ---
print(f"\n--- Step 2: Checking for existing data in '{json_file_path}' ---")

processed_ids = set()
if os.path.exists(json_file_path):
    try:
        with open(json_file_path, 'r') as f:
            existing_data = json.load(f)
        for cat_data in existing_data.values():
            for item_id in cat_data.keys():
                processed_ids.add(item_id)
        print(f"Loaded {len(processed_ids)} previously scraped items. Will skip them.")
    except (json.JSONDecodeError, AttributeError):
        print("Warning: JSON file is corrupted or has an old format. Please delete it and restart.")
else:
    print("No data file found. Starting a new scrape from scratch.")

ids_to_scrape = sorted(list(all_ids_from_site - processed_ids))
print(f"There are {len(ids_to_scrape)} new items to scrape.")

# --- Step 3: Scrape new items and save them one-by-one ---
print("\n--- Step 3: Scraping new items and saving live ---")

if not ids_to_scrape:
    print("Everything is already up-to-date!")
else:
    for id_str in ids_to_scrape:
        time.sleep(0.1)
        url = detail_template + id_str
        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')

            # --- Extract data ---

            # **FIX 1: More robust name scraping**
            # Prioritize <h2>, then <h1>, then <title> as a last resort.
            name_tag = soup.find('h2') or soup.find('h1') or soup.find('title')
            name = name_tag.get_text(strip=True).split(' - ')[0] if name_tag else f"Unknown ID {id_str}"

            # Regex for value is still reliable
            value_match = re.search(r'(\d+(?:\.\d+)?)\s*RP', resp.text)
            value = float(value_match.group(1)) if value_match else 0.0

            # **FIX 2: Scrape data from the table for better accuracy**
            item_type = 'Unknown'
            rarity = 'Unknown'
            origin = 'Unknown'
            
            table = soup.find('table', class_='styled-table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].get_text(strip=True).lower()
                        val = cells[1].get_text(strip=True)
                        if key == 'type':
                            item_type = val
                        elif key == 'rarity':
                            rarity = val
                        elif key == 'origin':
                            # The origin can have extra text after a newline, clean it up
                            origin = val.split('\n')[0]

            image_url = f"{base_url}/images/{id_str}.png"
            cat = id_to_category.get(id_str, 'unknown')

            # --- Read, Modify, and Write ---
            try:
                with open(json_file_path, 'r') as f:
                    all_values = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                all_values = {c: {} for c in categories}
            
            if cat not in all_values:
                all_values[cat] = {}
            
            # **FIX 3: Add the new fields to the saved dictionary**
            all_values[cat][id_str] = {
                'name': name,
                'type': item_type,
                'rarity': rarity,
                'origin': origin,
                'value': value,
                'image_url': image_url
            }

            with open(json_file_path, 'w') as f:
                json.dump(all_values, f, indent=4)
            
            print(f"SAVED: {name} (ID: {id_str})")

        except Exception as e:
            print(f"ERROR on ID {id_str}: {e} - SKIPPING")

# --- Step 4: Generate a final, complete CSV ---
print(f"\n--- Step 4: Generating a complete CSV file at '{csv_file_path}' ---")

try:
    with open(json_file_path, 'r') as f:
        final_data = json.load(f)
    
    data_list = []
    if isinstance(final_data, dict):
        for cat, items in final_data.items():
            for item_id, d in items.items():
                row = d.copy()
                row['id'] = item_id
                row['category'] = cat
                data_list.append(row)

    if data_list:
        df = pd.DataFrame(data_list)
        # **FIX 4: Add new columns to the CSV output**
        df = df[['id', 'name', 'category', 'type', 'rarity', 'origin', 'value', 'image_url']]
        df.to_csv(csv_file_path, index=False)
        print("CSV file has been created/updated successfully.")
    else:
        print("No data available to create a CSV file.")
except FileNotFoundError:
    print(f"Cannot create CSV because the JSON file ('{json_file_path}') was not found.")

print("\nProcess finished.")