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

# --- THIS IS THE MISSING FUNCTION THAT HAS BEEN ADDED BACK ---
def process_with_ai(model, text_batch, prompt_template):
    """Sends text to the AI and returns the parsed JSON response."""
    prompt = prompt_template.format(text_batch=text_batch)
    
    # The API call itself is wrapped in the main loop's try/except for retry logic
    response = model.generate_content(prompt)
    
    # Robustly find the JSON block in the response text
    match = re.search(r'\{.*\}|\[.*\]', response.text, re.DOTALL)
    if not match:
        # This will be caught by the main loop's generic exception handler
        raise json.JSONDecodeError("No JSON array or object found in AI response.", response.text, 0)
    
    return json.loads(match.group(0))
# --- END OF MISSING FUNCTION ---


def main():
    """
    Reads a master list from character_data.json (as a dictionary), processes the
    corresponding .txt files, and saves a final structured JSON.
    """
    # --- Configuration ---
    try:
        genai.configure(api_key=get_api_key())
        generation_config = {"response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
        BATCH_SIZE = 20
        MAX_RETRIES = 3
    except Exception as e:
        print(f"❌ Error configuring the AI model: {e}", file=sys.stderr)
        sys.exit(1)

    input_json_list = "character_data.json"
    base_path = "lookism_wiki_output"
    output_filename = "lookism_database_final.json"
    recovery_filename = "recovery_log.json"
    failed_batches_log = []

    # --- Step 1: Read the character list from character_data.json ---
    print(f"⚙️  Step 1: Reading master character list from '{input_json_list}'...")
    try:
        with open(input_json_list, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
            if isinstance(source_data, dict):
                target_characters = set(source_data.keys())
            else:
                print("Warning: Expected a JSON object but found a list. Trying to parse names anyway.", file=sys.stderr)
                target_characters = {item['name'].strip() for item in source_data if isinstance(item, dict) and 'name' in item and item['name']}
        print(f"Found {len(target_characters)} target characters in your JSON file.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ Error: Could not read or parse '{input_json_list}'. Details: {e}", file=sys.stderr)
        sys.exit(1)
        
    if not target_characters:
        print("❌ Error: No character names were extracted from the JSON. Please check the file format.", file=sys.stderr)
        sys.exit(1)

    # --- Step 2: Find and read the content for the target characters ---
    print("⚙️  Step 2: Finding and reading the specified character files...")
    character_blocks = []
    for char_name in target_characters:
        filename = source_data.get(char_name) if isinstance(source_data, dict) else f"{char_name.replace(' ', '_')}.txt"
        filepath = os.path.join(base_path, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    character_blocks.append(f.read())
            except Exception as e:
                print(f"  - Warning: Could not read file {filepath}: {e}", file=sys.stderr)
        else:
            print(f"  - Warning: Could not find file for character '{char_name}' at path: {filepath}", file=sys.stderr)

    print(f"Successfully read content for {len(character_blocks)} of your selected character files.")

    # --- Step 3: Process Characters with AI ---
    final_character_list = []
    character_prompt = "Based on the text which contains multiple character descriptions separated by '--- NEXT CHARACTER ---', create a JSON array. For EACH character, create one JSON object with a \"name\" key and snake_case keys for each section (like \"appearance\"). Your output must be ONLY the JSON array. Here is the text batch:\n---\n{text_batch}\n---"
    
    print(f"⚙️  Step 3: Processing {len(character_blocks)} characters with the AI...")
    for i in range(0, len(character_blocks), BATCH_SIZE):
        batch = character_blocks[i:i + BATCH_SIZE]
        batch_text = "\n\n--- NEXT CHARACTER ---\n\n".join(batch)
        current_batch_num = (i // BATCH_SIZE) + 1
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"  - Sending character batch {current_batch_num} (Attempt {attempt + 1})...")
                result = process_with_ai(model, batch_text, character_prompt)
                if result and isinstance(result, list):
                    final_character_list.extend(result)
                    print(f"    ✅ Successfully parsed {len(result)} characters from batch.")
                    break 
            except ResourceExhausted:
                wait_time = (2 ** attempt) * 5
                print(f"    Rate limit hit. Waiting for {wait_time} seconds before retrying...", file=sys.stderr)
                time.sleep(wait_time)
            except Exception as e:
                print(f"    ❌ An unrecoverable error occurred on this batch: {e}", file=sys.stderr)
                break 
        else: # Runs if the retry loop finishes without a 'break'
            print(f"    ❌ FAILED character batch {current_batch_num} after all retries. Logging for recovery.")
            failed_batches_log.append({"type": "characters", "prompt_template": character_prompt, "text_batch": batch_text})

    # --- Final Save ---
    print("⚙️  Final Step: Saving the complete database...")
    final_data = {"characters": final_character_list}
    
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