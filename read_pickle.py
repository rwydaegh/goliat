import pickle

def read_pickle(file_path):
    """
    Reads a pickle file and returns the content.

    Args:
        file_path (str): The path to the pickle file.

    Returns:
        The content of the pickle file.
    """
    try:
        with open(file_path, 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Pickle file not found at: {file_path}")
    except Exception as e:
        raise Exception(f"An error occurred while reading the pickle file: {e}")
    
if __name__ == "__main__":
    # Example usage
    file_path = 'results/thelonius/1450MHz/front_of_eyes/sar_stats_all_tissues.pkl'  # Replace with your actual pickle file path
    try:
        print(read_pickle(file_path))
    except Exception as e:
        print(e)