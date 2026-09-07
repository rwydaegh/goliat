"""Regression coverage for tissue extraction from verbose simulation logs."""

from goliat.analysis.parse_verbose_log import _extract_materials_info


def test_tissue_names_with_underscores_and_malformed_lines():
    content = "\n".join(
        [
            "  grey_matter (Eartha): dielectric (eps_r=40)",
            "  skin_outer_layer (Eartha): dielectric (eps_r=30)",
            "  " + "a_" * 40 + " (Other): dielectric",
        ]
    )

    materials = _extract_materials_info(content)

    assert materials["tissues"] == [
        {"name": "grey_matter", "type": "dielectric"},
        {"name": "skin_outer_layer", "type": "dielectric"},
    ]
    assert materials["tissue_count"] == 2
