import requests
from bs4 import BeautifulSoup
import re
import json
import pandas as pd
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# --- Configuration ---
base_url = "https://adoptmetradingvalues.com"
list_url = f"{base_url}/pet-value-list.php?params=petsneons"
json_file_path = 'adoptme_neons_megas_values.json'
csv_file_path = 'adoptme_neons_megas_values.csv'

# Set up Selenium
print("Setting up Selenium driver...")
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# --- Step 1: Fetch and parse the list page with Selenium ---
print("--- Step 1: Fetching and parsing the petsneons list page with Selenium ---")
try:
    driver.get(list_url)
    time.sleep(5)  # Wait for JavaScript to load content
    soup = BeautifulSoup(driver.page_source, 'lxml')
    driver.quit()
    print("Page fetched and parsed successfully.")
except Exception as e:
    print(f"Error fetching page with Selenium: {e}")
    driver.quit()
    exit(1)

# --- Step 2: Extract data from all <li> elements ---
print("\n--- Step 2: Extracting data from list items ---")
values = {'neons': {}, 'megas': {}}
item_count = 0

for li in soup.find_all('li', class_='liclass'):
    try:
        # Extract value
        value_span = li.find('span', class_='ctr')
        if value_span:
            value_text = value_span.get_text(strip=True).replace(' RP', '').replace(',', '')
            value = float(value_text) if value_text else 0.0
        else:
            value = 0.0

        # Extract link and ID
        a = li.find('a', href=re.compile(r'id=\d+'))
        if not a:
            continue
        match = re.search(r'id=(\d+)', a.get('href'))
        id_str = match.group(1) if match else 'unknown'

        # Extract image
        img = a.find('img')
        if img:
            image_url = urljoin(base_url, img['src'].replace('\\', '/'))  # Fix backslash if any
            alt = img.get('alt', '').strip()
            title = img.get('title', alt).strip()
        else:
            continue

        # Parse name, rarity, origin from title/alt
        # Example: "Bat Dragon - Legendary from Halloween 2019 (Candy)"
        parts = re.split(r' - | from ', title)
        name = parts[0].strip() if len(parts) > 0 else 'Unknown'
        rarity = parts[1].strip() if len(parts) > 1 else 'Unknown'
        origin = ' '.join(parts[2:]).strip() if len(parts) > 2 else 'Unknown'

        # Determine variant (neon or mega)
        variant_div = li.find('div', class_='bottom-right-mega')
        if variant_div and variant_div.get_text(strip=True) == 'M':
            variant = 'megas'
            variant_label = 'Mega'
        else:
            # Check hidden input for 'N'
            hidden_inputs = li.find_all('input', {'type': 'hidden', 'name': 'pets[]'})
            is_neon = any('N' in inp.get('value', '') for inp in hidden_inputs)
            if is_neon:
                variant = 'neons'
                variant_label = 'Neon'
            else:
                variant = 'neons'  # Default
                variant_label = 'Neon'

        # Adjust name to include variant
        full_name = f"{variant_label} {name}"

        # Store data
        values[variant][id_str] = {
            'name': full_name,
            'base_name': name,
            'rarity': rarity,
            'origin': origin,
            'value': value,
            'image_url': image_url
        }

        item_count += 1
        print(f"Extracted: {full_name} (ID: {id_str}) = {value} RP ({rarity}) from {origin}")

    except Exception as e:
        print(f"Error extracting item: {e}")

print(f"\nExtracted {item_count} items in total.")

# --- Step 3: Save to JSON and CSV ---
print("\n--- Step 3: Saving data to JSON and CSV ---")

# Save to JSON
with open(json_file_path, 'w') as f:
    json.dump(values, f, indent=4)
print(f"JSON saved to '{json_file_path}'")

# Flatten for CSV
data_list = []
for var, items in values.items():
    for item_id, d in items.items():
        row = d.copy()
        row['id'] = item_id
        row['variant'] = var
        data_list.append(row)

if data_list:
    df = pd.DataFrame(data_list)
    df = df[['id', 'name', 'base_name', 'variant', 'rarity', 'origin', 'value', 'image_url']]
    df.to_csv(csv_file_path, index=False)
    print(f"CSV saved to '{csv_file_path}'")
else:
    print("No data to save.")

print("\nProcess finished.")