import json

def linear_series(start, end, num_values):
    """Generates a linear series of numbers."""
    return [start + i * (end - start) / (num_values - 1) for i in range(num_values)]

def main():
    """
    Calculates gridding values for a linear series of frequencies and
    prints them as a JSON object.
    """
    # Define the parameters
    start_mm = 2.5
    end_mm = 1.5
    num_values = 6

    start_freq_mhz = 450
    end_freq_mhz = 2140

    # Generate the linear series for mm and frequencies
    mm_values = linear_series(start_mm, end_mm, num_values)
    freq_values_mhz = linear_series(start_freq_mhz, end_freq_mhz, num_values)

    # Create the dictionary for JSON output
    gridding_per_frequency = {
        str(int(round(freq))): round(mm, 4)
        for freq, mm in zip(freq_values_mhz, mm_values)
    }

    # Print the JSON object
    print(json.dumps(gridding_per_frequency, indent=4))

if __name__ == "__main__":
    main()