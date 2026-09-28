"""Seeded post-earthquake scene generation built on the Phase 1 environment."""

import json
import html
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from .environment import Base, Environment, Obstacle, Point, Polygon2D, World, _ground_trace, _point_in_polygon, is_valid_point


Bounds = Tuple[float, float, float, float, float, float]
STATES = ("intact", "minor", "major", "destroyed")

# DU and fully synthetic scenes use the same lightweight, seeded damage mesh
# vocabulary. These rules are separate from the heiDATA source meshes, which
# belong to the L'Aquila benchmark package.
DAMAGE_MESH_TEMPLATE_VERSION = "synthetic_damage_mesh.v1"
DAMAGE_MESH_TEMPLATES = {
    "intact": {
        "id": "standing_full_volume.v1",
        "description": "full standing building volume",
    },
    "minor": {
        "id": "standing_minor_damage.v1",
        "description": "standing building with minor damage state",
    },
    "major": {
        "id": "major_partial_collapse.v1",
        "description": "standing section plus disjoint collapsed section with irregular debris",
    },
    "destroyed": {
        "id": "destroyed_rubble_cluster.v1",
        "description": "destroyed footprint with a dense multi-piece irregular rubble cluster",
    },
}

# DU and synthetic rubble follows the same readable visual language as the
# heiDATA storyboard: several larger broken pieces, smaller fragments, uneven
# tops, and earthy variation. These are procedural colors, not copied source
# materials or surveyed DU surface colors.
RUBBLE_COLORS = (
    "#8c5a3c",
    "#a66a3f",
    "#b97845",
    "#c08a55",
    "#76513a",
)


class SceneConfigurationError(ValueError):
    """Raised when requested scene geometry cannot be constructed."""


class SceneTemplateError(ValueError):
    """Raised when a local scene template is missing or invalid."""


@dataclass(frozen=True)
class DataSource:
    identifier: str
    title: str
    url_or_doi: str
    licence: str
    role: str
    preprocessing_version: str

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class RoadSegment:
    identifier: str
    minimum: Point
    width: float
    depth: float
    centerline: Tuple[Tuple[float, float], ...] = ()
    status: str = "clear"

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class Structure:
    identifier: str
    minimum: Point
    width: float
    depth: float
    height: float
    damage_state: str
    height_source: str = "preset"
    source_ref: Optional[str] = None
    footprint: Polygon2D = ()
    scene_role: str = "target"
    source_name: Optional[str] = None
    source_id: Optional[str] = None
    pre_asset_id: Optional[str] = None
    post_asset_id: Optional[str] = None
    visual_mesh_asset: Optional[str] = None
    visual_mesh_phase: str = "none"
    visual_provenance: str = "procedural_scene_geometry"
    # Runtime only. The source OBJ is represented in the HTML preview, while
    # the scenario JSON stores its asset id and summary instead of all faces.
    visual_mesh: Any = field(default=None, repr=False, compare=False)
    visual_face_materials: Tuple[str, ...] = field(default=(), repr=False, compare=False)

    def as_dict(self) -> Dict[str, Any]:
        values = {
            "identifier": self.identifier,
            "minimum": list(self.minimum),
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "damage_state": self.damage_state,
            "height_source": self.height_source,
            "source_ref": self.source_ref,
            "footprint": [list(point) for point in self.footprint],
            "scene_role": self.scene_role,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "pre_asset_id": self.pre_asset_id,
            "post_asset_id": self.post_asset_id,
            "visual_mesh_asset": self.visual_mesh_asset,
            "visual_mesh_phase": self.visual_mesh_phase,
            "visual_provenance": self.visual_provenance,
        }
        if self.visual_mesh is not None:
            mesh_summary = {
                "vertex_count": int(len(self.visual_mesh.vertices)),
                "face_count": int(len(self.visual_mesh.faces)),
                "minimum": self.visual_mesh.minimum.tolist(),
                "maximum": self.visual_mesh.maximum.tolist(),
                "extent": self.visual_mesh.extent.tolist(),
                "axis_rule": "source_xyz_to_local_xzy.v1",
            }
            materials = sorted({material for material in self.visual_face_materials if material})
            if materials:
                mesh_summary["material_count"] = len(materials)
                mesh_summary["materials"] = materials
            values["visual_mesh_summary"] = mesh_summary
        else:
            values["visual_mesh_summary"] = None
        return values


@dataclass(frozen=True)
class CandidateSite:
    identifier: str
    kind: str
    position: Point
    surface_ref: str
    clearance_radius: float = 1.0
    allowed_use: str = "task"

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class IndoorRoom:
    identifier: str
    floor_id: str
    minimum: Point
    width: float
    depth: float
    height: float
    room_type: str
    source_label: str

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class IndoorConnection:
    identifier: str
    kind: str
    from_room: str
    to_room: str
    status: str = "open"

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class ScenePreset:
    identifier: str
    version: str
    severity: str
    damage_proportions: Mapping[str, float]
    road_block_probability: float
    rubble_probability: float
    broken_floor_probability: float
    elevated_debris_probability: float
    indoor_probabilities: Mapping[str, float]

    def as_dict(self) -> Dict[str, Any]: return dict(asdict(self))


PRESETS = {
    "light": ((.55, .30, .10, .05), .10, .25, .10, .10, (.10, .05, .05, .05, .25)),
    "moderate": ((.25, .30, .30, .15), .30, .65, .40, .35, (.30, .20, .25, .20, .65)),
    "severe": ((.05, .15, .40, .40), .55, .95, .70, .60, (.55, .45, .55, .45, .95)),
}


def _is_geospatial_mode(mode: Optional[str]) -> bool:
    return mode in ("laquila_informed", "heidata_full", "heidata_neighborhood")


def load_scene_preset(identifier: str) -> ScenePreset:
    if identifier not in PRESETS: raise SceneConfigurationError("unknown preset: {}".format(identifier))
    mix, road, rubble, floor, debris, indoor = PRESETS[identifier]
    return ScenePreset("earthquake.v1", "earthquake.v1", identifier, dict(zip(STATES, mix)), road, rubble, floor, debris,
                       dict(zip(("damaged_room", "blocked_door", "blocked_corridor", "damaged_stair", "indoor_debris"), indoor)))


@dataclass(frozen=True)
class SceneConfig:
    mode: str = "synthetic"
    severity: str = "moderate"
    world_bounds: Optional[Bounds] = None
    base_clearance: float = 12.0
    uav_count: int = 3
    ground_candidate_count: int = 12
    elevated_candidate_count: int = 6
    indoor_candidate_count: int = 6
    preset_id: Optional[str] = None
    template_path: Optional[str] = None
    seed: int = 0

    def validate(self) -> None:
        if self.mode not in ("synthetic", "du_outdoor", "real_building", "laquila_informed", "heidata_full", "heidata_neighborhood"): raise SceneConfigurationError("unsupported mode: {}".format(self.mode))
        load_scene_preset(self.preset_id or self.severity)
        if self.base_clearance <= 0 or self.uav_count < 1: raise SceneConfigurationError("base_clearance and uav_count must be positive")
        if min(self.ground_candidate_count, self.elevated_candidate_count, self.indoor_candidate_count) < 0: raise SceneConfigurationError("candidate counts must be non-negative")

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class DisasterScene:
    environment: Environment
    roads: Tuple[RoadSegment, ...]
    structures: Tuple[Structure, ...]
    indoor_rooms: Tuple[IndoorRoom, ...]
    indoor_connections: Tuple[IndoorConnection, ...]
    uav_initial_positions: Tuple[Point, ...]
    candidate_sites: Tuple[CandidateSite, ...]
    preset: ScenePreset
    provenance: Tuple[DataSource, ...]
    generation_metadata: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {"environment": {"world": asdict(self.environment.world), "obstacles": [asdict(x) for x in self.environment.obstacles], "base": asdict(self.environment.base), "seed": self.environment.seed}, "roads": [x.as_dict() for x in self.roads], "structures": [x.as_dict() for x in self.structures], "indoor_rooms": [x.as_dict() for x in self.indoor_rooms], "indoor_connections": [x.as_dict() for x in self.indoor_connections], "uav_initial_positions": [list(x) for x in self.uav_initial_positions], "candidate_sites": [x.as_dict() for x in self.candidate_sites], "preset": self.preset.as_dict(), "provenance": [x.as_dict() for x in self.provenance], "generation_metadata": dict(self.generation_metadata)}


def _template_path(config: SceneConfig) -> Path:
    if config.template_path: return Path(config.template_path)
    if config.mode == "du_outdoor":
        name = "du_science_complex.json"
    elif config.mode in ("laquila_informed", "heidata_full", "heidata_neighborhood"):
        name = "laquila_informed_layout.json"
    else:
        name = "real_building.json"
    return Path(__file__).parents[1] / "data" / "templates" / name


