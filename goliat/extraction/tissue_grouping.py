"""Tissue grouping logic for SAR analysis.

Groups tissues into logical categories (eyes, skin, brain) for aggregated
SAR metrics calculation. Uses explicit mapping from material_name_mapping.json.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config
    from ..logging_manager import LoggingMixin


class TissueGrouper:
    """Handles grouping of tissues into logical categories for SAR analysis."""

    def __init__(self, config: "Config", phantom_name: str, logger: "LoggingMixin"):
        """Initializes the tissue grouper.

        Args:
            config: Configuration object for accessing material mappings.
            phantom_name: Name of the phantom model.
            logger: Logger instance for logging messages.
        """
        self.config = config
        self.phantom_name = phantom_name
        self.logger = logger

    def group_tissues(self, available_tissues: list[str]) -> dict[str, list[str]]:
        """Groups tissues according to material_name_mapping.json.

        Simple matching: tissue_name -> material_name -> entity_name -> check group.

        Args:
            available_tissues: List of tissue names found in the simulation results.

        Returns:
            Dict mapping group names to lists of tissue names that belong to that group.
            Empty groups are still included but with empty lists.
        """
        material_mapping = self.config.get_material_mapping(self.phantom_name)

        if "_tissue_groups" not in material_mapping:
            return {}

        return self._group_from_config(material_mapping, available_tissues)

    def _group_from_config(self, material_mapping: dict, available_tissues: list[str]) -> dict[str, list[str]]:
        """Groups tissues using explicit configuration from material mapping.

        Simple approach:
        1. Build reverse map: material_name -> entity_name
        2. For each tissue: match to entity, check if entity is in group

        Args:
            material_mapping: Material mapping dictionary from config.
            available_tissues: List of tissue names found in simulation results.

        Returns:
            Dict mapping group names to lists of matched tissue names.
        """
        phantom_groups = material_mapping["_tissue_groups"]

        # Build simple reverse mapping: material_name -> entity_name
        material_to_entity = {}
        entity_to_material = {}
        for entity_name, material_name in material_mapping.items():
            if entity_name == "_tissue_groups":
                continue
            material_to_entity[material_name] = entity_name
            entity_to_material[entity_name] = material_name

        # Initialize groups with all expected tissues from JSON config
        # This ensures all groups show up in reports even if some tissues aren't present
        tissue_groups = {}
        for group_name, entity_list in phantom_groups.items():
            tissue_groups[group_name] = []
            # Pre-populate with entity names - will be replaced with actual tissue names if found
            for entity_name in entity_list:
                # Try to find matching tissue from Sim4Life results
                found_tissue = None
                for tissue in available_tissues:
                    cleaned_tissue = tissue.split("  (")[0].strip() if "  (" in tissue else tissue
                    # Check if this tissue matches the entity
                    if cleaned_tissue == entity_name:
                        found_tissue = tissue  # Use original tissue name with phantom suffix
                        break
                    # Also check material name match
                    elif entity_name in material_mapping:
                        material_name = material_mapping[entity_name]
                        if cleaned_tissue == material_name:
                            found_tissue = tissue
                            break

                if found_tissue:
                    tissue_groups[group_name].append(found_tissue)
                else:
                    # Tissue not found in simulation - still include entity name for display
                    # Format: "EntityName (not present)"
                    tissue_groups[group_name].append(f"{entity_name} (not present)")

        # For each tissue from Sim4Life, find which group(s) it belongs to
        # (This ensures we catch any tissues that might have been missed)
        for tissue in available_tissues:
            # Strip phantom suffix (e.g., "Cornea  (Thelonious_6y_V6)" -> "Cornea")
            # Sim4Life appends phantom name and version to tissue names
            cleaned_tissue = tissue
            if "  (" in tissue:
                cleaned_tissue = tissue.split("  (")[0].strip()

            entity_name = None

            # Try 1: Direct entity name match (Sim4Life returned entity name)
            if cleaned_tissue in material_mapping and cleaned_tissue != "_tissue_groups":
                entity_name = cleaned_tissue

            # Try 2: Material name match (Sim4Life returned material name)
            elif cleaned_tissue in material_to_entity:
                entity_name = material_to_entity[cleaned_tissue]

            if entity_name is None:
                continue

            # Check which group(s) this entity belongs to
            matched_groups = []
            for group_name, entity_list in phantom_groups.items():
                if entity_name in entity_list:
                    # Replace "(not present)" entry with actual tissue name if it exists
                    if f"{entity_name} (not present)" in tissue_groups[group_name]:
                        idx = tissue_groups[group_name].index(f"{entity_name} (not present)")
                        tissue_groups[group_name][idx] = tissue
                    elif tissue not in tissue_groups[group_name]:
                        # Only add if not already present (shouldn't happen, but safety check)
                        tissue_groups[group_name].append(tissue)
                    matched_groups.append(group_name)

        return tissue_groups
