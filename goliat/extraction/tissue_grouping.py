"""Tissue grouping logic for SAR analysis.

Groups tissues into logical categories (eyes, skin, brain) for aggregated
SAR metrics calculation. Supports both explicit mapping from configuration
files and keyword-based fallback matching.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Config
    from ..logging_manager import LoggingMixin


# Default tissue group definitions (fallback when not in config)
DEFAULT_TISSUE_GROUPS = {
    "eyes_group": ["eye", "cornea", "sclera", "lens", "vitreous"],
    "skin_group": ["skin"],
    "brain_group": [
        "brain",
        "commissura",
        "midbrain",
        "pineal",
        "hypophysis",
        "medulla_oblongata",
        "pons",
        "thalamus",
        "hippocampus",
        "cerebellum",
    ],
}


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
        """Groups tissues into logical categories (eyes, skin, brain).

        Tries two approaches in order:
        1. Explicit mapping: Uses tissue group definitions from material_name_mapping.json
           if available. This is preferred as it's explicit and configurable.

        2. Keyword matching: Falls back to matching tissue names against known keywords.
           For example, tissues containing 'eye', 'cornea', 'sclera' go into eyes_group.

        This grouping is used later to calculate aggregated SAR metrics (weighted average
        and peak SAR) for each anatomical region, which is more meaningful than individual
        tissue values for safety assessment.

        Args:
            available_tissues: List of tissue names found in the simulation results.

        Returns:
            Dict mapping group names to lists of tissue names that belong to that group.
            Empty groups are still included but with empty lists.
        """
        material_mapping = self.config.get_material_mapping(self.phantom_name)

        if "_tissue_groups" in material_mapping:
            return self._group_from_config(material_mapping, available_tissues)

        return self._group_by_keywords(available_tissues)

    def _group_from_config(self, material_mapping: dict, available_tissues: list[str]) -> dict[str, list[str]]:
        """Groups tissues using explicit configuration from material mapping.

        Args:
            material_mapping: Material mapping dictionary from config.
            available_tissues: List of tissue names found in simulation results.

        Returns:
            Dict mapping group names to lists of matched tissue names.
        """
        self.logger._log(
            f"  - Loading tissue groups for '{self.phantom_name}' from material_name_mapping.json",
            log_type="info",
        )
        phantom_groups = material_mapping["_tissue_groups"]
        tissue_groups = {}

        # Build mapping dictionaries for entity name resolution
        mappings = self._build_entity_mappings(material_mapping)

        for group_name, tissue_list in phantom_groups.items():
            s4l_names_in_group = set(tissue_list)
            matched_tissues = []

            for tissue in available_tissues:
                entity_names = self._find_entity_names(tissue, mappings, material_mapping)
                # If any of the found entity names are in this group, include this tissue
                if any(entity_name in s4l_names_in_group for entity_name in entity_names):
                    matched_tissues.append(tissue)

            tissue_groups[group_name] = matched_tissues

        return tissue_groups

    def _build_entity_mappings(self, material_mapping: dict) -> dict:
        """Builds various mapping dictionaries for entity name resolution.

        Creates mappings to handle normalization for spaces/underscores and case differences.

        Args:
            material_mapping: Material mapping dictionary from config.

        Returns:
            Dict containing various mapping dictionaries:
            - material_to_entity: Direct material name -> entity name
            - normalized_material_to_entity: Normalized material -> entity name
            - normalized_entity_to_entity: Normalized entity -> entity name
            - cleaned_material_to_entities: Cleaned material -> list of entity names
        """
        material_to_entity = {}
        normalized_material_to_entity = {}
        normalized_entity_to_entity = {}
        cleaned_material_to_entities = {}

        for entity_name, material_name in material_mapping.items():
            if entity_name == "_tissue_groups":
                continue

            material_to_entity[material_name] = entity_name

            # Normalize: lowercase, replace spaces with underscores
            normalized_mat = material_name.lower().replace(" ", "_")
            normalized_ent = entity_name.lower()
            normalized_material_to_entity[normalized_mat] = entity_name
            normalized_entity_to_entity[normalized_ent] = entity_name

            # Simulate the cleaning that happens in extract_sar_statistics
            cleaned_mat = re.sub(r"\s*\(.*\)\s*$", "", material_name).strip().replace(")", "")
            if cleaned_mat not in cleaned_material_to_entities:
                cleaned_material_to_entities[cleaned_mat] = []
            cleaned_material_to_entities[cleaned_mat].append(entity_name)

        return {
            "material_to_entity": material_to_entity,
            "normalized_material_to_entity": normalized_material_to_entity,
            "normalized_entity_to_entity": normalized_entity_to_entity,
            "cleaned_material_to_entities": cleaned_material_to_entities,
        }

    def _find_entity_names(self, cleaned_tissue: str, mappings: dict, material_mapping: dict) -> list[str]:
        """Finds entity names from a cleaned tissue name using various matching strategies.

        Args:
            cleaned_tissue: Cleaned tissue name from simulation results.
            mappings: Dict containing various mapping dictionaries.
            material_mapping: Material mapping dictionary from config.

        Returns:
            List of entity names that match the tissue name.
        """
        entity_names = []
        material_to_entity = mappings["material_to_entity"]
        normalized_material_to_entity = mappings["normalized_material_to_entity"]
        normalized_entity_to_entity = mappings["normalized_entity_to_entity"]
        cleaned_material_to_entities = mappings["cleaned_material_to_entities"]

        # First try exact match (for cases where Sim4Life returns entity names directly)
        if cleaned_tissue in material_mapping:
            entity_names.append(cleaned_tissue)

        # Try normalized exact match
        normalized_cleaned = cleaned_tissue.lower().replace(" ", "_")
        if normalized_cleaned in normalized_entity_to_entity:
            entity_name = normalized_entity_to_entity[normalized_cleaned]
            if entity_name not in entity_names:
                entity_names.append(entity_name)

        # Try reverse mapping from material name (exact match)
        if cleaned_tissue in material_to_entity:
            entity_name = material_to_entity[cleaned_tissue]
            if entity_name not in entity_names:
                entity_names.append(entity_name)

        # Try normalized material name mapping
        if normalized_cleaned in normalized_material_to_entity:
            entity_name = normalized_material_to_entity[normalized_cleaned]
            if entity_name not in entity_names:
                entity_names.append(entity_name)

        # Try cleaned material mapping (handles cases like "Eye" -> ["Cornea", "Eye_lens", ...])
        if cleaned_tissue in cleaned_material_to_entities:
            for entity_name in cleaned_material_to_entities[cleaned_tissue]:
                if entity_name not in entity_names:
                    entity_names.append(entity_name)

        return entity_names

    def _group_by_keywords(self, available_tissues: list[str]) -> dict[str, list[str]]:
        """Groups tissues using keyword matching as fallback.

        Args:
            available_tissues: List of tissue names found in simulation results.

        Returns:
            Dict mapping group names to lists of matched tissue names.
        """
        self.logger._log(
            "  - WARNING: '_tissue_groups' not found in material mapping. Falling back to keyword-based tissue grouping.",
            log_type="warning",
        )
        return {
            group: [t for t in available_tissues if any(k in t.lower() for k in keywords)]
            for group, keywords in DEFAULT_TISSUE_GROUPS.items()
        }