def load_scene_template(path: str) -> Mapping[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error: raise SceneTemplateError("template is unavailable: {}".format(path)) from error
    except json.JSONDecodeError as error: raise SceneTemplateError("template is corrupt: {}".format(path)) from error
    if not isinstance(value, dict) or "bounds" not in value or "structures" not in value: raise SceneTemplateError("template is unsupported or incomplete: {}".format(path))
    bounds=value["bounds"]
    if len(bounds)!=6 or any(float(bounds[index])>=float(bounds[index+3]) for index in range(3)): raise SceneTemplateError("template bounds are invalid: {}".format(path))
    for structure in value["structures"]:
        footprint=structure.get("footprint")
        if footprint and any(point[0]<bounds[0] or point[1]<bounds[1] or point[0]>bounds[3] or point[1]>bounds[4] for point in footprint): raise SceneTemplateError("structure footprint is outside template bounds: {}".format(structure.get("identifier","unknown")))
    for road in value.get("roads", []):
        for point in road.get("centerline", ()):
            if point[0] < bounds[0] or point[1] < bounds[1] or point[0] > bounds[3] or point[1] > bounds[4]:
                raise SceneTemplateError("road centerline is outside template bounds: {}".format(road.get("identifier", "unknown")))
    return value


def _bounds(config: SceneConfig, template: Optional[Mapping[str, Any]]) -> Bounds:
    if config.world_bounds: return config.world_bounds
    if template: return tuple(template["bounds"])  # type: ignore[return-value]
    return (0., 0., 0., 100., 100., 60.)


def _largest_remainder(preset: ScenePreset, count: int) -> Dict[str, int]:
    raw = {state: preset.damage_proportions[state] * count for state in STATES}; result = {state: int(raw[state]) for state in STATES}
    for state in ("destroyed", "major", "minor", "intact"):
        if sum(result.values()) >= count: break
        result[state] += 1
    return result


def _overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _synthetic_layout(bounds: Bounds, rng: random.Random, preset: ScenePreset) -> Tuple[Tuple[RoadSegment, ...], Tuple[Structure, ...]]:
    x0,y0,_,x1,y1,_=bounds; cx=(x0+x1)/2; cy=(y0+y1)/2; rw=8.
    roads=(RoadSegment("road_east_west",(x0,cy-rw/2,0),x1-x0,rw,((x0,cy),(x1,cy))),RoadSegment("road_north_south",(cx-rw/2,y0,0),rw,y1-y0,((cx,y0),(cx,y1))))
    counts=_largest_remainder(preset,8); states=[s for s in STATES for _ in range(counts[s])]; rng.shuffle(states); structures=[]
    lots=[(x0+8,y0+8,cx-rw/2-3,cy-rw/2-3),(cx+rw/2+3,y0+8,x1-8,cy-rw/2-3),(x0+8,cy+rw/2+3,cx-rw/2-3,y1-8),(cx+rw/2+3,cy+rw/2+3,x1-8,y1-8)]
    for index,state in enumerate(states):
        lx0,ly0,lx1,ly1=lots[index%4]
        # Each lot contains two disjoint slots. The earlier fully random
        # packing could fail for an otherwise valid seed when the first large
        # rectangle blocked the remaining lot area.
        slot=index//4
        slot_gap=2.0
        slot_width=(lx1-lx0-slot_gap)/2.0
        slot_x0=lx0+slot*(slot_width+slot_gap)
        slot_x1=slot_x0+slot_width
        max_width=min(18.0,slot_width)
        max_depth=min(18.0,ly1-ly0)
        if max_width < 10.0 or max_depth < 10.0:
            raise SceneConfigurationError("world cannot fit requested structured layout")
        w=rng.uniform(10.0,max_width)
        d=rng.uniform(10.0,max_depth)
        x=rng.uniform(slot_x0,slot_x1-w)
        y=rng.uniform(ly0,ly1-d)
        structures.append(Structure("structure_{}".format(index+1),(x,y,0),w,d,rng.uniform(12,35),state,footprint=_rectangle_polygon(x,y,w,d)))
    return roads,tuple(structures)


def _template_layout(template: Mapping[str, Any], preset: ScenePreset, rng: random.Random) -> Tuple[Tuple[RoadSegment, ...], Tuple[Structure, ...], Tuple[DataSource, ...]]:
    damageable=[item for item in template["structures"] if item.get("scene_role", "target")=="target"]
    states=[s for s,n in _largest_remainder(preset,len(damageable)).items() for _ in range(n)]
    rng.shuffle(states)
    roads=tuple(RoadSegment(x["identifier"],tuple(x["minimum"]),x["width"],x["depth"],tuple(tuple(point) for point in x.get("centerline",())),x.get("status","clear")) for x in template.get("roads",[]))
    state_iter=iter(states)
    structures=tuple(Structure(x["identifier"],tuple(x["minimum"]),x["width"],x["depth"],x["height"],next(state_iter) if x.get("scene_role", "target")=="target" else "intact",x.get("height_source","source"),x.get("source_ref"),tuple(tuple(point) for point in x.get("footprint",())),x.get("scene_role", "target")) for x in template["structures"])
    provenance=tuple(DataSource(**x) for x in template.get("provenance",[])); return roads,structures,provenance


def _damage_template_id(damage_state: str) -> str:
    """Return the named visual rule for one generated damage state."""
    try:
        return str(DAMAGE_MESH_TEMPLATES[damage_state]["id"])
    except KeyError as error:
        raise SceneConfigurationError("unknown damage state for mesh template: {}".format(damage_state)) from error


def _damage(
    structures: Tuple[Structure, ...],
    rng: random.Random,
    preset: ScenePreset,
    source_exact: bool = False,
) -> Tuple[Obstacle, ...]:
    """Generate airborne-UAV collision objects from building damage only.

    Roads are deliberately not runtime geometry: they help source-map curation and
    synthetic lot placement, but flying UAVs do not navigate through road lanes.
    """
    obstacles=[]
    for s in structures:
        x,y,z=s.minimum; polygon=s.footprint or _rectangle_polygon(x,y,s.width,s.depth)
        template_id = _damage_template_id(s.damage_state) if s.scene_role == "target" else None
        if s.damage_state in ("intact","minor"):
            obstacles.append(_polygon_obstacle(
                "solid_"+s.identifier,
                "building",
                polygon,
                s.height,
                s,
                damage_template_id=template_id,
            ))
        elif s.damage_state=="major":
            standing,collapsed=_partition_polygon(polygon)
            if standing:
                obstacles.append(_polygon_obstacle(
                    "standing_"+s.identifier,
                    "building",
                    standing,
                    s.height,
                    s,
                    visual_top_profile=_uneven_top_profile(
                        len(standing[:-1] if len(standing) > 1 and standing[0] == standing[-1] else standing),
                        rng,
                        .62,
                    ),
                    damage_template_id=template_id,
                ))
            if not source_exact and rng.random()<preset.broken_floor_probability and collapsed:
                obstacles.append(_polygon_obstacle(
                    "floor_"+s.identifier,
                    "broken_floor",
                    collapsed,
                    max(1.5,s.height*.04),
                    s,
                    z=max(2,s.height*.45),
                    damage_template_id=template_id,
                ))
            if not source_exact and rng.random()<preset.elevated_debris_probability and collapsed:
                for debris_index, debris_polygon in enumerate(_irregular_fragment_polygons(collapsed,rng,2,(.12,.24))):
                    debris_height=(4.0,7.0,10.0)[(len(s.identifier)+debris_index)%3]
                    obstacles.append(_polygon_obstacle(
                        "debris_{}_{}".format(s.identifier,debris_index+1), "elevated_debris", debris_polygon,
                        debris_height, s,
                        z=max(3,s.height*rng.uniform(.18,.34)),
                        rotation_degrees=rng.uniform(-28,28),
                        visual_top_profile=_uneven_top_profile(len(debris_polygon),rng,.32),
                        damage_template_id=template_id,
                    ))
        # A major-damage marker always has a visible collapsed section, so it
        # must also receive a rubble cluster. The preset still controls the
        # broader scenario severity, while this rule prevents a misleading
        # major marker with no debris in the operational preview.
        # Consume the historical seeded draw for synthetic modes only.
        if not source_exact:
            rng.random()
        has_rubble = s.damage_state in {"major", "destroyed"}
        if s.damage_state in ("major","destroyed") and has_rubble:
            # Major damage has a standing half and a collapsed half. Rubble
            # belongs to the collapsed half only; using the source footprint
            # here would place debris over the visually intact building.
            rubble_parent = polygon
            if s.damage_state == "major":
                _, rubble_parent = _partition_polygon(polygon)
            if not rubble_parent:
                continue
            rubble_height_range = (0.16, 0.30) if s.damage_state == "destroyed" else (0.12, 0.24)
            rubble_height = min(
                7.5,
                max(2.8 if s.damage_state == "destroyed" else 1.8, s.height * rng.uniform(*rubble_height_range)),
            )
            rubble_density = 1.0 if source_exact else preset.rubble_probability
            for rubble_index, rubble_polygon in enumerate(
                _rubble_polygons(rubble_parent, rng, s.damage_state, rubble_density)
            ):
                obstacles.append(_polygon_obstacle(
                    "rubble_{}_{}".format(s.identifier,rubble_index+1), "ground_rubble", rubble_polygon,
                    min(7.5, rubble_height * rng.uniform(.58, 1.18)), s,
                    visual_top_profile=_uneven_top_profile(len(rubble_polygon),rng,.28),
                    damage_template_id=template_id,
                ))
    return tuple(obstacles)


def _rectangle_polygon(x: float, y: float, width: float, depth: float) -> Polygon2D:
    return ((x,y),(x+width,y),(x+width,y+depth),(x,y+depth))


def _polygon_bbox(polygon: Polygon2D) -> Tuple[float,float,float,float]:
    xs=[point[0] for point in polygon]; ys=[point[1] for point in polygon]
    return min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)


def _polygon_obstacle(
    identifier: str,
    kind: str,
    polygon: Polygon2D,
    height: float,
    structure: Structure,
    z: float = 0.0,
    rotation_degrees: float = 0.0,
    visual_top_profile: Tuple[float, ...] = (),
    damage_template_id: Optional[str] = None,
) -> Obstacle:
    x,y,width,depth=_polygon_bbox(polygon)
    return Obstacle(
        identifier,
        kind,
        (x,y,z),
        max(width,.01),
        max(depth,.01),
        max(height,.01),
        parent_structure_id=structure.identifier,
        source_ref=structure.source_ref,
        footprint=polygon,
        rotation_degrees=rotation_degrees,
        visual_top_profile=visual_top_profile,
        damage_template_id=damage_template_id,
    )


def _polygon_centroid(polygon: Polygon2D) -> Tuple[float,float]:
    return sum(point[0] for point in polygon)/len(polygon),sum(point[1] for point in polygon)/len(polygon)


def _clip_polygon(polygon: Polygon2D, axis: int, threshold: float, keep_less: bool) -> Polygon2D:
    result=[]
    for current, previous in zip(polygon, polygon[-1:]+polygon[:-1]):
        current_inside=current[axis] <= threshold if keep_less else current[axis] >= threshold
        previous_inside=previous[axis] <= threshold if keep_less else previous[axis] >= threshold
        if current_inside != previous_inside:
            ratio=(threshold-previous[axis])/(current[axis]-previous[axis] or 1e-12)
            result.append((previous[0]+ratio*(current[0]-previous[0]),previous[1]+ratio*(current[1]-previous[1])))
        if current_inside: result.append(current)
    return tuple(result)


def _partition_polygon(polygon: Polygon2D) -> Tuple[Polygon2D,Polygon2D]:
    """Split a footprint into disjoint standing and collapsed sections.

    The earlier two-threshold split produced overlapping halves. That made a
    standing volume and its rubble occupy the same footprint, so the preview
    could show debris on the apparently intact side. A single centroid cut
    keeps the two sections edge-to-edge and makes the collapsed side an
    unambiguous parent region for rubble, broken floors, and elevated debris.
    """
    cx,cy=_polygon_centroid(polygon); xs=[point[0] for point in polygon]; ys=[point[1] for point in polygon]
    axis=0 if max(xs)-min(xs)>=max(ys)-min(ys) else 1
    threshold=cx if axis==0 else cy
    collapsed=_clip_polygon(polygon,axis,threshold,True)
    standing=_clip_polygon(polygon,axis,threshold,False)
    return standing,collapsed


def _uneven_top_profile(vertex_count: int, rng: random.Random, minimum_fraction: float) -> Tuple[float,...]:
    """Return a repeatable non-flat top profile within an obstacle's envelope."""
    profile=[rng.uniform(minimum_fraction,.92) for _ in range(vertex_count)]
    highest=rng.randrange(vertex_count)
    lowest=(highest+rng.randrange(1,vertex_count))%vertex_count
    profile[highest]=1.0
    profile[lowest]=minimum_fraction
    return tuple(profile)


