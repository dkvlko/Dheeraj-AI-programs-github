from gemini_grammar_check import check_sentence

def main():
    sentence = "Dogs ambushed the Hyena , who was eating his hunt."
    
    print("Sending to Gemini...")
    result = check_sentence(sentence)

    print("\n=== Result ===")
    print(result)

if __name__ == "__main__":
    main()
