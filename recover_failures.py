import google.generativeai as genai
import json
import os
import sys
import time

# Copied directly from the main script
def get_api_key():
    """Fetches the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ FATAL ERROR: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return api_key

# Copied directly from the main script
def process_with_ai(model, text_batch, prompt_template):
    """Generic function to send a text batch to the AI and parse the response."""
    prompt = prompt_template.format(text_batch=text_batch)
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        # We don't print warnings here, just return None so the caller knows it failed
        return None

def main():
    """
    Reads a recovery log, re-tries failed batches, and merges them into the main JSON file.
    """
    # --- Configuration ---
    try:
        genai.configure(api_key=get_api_key())
        generation_config = {"response_mime_type": "application/json"}
        model = genai.GenerativeModel('gemini-1.5-flash-latest', generation_config=generation_config)
    except Exception as e:
        print(f"❌ Error configuring the AI model: {e}", file=sys.stderr)
        sys.exit(1)
        
    main_data_filename = "character_data_final.json"
    recovery_log_filename = "recovery_log.json"
    new_recovery_log = []

    # --- Step 1: Load existing data and recovery log ---
    print("⚙️  Step 1: Loading existing data and recovery log...")
    try:
        with open(recovery_log_filename, 'r', encoding='utf-8') as f:
            failed_batches = json.load(f)
    except FileNotFoundError:
        print(f"✅ No '{recovery_log_filename}' found. Nothing to recover.")
        sys.exit(0)
        
    try:
        with open(main_data_filename, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
    except FileNotFoundError:
        # If the main file doesn't exist, create a skeleton
        main_data = {"characters": [], "groups": []}

    print(f"Found {len(failed_batches)} failed batch(es) to retry.")

    # --- Step 2: Retry failed batches ---
    print("⚙️  Step 2: Re-trying failed batches...")
    for batch_info in failed_batches:
        batch_id = batch_info.get("batch_id", "Unknown")
        print(f"  - Retrying batch '{batch_id}'...")
        
        result = process_with_ai(model, batch_info["text_batch"], batch_info["prompt_template"])
        
        if result:
            # Success! Merge the data.
            print(f"    ✅ Success! Merging data from batch '{batch_id}'.")
            if batch_info["type"] == "characters" and isinstance(result, list):
                main_data["characters"].extend(result)
            elif batch_info["type"] == "groups" and isinstance(result, dict):
                main_data["groups"].append(result)
            else:
                print(f"    ❌ Data type mismatch for batch '{batch_id}'. Re-logging failure.")
                new_recovery_log.append(batch_info) # Log it again if the type is weird
        else:
            # Failed again, log it for the next recovery run
            print(f"    ❌ Batch '{batch_id}' failed again. Re-logging for next time.")
            new_recovery_log.append(batch_info)
            
        time.sleep(1)

    # --- Step 3: Save updated data and new recovery log ---
    print("⚙️  Step 3: Saving updated data...")
    with open(main_data_filename, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, indent=4)
    print(f"✅ Main data file '{main_data_filename}' has been updated.")
    
    # Overwrite the old recovery log with the batches that still failed
    with open(recovery_log_filename, 'w', encoding='utf-8') as f:
        json.dump(new_recovery_log, f, indent=4)
        
    if new_recovery_log:
        print(f"\n⚠️  {len(new_recovery_log)} batch(es) still failed. The recovery log has been updated.")
        print("You can run this script again later to retry.")
    else:
        print(f"\n🎉 All failed batches successfully recovered and merged!")
        os.remove(recovery_log_filename) # Clean up the log file since it's now empty
        print("✅ Recovery log has been removed.")


if __name__ == "__main__":
    main()