def _irregular_fragment_polygons(
    polygon: Polygon2D,
    rng: random.Random,
    count: int,
    radius_fraction: Tuple[float,float],
    existing: Iterable[Polygon2D] = (),
) -> Tuple[Polygon2D,...]:
    """Sample non-overlapping five-to-eight-sided fragments wholly inside a footprint."""
    x,y,width,depth=_polygon_bbox(polygon); result=list(existing)
    for _ in range(count):
        for _ in range(320):
            cx=rng.uniform(x+width*.08,x+width*.92); cy=rng.uniform(y+depth*.08,y+depth*.92)
            if not _point_in_polygon(cx,cy,polygon):
                continue
            sides=rng.randint(5,8); rotation=rng.uniform(0,math.tau)
            radius_x=max(.55,width*rng.uniform(*radius_fraction)); radius_y=max(.55,depth*rng.uniform(*radius_fraction))
            candidate=tuple(
                (cx+math.cos(rotation+math.tau*index/sides+rng.uniform(-.12,.12))*radius_x*rng.uniform(.72,1.0),
                 cy+math.sin(rotation+math.tau*index/sides+rng.uniform(-.12,.12))*radius_y*rng.uniform(.72,1.0))
                for index in range(sides)
            )
            if _polygon_area(candidate) <= .05 or not all(_point_in_polygon(px,py,polygon) for px,py in candidate):
                continue
            if any(_polygons_intersect(candidate,prior) for prior in result):
                continue
            result.append(candidate)
            break
    return tuple(result)


def _rubble_polygons(
    polygon: Polygon2D,
    rng: random.Random,
    damage_state: str,
    density: float = 1.0,
) -> Tuple[Polygon2D,...]:
    """Create larger three dimensional rubble clusters for collapsed structures.

    Destroyed structures receive a denser field than major damage. The first
    pass creates large chunks, and the second pass fills the cluster with
    smaller pieces while preserving navigable gaps and the parent footprint.
    """
    density = max(0.0, min(1.0, density))
    density_bonus = round(density * 2)
    fragment_bonus = round(density * 3)
    if damage_state == "destroyed":
        large_count, small_count = 5 + density_bonus, 8 + fragment_bonus
        large_radius, small_radius = (.14, .30), (.06, .16)
    else:
        # Major damage has a smaller collapsed half, so use fewer but more
        # legible chunks there. Destroyed footprints remain visibly denser.
        large_count, small_count = 2 + density_bonus, 4 + fragment_bonus
        large_radius, small_radius = (.14, .28), (.065, .16)
    large = _irregular_fragment_polygons(polygon, rng, large_count, large_radius)
    return _irregular_fragment_polygons(polygon, rng, small_count, small_radius, existing=large)


def _base(bounds: Bounds, clearance: float, configured_position: Optional[Point] = None) -> Base:
    x0,y0,_,_,_,_=bounds
    return Base("base_1",configured_position or (x0+clearance/2,y0+clearance/2,0))


def _candidates(env: Environment, structures: Iterable[Structure], base: Base, ground: int, elevated: int) -> Tuple[CandidateSite,...]:
    result=[]; x0,y0,_,x1,y1,_=(*env.world.minimum,*env.world.maximum)
    for index in range(ground):
        for row in range(20):
            point=(x0+5+((index*17+row*7)%(int(x1-x0-10))),y0+5+((index*29+row*11)%(int(y1-y0-10))),0.)
            if is_valid_point(env,point): result.append(CandidateSite("ground_{}".format(index+1),"ground",point,"ground")); break
        else: raise SceneConfigurationError("world has insufficient valid ground candidate capacity")
    supports=[s for s in structures if s.damage_state in ("intact","minor")]
    if elevated and not supports: raise SceneConfigurationError("scene has no accessible elevated support surfaces")
    support_points=[]
    for support in supports:
        polygon=support.footprint or _rectangle_polygon(support.minimum[0],support.minimum[1],support.width,support.depth)
        sx,sy,sw,sd=_polygon_bbox(polygon)
        for row in range(1,8):
            for column in range(1,8):
                point=(sx+sw*column/8,sy+sd*row/8)
                if _point_in_polygon(point[0],point[1],polygon) and point not in [item[0] for item in support_points if item[1]==support.identifier]:
                    support_points.append((point,support.identifier,support.height)); break
            if sum(item[1]==support.identifier for item in support_points)>=12: break
    if elevated>len(support_points): raise SceneConfigurationError("scene has insufficient unique elevated candidate capacity")
    for index,(point,support_id,height) in enumerate(support_points[:elevated]):
        result.append(CandidateSite("elevated_{}".format(index+1),"elevated",(point[0],point[1],height),support_id))
    return tuple(result)


def generate_disaster_scene(config: SceneConfig, seed: Optional[int] = None) -> DisasterScene:
    config.validate(); actual_seed=config.seed if seed is None else seed; rng=random.Random(actual_seed); template=None; laquila_metadata={}
    laquila_layout_path = None
    if config.mode in ("laquila_informed", "heidata_full", "heidata_neighborhood"):
        laquila_layout_path = _template_path(config)
        try:
            from .laquila_informed import load_laquila_layout

            _, template, _ = load_laquila_layout(str(laquila_layout_path))
        except Exception as error:
            if isinstance(error, SceneConfigurationError):
                raise
            raise SceneTemplateError(str(error)) from error
    if config.mode in ("du_outdoor","real_building"): template=load_scene_template(str(_template_path(config)))
    if config.mode=="real_building":
        if not template.get("indoor_rooms") or not template.get("exterior_shell"): raise SceneTemplateError("real building template requires exterior shell and indoor rooms")
    bounds=_bounds(config,template); world=World(tuple(bounds[:3]),tuple(bounds[3:]),"meter")
    preset=load_scene_preset(config.preset_id or config.severity)
    if config.mode == "synthetic":
        _layout_roads,structures=_synthetic_layout(bounds,rng,preset); provenance=()
    elif config.mode in ("laquila_informed", "heidata_full", "heidata_neighborhood"):
        from .laquila_informed import build_laquila_structure_specs

        specs, provenance_values, laquila_metadata = build_laquila_structure_specs(
            str(laquila_layout_path), bounds, seed=actual_seed,
        )
        structures = tuple(Structure(**spec) for spec in specs)
        provenance = tuple(DataSource(**value) for value in provenance_values)
    else:
        _template_roads,structures,provenance=_template_layout(template,preset,rng)
    obstacles = _damage(structures, rng, preset, source_exact=config.mode in ("laquila_informed", "heidata_full", "heidata_neighborhood"))
    configured_position = None
    if template and template.get("base_position"):
        configured_position = tuple(float(value) for value in template["base_position"])
    base = _base(bounds, config.base_clearance, configured_position)
    if any(o.minimum[0] <= base.position[0] <= o.maximum[0] and o.minimum[1] <= base.position[1] <= o.maximum[1] for o in obstacles): raise SceneConfigurationError("base clearance area intersects generated geometry")
    env=Environment(world,obstacles,base,actual_seed,config.as_dict(),{"mode":config.mode,"preset_version":preset.version})
    candidates=_candidates(env,structures,base,config.ground_candidate_count,config.elevated_candidate_count)
    scene=DisasterScene(
        env,
        (),
        structures,
        (),
        (),
        tuple(base.position for _ in range(config.uav_count)),
        candidates,
        preset,
        provenance,
        {
            "mode": config.mode,
            "seed": actual_seed,
            "template_version": None if not template else template.get("version"),
            **laquila_metadata,
            "damage_mesh_template_version": DAMAGE_MESH_TEMPLATE_VERSION,
            "damage_mesh_templates": {
                state: dict(values) for state, values in DAMAGE_MESH_TEMPLATES.items()
            },
            "imputed_values": [],
        },
    )
    validate_scene_geometry(scene)
    return scene


def is_valid_candidate_site(scene: DisasterScene, site: CandidateSite) -> bool:
    if site.kind=="ground": return is_valid_point(scene.environment,site.position)
    support=next((s for s in scene.structures if s.identifier==site.surface_ref),None)
    polygon=support.footprint if support else ()
    return support is not None and site.position[2]==support.height and _point_in_polygon(site.position[0],site.position[1],polygon or _rectangle_polygon(support.minimum[0],support.minimum[1],support.width,support.depth))


def is_valid_indoor_route(scene: DisasterScene, connection_ids: Iterable[str]) -> bool:
    available={item.identifier:item for item in scene.indoor_connections}
    return all(identifier in available and available[identifier].status=="open" for identifier in connection_ids)


def _polygon_area(polygon: Polygon2D) -> float:
    return abs(sum(polygon[index - 1][0] * polygon[index][1] - polygon[index][0] * polygon[index - 1][1] for index in range(len(polygon))) / 2.0)


def _segments_touch(first_start: Tuple[float, float], first_end: Tuple[float, float], second_start: Tuple[float, float], second_end: Tuple[float, float]) -> bool:
    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    values=(orientation(first_start,first_end,second_start),orientation(first_start,first_end,second_end),orientation(second_start,second_end,first_start),orientation(second_start,second_end,first_end))
    if values[0] == 0 and min(first_start[0],first_end[0]) <= second_start[0] <= max(first_start[0],first_end[0]) and min(first_start[1],first_end[1]) <= second_start[1] <= max(first_start[1],first_end[1]): return True
    if values[1] == 0 and min(first_start[0],first_end[0]) <= second_end[0] <= max(first_start[0],first_end[0]) and min(first_start[1],first_end[1]) <= second_end[1] <= max(first_start[1],first_end[1]): return True
    if values[2] == 0 and min(second_start[0],second_end[0]) <= first_start[0] <= max(second_start[0],second_end[0]) and min(second_start[1],second_end[1]) <= first_start[1] <= max(second_start[1],second_end[1]): return True
    if values[3] == 0 and min(second_start[0],second_end[0]) <= first_end[0] <= max(second_start[0],second_end[0]) and min(second_start[1],second_end[1]) <= first_end[1] <= max(second_start[1],second_end[1]): return True
    return ((values[0] > 0) != (values[1] > 0)) and ((values[2] > 0) != (values[3] > 0))


def _polygons_intersect(first: Polygon2D, second: Polygon2D) -> bool:
    for index in range(len(first)):
        for other_index in range(len(second)):
            if _segments_touch(first[index - 1], first[index], second[other_index - 1], second[other_index]): return True
    return _point_in_polygon(first[0][0], first[0][1], second) or _point_in_polygon(second[0][0], second[0][1], first)


