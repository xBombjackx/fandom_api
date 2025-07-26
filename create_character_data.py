import json
import re
import sys
import os
import glob

def parse_character_data(full_text_content):
    """
    Parses the combined text from the wiki files. This version is specifically
    tailored to the format found in the debug output file, where sections are
    denoted by plain text headings on their own lines.
    """
    # A list of all possible section titles. Add any other titles you see.
    KNOWN_HEADINGS = [
        "Description", "Appearance", "Personality", "Background", "History",
        "Fighting Prowess", "Plot", "Relationships", "Abilities",
        "Powers and Abilities", "Equipment", "Synopsis"
    ]
    
    characters = []
    
    # Split the full text into blocks, one for each original file
    character_blocks = re.split(r'--- FILE: .*? ---\n', full_text_content)

    for block in character_blocks:
        block = block.strip()
        if not block:
            continue

        lines = block.split('\n')
        
        # Find the first non-empty line to use as the character's name
        character_name = ""
        content_start_index = 0
        for i, line in enumerate(lines):
            if line.strip():
                character_name = line.strip()
                content_start_index = i + 1
                break
        
        # If no name is found, skip this file block
        if not character_name:
            continue

        character_data = {'name': character_name}
        current_heading_key = None
        current_content = []

        # Process the rest of the lines in the block
        for line in lines[content_start_index:]:
            line_stripped = line.strip()

            # Check if the current line is a known heading
            if line_stripped in KNOWN_HEADINGS:
                # If we were already building a section, save it first
                if current_heading_key:
                    character_data[current_heading_key] = '\n'.join(current_content).strip()
                
                # Start the new section
                current_heading_key = line_stripped.lower().replace(' ', '_')
                current_content = [] # Reset the content buffer
            elif current_heading_key:
                # If we are currently inside a section, append the line
                current_content.append(line)
        
        # After the loop, save the very last section that was being processed
        if current_heading_key and current_content:
            character_data[current_heading_key] = '\n'.join(current_content).strip()
            
        # Only add characters that have at least one piece of data besides a name
        if len(character_data) > 1:
            characters.append(character_data)
            
    return characters

def main():
    """
    Finds all .txt files, concatenates their content, parses the result,
    and saves the structured data to a file.
    """
    print("⚙️  Step 1: Finding .txt files in 'lookism_wiki_output' folder...")
    
    search_pattern = os.path.join('lookism_wiki_output', '**', '*.txt')
    file_list = glob.glob(search_pattern, recursive=True)

    if not file_list:
        print(f"❌ Error: No .txt files found in the 'lookism_wiki_output' directory.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(file_list)} file(s) to process.")
    print("⚙️  Step 2: Reading and combining text from all files...")
    
    all_text_parts = []
    for filepath in file_list:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                all_text_parts.append(f"--- FILE: {os.path.basename(filepath)} ---\n")
                all_text_parts.append(f.read())
                all_text_parts.append("\n\n")
        except Exception as e:
            print(f"  - Warning: Could not read file {filepath}: {e}", file=sys.stderr)
    
    full_text = "".join(all_text_parts)

    print("⚙️  Step 3: Parsing combined text and extracting character data...")
    structured_data = parse_character_data(full_text)
    
    if not structured_data:
        print("⚠️ Warning: Could not find any character data. Check the KNOWN_HEADINGS list in the script.", file=sys.stderr)

    output_filename = "character_data.json"
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(structured_data, f, indent=4)
        
    print(f"\n✅ Success! Extracted information for {len(structured_data)} characters.")
    print(f"✅ Clean data saved to: {output_filename}")


if __name__ == "__main__":
    main()