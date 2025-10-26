import numpy as np
import matplotlib.pyplot as plt


def get_max_mismatch(ratio):
    """
    Calculates the maximal percentual mismatch for a given cube_length/radius ratio.

    This function provides an analytical approximation of the mismatch, which is fast
    but might not be perfectly accurate across all ratio values compared to a simulation.
    The logic is based on finding the furthest voxel corner by analyzing the geometry
    in the principal directions (1,0,0), (1,1,0), and (1,1,1).
    """
    if ratio <= 0:
        return 0
    # Let R=1 for simplicity. Then L = ratio.
    inv_ratio_sq = (1 / ratio) ** 2

    # Direction (1,0,0)
    # (i-0.5)^2 + 0.5 <= inv_ratio_sq
    # We need inv_ratio_sq > 0.5
    if inv_ratio_sq > 0.5:
        i_x = np.floor(np.sqrt(inv_ratio_sq - 0.5) + 0.5)
        d_x = i_x * ratio
        mismatch_x = (d_x - 1) * 100
    else:
        mismatch_x = -100  # Invalid case, will be ignored by max

    # Direction (1,1,0)
    # 2*(i-0.5)^2 + 0.25 <= inv_ratio_sq
    if inv_ratio_sq > 0.25:
        i_xy = np.floor(np.sqrt((inv_ratio_sq - 0.25) / 2) + 0.5)
        d_xy = np.sqrt(2) * i_xy * ratio
        mismatch_xy = (d_xy - 1) * 100
    else:
        mismatch_xy = -100

    # Direction (1,1,1)
    # 3*(i-0.5)^2 <= inv_ratio_sq
    i = np.floor(1 / (ratio * np.sqrt(3)) + 0.5)
    d_xyz = np.sqrt(3) * i * ratio
    mismatch_xyz = (d_xyz - 1) * 100

    return np.maximum(mismatch_xyz, np.maximum(mismatch_x, mismatch_xy))


def plot_mismatch_vs_ratio():
    """
    Generates a plot of the voxelization fidelity vs. the cube_length/radius ratio.
    """
    # Changed to a linear space from 0.01 to 1 for the new plot requirements
    ratios = np.linspace(0.01, 1, 400)

    # Using the analytical get_max_mismatch is much faster than simulation
    mismatches = np.array([get_max_mismatch(r) for r in ratios])

    # New metric: "Fidelity" or "Agreement"
    fidelity = 100 - mismatches

    plt.figure(figsize=(10, 6))
    plt.plot(ratios, fidelity, label="Voxelization Fidelity (100% - Mismatch)")

    plt.title("Voxelization Fidelity vs. Cube Length/Radius Ratio")
    plt.xlabel("Cube Length / Radius (L/R)")
    plt.ylabel("Fidelity (%)")
    plt.grid(True, which="both", ls="--")
    plt.legend()
    plt.xscale("linear")  # Changed to linear scale
    plt.yscale("linear")
    plt.ylim(0, 100)  # Y-axis from 0% to 100%
    plt.xlim(0, 1)  # X-axis from 0 to 1

    output_filename = "voxelization_fidelity.png"
    plt.savefig(output_filename, dpi=300, bbox_inches="tight")
    print(f"Plot saved as {output_filename}")
    plt.show()  # Re-enabled to show the plot interactively


def get_max_mismatch_simulation(ratio):
    """
    Calculates the max mismatch by simulating a sphere.
    This is a more robust but computationally heavier approach.
    Let R=1. L=ratio.
    """
    if ratio <= 0:
        return 0

    # 1. Create a grid of voxel centers.
    # The sphere extends from -1 to 1 in each dimension.
    # The voxel centers must be in a slightly larger box.
    limit = 1.0 + ratio * np.sqrt(3) / 2
    # Reduce number of voxels by using a more precise limit
    n_voxels_half = int(np.ceil(1.0 / ratio))

    # Generate voxel center coordinates
    axis_coords = np.arange(-n_voxels_half, n_voxels_half + 1) * ratio

    # Use a more memory-efficient way to find centers inside the sphere
    max_dist_sq = 0

    # This part can be slow. The analytical method is preferred.
    # For a lightweight script, we avoid creating the full meshgrid in memory.
    for x in axis_coords:
        for y in axis_coords:
            # Optimization: if x^2+y^2 > 1, no need to check z
            if x**2 + y**2 > (limit) ** 2:
                continue
            for z in axis_coords:
                if x**2 + y**2 + z**2 <= 1.0:
                    # This is a center inside the sphere
                    # Find its furthest corner
                    corner_x = x + np.sign(x) * ratio / 2 if x != 0 else ratio / 2
                    corner_y = y + np.sign(y) * ratio / 2 if y != 0 else ratio / 2
                    corner_z = z + np.sign(z) * ratio / 2 if z != 0 else ratio / 2

                    dist_sq = corner_x**2 + corner_y**2 + corner_z**2
                    if dist_sq > max_dist_sq:
                        max_dist_sq = dist_sq

    if max_dist_sq == 0:
        # Handle case where no voxel center is inside (for large ratios)
        # If R=1, origin voxel is always inside.
        # Furthest corner of origin voxel:
        max_dist_sq = 3 * (ratio / 2) ** 2

    max_dist = np.sqrt(max_dist_sq)

    mismatch = (max_dist - 1.0) * 100
    return mismatch


if __name__ == "__main__":
    # The script now uses the fast analytical method by default.
    # To run the simulation (which is slow), you would have to modify the
    # plot_mismatch_vs_ratio function to call get_max_mismatch_simulation.
    plot_mismatch_vs_ratio()