def validate_scene_geometry(scene: DisasterScene) -> None:
    """Validate persisted scene geometry without changing source-derived shapes."""
    world=scene.environment.world; x0,y0,z0=world.minimum; x1,y1,z1=world.maximum
    source_exact = _is_geospatial_mode(scene.generation_metadata.get("mode"))
    source_overlap_check = None
    if source_exact:
        try:
            from heidata_benchmark.geospatial import footprints_overlap
            source_overlap_check = footprints_overlap
        except ImportError as error:
            raise SceneConfigurationError("exact L'Aquila validation needs the local geospatial source package") from error
    if scene.roads:
        raise SceneConfigurationError("airborne UAV scene must not contain active road geometry")
    for index, first in enumerate(scene.structures):
        polygon=first.footprint or _rectangle_polygon(first.minimum[0],first.minimum[1],first.width,first.depth)
        if first.width <= 0 or first.depth <= 0 or first.height <= 0 or _polygon_area(polygon) <= 0: raise SceneConfigurationError("structure geometry is invalid: {}".format(first.identifier))
        if any(not x0 <= point[0] <= x1 or not y0 <= point[1] <= y1 for point in polygon): raise SceneConfigurationError("structure footprint is outside world: {}".format(first.identifier))
        for second in scene.structures[index+1:]:
            second_polygon=second.footprint or _rectangle_polygon(second.minimum[0],second.minimum[1],second.width,second.depth)
            overlaps = (
                source_overlap_check(polygon, second_polygon, 0.05)
                if source_overlap_check is not None
                else _polygons_intersect(polygon, second_polygon)
            )
            if overlaps: raise SceneConfigurationError("structure footprints overlap: {} and {}".format(first.identifier,second.identifier))
    for obstacle in scene.environment.obstacles:
        if obstacle.width <= 0 or obstacle.depth <= 0 or obstacle.height <= 0: raise SceneConfigurationError("obstacle has non-positive dimensions: {}".format(obstacle.identifier))
        if obstacle.minimum[0] < x0 or obstacle.minimum[1] < y0 or obstacle.minimum[2] < z0 or obstacle.maximum[0] > x1 or obstacle.maximum[1] > y1 or obstacle.maximum[2] > z1: raise SceneConfigurationError("obstacle is outside world: {}".format(obstacle.identifier))
        if obstacle.footprint and any(not x0 <= point[0] <= x1 or not y0 <= point[1] <= y1 for point in obstacle.footprint): raise SceneConfigurationError("obstacle footprint is outside world: {}".format(obstacle.identifier))
        if obstacle.footprint and _polygon_area(obstacle.footprint) <= 0: raise SceneConfigurationError("obstacle footprint is degenerate: {}".format(obstacle.identifier))
        if obstacle.kind == "road_block" or obstacle.road_segment_id:
            raise SceneConfigurationError("airborne UAV scene must not contain road blocks: {}".format(obstacle.identifier))
        if obstacle.visual_top_profile:
            footprint=obstacle.footprint or ()
            footprint_points = footprint[:-1] if len(footprint) > 1 and footprint[0] == footprint[-1] else footprint
            if len(obstacle.visual_top_profile) != len(footprint_points):
                raise SceneConfigurationError("visual top profile does not match footprint: {}".format(obstacle.identifier))
            if any(not 0 < fraction <= 1 for fraction in obstacle.visual_top_profile):
                raise SceneConfigurationError("visual top profile is outside collision envelope: {}".format(obstacle.identifier))
    if scene.environment.base.position[2] != z0 or not is_valid_point(scene.environment,scene.environment.base.position): raise SceneConfigurationError("base is not valid ground space")
    positions=[site.position for site in scene.candidate_sites]
    if len(positions)!=len(set(positions)): raise SceneConfigurationError("candidate sites are not unique")
    for site in scene.candidate_sites:
        if not is_valid_candidate_site(scene,site): raise SceneConfigurationError("candidate site is invalid: {}".format(site.identifier))


def _polygon_triangles(polygon: Polygon2D) -> Tuple[Tuple[int,int,int], ...]:
    points=list(polygon[:-1] if len(polygon)>1 and polygon[0]==polygon[-1] else polygon)
    if len(points)<3: return ()
    area=sum(points[index][0]*points[(index+1)%len(points)][1]-points[(index+1)%len(points)][0]*points[index][1] for index in range(len(points)))
    if area<0: points.reverse()
    remaining=list(range(len(points))); triangles=[]
    while len(remaining)>3:
        found=False
        for index in range(len(remaining)):
            previous=remaining[index-1]; current=remaining[index]; following=remaining[(index+1)%len(remaining)]
            ax,ay=points[previous]; bx,by=points[current]; cx,cy=points[following]
            if (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)<=0: continue
            triangle=((ax,ay),(bx,by),(cx,cy))
            if any(_point_in_triangle(points[other],triangle) for other in remaining if other not in (previous,current,following)): continue
            triangles.append((previous,current,following)); remaining.pop(index); found=True; break
        if not found: break
    if len(remaining)==3: triangles.append(tuple(remaining))
    return tuple(triangles)


def _point_in_triangle(point: Tuple[float,float], triangle: Tuple[Tuple[float,float],Tuple[float,float],Tuple[float,float]]) -> bool:
    def sign(a,b,c): return (a[0]-c[0])*(b[1]-c[1])-(b[0]-c[0])*(a[1]-c[1])
    first=sign(point,triangle[0],triangle[1]); second=sign(point,triangle[1],triangle[2]); third=sign(point,triangle[2],triangle[0])
    return not ((first<0 and second>0) or (first>0 and second<0) or (second<0 and third>0) or (second>0 and third<0))


def _polygon_prism_trace(polygon: Polygon2D, z0: float, z1: float, color: str, label: str, opacity: float = .62, top_profile: Tuple[float,...] = ()):
    import plotly.graph_objects as go
    points=list(polygon[:-1] if len(polygon)>1 and polygon[0]==polygon[-1] else polygon); triangles=_polygon_triangles(polygon)
    if top_profile and len(top_profile) != len(points):
        raise SceneConfigurationError("visual top profile does not match rendered footprint: {}".format(label))
    top_heights=[z1 if not top_profile else z0+(z1-z0)*fraction for fraction in (top_profile or tuple(1.0 for _ in points))]
    vertices=[(x,y,z0) for x,y in points]+[(x,y,top_heights[index]) for index,(x,y) in enumerate(points)]; n=len(points); faces=[]
    for a,b,c in triangles: faces.extend(((a,c,b),(a+n,b+n,c+n)))
    for index in range(n):
        following=(index+1)%n; faces.extend(((index,following,following+n),(index,following+n,index+n)))
    return go.Mesh3d(x=[v[0] for v in vertices],y=[v[1] for v in vertices],z=[v[2] for v in vertices],i=[f[0] for f in faces],j=[f[1] for f in faces],k=[f[2] for f in faces],name=label,color=color,opacity=opacity,hovertext=label,hoverinfo="text")


def _obstacle_visual_trace(
    obstacle: Obstacle,
    color: str,
    label: str,
    opacity: float,
    hover_text: Optional[str] = None,
):
    footprint=obstacle.footprint or _rectangle_polygon(obstacle.minimum[0],obstacle.minimum[1],obstacle.width,obstacle.depth)
    trace = _polygon_prism_trace(footprint,obstacle.minimum[2],obstacle.maximum[2],color,label,opacity,obstacle.visual_top_profile)
    if hover_text is not None:
        trace.update(hovertext=hover_text, hoverinfo="text")
    return trace


def _structure_visual_label(structure: Structure) -> str:
    """Return a clear label for a source or derived building mesh."""
    if structure.visual_mesh_phase == "context_footprint":
        return "OSM context footprint, no heiDATA mesh"
    if structure.visual_mesh_phase in {"pre", "source_pre"}:
        if structure.damage_state == "minor":
            return "source pre-event building mesh — minor state"
        return "source pre-event building mesh — intact"
    if structure.visual_mesh_phase in {"post", "source_post"}:
        return "source post-event {} damage mesh".format(structure.damage_state)
    if structure.visual_mesh_phase == "derived_partial":
        return "derived partial-collapse mesh"
    if structure.visual_mesh_phase == "derived_damage":
        return "derived OSM damage mesh"
    if structure.visual_mesh_phase == "footprint_extrusion":
        return "exact OSM footprint extrusion"
    if structure.visual_mesh_phase == "rubble_only":
        return "destroyed footprint, rubble only"
    return "standing building volume"


def _source_mesh_color(visual_mesh_phase: str, damage_state: Optional[str] = None) -> str:
    """Return a readable state-aware color for source or derived geometry."""
    if damage_state in {"intact", "minor", "major", "destroyed"}:
        return {
            "intact": "#8198ad",
            "minor": "#c58b35",
            "major": "#a95735",
            "destroyed": "#704b43",
        }[damage_state]
    return {
        "pre": "#416b9a",
        "source_pre": "#416b9a",
        "post": "#9a5b39",
        "source_post": "#9a5b39",
        "derived_partial": "#c56b35",
        "derived_damage": "#c56b35",
        "footprint_extrusion": "#64748b",
        "rubble_only": "#7f1d1d",
    }.get(visual_mesh_phase, "#8c564b")


def _source_mesh_opacity(visual_mesh_phase: str, damage_state: Optional[str] = None) -> float:
    """Keep source meshes solid while leaving collapse debris legible."""
    if damage_state == "destroyed":
        return 0.68
    if damage_state == "major":
        return 0.76
    if damage_state == "minor":
        return 0.84
    if damage_state == "intact":
        return 0.86
    return 0.80 if visual_mesh_phase in {"post", "source_post"} else 0.82


def _structure_visual_color(structure: Structure) -> str:
    return _source_mesh_color(structure.visual_mesh_phase, structure.damage_state)


def _material_face_color(material: str, damage_state: str, fallback: str) -> str:
    """Map the OBJ material names to a restrained architectural palette."""
    name = str(material).lower()
    if not name:
        return fallback
    if "glass" in name or "window" in name:
        return "#355d73"
    if "metal" in name or "steel" in name or "brushed" in name:
        return "#59636b"
    if "roof" in name or "tile" in name:
        return "#7b4b3b"
    if "plaster" in name or "porcelain" in name or "white" in name:
        return "#c9bda9"
    if "concrete" in name:
        return "#989a98"
    if "stone" in name or "curb" in name:
        return "#817b73"
    if "brick" in name or "foundation" in name:
        return "#875747"
    if "wood" in name or "beech" in name:
        return "#8a6043"
    if "carbon" in name or "black" in name or "rough" in name:
        return "#4b4a47"
    if damage_state == "destroyed":
        return "#66514a"
    return fallback


def _structure_face_colors(structure: Structure) -> Optional[Tuple[str, ...]]:
    if structure.visual_mesh is None or not structure.visual_face_materials:
        return None
    if not any(structure.visual_face_materials):
        return None
    fallback = _structure_visual_color(structure)
    return tuple(
        _material_face_color(material, structure.damage_state, fallback)
        for material in structure.visual_face_materials
    )


def _structure_visual_trace(
    structure: Structure,
    color: str,
    opacity: float,
    hover_text: str,
):
    """Render a runtime source OBJ mesh without changing collision geometry."""
    import plotly.graph_objects as go

    mesh = structure.visual_mesh
    if mesh is None:
        return None
    label = _structure_visual_label(structure)
    trace_values = dict(
        x=mesh.vertices[:, 0],
        y=mesh.vertices[:, 1],
        z=mesh.vertices[:, 2],
        i=mesh.faces[:, 0],
        j=mesh.faces[:, 1],
        k=mesh.faces[:, 2],
        name=label,
        color=color,
        opacity=opacity,
        hovertext=hover_text,
        hoverinfo="text",
        flatshading=False,
        lighting={"ambient": 0.45, "diffuse": 0.75, "specular": 0.15, "roughness": 0.8},
    )
    face_colors = _structure_face_colors(structure)
    if face_colors is not None:
        trace_values["facecolor"] = face_colors
    return go.Mesh3d(**trace_values)


