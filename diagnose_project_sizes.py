import os
import pandas as pd
import logging
from datetime import datetime

def setup_diagnostic_logger():
    """Sets up a simple logger for the diagnostic script."""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    session_timestamp = datetime.now().strftime('%d-%m_%H-%M-%S')
    log_filename = os.path.join(log_dir, f'diagnostics_{session_timestamp}.log')
    
    logger = logging.getLogger('diagnostic_logger')
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers if run multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    file_handler = logging.FileHandler(log_filename, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    return logger

def analyze_project_sizes(base_dir, logger):
    """
    Analyzes the size of .smash files in the results directory.
    """
    results_dir = os.path.join(base_dir, 'results', 'far_field')
    if not os.path.exists(results_dir):
        logger.info(f"Results directory not found at: {results_dir}")
        return

    project_data = []
    logger.info(f"Scanning for .smash files in: {results_dir}")

    for root, _, files in os.walk(results_dir):
        for file in files:
            if file.endswith('.smash'):
                project_path = os.path.join(root, file)
                try:
                    file_size_mb = os.path.getsize(project_path) / (1024 * 1024)
                    
                    # Extract parameters from the path using regex for robustness
                    import re
                    match = re.search(r'results[\\/]far_field[\\/](?P<phantom>\w+)[\\/](?P<freq>\d+)MHz', project_path)
                    
                    if match:
                        phantom = match.group('phantom')
                        frequency = match.group('freq')
                    else:
                        phantom = "N/A"
                        frequency = "N/A"

                    project_data.append({
                        'Phantom': phantom,
                        'Frequency (MHz)': int(frequency) if frequency.isdigit() else frequency,
                        'File Size (MB)': file_size_mb,
                        'Path': project_path
                    })
                except Exception as e:
                    logger.error(f"Could not process file {project_path}: {e}")

    if not project_data:
        logger.info("No .smash files found to analyze.")
        return

    df = pd.DataFrame(project_data)
    df = df.sort_values(by=['Frequency (MHz)', 'File Size (MB)']).reset_index(drop=True)

    logger.info("\n--- Project Size Analysis ---")
    logger.info(df.to_string())
    
    # Analyze and log the trend
    avg_size_by_freq = df.groupby('Frequency (MHz)')['File Size (MB)'].mean().reset_index()
    logger.info("\n--- Average Project Size by Frequency ---")
    logger.info(avg_size_by_freq.to_string())
    
    logger.info("\n--- Analysis Complete ---")
    logger.info(f"Full diagnostic report saved to the logs directory.")


if __name__ == "__main__":
    base_directory = os.getcwd()
    logger = setup_diagnostic_logger()
    analyze_project_sizes(base_directory, logger)
