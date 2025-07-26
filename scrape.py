import requests
import time
import os
import re
from bs4 import BeautifulSoup

# --- Configuration ---
WIKI_DOMAIN = "lookism.fandom.com"
API_URL = f"https://{WIKI_DOMAIN}/api.php"
OUTPUT_DIR = "lookism_wiki_output"

# IMPORTANT: Change this to identify your script.
# Be a good internet citizen! Include your contact info in case of issues.
USER_AGENT = "LookismArchiveBot/1.0 (mikehaggar@gmail.com; personal project)"

# Create a session object to reuse settings and connections
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

def sanitize_filename(name):
    """Removes characters that are invalid in filenames."""
    # Remove invalid characters
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    return name

def get_all_page_titles():
    """Gets a list of all page titles from the main namespace (ns=0)."""
    all_titles = []
    params = {
        "action": "query",
        "format": "json",
        "list": "allpages",
        "aplimit": "max",  # Request the maximum allowed (500)
        "apnamespace": 0,  # Namespace 0 is for main articles
        "apfilterredir": "nonredirects", # We only want actual pages, not redirects
    }
    last_continue = {}
    print("Fetching all page titles from the Lookism Wiki...")

    while True:
        req_params = params.copy()
        req_params.update(last_continue)

        response = SESSION.get(url=API_URL, params=req_params)
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("allpages", [])
        for page in pages:
            all_titles.append(page["title"])

        if "continue" not in data:
            break
        
        last_continue = data["continue"]
        print(f"  ... found {len(all_titles)} titles so far.")
        # No need to sleep here as we're just getting the list in chunks
        
    print(f"Finished. Found {len(all_titles)} total page titles.")
    return all_titles

def get_and_save_page_content(page_title, output_dir):
    """Fetches, cleans, and saves the content of a single page."""
    print(f"Processing: {page_title}")
    
    params = {
        "action": "parse",
        "page": page_title,
        "format": "json",
        "prop": "text",       # We want the HTML content
        "disabletoc": True,   # Don't need the table of contents
    }
    
    try:
        response = SESSION.get(url=API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        html_content = data.get("parse", {}).get("text", {}).get("*", "")
        if not html_content:
            print(f"  -> No content found for: {page_title}")
            return

        # Use BeautifulSoup to convert HTML to plain text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove elements that are often not needed, like navigation boxes or categories
        for element in soup.select('.navbox, .portable-infobox, .catlinks, .mw-editsection'):
            element.decompose()
            
        plain_text = soup.get_text(separator='\n', strip=True)

        # Save the plain text to a file
        filename = sanitize_filename(page_title) + ".txt"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(plain_text)
            
        print(f"  -> Saved to {filepath}")

    except requests.exceptions.RequestException as e:
        print(f"  -> Error fetching {page_title}: {e}")

if __name__ == "__main__":
    # Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    # Get the list of all pages
    page_titles = get_all_page_titles()

    # Loop through each title and save its content
    total_pages = len(page_titles)
    for i, title in enumerate(page_titles):
        get_and_save_page_content(title, OUTPUT_DIR)
        
        # This is the most important part for being a good citizen!
        # Wait for 1 second before the next request.
        print(f"  --- Progress: {i+1}/{total_pages} ---")
        time.sleep(1)

    print("\nAll done! Check the 'lookism_wiki_output' folder.")