def _elevation_guide_trace(obstacle: Obstacle):
    """Make positive-z debris visibly separate from the ground plane."""
    import plotly.graph_objects as go
    footprint=obstacle.footprint or _rectangle_polygon(obstacle.minimum[0],obstacle.minimum[1],obstacle.width,obstacle.depth)
    cx,cy=_polygon_centroid(footprint)
    label="{}: z={:.1f} to {:.1f} m".format(obstacle.identifier, obstacle.minimum[2], obstacle.maximum[2])
    return go.Scatter3d(
        x=[cx,cx], y=[cy,cy], z=[0.0,obstacle.minimum[2]], mode="lines+markers",
        line={"color":"#7c3aed","width":4,"dash":"dash"},
        marker={"size":[3,6],"color":"#7c3aed"}, name="elevation guide",
        hovertext=[label,label], hoverinfo="text", showlegend=False, legendgroup="elevated-blocked",
    )


def _display_name(identifier: Any) -> str:
    """Turn an internal OSM/template identifier into a readable hover name."""
    value = str(identifier)
    if value.startswith("context_"):
        value = value[len("context_"):]
    value = value.replace("-", "_")
    return " ".join(part for part in value.split("_") if part).title() or "Unnamed object"


def _structure_hover_text(structure: Structure) -> str:
    role = "static context" if structure.scene_role == "context" else "earthquake target"
    source = structure.source_ref or "bundled scene template"
    display_name = structure.source_name or _display_name(structure.identifier)
    source_name = (
        "<br>Source building: {}".format(html.escape(structure.source_name))
        if structure.source_name else ""
    )
    template_line = ""
    if structure.scene_role == "target":
        template_id = _damage_template_id(structure.damage_state)
        template_line = "<br>Damage mesh template: {}".format(html.escape(template_id))
    source_id_line = (
        "<br>heiDATA prototype: {}".format(html.escape(structure.source_id))
        if structure.source_id else ""
    )
    asset_line = (
        "<br>Visible asset: {} ({})".format(
            html.escape(structure.visual_mesh_asset),
            html.escape(structure.visual_mesh_phase),
        )
        if structure.visual_mesh_asset else
        "<br>Visible geometry: {}".format(html.escape(_structure_visual_label(structure)))
    )
    post_line = (
        "<br>Post asset review: accepted source mesh"
        if structure.post_asset_id else ""
    )
    return (
        "<b>{}</b><br>Role: {}<br>Damage state: {}<br>"
        "Mapped height: {:.1f} m{}{}{}{}{}<br>Provenance: {}<br>Source: {}<extra></extra>"
    ).format(
        html.escape(display_name),
        html.escape(role),
        html.escape(structure.damage_state),
        float(structure.height),
        template_line,
        source_name,
        source_id_line,
        asset_line,
        post_line,
        html.escape(structure.visual_provenance),
        html.escape(str(source)),
    )


def _obstacle_hover_text(obstacle: Obstacle, parent_name: str) -> str:
    kind = obstacle.kind.replace("_", " ").title()
    template_line = (
        "<br>Damage mesh template: {}".format(html.escape(obstacle.damage_template_id))
        if obstacle.damage_template_id
        else ""
    )
    return (
        "<b>{}</b><br>Parent building: {}<br>Type: {}<br>"
        "z range: {:.1f} to {:.1f} m{}<extra></extra>"
    ).format(
        html.escape(_display_name(obstacle.identifier)),
        html.escape(parent_name),
        html.escape(kind),
        float(obstacle.minimum[2]),
        float(obstacle.maximum[2]),
        template_line,
    )


def _task_hover_text(
    task: Any,
    assigned_uav: Optional[str] = None,
    visual_reference: Optional[str] = None,
) -> str:
    """Build a readable hover card from a SurvivorTask or task mapping."""
    def value(name: str, default: Any = "unknown"):
        return task.get(name, default) if isinstance(task, Mapping) else getattr(task, name, default)

    demand=value("demand", {})
    demand_text=", ".join("{}: {}".format(html.escape(str(key)), html.escape(str(amount))) for key,amount in dict(demand).items()) or "none"
    survivor=value("survivor_position", value("position", "unknown"))
    dropoff=value("dropoff_waypoint", value("position", "unknown"))
    vertical_separation="unknown"
    if isinstance(survivor, (tuple, list)) and isinstance(dropoff, (tuple, list)) and len(survivor) >= 3 and len(dropoff) >= 3:
        vertical_separation="{:.1f} m".format(float(dropoff[2]) - float(survivor[2]))
    return (
        "<b>{}</b><br>Type: {}<br>Severity: {:.2f}<br>"
        "Task position: {}<br>Drop off waypoint: {}<br>Vertical drop off separation: {}<br>Demand: {}<br>"
        "Detected at: {:.1f} s<br>Status: {}{}{}<extra></extra>"
    ).format(
        html.escape(str(value("identifier"))), html.escape(str(value("task_type"))),
        float(value("severity", 0.0)), html.escape(str(survivor)), html.escape(str(dropoff)), vertical_separation,
        demand_text, float(value("detected_at", 0.0)),
        html.escape(str(value("status"))),
        "<br>Assigned UAV: {}".format(html.escape(assigned_uav)) if assigned_uav else "",
        "<br>Visual reference building: {}".format(html.escape(visual_reference)) if visual_reference else "",
    )


def _nearest_target_name(scene: DisasterScene, point: Point) -> str:
    """Return a visual building reference without changing task semantics."""
    targets = [structure for structure in scene.structures if structure.scene_role == "target"]
    if not targets:
        return "none"
    px, py = point[0], point[1]
    for structure in targets:
        if _point_in_polygon(px, py, _structure_polygon(structure)):
            return "{} ({} damage footprint)".format(
                structure.source_name or _display_name(structure.identifier),
                structure.damage_state,
            )
    nearest = min(
        targets,
        key=lambda structure: (
            _polygon_centroid(_structure_polygon(structure))[0] - px
        ) ** 2 + (
            _polygon_centroid(_structure_polygon(structure))[1] - py
        ) ** 2,
    )
    return nearest.source_name or _display_name(nearest.identifier)


