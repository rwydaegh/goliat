"""Auto-induced exposure SAPD extractor.

Extracts SAPD from a combined H5 file (created by field_combiner) without
requiring a running simulation. Uses Sim4Life's SimulationExtractor to load
the H5 directly.
"""

import json
import os
from pathlib import Path
from typing import Optional


def extract_sapd_from_h5(
    combined_h5_path: str | Path,
    config_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    candidate_index: int = 1,
) -> dict:
    """Extract SAPD from a combined H5 file.

    This function loads the combined H5 into Sim4Life's analysis pipeline
    and computes SAPD on the skin surface.

    Args:
        combined_h5_path: Path to the combined _Output.h5 file.
        config_path: Optional path to GOLIAT config for skin entity lookup.
        output_dir: Directory to save SAPD results JSON.
        candidate_index: Index of this candidate (for naming).

    Returns:
        Dict with SAPD results including peak_sapd_W_m2 and peak_location_m.
    """
    import s4l_v1.analysis as analysis
    import s4l_v1.document as document
    import s4l_v1.model as model
    import s4l_v1.units as units

    h5_path = Path(combined_h5_path)
    if not h5_path.exists():
        raise FileNotFoundError(f"Combined H5 not found: {h5_path}")

    # Load config for skin entity names if provided
    skin_entity_names = ["Skin", "Ear_skin"]  # Default fallback
    phantom_name: str | None = None
    if config_path and os.path.exists(config_path):
        try:
            from goliat.config import Config

            config = Config(config_path)
            # Get known phantoms from material mapping keys
            known_phantoms = set(config.material_mapping.keys())
            # Try to get skin group from material mapping
            # We need phantom name - try to infer from path
            path_parts = h5_path.parts
            for part in path_parts:
                if part.lower() in known_phantoms:
                    phantom_name = part.lower()
                    break

            if phantom_name:
                material_mapping = config.get_material_mapping(phantom_name)
                tissue_groups = material_mapping.get("_tissue_groups", {})
                skin_entity_names = tissue_groups.get("skin_group", skin_entity_names)
        except Exception as e:
            print(f"      DEBUG: Config lookup failed: {e}")

    # Infer phantom name from path if not found (fallback to checking path parts)
    if phantom_name is None:
        # Try to load material mapping directly
        try:
            # Find base_dir by looking for 'results' in path
            for i, part in enumerate(h5_path.parts):
                if part == "results":
                    base_dir = Path(*h5_path.parts[:i])
                    mapping_path = base_dir / "data" / "material_name_mapping.json"
                    if mapping_path.exists():
                        with open(mapping_path) as f:
                            known_phantoms = set(json.load(f).keys())
                        for part in h5_path.parts:
                            if part.lower() in known_phantoms:
                                phantom_name = part.lower()
                                break
                    break
        except Exception:
            pass

    print(f"      DEBUG: Creating SimulationExtractor for {h5_path.name}")

    # Create extractor pointing to the combined H5 file
    sliced_extractor = analysis.extractors.SimulationExtractor(inputs=[])
    sliced_extractor.Name = "AutoInduced_Extractor"
    sliced_extractor.FileName = str(h5_path)
    sliced_extractor.UpdateAttributes()
    document.AllAlgorithms.Add(sliced_extractor)
    print("      DEBUG: SimulationExtractor created successfully")

    try:
        # Get overall field sensor extractor
        print("      DEBUG: Getting Overall Field extractor...")
        em_sensor_extractor = sliced_extractor["Overall Field"]
        em_sensor_extractor.FrequencySettings.ExtractedFrequency = "All"
        document.AllAlgorithms.Add(em_sensor_extractor)
        print("      DEBUG: Updating EM sensor extractor...")
        em_sensor_extractor.Update()
        print("      DEBUG: EM sensor extractor updated")

        # Load skin surface from cached SAB file
        # The SapdExtractor caches skin as data/phantoms_skin/{phantom}_skin.sab
        surface_entity = None

        if phantom_name:
            # Try to find the cached skin SAB file
            # Look relative to the H5 path (results dir) by going up to base
            base_dir = None
            for i, part in enumerate(h5_path.parts):
                if part == "results":
                    base_dir = Path(*h5_path.parts[:i])
                    break

            if base_dir:
                cache_path = base_dir / "data" / "phantoms_skin" / f"{phantom_name}_skin.sab"
                print(f"      DEBUG: Looking for skin cache at: {cache_path}")

                if cache_path.exists():
                    print("      DEBUG: Importing cached skin SAB file...")
                    try:
                        imported_entities = list(model.Import(str(cache_path)))
                        if imported_entities:
                            surface_entity = imported_entities[0]
                            surface_entity.Name = "AutoInduced_Skin_Surface"
                            print("      DEBUG: Skin surface loaded from cache")
                    except Exception as e:
                        print(f"      DEBUG: SAB import failed: {e}")
                else:
                    print(f"      DEBUG: No cached skin file found at {cache_path}")
                    print("      DEBUG: Run a normal SAPD extraction first to create the cache")

        if surface_entity is None:
            return {
                "error": f"No skin surface available. Run 'goliat study' with extract_sapd=true first to cache the skin mesh for {phantom_name}.",
                "combined_h5": str(h5_path),
            }

        # Create ModelToGridFilter for skin surface
        model_to_grid = analysis.core.ModelToGridFilter(inputs=[])
        model_to_grid.Name = "AutoInduced_SkinSurface"
        model_to_grid.Entity = surface_entity
        model_to_grid.UpdateAttributes()
        document.AllAlgorithms.Add(model_to_grid)

        # Setup SAPD evaluator
        inputs = [
            em_sensor_extractor.Outputs["S(x,y,z,f0)"],
            model_to_grid.Outputs["Surface"],
        ]

        sapd_evaluator = analysis.em_evaluators.GenericSAPDEvaluator(inputs=inputs)
        sapd_evaluator.AveragingArea = 4.0, units.SquareCentiMeters
        sapd_evaluator.Threshold = 0.01, units.Meters  # 10mm
        sapd_evaluator.UpdateAttributes()
        document.AllAlgorithms.Add(sapd_evaluator)

        # Extract results
        sapd_report = sapd_evaluator.Outputs["Spatial-Averaged Power Density Report"]
        sapd_report.Update()

        # Parse results
        data_collection = sapd_report.Data.DataSimpleDataCollection
        if not data_collection:
            return {"error": "No SAPD data in report"}

        peak_sapd = None
        peak_loc = None

        def safe_get(key):
            try:
                return data_collection.FieldValue(key, 0)
            except TypeError:
                return None

        for key in data_collection.Keys():
            val = safe_get(key)
            if val is not None:
                if "Peak" in key and "Power" in key:
                    peak_sapd = val
                if "Peak" in key and "Location" in key:
                    peak_loc = val

        result = {
            "peak_sapd_W_m2": peak_sapd,
            "peak_sapd_location_m": list(peak_loc) if peak_loc else None,
            "combined_h5": str(h5_path),
            "candidate_index": candidate_index,
        }

        # Save to JSON if output_dir provided
        if output_dir:
            output_path = Path(output_dir) / f"sapd_results_candidate{candidate_index}.json"
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)

        # Cleanup
        document.AllAlgorithms.Remove(sapd_evaluator)
        document.AllAlgorithms.Remove(model_to_grid)
        document.AllAlgorithms.Remove(em_sensor_extractor)
        document.AllAlgorithms.Remove(sliced_extractor)

        # Delete temporary skin entity
        try:
            surface_entity.Delete()
        except Exception:
            pass

        return result

    except Exception as e:
        # Cleanup on error
        try:
            document.AllAlgorithms.Remove(sliced_extractor)
        except Exception:
            pass
        raise e
