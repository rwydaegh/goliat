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
        self.logger._log(
            f"[TISSUE_GROUPING] Starting tissue grouping for '{self.phantom_name}'",
            log_type="info",
        )
        self.logger._log(
            f"[TISSUE_GROUPING] Available tissues from Sim4Life ({len(available_tissues)}): {available_tissues[:10]}{'...' if len(available_tissues) > 10 else ''}",
            log_type="info",
        )

        material_mapping = self.config.get_material_mapping(self.phantom_name)

        if "_tissue_groups" not in material_mapping:
            self.logger._log(
                "[TISSUE_GROUPING] ERROR: '_tissue_groups' not found in material mapping. Returning empty groups.",
                log_type="error",
            )
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
        self.logger._log(
            "[TISSUE_GROUPING] Loading tissue groups from material_name_mapping.json",
            log_type="info",
        )

        phantom_groups = material_mapping["_tissue_groups"]
        self.logger._log(
            f"[TISSUE_GROUPING] Found groups: {list(phantom_groups.keys())}",
            log_type="info",
        )

        # Build reverse mapping: material_name -> list of entity_names
        # (multiple entities can map to same material, e.g., "Skin" and "Ear_skin" both map to "Skin")
        material_to_entities = {}
        entity_to_material = {}
        for entity_name, material_name in material_mapping.items():
            if entity_name == "_tissue_groups":
                continue
            if material_name not in material_to_entities:
                material_to_entities[material_name] = []
            material_to_entities[material_name].append(entity_name)
            entity_to_material[entity_name] = material_name

        self.logger._log(
            f"[TISSUE_GROUPING] Built material->entities map with {len(material_to_entities)} entries",
            log_type="info",
        )

        # Initialize groups with all expected tissues from JSON config
        # This ensures all groups show up in reports even if some tissues aren't present
        tissue_groups = {}
        for group_name, entity_list in phantom_groups.items():
            tissue_groups[group_name] = []
            # Track which tissues we've already matched to prevent duplicates
            # Key: tissue name, Value: entity name that matched it
            matched_tissues = {}
            
            # Pre-populate with entity names - will be replaced with actual tissue names if found
            for entity_name in entity_list:
                # Try to find matching tissue from Sim4Life results
                found_tissue = None
                for tissue in available_tissues:
                    cleaned_tissue = tissue.split("  (")[0].strip() if "  (" in tissue else tissue
                    # Check if this tissue matches the entity name directly
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
                    # Check if this tissue was already matched to another entity
                    if found_tissue in matched_tissues:
                        # This tissue matches multiple entities (e.g., "Skin" matches both "Skin" and "Ear_skin")
                        # Only add it once, mark others as "(not present)"
                        if matched_tissues[found_tissue] == entity_name:
                            # This is the first entity that matched - already added, skip
                            continue
                        else:
                            # Another entity already matched this tissue - mark this one as "(not present)"
                            tissue_groups[group_name].append(f"{entity_name} (not present)")
                    else:
                        # First time this tissue is matched - add it
                        tissue_groups[group_name].append(found_tissue)
                        matched_tissues[found_tissue] = entity_name
                else:
                    # Tissue not found in simulation - still include entity name for display
                    tissue_groups[group_name].append(f"{entity_name} (not present)")

        # For each tissue from Sim4Life, find which group(s) it belongs to
        # (This ensures we catch any tissues that might have been missed)
        for tissue in available_tissues:
            self.logger._log(
                f"[TISSUE_GROUPING] Processing tissue: '{tissue}'",
                log_type="info",
            )

            # Strip phantom suffix (e.g., "Cornea  (Thelonious_6y_V6)" -> "Cornea")
            # Sim4Life appends phantom name and version to tissue names
            cleaned_tissue = tissue
            if "  (" in tissue:
                cleaned_tissue = tissue.split("  (")[0].strip()
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Stripped phantom suffix: '{cleaned_tissue}'",
                    log_type="info",
                )

            entity_name = None

            # Try 1: Direct entity name match (Sim4Life returned entity name)
            if cleaned_tissue in material_mapping and cleaned_tissue != "_tissue_groups":
                entity_name = cleaned_tissue
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Matched as entity name: '{entity_name}'",
                    log_type="info",
                )

            # Try 2: Material name match (Sim4Life returned material name)
            elif cleaned_tissue in material_to_entities:
                # Multiple entities can map to same material - try to find one that matches
                possible_entities = material_to_entities[cleaned_tissue]
                # Prefer direct entity name match if available
                entity_name = None
                for ent in possible_entities:
                    if cleaned_tissue == ent:
                        entity_name = ent
                        break
                # If no direct match, use first entity (they all map to same material anyway)
                if entity_name is None:
                    entity_name = possible_entities[0]
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Matched as material name -> entity: '{entity_name}' (from {len(possible_entities)} possible entities)",
                    log_type="info",
                )

            if entity_name is None:
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> WARNING: No match found for '{tissue}' (cleaned: '{cleaned_tissue}')",
                    log_type="warning",
                )
                continue

            # Check which group(s) this entity belongs to
            matched_groups = []
            for group_name, entity_list in phantom_groups.items():
                if entity_name in entity_list:
                    # Replace "(not present)" entry with actual tissue name if it exists
                    if f"{entity_name} (not present)" in tissue_groups[group_name]:
                        idx = tissue_groups[group_name].index(f"{entity_name} (not present)")
                        tissue_groups[group_name][idx] = tissue
                        matched_groups.append(group_name)
                        self.logger._log(
                            f"[TISSUE_GROUPING]   -> Added to group '{group_name}'",
                            log_type="info",
                        )
                    elif tissue not in tissue_groups[group_name]:
                        # Only add if not already present (prevents duplicates)
                        tissue_groups[group_name].append(tissue)
                        matched_groups.append(group_name)
                        self.logger._log(
                            f"[TISSUE_GROUPING]   -> Added to group '{group_name}'",
                            log_type="info",
                        )

            if not matched_groups:
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Entity '{entity_name}' not found in any group",
                    log_type="warning",
                )

        # Log final results
        self.logger._log(
            "[TISSUE_GROUPING] Final grouping results:",
            log_type="info",
        )
        for group_name, tissues in tissue_groups.items():
            self.logger._log(
                f"[TISSUE_GROUPING]   {group_name}: {len(tissues)} tissues - {tissues}",
                log_type="info",
            )

        return tissue_groups