def plot_disaster_scene(
    scene: DisasterScene,
    task_positions: Iterable[Point] = (),
    routes: Optional[Mapping[str, Iterable[Point]]] = None,
    tasks: Iterable[Any] = (),
    task_assignees: Optional[Mapping[str, str]] = None,
    show_context: bool = False,
    show_candidate_sites: bool = False,
    show_elevation_guides: bool = True,
):
    """Build the operational 3D view without repeating every object in its legend.

    The default view is intentionally an environment view: earthquake target
    buildings, damage geometry, selected tasks, vertical drop off waypoints,
    and the base remain visible. UAV routes are optional planning overlays,
    while static context and all unused candidate sites are opt in diagnostic
    layers. This keeps the world readable without removing source geometry.
    """
    import plotly.graph_objects as go

    figure = go.Figure()
    figure.add_trace(_ground_trace(scene.environment.world))
    structure_roles = {structure.identifier: structure.scene_role for structure in scene.structures}
    damage_colors = {
        "intact": "#16a34a",
        "minor": "#ca8a04",
        "major": "#ea580c",
        "destroyed": "#dc2626",
    }
    obstacle_colors = {
        "building": "#8c564b",
        "ground_rubble": "#ca8a04",
        "broken_floor": "#f97316",
        "elevated_debris": "#7c3aed",
    }
    structure_states = {structure.identifier: structure.damage_state for structure in scene.structures}

    target_states = sorted({
        structure.damage_state
        for structure in scene.structures
        if structure.scene_role == "target"
    })
    for state in target_states:
        _add_3d_legend_proxy(
            figure,
            "{} damage footprint".format(state),
            damage_colors[state],
            "damage-{}".format(state),
        )
    if show_context:
        _add_3d_legend_proxy(figure, "static context footprint", "#94a3b8", "context")

    for structure in scene.structures:
        is_context = structure.scene_role == "context"
        if is_context and not show_context:
            continue
        polygon = _structure_polygon(structure)
        points = list(polygon) + [polygon[0]]
        state_group = "context" if is_context else "damage-{}".format(structure.damage_state)
        color = "#94a3b8" if is_context else damage_colors[structure.damage_state]
        # A shallow filled footprint means a destroyed building remains visible
        # as a mapped target even when its standing volume has collapsed.
        if not is_context:
            footprint_fill = _polygon_prism_trace(
                polygon,
                0.02,
                0.16,
                color,
                "{} damage footprint".format(_display_name(structure.identifier)),
                0.26,
            )
            footprint_fill.update(showlegend=False, legendgroup=state_group)
            figure.add_trace(footprint_fill)
        hover = _structure_hover_text(structure)
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in points],
                y=[point[1] for point in points],
                z=[0.18] * len(points),
                mode="lines",
                name="{} footprint".format(
                    "context" if is_context else structure.damage_state
                ),
                line={
                    "color": color,
                    "width": 2 if is_context else 4,
                    "dash": "dot" if is_context else "solid",
                },
                hovertext=[hover] * len(points),
                hoverinfo="text",
                legendgroup=state_group,
                showlegend=False,
            )
        )

    shown_source_mesh_labels = set()
    for structure in scene.structures:
        if structure.visual_mesh is None:
            continue
        label = _structure_visual_label(structure)
        if label not in shown_source_mesh_labels:
            _add_3d_legend_proxy(
                figure,
                label,
                _structure_visual_color(structure),
                "source-mesh-{}".format(structure.visual_mesh_phase),
            )
            shown_source_mesh_labels.add(label)
        mesh_trace = _structure_visual_trace(
            structure,
            _structure_visual_color(structure),
            _source_mesh_opacity(structure.visual_mesh_phase, structure.damage_state),
            _structure_hover_text(structure),
        )
        if mesh_trace is not None:
            mesh_trace.update(
                showlegend=False,
                legendgroup="source-mesh-{}".format(structure.visual_mesh_phase),
            )
            figure.add_trace(mesh_trace)

    present_obstacles = [
        obstacle
        for obstacle in scene.environment.obstacles
        if not (
            obstacle.kind == "building"
            and structure_roles.get(obstacle.parent_structure_id) == "context"
        ) and not (
            obstacle.kind == "building"
            and any(
                structure.identifier == obstacle.parent_structure_id and structure.visual_mesh is not None
                for structure in scene.structures
            )
        )
    ]
    legend_items = {}
    for obstacle in present_obstacles:
        label = _obstacle_visual_label(obstacle, structure_states)
        legend_items[label] = (obstacle.kind, _obstacle_legend_group(obstacle, structure_states))
    for label, (kind, group) in sorted(legend_items.items()):
        _add_3d_legend_proxy(
            figure,
            label,
            obstacle_colors[kind],
            group,
        )
    if show_context:
        _add_3d_legend_proxy(figure, "static context building", "#94a3b8", "context-obstacles")

    for obstacle in scene.environment.obstacles:
        is_context_building = (
            obstacle.kind == "building"
            and structure_roles.get(obstacle.parent_structure_id) == "context"
        )
        has_source_mesh = any(
            structure.identifier == obstacle.parent_structure_id and structure.visual_mesh is not None
            for structure in scene.structures
        )
        if is_context_building and not show_context:
            continue
        if obstacle.kind == "building" and has_source_mesh:
            continue
        label = "static context building" if is_context_building else _obstacle_visual_label(obstacle, structure_states)
        group = "context-obstacles" if is_context_building else _obstacle_legend_group(obstacle, structure_states)
        color = "#94a3b8" if is_context_building else _obstacle_render_color(obstacle)
        parent = structure_roles.get(obstacle.parent_structure_id)
        parent_name = _display_name(obstacle.parent_structure_id) if obstacle.parent_structure_id else "unassigned"
        trace = _obstacle_visual_trace(
            obstacle,
            color,
            label,
            0.34 if is_context_building else (0.84 if obstacle.kind == "ground_rubble" else 0.68),
            _obstacle_hover_text(obstacle, parent_name),
        )
        trace.update(showlegend=False, legendgroup=group)
        figure.add_trace(trace)
        if (
            show_elevation_guides
            and not is_context_building
            and obstacle.kind in {"elevated_debris", "broken_floor"}
            and obstacle.minimum[2] > 0
        ):
            figure.add_trace(_elevation_guide_trace(obstacle))

    if show_candidate_sites:
        for kind, color in (("ground", "#16a34a"), ("elevated", "#0891b2")):
            sites = [site for site in scene.candidate_sites if site.kind == kind]
            if not sites:
                continue
            figure.add_trace(
                go.Scatter3d(
                    x=[site.position[0] for site in sites],
                    y=[site.position[1] for site in sites],
                    z=[site.position[2] for site in sites],
                    mode="markers",
                    name="{} candidate sites".format(kind),
                    marker={"size": 4, "color": color},
                    hovertext=[
                        "<b>{}</b><br>Type: {}<extra></extra>".format(
                            html.escape(site.identifier), html.escape(kind)
                        )
                        for site in sites
                    ],
                    hoverinfo="text",
                    legendgroup="candidate-sites-{}".format(kind),
                )
            )

    tasks = tuple(tasks)
    task_positions = tuple(task_positions)
    if tasks:
        task_positions = tuple(
            task.survivor_position
            if hasattr(task, "survivor_position")
            else task.get("survivor_position", task.get("position"))
            for task in tasks
        )
        task_labels = [
            str(
                task.identifier
                if hasattr(task, "identifier")
                else task.get("identifier", "task_{}".format(index))
            )
            for index, task in enumerate(tasks, 1)
        ]
        task_visual_references = [
            _nearest_target_name(scene, point) for point in task_positions
        ]
        task_hover = [
            _task_hover_text(
                task,
                (task_assignees or {}).get(identifier),
                visual_reference,
            )
            for task, identifier, visual_reference in zip(tasks, task_labels, task_visual_references)
        ]
    else:
        task_labels = ["task_{}".format(index) for index in range(1, len(task_positions) + 1)]
        task_hover = task_labels
        task_visual_references = [
            _nearest_target_name(scene, point) for point in task_positions
        ]
    if task_positions:
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in task_positions],
                y=[point[1] for point in task_positions],
                z=[point[2] for point in task_positions],
                mode="markers+text",
                text=task_labels,
                textposition="top center",
                name="survivor tasks",
                marker={"size": 7, "color": "#db2777", "symbol": "circle"},
                hovertext=task_hover,
                hoverinfo="text",
                legendgroup="tasks",
                showlegend=True,
            )
        )
    if tasks:
        dropoff_positions = tuple(
            task.dropoff_waypoint
            if hasattr(task, "dropoff_waypoint")
            else task.get("dropoff_waypoint", task.get("position"))
            for task in tasks
        )
        _add_3d_legend_proxy(figure, "vertical drop off path", "#0891b2", "drop-off-waypoints")
        for label, reference, task_position, dropoff_position in zip(task_labels, task_visual_references, task_positions, dropoff_positions):
            vertical_separation = float(dropoff_position[2]) - float(task_position[2])
            assignment = (
                "Assigned UAV: {}".format(html.escape((task_assignees or {}).get(label, "unassigned")))
                if task_assignees
                else "UAV assignment: not planned in environment preview"
            )
            figure.add_trace(
                go.Scatter3d(
                    x=[task_position[0], dropoff_position[0]],
                    y=[task_position[1], dropoff_position[1]],
                    z=[task_position[2], dropoff_position[2]],
                    mode="lines",
                    name="vertical drop off path",
                    line={"color": "#0891b2", "width": 4, "dash": "dash"},
                    hovertext=[
                        "<b>{}</b><br>Vertical drop off path<br>Separation: {:.1f} m<br>{}<br>"
                        "Visual reference building: {}<extra></extra>".format(
                            html.escape(label), vertical_separation, assignment, html.escape(reference)
                        )
                    ] * 2,
                    hoverinfo="text",
                    legendgroup="drop-off-waypoints",
                    showlegend=False,
                )
            )
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in dropoff_positions],
                y=[point[1] for point in dropoff_positions],
                z=[point[2] for point in dropoff_positions],
                mode="markers+text",
                text=["{} drop".format(label) for label in task_labels],
                textposition="bottom center",
                name="UAV drop off waypoints",
                marker={"size": 6, "color": "#0891b2", "symbol": "diamond"},
                hovertext=[
                    "<b>{}</b><br>UAV drop-off waypoint<br>Vertical separation: {:.1f} m<br>{}<br>"
                    "Visual reference building: {}<extra></extra>".format(
                        html.escape(label),
                        float(dropoff[2]) - float(task_position[2]),
                        (
                            "Assigned UAV: {}".format(html.escape((task_assignees or {}).get(label, "unassigned")))
                            if task_assignees
                            else "UAV assignment: not planned in environment preview"
                        ),
                        html.escape(reference),
                    )
                    for label, reference, task_position, dropoff in zip(task_labels, task_visual_references, task_positions, dropoff_positions)
                ],
                hoverinfo="text",
                legendgroup="drop-off-waypoints",
                showlegend=True,
            )
        )

    route_colors = ("#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed", "#0891b2")
    route_count = 0
    for route_index, (route_id, route_points) in enumerate((routes or {}).items()):
        route_points = tuple(route_points)
        if len(route_points) <= 1:
            continue
        route_count += 1
        assigned = [
            label for label in task_labels if (task_assignees or {}).get(label) == route_id
        ]
        order = " → ".join(assigned) if assigned else "no assigned task"
        route_label = "{} route".format(route_id)
        route_hover = "<b>{}</b><br>Task order: {}<extra></extra>".format(
            html.escape(route_label), html.escape(order)
        )
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in route_points],
                y=[point[1] for point in route_points],
                z=[point[2] for point in route_points],
                mode="lines",
                name=route_label,
                line={"width": 6, "color": route_colors[route_index % len(route_colors)]},
                hovertext=[route_hover] * len(route_points),
                hoverinfo="text",
                legendgroup="route-{}".format(route_id),
                showlegend=True,
            )
        )
        direction_index = next(
            (
                index
                for index in range(1, len(route_points))
                if route_points[index] != route_points[index - 1]
            ),
            None,
        )
        if direction_index is not None:
            previous = route_points[direction_index - 1]
            current = route_points[direction_index]
            midpoint = tuple((previous[axis] + current[axis]) / 2 for axis in range(3))
            figure.add_trace(
                go.Scatter3d(
                    x=[midpoint[0]],
                    y=[midpoint[1]],
                    z=[midpoint[2]],
                    mode="markers+text",
                    text=["{} →".format(route_id)],
                    textposition="top center",
                    name="{} direction".format(route_id),
                    marker={"size": 5, "color": route_colors[route_index % len(route_colors)]},
                    hovertext=[route_hover + "<br>Direction marker: base → task order"],
                    hoverinfo="text",
                    legendgroup="route-{}".format(route_id),
                    showlegend=False,
                )
            )

    base = scene.environment.base.position
    figure.add_trace(
        go.Scatter3d(
            x=[base[0]],
            y=[base[1]],
            z=[base[2]],
            mode="markers+text",
            text=["base"],
            textposition="top center",
            name="base",
            marker={"size": 9, "color": "#1d4ed8", "symbol": "diamond"},
            hovertext=["<b>UAV operating base</b><br>z = 0 m<extra></extra>"],
            hoverinfo="text",
            showlegend=True,
        )
    )

    visible_targets = sum(structure.scene_role == "target" for structure in scene.structures)
    visible_objects = sum(
        not (
            obstacle.kind == "building"
            and structure_roles.get(obstacle.parent_structure_id) == "context"
            and not show_context
        )
        for obstacle in scene.environment.obstacles
    )
    scene_label = "DU Science Complex outdoor" if scene.generation_metadata["mode"] == "du_outdoor" else _mode_label(scene)
    dropoff_offsets = []
    for task in tasks:
        survivor = task.survivor_position if hasattr(task, "survivor_position") else task.get("survivor_position", task.get("position"))
        dropoff = task.dropoff_waypoint if hasattr(task, "dropoff_waypoint") else task.get("dropoff_waypoint", task.get("position"))
        if isinstance(survivor, (tuple, list)) and isinstance(dropoff, (tuple, list)) and len(survivor) >= 3 and len(dropoff) >= 3:
            dropoff_offsets.append(float(dropoff[2]) - float(survivor[2]))
    dropoff_summary = (
        "Drop off vertical separation: {:.1f} to {:.1f} m".format(min(dropoff_offsets), max(dropoff_offsets))
        if dropoff_offsets
        else "Drop off waypoint: not shown"
    )
    solution_summary = "UAV assignment: not included" if not routes else "UAV routes: {}".format(route_count)
    mesh_usage = scene.generation_metadata.get("visual_mesh_usage", {})
    mesh_summary = (
        "Geometry provenance: source pre {} | source post {} | derived damage {} | OSM context footprints {} | rubble only {}".format(
            mesh_usage.get("source_pre_mesh", 0),
            mesh_usage.get("source_post_mesh", 0),
            mesh_usage.get("derived_partial_mesh", 0),
            mesh_usage.get("footprint_extrusion", 0),
            mesh_usage.get("rubble_only", 0),
        )
        if mesh_usage else "Source mesh layer: not used"
    )
    if scene.generation_metadata.get("mode") == "heidata_neighborhood":
        source_header = "Layout: ordered controlled neighbourhood | derived positions, source mesh identities retained"
    elif _is_geospatial_mode(scene.generation_metadata.get("mode")):
        source_header = "Source scenario: {} | original source positions preserved".format(
            scene.generation_metadata.get("source_scenario_schema", "scenario.v1")
        )
    else:
        source_header = "Preset: {}".format(scene.preset.severity)
    title = (
        "{} post-earthquake operational environment<br>"
        "<sup>{} | Target buildings: {} | Visible damage objects: {} | Tasks: {}<br>"
        "{} | {}<br>{}</sup>"
    ).format(
        scene_label,
        source_header,
        visible_targets,
        visible_objects,
        len(tasks),
        dropoff_summary,
        solution_summary,
        mesh_summary,
    )
    _scene_layout(figure, scene, title)
    figure.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.08,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 11},
            "itemsizing": "constant",
        },
        margin={"l": 0, "r": 0, "t": 95, "b": 105},
        hoverlabel={"namelength": -1},
    )
    figure.layout.scene.camera = {
        "eye": {"x": 1.55, "y": -1.65, "z": 1.10} if _is_geospatial_mode(scene.generation_metadata.get("mode")) else {"x": 1.60, "y": -1.90, "z": 3.20},
        "center": {"x": 0.0, "y": 0.0, "z": 0.0},
        "projection": {"type": "orthographic"},
        "up": {"x": 0, "y": 0, "z": 1},
    }
    return figure


