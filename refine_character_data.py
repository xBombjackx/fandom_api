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
    Reads a list of characters from character_data.json, processes their corresponding
    .txt files using the Gemini API, and saves the refined data.
    """
    # --- Configuration ---
    try:
        genai.configure(api_key=get_api_key())
        generation_config = {"response_mime_type": "application/json"}
        # Note: Using the latest public model name. Replace if you have access to a different one.
        model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
        BATCH_SIZE = 20
        MAX_RETRIES = 3
    except Exception as e:
        print(f"❌ Error configuring the AI model: {e}", file=sys.stderr)
        sys.exit(1)

    input_json_list = "character_data.json"
    source_text_folder = "lookism_wiki_output"
    output_filename = "character_data_refined.json"
    recovery_filename = "recovery_log.json"
    failed_batches_log = []

    # --- Step 1: Read character list from the input JSON file ---
    print(f"⚙️  Step 1: Reading target character list from '{input_json_list}'...")
    try:
        with open(input_json_list, 'r', encoding='utf-8') as f:
            # Create a set of character names from the "name" key of each object
            source_data = json.load(f)
            target_characters = {item['name'].strip() for item in source_data if 'name' in item and item['name']}
        print(f"Found {len(target_characters)} unique target characters in the JSON file.")
    except FileNotFoundError:
        print(f"❌ Error: The input file '{input_json_list}' was not found.", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        print(f"❌ Error: Could not parse character names from '{input_json_list}'. Ensure it's a valid JSON array of objects with a 'name' key. Details: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Step 2: Find and read the content for ONLY the target characters ---
    print("⚙️  Step 2: Finding and reading corresponding .txt files...")
    character_content_map = {}
    missing_character_files = set(target_characters)

    for char_name in target_characters:
        filename = f"{char_name.replace(' ', '_')}.txt"
        filepath = os.path.join(source_text_folder, filename)
        if os.path.exists(filepath):
            missing_character_files.remove(char_name)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f_char:
                    character_content_map[char_name] = f_char.read()
            except Exception as e:
                print(f"  - Warning: Could not read file {filepath}: {e}", file=sys.stderr)
    
    if missing_character_files:
        print("\n⚠️  Warning: The following character files were not found in 'lookism_wiki_output':", file=sys.stderr)
        for name in sorted(missing_character_files):
            print(f"  - {name}", file=sys.stderr)
    
    print(f"\nSuccessfully read content for {len(character_content_map)} character files.")
    
    # --- Step 3: Process Characters with AI, with Retries ---
    final_character_list = []
    character_blocks = list(character_content_map.values())
    character_prompt = "Based on the text which contains multiple character descriptions separated by '--- NEXT CHARACTER ---', create a JSON array. For EACH character, create one JSON object with a \"name\" key and snake_case keys for each section (like \"appearance\"). Your output must be ONLY the JSON array. Here is the text batch:\n---\n{text_batch}\n---"
    
    print(f"⚙️  Step 3: Processing {len(character_blocks)} characters with the AI...")
    for i in range(0, len(character_blocks), BATCH_SIZE):
        batch = character_blocks[i:i + BATCH_SIZE]
        batch_text = "\n\n--- NEXT CHARACTER ---\n\n".join(batch)
        current_batch_num = (i // BATCH_SIZE) + 1
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  - Sending character batch {current_batch_num} (Attempt {attempt + 1})...")
                response = model.generate_content(character_prompt.format(text_batch=batch_text))
                
                match = re.search(r'\[.*\]', response.text, re.DOTALL)
                if not match:
                    raise json.JSONDecodeError("No JSON array found in response.", response.text, 0)
                
                cleaned_text = match.group(0)
                list_of_chars = json.loads(cleaned_text)

                if isinstance(list_of_chars, list):
                    final_character_list.extend(list_of_chars)
                    print(f"    ✅ Successfully parsed {len(list_of_chars)} characters from batch.")
                    break 
                
            except ResourceExhausted as e:
                wait_time = (2 ** attempt) * 5
                print(f"    Rate limit hit. Waiting for {wait_time} seconds before retrying...", file=sys.stderr)
                time.sleep(wait_time)
            except Exception as e:
                print(f"    ❌ An unrecoverable error occurred on this batch: {e}", file=sys.stderr)
                break 

        else: # Runs if the retry loop finishes without a 'break'
            print(f"    ❌ FAILED character batch {current_batch_num} after all retries. Logging for recovery.")
            failed_batches_log.append({"type": "characters", "text_batch": batch_text})

    # --- Final Save ---
    print("⚙️  Final Step: Saving refined data...")
    # This structure is now simpler as we are not processing groups separately in this plan
    final_data = {"characters": final_character_list}
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4)
        
    print(f"\n🎉 Run complete! Refined data for {len(final_character_list)} characters.")
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