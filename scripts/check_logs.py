import os

def check_log_files():
    """
    Loops through all files in logs/osparc_submission_logs,
    checks if the last line of each file contains the word "moved",
    and prints the files that do not contain the word.
    """
    log_dir = "logs/osparc_submission_logs"
    files_without_moved = []

    if not os.path.isdir(log_dir):
        print(f"Error: Directory '{log_dir}' not found.")
        return

    for filename in os.listdir(log_dir):
        if filename.endswith(".log"):
            filepath = os.path.join(log_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        if "moved" not in last_line:
                            files_without_moved.append((filename, "".join(lines)))
                    else:
                        files_without_moved.append((f"{filename} (empty)", ""))
            except Exception as e:
                files_without_moved.append((f"{filename} (error reading: {e})", ""))

    if files_without_moved:
        print("The following log files did not contain 'moved' in the last line:")
        for file, content in files_without_moved:
            print(f"--- Contents of {file} ---")
            print(content)
            print(f"--- End of {file} ---")
    else:
        print("All log files checked contain 'moved' in the last line.")

if __name__ == "__main__":
    check_log_files()