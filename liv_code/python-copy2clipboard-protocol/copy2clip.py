import sys
import pyperclip
from urllib.parse import unquote

def main():
    # The browser passes the full URL: "copy-query:The%20Text%20Here"
    if len(sys.argv) > 1:
        raw_data = sys.argv[1]
        
        # Remove the protocol prefix
        if raw_data.startswith("copy-query:"):
            payload = raw_data.replace("copy-query:", "", 1)
            
            # Decode URL characters (e.g., %20 to space)
            final_text = unquote(payload)
            
            # Copy to clipboard
            pyperclip.copy(final_text)

if __name__ == "__main__":
    main()