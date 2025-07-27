import google.generativeai as genai
import json
import os
import re
import sys
import time
from google.api_core.exceptions import ResourceExhausted

def get_api_key():
    """Fetches the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ FATAL ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return api_key

def main():
    """
    Parses specific characters and groups using the Gemini API, with automatic retries and failure logging.
    """
    # --- Configuration ---
    try:
        genai.configure(api_key=get_api_key())
        generation_config = {"response_mime_type": "application/json"}
        # Using the specific model name you requested
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        BATCH_SIZE = 20
        MAX_RETRIES = 3
    except Exception as e:
        print(f"❌ Error configuring the AI model: {e}", file=sys.stderr)
        sys.exit(1)

    base_path = "lookism_wiki_output"
    output_filename = "character_data_final.json"
    recovery_filename = "recovery_log.json"
    failed_batches_log = []

    # --- Step 1: Read target characters and check for missing files ---
    print(f"⚙️  Step 1: Reading target files and checking for missing data...")
    try:
        with open(os.path.join(base_path, "Characters.txt"), 'r', encoding='utf-8') as f:
            target_characters = {name.strip() for name in f if name.strip()}
        print(f"Found {len(target_characters)} target characters in Characters.txt.")
        
        character_content_map = {}
        missing_character_files = set(target_characters)

        for char_name in target_characters:
            filename = f"{char_name.replace(' ', '_')}.txt"
            filepath = os.path.join(base_path, filename)
            if os.path.exists(filepath):
                missing_character_files.remove(char_name) # Found it, remove from missing set
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f_char:
                        character_content_map[char_name] = f_char.read()
                except Exception as e:
                    print(f"  - Warning: Could not read file {filepath}: {e}", file=sys.stderr)
        
        if missing_character_files:
            print("\n⚠️  Warning: The following character files were not found:", file=sys.stderr)
            for name in sorted(missing_character_files):
                print(f"  - {name}", file=sys.stderr)
        
        print(f"\nSuccessfully read content for {len(character_content_map)} character files.")
    except FileNotFoundError:
        print(f"❌ Error: 'lookism_wiki_output/Characters.txt' not found.", file=sys.stderr)
        sys.exit(1)

    # --- Step 2: Process Characters with AI, with Retries ---
    final_character_list = []
    character_blocks = list(character_content_map.values())
    character_prompt = "Based on the text which contains multiple character descriptions separated by '--- NEXT CHARACTER ---', create a JSON array. For EACH character, create one JSON object with a \"name\" key and snake_case keys for each section (like \"appearance\"). Your output must be ONLY the JSON array. Here is the text batch:\n---\n{text_batch}\n---"
    
    print(f"⚙️  Step 2: Processing {len(character_blocks)} characters with the AI...")
    for i in range(0, len(character_blocks), BATCH_SIZE):
        batch = character_blocks[i:i + BATCH_SIZE]
        batch_text = "\n\n--- NEXT CHARACTER ---\n\n".join(batch)
        current_batch_num = (i // BATCH_SIZE) + 1
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  - Sending character batch {current_batch_num} (Attempt {attempt + 1})...")
                response = model.generate_content(character_prompt.format(text_batch=batch_text))
                
                # More robust cleaning: find the first '[' and the last ']'
                match = re.search(r'\[.*\]', response.text, re.DOTALL)
                if not match:
                    raise json.JSONDecodeError("No JSON array found in response.", response.text, 0)
                
                cleaned_text = match.group(0)
                list_of_chars = json.loads(cleaned_text)

                if isinstance(list_of_chars, list):
                    final_character_list.extend(list_of_chars)
                    print(f"    ✅ Successfully parsed {len(list_of_chars)} characters from batch.")
                    break # Success, break the retry loop
                
            except ResourceExhausted as e:
                wait_time = (2 ** attempt) * 5 # Exponential backoff: 5s, 10s, 20s
                print(f"    Rate limit hit. Waiting for {wait_time} seconds before retrying...", file=sys.stderr)
                time.sleep(wait_time)
            except Exception as e:
                print(f"    ❌ An unrecoverable error occurred on this batch: {e}", file=sys.stderr)
                break # Break on other errors, like bad JSON

        else: # This 'else' belongs to the 'for' loop, it runs if the loop wasn't broken
            print(f"    ❌ FAILED character batch {current_batch_num} after all retries. Logging for recovery.")
            failed_batches_log.append({"type": "characters", "text_batch": batch_text})

    # --- (The rest of the script for processing groups and saving remains largely the same) ---
    # ... This section can be added back if the 'Four_Major_Crews' processing is still needed ...

    # --- Final Save ---
    print("⚙️  Final Step: Combining all data and saving file...")
    final_data = {"characters": final_character_list, "groups": []} # Assuming groups are handled separately if needed
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4)
        
    print(f"\n🎉 Run complete! Extracted {len(final_character_list)} characters.")
    print(f"✅ Data saved in: {output_filename}")
    
    if failed_batches_log:
        print(f"\n⚠️  {len(failed_batches_log)} batch(es) failed to process.")
        with open(recovery_filename, 'w', encoding='utf-8') as f:
            json.dump(failed_batches_log, f, indent=4)
        print(f"✅ A log of failed batches has been saved to '{recovery_filename}'.")
    else:
        print("\n✨ All batches processed successfully!")


if __name__ == "__main__":
    main()