import google.generativeai as genai
import json
import os
import re
import sys
import time

def get_api_key():
    """Fetches the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ FATAL ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        print("Please follow the setup instructions to get and set your API key.", file=sys.stderr)
        sys.exit(1)
    return api_key

def main():
    """
    Uses the Gemini API to parse the combined text file in batches and generate structured JSON.
    """
    # --- Configuration ---
    try:
        genai.configure(api_key=get_api_key())
        # --- THIS IS THE UPDATED MODEL NAME ---
        model = genai.GenerativeModel('gemini-2.5-flash')
        BATCH_SIZE = 50
    except Exception as e:
        print(f"❌ Error configuring the AI model: {e}", file=sys.stderr)
        sys.exit(1)

    input_filename = "debug_full_text_output.txt"
    output_filename = "character_data_final.json"
    
    # --- File Reading ---
    print(f"⚙️  Step 1: Reading source text from '{input_filename}'...")
    try:
        with open(input_filename, 'r', encoding='utf-8') as f:
            full_text = f.read()
    except FileNotFoundError:
        print(f"❌ Error: The input file '{input_filename}' was not found.", file=sys.stderr)
        sys.exit(1)

    # --- AI Processing Loop ---
    print(f"⚙️  Step 2: Processing character data in batches of {BATCH_SIZE} with gemini-2.5-flash...")
    
    all_characters_data = []
    
    character_blocks = [block.strip() for block in re.split(r'--- FILE: .*? ---\n', full_text) if block.strip()]
    total_batches = (len(character_blocks) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(character_blocks), BATCH_SIZE):
        batch_blocks = character_blocks[i:i + BATCH_SIZE]
        combined_batch_text = "\n\n--- NEXT CHARACTER ---\n\n".join(batch_blocks)
        
        current_batch_num = (i // BATCH_SIZE) + 1
        print(f"  - Sending batch {current_batch_num} of {total_batches} to AI...")

        prompt = f"""
            You are a data extraction expert. Based on the following text which contains multiple character descriptions separated by '--- NEXT CHARACTER ---', create a JSON array (a list of JSON objects).

            Instructions:
            1. For EACH character in the provided text, create one JSON object.
            2. Each object must have a "name" key.
            3. For each section for a character (like "Appearance", "Personality", etc.), create a corresponding key in that character's object in snake_case (e.g., "fighting_prowess").
            4. The value for each key must be the complete text of that section.
            5. Your entire output must be ONLY the JSON array, without any surrounding text, comments, or markdown formatting like ```json.

            Here is the text batch:
            ---
            {combined_batch_text}
            ---
        """
        
        try:
            response = model.generate_content(prompt)
            cleaned_response_text = response.text.strip().replace("```json", "").replace("```", "")
            list_of_chars = json.loads(cleaned_response_text)
            
            if isinstance(list_of_chars, list):
                all_characters_data.extend(list_of_chars)
                print(f"    ✅ Successfully parsed {len(list_of_chars)} characters from batch.")
            else:
                print(f"    ❌ Warning: AI did not return a list for batch {current_batch_num}. Skipping.", file=sys.stderr)

        except json.JSONDecodeError:
            print(f"    ❌ Warning: AI returned malformed JSON for batch {current_batch_num}. Skipping.", file=sys.stderr)
        except Exception as e:
            print(f"    ❌ An error occurred processing batch {current_batch_num}: {e}", file=sys.stderr)
        
        time.sleep(1) 

    # --- Final Output ---
    print("⚙️  Step 3: Saving final structured data...")
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(all_characters_data, f, indent=4)
        
    print(f"\n🎉 All done! Extracted information for {len(all_characters_data)} characters.")
    print(f"✅ Your final, clean data is saved in: {output_filename}")


if __name__ == "__main__":
    main()