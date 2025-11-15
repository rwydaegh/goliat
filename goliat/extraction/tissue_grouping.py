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

        # Build simple reverse mapping: material_name -> entity_name
        material_to_entity = {}
        entity_to_material = {}
        for entity_name, material_name in material_mapping.items():
            if entity_name == "_tissue_groups":
                continue
            material_to_entity[material_name] = entity_name
            entity_to_material[entity_name] = material_name

        self.logger._log(
            f"[TISSUE_GROUPING] Built material->entity map with {len(material_to_entity)} entries",
            log_type="info",
        )

        # Initialize groups
        tissue_groups = {group_name: [] for group_name in phantom_groups.keys()}

        # For each tissue from Sim4Life, find which group(s) it belongs to
        for tissue in available_tissues:
            self.logger._log(
                f"[TISSUE_GROUPING] Processing tissue: '{tissue}'",
                log_type="info",
            )

            entity_name = None

            # Try 1: Direct entity name match (Sim4Life returned entity name)
            if tissue in material_mapping and tissue != "_tissue_groups":
                entity_name = tissue
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Matched as entity name: '{entity_name}'",
                    log_type="info",
                )

            # Try 2: Material name match (Sim4Life returned material name)
            elif tissue in material_to_entity:
                entity_name = material_to_entity[tissue]
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> Matched as material name -> entity: '{entity_name}'",
                    log_type="info",
                )

            if entity_name is None:
                self.logger._log(
                    f"[TISSUE_GROUPING]   -> WARNING: No match found for '{tissue}'",
                    log_type="warning",
                )
                continue

            # Check which group(s) this entity belongs to
            matched_groups = []
            for group_name, entity_list in phantom_groups.items():
                if entity_name in entity_list:
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
