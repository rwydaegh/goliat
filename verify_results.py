import os
import datetime

def verify_far_field_results(base_results_dir='results/far_field', phantom='thelonius'):
    """
    Scans the far-field results for a given phantom to check for the presence
    of sar_results.json and the HTML report, and verifies the report's timestamp.
    """
    print(f"Starting verification for phantom: '{phantom}' in '{base_results_dir}'")
    
    phantom_dir = os.path.join(base_results_dir, phantom)
    if not os.path.exists(phantom_dir):
        print(f"Error: Phantom directory not found at '{phantom_dir}'")
        return

    missing_html = []
    html_found_with_json = 0
    json_found_total = 0
    
    # Timestamp for comparison: 5th August 2025, 9:00 AM
    # Note: The user's timezone is UTC+2, so 9 AM Paris time is 7 AM UTC.
    # We'll use a timezone-aware object for correct comparison.
    cutoff_datetime = datetime.datetime(2025, 8, 5, 9, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
    print(f"Timestamp cutoff: {cutoff_datetime}")


    for freq_dir in os.listdir(phantom_dir):
        freq_path = os.path.join(phantom_dir, freq_dir)
        if os.path.isdir(freq_path) and freq_dir.endswith('MHz'):
            try:
                frequency = int(freq_dir.replace('MHz', ''))
            except ValueError:
                continue

            for placement_dir in os.listdir(freq_path):
                case_path = os.path.join(freq_path, placement_dir)
                if os.path.isdir(case_path):
                    json_path = os.path.join(case_path, 'sar_results.json')
                    html_path = os.path.join(case_path, 'sar_stats_all_tissues.html')

                    json_exists = os.path.exists(json_path)
                    html_exists = os.path.exists(html_path)

                    if json_exists:
                        json_found_total += 1
                        if html_exists:
                            html_found_with_json += 1
                            
                            # Check timestamp
                            html_mod_time_ts = os.path.getmtime(html_path)
                            html_mod_datetime = datetime.datetime.fromtimestamp(html_mod_time_ts, tz=datetime.timezone.utc).astimezone(cutoff_datetime.tzinfo)

                            if html_mod_datetime >= cutoff_datetime:
                                print(f"  [WARNING] HTML report for {freq_dir}/{placement_dir} is TOO RECENT: {html_mod_datetime}")

                        else:
                            missing_html.append(f"{freq_dir}/{placement_dir}")
    
    print("\n--- Verification Summary ---")
    print(f"Total cases with 'sar_results.json': {json_found_total}")
    print(f"Cases with both JSON and HTML report: {html_found_with_json}")
    print(f"Cases missing HTML report: {len(missing_html)}")

    if missing_html:
        print("\nCases missing 'sar_stats_all_tissues.html':")
        # Sort missing cases for readability, by frequency then placement
        missing_html.sort(key=lambda x: (int(x.split('/')[0].replace('MHz','')), x.split('/')[1]))
        for case in missing_html:
            print(f"  - {case}")

if __name__ == "__main__":
    verify_far_field_results()