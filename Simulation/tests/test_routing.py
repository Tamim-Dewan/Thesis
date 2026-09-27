import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import (  # noqa: E402
    Base,
    Environment,
    Obstacle,
    RouteConfig,
    World,
    route_between,
)


def _blocked_environment():
    return Environment(
        world=World((0.0, 0.0, 0.0), (30.0, 30.0, 20.0), "meter"),
        obstacles=(
            Obstacle(
                "building_1",
                "building",
                (12.0, 8.0, 0.0),
                6.0,
                14.0,
                10.0,
                footprint=((12.0, 8.0), (18.0, 8.0), (18.0, 22.0), (12.0, 22.0)),
            ),
        ),
        base=Base("base_1", (3.0, 15.0, 0.0)),
        seed=1,
        effective_config={},
        generation_metadata={},
    )


def test_route_avoids_polygon_obstacle_instead_of_using_direct_line():
    environment = _blocked_environment()
    result = route_between(environment, (3.0, 15.0, 0.0), (27.0, 15.0, 0.0), RouteConfig(cruise_altitude=0.0, grid_resolution=2.0))
    assert result.feasible
    assert result.distance > 24.0
    assert any(point[1] < 8.0 or point[1] > 22.0 for point in result.route)


def test_route_can_reach_a_roof_surface_from_above():
    environment = _blocked_environment()
    result = route_between(environment, (3.0, 15.0, 0.0), (15.0, 15.0, 10.0), RouteConfig(cruise_altitude=12.0, grid_resolution=2.0))
    assert result.feasible
    assert result.route[-1] == (15.0, 15.0, 10.0)
