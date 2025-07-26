import json
import sys

def extract_text_from_repomix_json(json_string):
    """Extracts the text content from a repomix-generated JSON string."""
    try:
        # Parse the JSON string into a Python dictionary
        data = json.loads(json_string)
        # The text we need is stored under the "content" key
        text_content = data.get("content")
        return text_content
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}", file=sys.stderr)
        return None
    except KeyError:
        print("Error: 'content' key not found in the JSON file.", file=sys.stderr)
        return None

def main():
    """
    Main function to read a JSON file from the command line,
    extract its text content, and print a new JSON object.
    """
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <path_to_json_file>", file=sys.stderr)
        sys.exit(1)

    json_file_path = sys.argv[1]

    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            json_string = file.read()
    except FileNotFoundError:
        print(f"Error: File not found at {json_file_path}", file=sys.stderr)
        sys.exit(1)

    # Extract the raw text from the input JSON
    text = extract_text_from_repomix_json(json_string)

    # If text was successfully extracted, wrap it in a new JSON object and print it
    if text is not None:
        output_json = {"text_content": text}
        print(json.dumps(output_json, indent=4))

if __name__ == "__main__":
    main()