def _structure_polygon(structure: Structure) -> Polygon2D:
    return structure.footprint or _rectangle_polygon(structure.minimum[0],structure.minimum[1],structure.width,structure.depth)


def _add_base(figure, scene: DisasterScene) -> None:
    import plotly.graph_objects as go
    base=scene.environment.base.position
    figure.add_trace(go.Scatter3d(x=[base[0]],y=[base[1]],z=[base[2]],mode="markers+text",text=["base"],textposition="top center",name="base",marker={"size":8,"color":"#1d4ed8","symbol":"diamond"},hovertext=["safe operating base"],hoverinfo="text"))


def _scene_layout(figure, scene: DisasterScene, title: str) -> None:
    world=scene.environment.world
    x_span = world.maximum[0] - world.minimum[0]
    y_span = world.maximum[1] - world.minimum[1]
    # The exact L'Aquila source extent is irregular and much wider than the
    # compact DU/synthetic scenes. Extra 3D viewport padding prevents the
    # diagonal camera projection from clipping source buildings at the frame
    # edges while keeping the other previews focused.
    padding_fraction = (
        0.10
        if scene.generation_metadata.get("mode") == "heidata_neighborhood"
        else 0.18 if _is_geospatial_mode(scene.generation_metadata.get("mode")) else 0.08
    )
    x_padding = max(8.0, x_span * padding_fraction)
    y_padding = max(8.0, y_span * padding_fraction)
    figure.update_layout(title=title,template="plotly_white",scene={"xaxis":{"title":"x, metres","range":[world.minimum[0] - x_padding,world.maximum[0] + x_padding]},"yaxis":{"title":"y, metres","range":[world.minimum[1] - y_padding,world.maximum[1] + y_padding]},"zaxis":{"title":"z, metres","range":[world.minimum[2],world.maximum[2]]},"aspectmode":"data","camera":{"eye":{"x":1.45,"y":-1.65,"z":1.2}}},legend={"orientation":"h"})


def _mode_label(scene: DisasterScene) -> str:
    if scene.generation_metadata["mode"] == "heidata_neighborhood":
        return "HEIDATA CONTROLLED NEIGHBOURHOOD"
    if _is_geospatial_mode(scene.generation_metadata["mode"]):
        return "L’AQUILA EXACT GEOREFERENCED SOURCE"
    return str(scene.generation_metadata["mode"]).replace("_", " ").upper()


def _add_3d_legend_proxy(figure, label: str, color: str, legendgroup: str) -> None:
    """Add one readable legend entry for a category of otherwise independent meshes."""
    import plotly.graph_objects as go
    figure.add_trace(go.Scatter3d(
        x=[None], y=[None], z=[None], mode="markers", name=label,
        marker={"size": 8, "color": color}, legendgroup=legendgroup,
        hoverinfo="skip", showlegend=True,
    ))


def _obstacle_visual_label(obstacle: Obstacle, structure_states: Mapping[str, str]) -> str:
    """Return a supervisor readable label for a generated damage mesh."""
    state = structure_states.get(obstacle.parent_structure_id or "")
    if state == "major" and obstacle.kind == "building":
        return "major damaged building mesh"
    if state == "major" and obstacle.kind == "ground_rubble":
        return "major collapse rubble mesh"
    if state == "destroyed" and obstacle.kind == "ground_rubble":
        return "destroyed building rubble mesh"
    if state == "major" and obstacle.kind == "broken_floor":
        return "major broken floor mesh"
    if state == "major" and obstacle.kind == "elevated_debris":
        return "major elevated debris mesh"
    if obstacle.kind == "building":
        return "standing building volume"
    if obstacle.kind == "ground_rubble":
        return "ground rubble"
    if obstacle.kind == "broken_floor":
        return "broken floor"
    if obstacle.kind == "elevated_debris":
        return "elevated debris"
    return obstacle.kind.replace("_", " ")


def _obstacle_legend_group(obstacle: Obstacle, structure_states: Mapping[str, str]) -> str:
    label = _obstacle_visual_label(obstacle, structure_states)
    return "obstacle-{}".format(label.replace(" ", "-"))


def _obstacle_color(kind: str) -> str:
    return {
        "building": "#8c564b",
        "ground_rubble": RUBBLE_COLORS[0],
        "broken_floor": "#f97316",
        "elevated_debris": "#7c3aed",
    }[kind]


def _obstacle_render_color(obstacle: Obstacle) -> str:
    """Return a deterministic, readable material color for an obstacle.

    L'Aquila's preview is easier to read because one rubble field contains
    several earthy tones rather than one flat marker color. Apply that visual
    treatment to DU and synthetic fragments while keeping each scene seeded
    and keeping the underlying geometry/data source unchanged.
    """
    if obstacle.kind == "ground_rubble":
        checksum = sum((index + 1) * ord(character) for index, character in enumerate(obstacle.identifier))
        return RUBBLE_COLORS[checksum % len(RUBBLE_COLORS)]
    return _obstacle_color(obstacle.kind)


def _source_layout_bounds(scene: DisasterScene) -> Tuple[float, float, float, float]:
    """Return a padded 2D viewport around the mapped source footprints."""
    points = [point for structure in scene.structures for point in _structure_polygon(structure)]
    if not points:
        world = scene.environment.world
        return world.minimum[0], world.minimum[1], world.maximum[0], world.maximum[1]

    minimum_x = min(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_x = max(point[0] for point in points)
    maximum_y = max(point[1] for point in points)
    span_x = max(maximum_x - minimum_x, 1.0)
    span_y = max(maximum_y - minimum_y, 1.0)
    padding_x = max(8.0, span_x * 0.08)
    padding_y = max(8.0, span_y * 0.08)
    return minimum_x - padding_x, minimum_y - padding_y, maximum_x + padding_x, maximum_y + padding_y


def _source_scale_length(span: float) -> float:
    """Choose a readable scale-bar length that occupies part of the viewport."""
    selected = 1.0
    for candidate in (5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0, 500.0):
        if candidate <= span * 0.25:
            selected = candidate
    return selected


def _add_source_orientation(figure, bounds: Tuple[float, float, float, float]) -> None:
    """Add north and scale references to the source-only plan view."""
    minimum_x, minimum_y, maximum_x, maximum_y = bounds
    span_x = maximum_x - minimum_x
    span_y = maximum_y - minimum_y
    dark = "#0f172a"

    scale_length = _source_scale_length(span_x)
    scale_x = minimum_x + span_x * 0.06
    scale_y = minimum_y + span_y * 0.07
    figure.add_shape(type="line", x0=scale_x, x1=scale_x + scale_length, y0=scale_y, y1=scale_y, line={"color": dark, "width": 4})
    figure.add_shape(type="line", x0=scale_x, x1=scale_x, y0=scale_y - span_y * 0.012, y1=scale_y + span_y * 0.012, line={"color": dark, "width": 2})
    figure.add_shape(type="line", x0=scale_x + scale_length, x1=scale_x + scale_length, y0=scale_y - span_y * 0.012, y1=scale_y + span_y * 0.012, line={"color": dark, "width": 2})
    figure.add_annotation(x=scale_x + scale_length / 2, y=scale_y - span_y * 0.035, text="{:g} m".format(scale_length), showarrow=False, font={"size": 12, "color": dark})

    north_x = maximum_x - span_x * 0.10
    north_tail_y = maximum_y - span_y * 0.18
    north_head_y = north_tail_y + span_y * 0.08
    figure.add_annotation(
        x=north_x,
        y=north_head_y,
        ax=north_x,
        ay=north_tail_y,
        xref="x",
        yref="y",
        axref="x",
        ayref="y",
        text="<b>N</b>",
        showarrow=True,
        arrowhead=2,
        arrowsize=1.2,
        arrowwidth=2,
        arrowcolor=dark,
        font={"size": 14, "color": dark},
    )


def _source_structure_hover_text(structure: Structure, role: str) -> str:
    """Describe one source footprint without implying damage or observed height."""
    source = structure.source_ref or "bundled scene template"
    source_name = structure.source_name or _display_name(structure.identifier)
    asset = structure.visual_mesh_asset or "not available"
    return (
        "<b>Building: {}</b><br>"
        "Layer: {}<br>"
        "Mapped object: {}<br>"
        "Visible asset: {}<br>"
        "Source reference: {}<extra></extra>"
    ).format(
        html.escape(source_name),
        html.escape(role),
        html.escape(str(structure.identifier)),
        html.escape(str(asset)),
        html.escape(str(source)),
    )


def _source_footprint_figure(scene: DisasterScene, title_suffix: str):
    """Build the canonical source-only footprint view used by Phase 3."""
    import plotly.graph_objects as go

    figure = go.Figure()
    shown_roles = set()
    for structure in scene.structures:
        is_target = structure.scene_role == "target"
        role = "mapped building footprint" if is_target else "static context footprint"
        polygon = _structure_polygon(structure)
        closed = tuple(polygon) + (polygon[0],)
        figure.add_trace(go.Scatter(
            x=[point[0] for point in closed],
            y=[point[1] for point in closed],
            mode="lines",
            fill="toself",
            fillcolor="rgba(37, 99, 235, .22)" if is_target else "rgba(148, 163, 184, .20)",
            line={"color": "#1d4ed8" if is_target else "#64748b", "width": 2},
            name=role,
            legendgroup=role,
            showlegend=role not in shown_roles,
            hovertext=[_source_structure_hover_text(structure, role)] * len(closed),
            hoverinfo="text",
        ))
        shown_roles.add(role)

    minimum_x, minimum_y, maximum_x, maximum_y = _source_layout_bounds(scene)
    target_count = sum(item.scene_role == "target" for item in scene.structures)
    context_count = sum(item.scene_role == "context" for item in scene.structures)
    figure.update_layout(
        title={
            "text": (
                "{} {}<br><sup>Source geometry only | {} total footprints | {} mapped buildings | {} context footprints<br>"
                "No base, roads, damage, tasks or UAV layers</sup>"
            ).format(_mode_label(scene), title_suffix, len(scene.structures), target_count, context_count)
        },
        template="plotly_white",
        xaxis={
            "title": "x, metres",
            "range": [minimum_x, maximum_x],
            "scaleanchor": "y",
            "scaleratio": 1,
            "showgrid": True,
            "gridcolor": "#e2e8f0",
            "zeroline": False,
        },
        yaxis={
            "title": "y, metres",
            "range": [minimum_y, maximum_y],
            "showgrid": True,
            "gridcolor": "#e2e8f0",
            "zeroline": False,
        },
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.12,
            "x": 0,
            "xanchor": "left",
            "font": {"size": 11},
        },
        margin={"l": 70, "r": 35, "t": 105, "b": 115},
        height=760,
        hoverlabel={"namelength": -1},
    )
    _add_source_orientation(figure, (minimum_x, minimum_y, maximum_x, maximum_y))
    return figure


