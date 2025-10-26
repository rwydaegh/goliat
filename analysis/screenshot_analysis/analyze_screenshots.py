import os
import logging
from PIL import Image
import collections
import re
import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

# --- Control Flags ---
DO_PLOTS = True  # Set to False to disable generating plot images for individual analyses
DO_INDIVIDUAL_REPORTS = True  # Set to False to disable generating individual perforation summary text files


def get_color_frequencies(image_path):
    """
    Analyzes an image to find the frequency of all non-transparent colors,
    focusing on the area within a "perfect red box".
    Returns a tuple of (color_counts, bounding_box).
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            width, height = img.size
            pixels = img.load()

            # Detect red pixels that could be part of the box
            red_pixels = []
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    if r >= 125 and g == 0 and b == 0 and a == 255:
                        red_pixels.append((x, y))

            bounding_box = None
            if not red_pixels:
                logging.warning(f"No red pixels found in {image_path}. Analyzing full image.")
                min_x, min_y, max_x, max_y = 0, 0, width - 1, height - 1
            else:
                # Find the most prominent horizontal and vertical lines
                x_counts = collections.Counter(p[0] for p in red_pixels)
                y_counts = collections.Counter(p[1] for p in red_pixels)

                # Find the two most frequent x and y coordinates
                top_x = [x for x, count in x_counts.most_common(2)]
                top_y = [y for y, count in y_counts.most_common(2)]

                if len(top_x) < 2 or len(top_y) < 2:
                    logging.warning(f"Could not define a bounding box from red lines in {image_path}. Analyzing full image.")
                    min_x, min_y, max_x, max_y = 0, 0, width - 1, height - 1
                else:
                    min_x, max_x = min(top_x), max(top_x)
                    min_y, max_y = min(top_y), max(top_y)
                    bounding_box = (min_x, min_y, max_x, max_y)

            # Process only the pixels inside the bounding box
            color_counts = collections.Counter()
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    p = pixels[x, y]
                    # Exclude the red box pixels themselves from the analysis
                    r, g, b, a = p
                    if r >= 125 and g == 0 and b == 0 and a == 255:
                        continue

                    # Filter out transparent colors and colors with at least two zero values in their RGB components.
                    if a == 0:
                        continue
                    if (r == 0) + (g == 0) + (b == 0) >= 2:
                        continue
                    color_counts[p] += 1

            if not color_counts:
                return None, None

            return color_counts, bounding_box

    except Exception as e:
        logging.error(f"Error processing {image_path}: {e}")
        return None, None


def rgb_to_hsl_array(rgb):
    """
    Converts a numpy array of RGB values to HSL.
    RGB values are in the range [0, 255].
    """
    rgb = rgb / 255.0
    max_c = np.max(rgb, axis=1)
    min_c = np.min(rgb, axis=1)

    l = (max_c + min_c) / 2.0

    delta = max_c - min_c
    # Add a small epsilon to the denominator to avoid division by zero for pure white/black
    denominator = 1 - np.abs(2 * l - 1)
    s = np.where(delta == 0, 0, delta / (denominator + 1e-9))

    h = np.zeros_like(l)

    idx_r = (max_c == rgb[:, 0]) & (delta != 0)
    h[idx_r] = ((rgb[idx_r, 1] - rgb[idx_r, 2]) / delta[idx_r]) % 6

    idx_g = (max_c == rgb[:, 1]) & (delta != 0)
    h[idx_g] = (rgb[idx_g, 2] - rgb[idx_g, 0]) / delta[idx_g] + 2

    idx_b = (max_c == rgb[:, 2]) & (delta != 0)
    h[idx_b] = (rgb[idx_b, 0] - rgb[idx_b, 1]) / delta[idx_b] + 4

    h = h * 60
    h[h < 0] += 360

    return np.stack([h, s, l], axis=1)


def plot_colors_in_3d_interactive(image_path, color_counts, output_dir):
    """
    Saves an interactive 3D color plot as an HTML file using plotly,
    representing colors in an HSL-based cylindrical space.
    """
    if not color_counts:
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        print("\n---")
        print("Warning: 'plotly' is not installed. Cannot create interactive 3D plot.")
        print("Please install it by running the following command in your terminal:")
        print(f'"C:/Program Files/Sim4Life_8.2.0.16876/Python/python.exe" -m pip install plotly')
        print("---\n")
        return

    items = list(color_counts.items())
    colors = np.array([item[0] for item in items])
    counts = np.array([item[1] for item in items])

    rgb = colors[:, :3]
    hsl = rgb_to_hsl_array(rgb)

    # Convert HSL to cylindrical coordinates for plotting
    hue_radians = np.deg2rad(hsl[:, 0])
    saturation = hsl[:, 1]
    lightness = hsl[:, 2]

    x = saturation * np.cos(hue_radians)
    y = saturation * np.sin(hue_radians)
    z = lightness

    # Create a string representation of the color for hover text and marker color
    color_strings = [f"rgb({r},{g},{b})" for r, g, b in rgb]
    hover_text = [f"RGB: ({r}, {g}, {b})<br>HSL: ({h:.1f}, {s:.2f}, {l:.2f})" for (r, g, b), (h, s, l) in zip(rgb, hsl)]

    # Scale marker size based on the log of the color count
    # Add 1 to counts to avoid log(0) for counts of 1, and scale for visibility
    marker_size = np.log(counts + 1) ** 1.8

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="markers",
                marker=dict(
                    size=marker_size,
                    color=color_strings,  # Use original RGB for marker colors
                    opacity=0.8,
                ),
                text=hover_text,
                hoverinfo="text",
            )
        ]
    )

    fig.update_layout(
        title=f"Interactive HSL Color Distribution for {os.path.basename(image_path)}",
        scene=dict(
            xaxis_title="Saturation (X)",
            yaxis_title="Saturation (Y)",
            zaxis_title="Lightness",
        ),
        margin=dict(r=20, b=10, l=10, t=40),
    )

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_color_dist_hsl_3d.html")

    fig.write_html(output_path)
    print(f"Interactive HSL 3D plot saved to {output_path}")


def visualize_color_distribution(image_path, color_counts, output_dir, bounding_box=None):
    """
    Analyzes color distribution. If DO_PLOTS is True, it visualizes the distribution.
    Always calculates and saves the proportion of the top two colors.
    If a bounding_box is provided, it's drawn on the output images.
    """
    if not color_counts:
        print(f"No colors to analyze for {image_path}.")
        return

    all_sorted_colors = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)

    if not all_sorted_colors:
        print(f"No colors to process for {image_path}.")
        return

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]

    # --- Report proportion for context, but do not save individual file ---
    if len(all_sorted_colors) >= 2:
        main_color_count = all_sorted_colors[0][1]
        second_color_count = all_sorted_colors[1][1]
        proportion = (second_color_count / main_color_count) * 100
        print(f"Proportion of #2 color to #1 color for {base_name}: {proportion:.2f}%")
    else:
        print(f"Not enough color data to calculate proportion for {base_name}.")

    # --- Conditional Plotting ---
    if not DO_PLOTS:
        print("DO_PLOTS is False, skipping visualization generation.")
        return

    main_color, main_color_count = all_sorted_colors[0]
    threshold = main_color_count * 0.01

    # Colors to be summed (from #2 down to the threshold)
    colors_to_sum = [item for item in all_sorted_colors[1:] if item[1] >= threshold]
    sum_of_significant_colors = sum(item[1] for item in colors_to_sum)

    # Prepare items for plotting
    display_items = [(main_color, main_color_count)]
    if sum_of_significant_colors > 0:
        display_items.insert(1, ((0, 0, 0, 255), sum_of_significant_colors))  # Black bar for the sum
    display_items.extend(all_sorted_colors[1:50])

    colors = [np.array(item[0]) / 255.0 for item in display_items]
    counts = [item[1] for item in display_items]

    # Create labels
    color_labels = []
    for item in display_items:
        if item[0] == (0, 0, 0, 255):
            color_labels.append("Sum of Significant Colors (>=1% of Main)")
        else:
            color_labels.append(f"RGB({item[0][0]}, {item[0][1]}, {item[0][2]})")

    # --- Generate and Save Linear Scale Plot ---
    plt.figure(figsize=(15, 10))
    plt.bar(range(len(colors)), counts, color=colors, tick_label=color_labels)
    plt.xlabel("Colors")
    plt.ylabel("Frequency (Number of Pixels)")
    plt.title(f"Color Distribution for {os.path.basename(image_path)} (Linear Scale)")
    plt.xticks(rotation=90)
    plt.tight_layout()

    linear_output_path = os.path.join(output_dir, f"{base_name}_color_dist_linear.png")
    plt.savefig(linear_output_path)
    print(f"Linear visualization saved to {linear_output_path}")
    plt.close()

    if bounding_box:
        create_annotated_image(image_path, bounding_box, output_dir)

    # --- Generate and Save Log Scale Plot ---
    plt.figure(figsize=(15, 10))
    plt.bar(range(len(colors)), counts, color=colors, tick_label=color_labels)
    plt.xlabel("Colors")
    plt.ylabel("Frequency (Number of Pixels) - Log Scale")
    plt.yscale("log")
    plt.title(f"Color Distribution for {os.path.basename(image_path)} (Log Scale)")
    plt.xticks(rotation=90)
    plt.tight_layout()

    log_output_path = os.path.join(output_dir, f"{base_name}_color_dist_log.png")
    plt.savefig(log_output_path)
    print(f"Logarithmic visualization saved to {log_output_path}")
    plt.close()

    # --- Generate and Save Interactive 3D Color Plot ---
    plot_colors_in_3d_interactive(image_path, color_counts, output_dir)


def create_annotated_image(original_image_path, bounding_box, output_dir):
    """
    Draws the bounding box on a copy of the original image and saves it.
    """
    try:
        with Image.open(original_image_path) as img:
            from PIL import ImageDraw

            draw = ImageDraw.Draw(img)

            min_x, min_y, max_x, max_y = bounding_box
            draw.rectangle([min_x, min_y, max_x, max_y], outline="lime", width=2)

            base_name = os.path.splitext(os.path.basename(original_image_path))[0]
            annotated_output_path = os.path.join(output_dir, f"{base_name}_annotated.png")
            img.save(annotated_output_path)
            print(f"Annotated image saved to {annotated_output_path}")

    except Exception as e:
        logging.error(f"Could not create annotated image for {original_image_path}: {e}")


def colors_are_similar(c1, c2, tolerance=30):
    """
    Checks if two colors are similar within a given tolerance.
    """
    return all(abs(c1[i] - c2[i]) <= tolerance for i in range(3))


def calculate_and_save_perforation(image_group_data, output_dir):
    """
    Calculates and saves the perforation based on aggregated color counts for a group of images.
    Returns a dictionary with the summary for cross-frequency analysis.
    """
    # --- Aggregate counts and verify color consistency ---
    total_counts_color1 = 0
    total_counts_color2 = 0

    if not image_group_data or len(image_group_data[0]["colors"]) < 2:
        print("Not enough data to determine base colors for perforation analysis.")
        return None

    # Use the first image's top two colors as the reference
    base_color1 = image_group_data[0]["colors"][0][0]
    base_color2 = image_group_data[0]["colors"][1][0]

    perforation_results = []
    for data in image_group_data:
        if len(data["colors"]) < 2:
            print(f"Warning: Not enough color data for {data['filename']}. Skipping from perforation analysis.")
            continue

        # Find colors in the current image that are similar to the base colors
        current_color1_data = next(
            (item for item in data["colors"] if colors_are_similar(item[0], base_color1)),
            None,
        )
        current_color2_data = next(
            (item for item in data["colors"] if colors_are_similar(item[0], base_color2)),
            None,
        )

        if not current_color1_data or not current_color2_data:
            print(f"Warning: Could not find consistent colors for {data['filename']}. Skipping.")
            continue

        count1 = current_color1_data[1]
        count2 = current_color2_data[1]

        total_counts_color1 += count1
        total_counts_color2 += count2

        perforation = (count2 / count1) * 100 if count1 > 0 else 0
        perforation_results.append({"filename": data["filename"], "perforation": perforation})

    if not perforation_results:
        print("\nNo images with consistent colors found. Cannot calculate total perforation.")
        return None

    total_perforation = (total_counts_color2 / total_counts_color1) * 100 if total_counts_color1 > 0 else 0

    # If the total perforation is less than 1%, consider it negligible and set to 0.
    if total_perforation < 1.0:
        total_perforation = 0

    if DO_INDIVIDUAL_REPORTS:
        # --- Save results to a text file ---
        group_name = os.path.commonprefix([d["filename"] for d in image_group_data]).strip("_")
        if not group_name:
            group_name = "perforation_analysis"

        output_path = os.path.join(output_dir, f"{group_name}_perforation_summary.txt")

        with open(output_path, "w") as f:
            f.write(f"Perforation Analysis Summary for Group: {group_name}\n")
            f.write("=" * 50 + "\n")
            f.write(f"Reference Color #1 (Surface): RGB{base_color1[:3]}\n")
            f.write(f"Reference Color #2 (Holes): RGB{base_color2[:3]}\n")
            f.write("-" * 50 + "\n")
            f.write("Individual Perforation (by view):\n")
            for result in perforation_results:
                f.write(f"  - {result['filename']}: {result['perforation']:.2f}%\n")
            f.write("-" * 50 + "\n")
            f.write(f"Total Aggregated Perforation: {total_perforation:.2f}%\n")
            f.write("=" * 50 + "\n")
            f.write(f"\nTotal counts for Color #1 (Surface): {total_counts_color1}\n")
            f.write(f"Total counts for Color #2 (Holes): {total_counts_color2}\n")

        print(f"\nPerforation summary saved to {output_path}")

    return {
        "total_perforation": total_perforation,
        "base_color1": base_color1,
        "base_color2": base_color2,
        "total_counts_color1": total_counts_color1,
        "total_counts_color2": total_counts_color2,
    }


def analyze_screenshots_in_folder(target_dir):
    """
    Analyzes all images in a directory, groups them, and calculates perforation.
    """
    if not os.path.isdir(target_dir):
        print(f"Error: Directory not found at '{target_dir}'")
        return

    print(f"\n--- Analyzing directory: {target_dir} ---")

    all_files = [
        f
        for f in os.listdir(target_dir)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
        and "_color_dist" not in f.lower()
        and "_perforation_summary" not in f.lower()
        and "_annotated" not in f.lower()
    ]

    # Simple grouping strategy: assume all images in the folder belong to one group.
    # For more complex scenarios, a more sophisticated grouping logic would be needed.
    image_group = all_files

    if not image_group:
        print("No images found to analyze.")
        return

    image_group_data = []
    for file in image_group:
        image_path = os.path.join(target_dir, file)
        print(f"\nAnalyzing {image_path}...")

        color_counts, bounding_box = get_color_frequencies(image_path)

        if color_counts:
            sorted_colors = sorted(color_counts.items(), key=lambda item: item[1], reverse=True)
            image_group_data.append({"filename": file, "colors": sorted_colors})
            # Pass the bounding box to the visualization function
            visualize_color_distribution(image_path, color_counts, target_dir, bounding_box=bounding_box)
        else:
            print(f"  No color data found for {image_path}.")

    if image_group_data:
        return calculate_and_save_perforation(image_group_data, target_dir)
    return None


def natural_sort_key(s):
    """
    A key for sorting strings in a 'natural' order (e.g., '2MHz' before '10MHz').
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split("([0-9]+)", s)]


