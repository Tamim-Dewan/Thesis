import importlib.util
from pathlib import Path


AUDIT_MODULE = Path(__file__).parents[1] / "render_du_map_audit.py"
SPEC = importlib.util.spec_from_file_location("render_du_map_audit", AUDIT_MODULE)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(audit)


def test_audit_hover_leads_with_the_actual_building_name_and_identifier():
    trace = audit._trace({
        "name": "Mukarram Hussain Khundker Bhaban",
        "display_name": "Mukarram Hussain Khundker Bhaban",
        "simulation_identifier": "mukarram_hussain_khundker_bhaban",
        "way_id": "12345",
        "building_type": "university",
        "footprint": [(0, 0), (1, 0), (1, 1), (0, 0)],
    }, "rgb(37, 99, 235)", "Present in simulation template", .2)

    assert trace.hovertemplate.startswith("<b>Mukarram Hussain Khundker Bhaban</b>")
    assert "Simulation ID: mukarram_hussain_khundker_bhaban" in trace.hovertemplate
    assert "Layer:" not in trace.hovertemplate
