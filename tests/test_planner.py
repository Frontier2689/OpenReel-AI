from openreel.planner import Planner
from openreel.assets import compact_query


def test_local_planner_exact_length():
    plan = Planner("http://unused", "unused").plan("A rover crossing Mars", 120)
    assert len(plan.scenes) == 24
    assert sum(scene.duration for scene in plan.scenes) == 120
    assert all(scene.visual_prompt for scene in plan.scenes)


def test_partial_final_scene():
    plan = Planner("http://unused", "unused").plan("Ocean sunrise", 17)
    assert [scene.duration for scene in plan.scenes] == [5, 5, 5, 2]


def test_asset_query_removes_directing_noise():
    query = compact_query("A blonde woman waving hello. cinematic lighting, tracking shot")
    assert query == "blonde woman waving"
