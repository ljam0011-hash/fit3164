import os
import re
from pathlib import Path

def clean_filename(filename):
    """Clean filename by removing special characters and limiting length"""
    # Remove file extension
    name_without_ext = os.path.splitext(filename)[0]
    
    # Replace spaces with underscores and remove special characters
    cleaned = re.sub(r'[^\w\s-]', '', name_without_ext)
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    
    # Convert to lowercase and limit length
    cleaned = cleaned.lower()[:50]  # Limit to 50 characters
    
    # Remove trailing underscores
    cleaned = cleaned.rstrip('_')
    
    return cleaned

def rename_files_in_folder(folder_path, prefix):
    """Rename all files in a folder with the given prefix and counter"""
    if not os.path.exists(folder_path):
        print(f"Folder {folder_path} does not exist!")
        return
    
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    files.sort()  # Sort files for consistent numbering
    
    counter = 1
    
    for filename in files:
        old_path = os.path.join(folder_path, filename)
        
        # Get file extension
        file_ext = os.path.splitext(filename)[1]
        if not file_ext:
            file_ext = '.txt'  # Default to .txt if no extension
        
        # Clean the original filename to create a descriptive part
        descriptive_part = clean_filename(filename)
        
        # Create new filename with format: PREFIX_##_descriptive_part.ext
        new_filename = f"{prefix}_{counter:02d}_{descriptive_part}{file_ext}"
        new_path = os.path.join(folder_path, new_filename)
        
        try:
            os.rename(old_path, new_path)
            print(f"Renamed: {filename} -> {new_filename}")
            counter += 1
        except Exception as e:
            print(f"Error renaming {filename}: {e}")

def main():
    base_path = r"C:\Users\suisei\Desktop\articles"
    
    # Define folder mappings
    folders = {
        "news": "NEWS",
        "movie": "MOVIE", 
        "fiction": "FICTION"
    }
    
    print("Starting file renaming process...")
    print("=" * 50)
    
    for folder_name, prefix in folders.items():
        folder_path = os.path.join(base_path, folder_name)
        print(f"\nProcessing {folder_name} folder...")
        print("-" * 30)
        rename_files_in_folder(folder_path, prefix)
    
    print("\n" + "=" * 50)
    print("File renaming completed!")

if __name__ == "__main__":
    main()