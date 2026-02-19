import importlib
import sys
import analyzer
from file_io import (
    get_input_output_paths,
    read_tab_csv,
    write_gift_file,
    write_tab_csv,
)

#returns the function  reference of dynamic module.
def load_processor(file_number: int, format: int):
    """
    Dynamically load processor module.
    Example: processors.english_1
    """
    
    module_name = f"processors.english_{file_number}"

    try:
        module = importlib.import_module(module_name)
        if format == 0:
           print("Processor 1 loaded")
           return module.process

        elif format == 1:
             print("Processor 2 loaded")
             return module.process_4gift

        elif format == 2:
             print("Processor 3 loaded")
             return module.process_4gift

        else:
              print("Default processor loaded")
        return module.process

    except ModuleNotFoundError:
        print(f"❌ No processor found for file {file_number}")
        sys.exit(1)

def main():
    # ---- Ask user input ----
    try:
        file_number = int(
            input("Enter english file number to process: ")
        )
    except ValueError:
        print("❌ Invalid number")
        return

    # ---- Build file paths ----
    input_path, output_path, input_path_gift, output_path_gift = get_input_output_paths(
        file_number
    )

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return

    # ---- Read data ----
    data = read_tab_csv(input_path)
    analyzer.validate_uniformity(data)  # Ensure uniform structure
    

    # ---- Analyze structure ----
    rows, cols = analyzer.analyze_uniform_tabular_data(data)
    

    print(f"Rows with data    : {rows}")
    print(f"Columns with data: {cols}")

    # ---- Load processor ----
    processor = load_processor(file_number,0)

    # ---- Process data ----
    processed_data = processor(data)

    # ---- Write output ----
    write_tab_csv(output_path, processed_data)


    # ---- Exit message ----
    print(f"✅ Output written to: {output_path}")

    if not input_path_gift.exists():
        print(f"❌ Input file not found: {input_path_gift}")
        return

    # ---- Read data ----
    data = read_tab_csv(input_path_gift)
    analyzer.validate_uniformity(data)  # Ensure uniform structure
    

    # ---- Analyze structure ----
    rows, cols = analyzer.analyze_uniform_tabular_data(data)
    

    print(f"Rows with data    : {rows}")
    print(f"Columns with data: {cols}")

        # ---- Load processor for gift----
    processor = load_processor(file_number,1)

    # ---- Process data for gift ----
    processed_data = processor(data)

    # ---- Write output for gift ----
    write_gift_file(output_path_gift, processed_data)

    
    # ---- Exit message ----
    print(f"✅ Output written to: {output_path_gift}")


if __name__ == "__main__":
    main()
