# Verification guide

Use this guide after `/develop synthetic disaster environment generation`.

## Automated verification

1. Run the complete existing and new Python test suite.
2. Generate `light`, `moderate`, and `severe` scenes across a representative fixed seed set.
3. Validate every scene invariant, relationship, count, world bound, collision rule, base clearance, and candidate support rule.
4. Compare complete dictionaries from identical inputs and confirm byte stable JSON after canonical encoding.
5. Confirm at least two different seeds produce different valid synthetic layouts.
6. Run existing environment tests unchanged to prove backward compatibility.
7. Disable network access and generate both synthetic and bundled real layout scenes.

## Visual verification

Open the generated Plotly preview and confirm:

* The DU outdoor world uses the complete source sized Science Complex extent and a 60 metre vertical bound by default.
* Roads create visible corridors and buildings occupy blocks rather than roads.
* The base sits on `z = 0` with a visibly clear safety area.
* Ground rubble and road blocks touch the ground.
* Broken floors and elevated debris are associated with a supporting structure.
* Damage states and obstacle categories use distinguishable legend groups.
* Ground and elevated candidate sites use different symbols and valid surfaces.
* The default scene contains 12 ground candidates and 6 elevated candidates.
* Major and destroyed structures visually follow the documented damage to geometry mapping.
* Hover text shows identifiers, kinds, damage state, parent references, and source metadata where relevant.
* Legend controls can hide and reveal each major layer.
* The real building preview shows exterior shell, floors, rooms, doors, stairs, lifts, blocked connections, indoor debris, and indoor candidate sites.
* Indoor `light`, `moderate`, and `severe` scenes show increasing damage, blocked connections, debris, and six indoor candidate sites when capacity allows.

## Failure verification

Confirm clear errors for:

* A custom density that cannot fit after reserving roads and the base.
* A base clearance larger than the usable world.
* An unsupported severity or mode.
* A missing or corrupt template.
* Template geometry outside its declared metric crop.
* A template that would require scaling to fit.
* An elevated candidate without a valid supporting surface.
* A UAV count that is zero or inconsistent with the generated initial position tuple.
* An unresolved structure, road, source, or surface relationship.
* An indoor route that uses a blocked door, corridor, stair, or lift.
* Missing Matterport3D access that does not trigger the documented ScanNet fallback.
* A real building source without an exterior shell or compatible companion source.
* An indoor candidate count that cannot fit on reachable floors.

No case may silently reduce object counts, alter severity, distort scale, relax a collision rule, or download replacement data.