def save_combined_summary(phantom_dir, all_freq_results):
    """
    Saves a text file summarizing perforation results across all frequencies for a phantom.
    """
    output_path = os.path.join(phantom_dir, "combined_perforation_summary.txt")

    with open(output_path, "w") as f:
        f.write(f"Combined Perforation Analysis Summary for: {os.path.basename(phantom_dir)}\n")
        f.write("=" * 60 + "\n")

        # Sort frequencies using the natural sort key
        sorted_freqs = sorted(all_freq_results.keys(), key=natural_sort_key)

        for freq in sorted_freqs:
            result = all_freq_results[freq]
            if result:
                f.write(f"\n--- Frequency: {freq} ---\n")
                f.write(f"  - Total Aggregated Perforation: {result['total_perforation']:.2f}%\n")
                f.write(f"  - Surface Color: RGB{result['base_color1'][:3]}\n")
                f.write(f"  - Holes Color: RGB{result['base_color2'][:3]}\n")
            else:
                f.write(f"\n--- Frequency: {freq} ---\n")
                f.write("  - No valid results found.\n")

        f.write("\n" + "=" * 60 + "\n")

    print(f"\nCombined summary saved to {output_path}")


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    results_dir = os.path.join(project_root, "results")

    for field_type in ["far_field", "near_field"]:
        field_dir = os.path.join(results_dir, field_type)
        if not os.path.isdir(field_dir):
            continue

        for phantom_name in os.listdir(field_dir):
            phantom_dir = os.path.join(field_dir, phantom_name)
            if not os.path.isdir(phantom_dir):
                continue

            # Skip files like 'aggregated_results.pkl'
            if not os.path.isdir(phantom_dir):
                continue

            all_freq_results = {}

            for freq_name in os.listdir(phantom_dir):
                freq_dir = os.path.join(phantom_dir, freq_name)
                if not os.path.isdir(freq_dir):
                    continue

                screenshots_dir = os.path.join(freq_dir, "screenshots")
                if os.path.isdir(screenshots_dir):
                    perforation_result = analyze_screenshots_in_folder(screenshots_dir)
                    all_freq_results[freq_name] = perforation_result
                else:
                    print(f"Skipping: No 'screenshots' directory found in {freq_dir}")

            if all_freq_results:
                save_combined_summary(phantom_dir, all_freq_results)