def plot_map_view(scene: DisasterScene):
    """Show every source building footprint in the canonical 2D plan view."""
    return _source_footprint_figure(scene, "source footprint map")


def plot_building_layout(scene: DisasterScene):
    """Show the Phase 3 source layout without artificial 3D height or overlays."""
    return _source_footprint_figure(scene, "source building footprints")


def plot_damage_view(scene: DisasterScene, show_elevation_guides: bool = True):
    """Show the post-earthquake layer with clear damage and source references."""
    import plotly.graph_objects as go

    figure = go.Figure()
    figure.add_trace(_ground_trace(scene.environment.world))
    damage_colors = {"intact": "#16a34a", "minor": "#ca8a04", "major": "#ea580c", "destroyed": "#dc2626"}
    roles = {structure.identifier: structure.scene_role for structure in scene.structures}
    target_structures = [structure for structure in scene.structures if structure.scene_role == "target"]
    target_state_counts = {
        state: sum(structure.damage_state == state for structure in target_structures)
        for state in STATES
    }
    for state in sorted({structure.damage_state for structure in target_structures}):
        _add_3d_legend_proxy(
            figure,
            "{} damage footprint marker".format(state),
            damage_colors[state],
            "damage-{}".format(state),
        )
    if any(structure.scene_role == "context" for structure in scene.structures):
        _add_3d_legend_proxy(figure, "static context footprint", "#94a3b8", "context")

    for structure in scene.structures:
        polygon = _structure_polygon(structure)
        points = list(polygon) + [polygon[0]]
        context = structure.scene_role == "context"
        state_group = "context" if context else "damage-{}".format(structure.damage_state)
        hover = _structure_hover_text(structure)
        if not context:
            footprint_fill = _polygon_prism_trace(
                polygon,
                0,
                .18,
                damage_colors[structure.damage_state],
                "{} damage footprint marker ({})".format(
                    structure.damage_state,
                    _display_name(structure.identifier),
                ),
                .26,
            )
            footprint_fill.update(showlegend=False, legendgroup=state_group, hovertext=hover, hoverinfo="text")
            figure.add_trace(footprint_fill)
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in points],
                y=[point[1] for point in points],
                z=[.08] * len(points),
                mode="lines",
                name="context footprint" if context else "{} footprint marker".format(structure.damage_state),
                line={
                    "color": "#94a3b8" if context else damage_colors[structure.damage_state],
                    "width": 1 if context else 4,
                    "dash": "dot" if context else "solid",
                },
                hovertext=[hover] * len(points),
                hoverinfo="text",
                legendgroup=state_group,
                showlegend=False,
            )
        )

    shown_source_mesh_labels = set()
    for structure in scene.structures:
        if structure.visual_mesh is None:
            continue
        label = _structure_visual_label(structure)
        if label not in shown_source_mesh_labels:
            _add_3d_legend_proxy(
                figure,
                label,
                _structure_visual_color(structure),
                "source-mesh-{}".format(structure.visual_mesh_phase),
            )
            shown_source_mesh_labels.add(label)
        mesh_trace = _structure_visual_trace(
            structure,
            _structure_visual_color(structure),
            _source_mesh_opacity(structure.visual_mesh_phase, structure.damage_state),
            _structure_hover_text(structure),
        )
        if mesh_trace is not None:
            mesh_trace.update(
                showlegend=False,
                legendgroup="source-mesh-{}".format(structure.visual_mesh_phase),
            )
            figure.add_trace(mesh_trace)

    colors = {"building": "#8c564b", "ground_rubble": "#ca8a04", "broken_floor": "#f97316", "elevated_debris": "#7c3aed"}
    structure_states = {structure.identifier: structure.damage_state for structure in scene.structures}
    present_obstacles = [
        obstacle
        for obstacle in scene.environment.obstacles
        if not (obstacle.kind == "building" and roles.get(obstacle.parent_structure_id) == "context")
        and not (
            obstacle.kind == "building"
            and any(
                structure.identifier == obstacle.parent_structure_id and structure.visual_mesh is not None
                for structure in scene.structures
            )
        )
    ]
    legend_items = {}
    for obstacle in present_obstacles:
        label = _obstacle_visual_label(obstacle, structure_states)
        legend_items[label] = (obstacle.kind, _obstacle_legend_group(obstacle, structure_states))
    for label, (kind, group) in sorted(legend_items.items()):
        _add_3d_legend_proxy(
            figure,
            label,
            colors[kind],
            group,
        )

    guide_present = show_elevation_guides and any(
        obstacle.minimum[2] > 0 and obstacle.kind in {"broken_floor", "elevated_debris"}
        for obstacle in scene.environment.obstacles
    )
    if guide_present:
        _add_3d_legend_proxy(
            figure,
            "elevation guide (helper)",
            "#7c3aed",
            "elevation-guides",
        )

    for obstacle in scene.environment.obstacles:
        if obstacle.kind == "building" and roles.get(obstacle.parent_structure_id) == "context":
            continue
        if obstacle.kind == "building" and any(
            structure.identifier == obstacle.parent_structure_id and structure.visual_mesh is not None
            for structure in scene.structures
        ):
            continue
        parent_name = _display_name(obstacle.parent_structure_id) if obstacle.parent_structure_id else "unassigned"
        label = _obstacle_visual_label(obstacle, structure_states)
        trace = _obstacle_visual_trace(
            obstacle,
            _obstacle_render_color(obstacle),
            label,
            .84 if obstacle.kind == "ground_rubble" else .68,
            _obstacle_hover_text(obstacle, parent_name),
        )
        trace.update(showlegend=False, legendgroup=_obstacle_legend_group(obstacle, structure_states))
        figure.add_trace(trace)
        if (
            show_elevation_guides
            and obstacle.kind in {"broken_floor", "elevated_debris"}
            and obstacle.minimum[2] > 0
        ):
            guide = _elevation_guide_trace(obstacle)
            guide.update(legendgroup="elevation-guides")
            figure.add_trace(guide)

    _add_base(figure, scene)
    target_summary = " | ".join(
        "{}: {}".format(state, target_state_counts[state])
        for state in ("intact", "minor", "major", "destroyed")
    )
    mesh_usage = scene.generation_metadata.get("visual_mesh_usage", {})
    mesh_summary = (
        "<br>Geometry provenance: source pre {} | source post {} | derived damage {} | OSM context footprints {} | rubble only {}".format(
            mesh_usage.get("source_pre_mesh", 0),
            mesh_usage.get("source_post_mesh", 0),
            mesh_usage.get("derived_partial_mesh", 0),
            mesh_usage.get("footprint_extrusion", 0),
            mesh_usage.get("rubble_only", 0),
        )
        if mesh_usage else ""
    )
    if scene.generation_metadata.get("mode") == "heidata_neighborhood":
        source_header = "Layout: ordered controlled neighbourhood | derived positions, source mesh identities retained"
    elif _is_geospatial_mode(scene.generation_metadata.get("mode")):
        source_header = "Source scenario: {} | original source positions preserved".format(
            scene.generation_metadata.get("source_scenario_schema", "scenario.v1")
        )
    else:
        source_header = "Preset: {}".format(scene.preset.severity)
    _scene_layout(
        figure,
        scene,
        "{} post-earthquake damage layer<br>"
        "<sup>{} | Target buildings: {} ({})<br>"
        "Static context: {} | Base: visible<br>"
        "Roads, tasks and UAV routes: not included{}</sup>".format(
            _mode_label(scene),
            source_header,
            len(target_structures),
            target_summary,
            sum(structure.scene_role == "context" for structure in scene.structures),
            mesh_summary,
        ),
    )
    figure.layout.scene.camera = {
        "eye": {"x": 1.55, "y": -1.65, "z": 1.10} if _is_geospatial_mode(scene.generation_metadata.get("mode")) else {"x": 1.60, "y": -1.90, "z": 3.20},
        "center": {"x": 0.0, "y": 0.0, "z": 0.0},
        "projection": {"type": "orthographic"},
        "up": {"x": 0, "y": 0, "z": 1},
    }
    figure.update_layout(legend={"groupclick": "togglegroup"})
    return figure


def plot_collision_view(scene: DisasterScene):
    """Show every blocked collision volume without non-geometric overlays."""
    import plotly.graph_objects as go
    figure=go.Figure(); figure.add_trace(_ground_trace(scene.environment.world)); _add_3d_legend_proxy(figure,"ground blocked volume","#dc2626","ground-blocked"); _add_3d_legend_proxy(figure,"elevated blocked volume","#7c3aed","elevated-blocked")
    for obstacle in scene.environment.obstacles:
        is_elevated=obstacle.minimum[2]>0
        color="#7c3aed" if is_elevated else "#dc2626"
        label="elevated blocked volume" if is_elevated else "ground blocked volume"
        footprint=obstacle.footprint or _rectangle_polygon(obstacle.minimum[0],obstacle.minimum[1],obstacle.maximum[0]-obstacle.minimum[0],obstacle.maximum[1]-obstacle.minimum[1])
        trace=_polygon_prism_trace(footprint,obstacle.minimum[2],obstacle.maximum[2],color,"{} ({})".format(label,obstacle.kind),.42)
        trace.update(showlegend=False,legendgroup="elevated-blocked" if is_elevated else "ground-blocked")
        figure.add_trace(trace)
        if is_elevated:
            figure.add_trace(_elevation_guide_trace(obstacle))
    _add_base(figure,scene); _scene_layout(figure,scene,"{} collision view: red ground volumes, purple elevated volumes".format(_mode_label(scene)))
    figure.layout.scene.camera = {
        "eye": {"x": 1.40, "y": -1.55, "z": 1.05} if _is_geospatial_mode(scene.generation_metadata.get("mode")) else {"x": 1.45, "y": -1.65, "z": 1.20},
        "center": {"x": 0.0, "y": 0.0, "z": 0.0},
        "projection": {"type": "orthographic"},
        "up": {"x": 0, "y": 0, "z": 1},
    }
    return figure
