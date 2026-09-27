# Synthetic disaster environment generation rationale

## Context

The thesis needs many repeatable post earthquake environments for controlled UAV planning experiments. Purely arbitrary boxes are easy to generate but weak as research evidence. Directly loading full photogrammetry, LiDAR, or satellite datasets would add large files, preprocessing dependencies, licensing concerns, and geometry that is too detailed for the current planning model.

The existing simulator already has a continuous world, typed rectangular obstacles, one ground base, point validity checks, and a Plotly preview. The next feature must enrich that foundation without breaking its public API or prematurely implementing survivor tasks, route planning, flight physics, or scenario persistence. The selected DU environment must fit the complete mapped Science Complex cluster, so its horizontal world bounds are source sized rather than fixed to an arbitrary rectangle. The real building mode also needs source sized local bounds.

The generator must also be dependable. Built in presets should not occasionally fail because random objects no longer fit. Real geometry must retain physical scale, and any simplification or imputation must be visible in provenance rather than hidden.

## Options considered

### Option 1: Fully random synthetic boxes

Continue sampling independent rectangular obstacles anywhere inside the world.

**Pros**:

* Small implementation and fast generation.
* Easy seed based reproducibility.

**Cons**:

* Weak urban structure and weak connection to published evidence.
* Blind placement can fail or produce implausible scenes.

### Option 2: Raw real world three dimensional datasets at runtime

Download and process point clouds, meshes, and map data when creating a scene.

**Pros**:

* Highest direct geometric detail.
* Strong visual connection to measured places.

**Cons**:

* Large data, complex tooling, slower execution, and poor Colab or Kaggle portability.
* Measured geometry does not directly provide all simulator relationships and candidate sites.

### Option 3: Real DU layout and real building layout with synthetic damage

Use OSM to create a preprocessed DU outdoor template, use Matterport3D or ScanNet to create one preprocessed building template with exterior and interior geometry, and apply versioned synthetic damage rules to both. Runtime geometry remains simple and local.

**Pros**:

* Balances experimental control, research grounding, visual inspection, and lightweight execution.
* Supports many seeded scenes across outdoor and indoor environments.
* Keeps source geometry real while making damage experiments repeatable.
* Makes provenance, imputation, and simplification explicit.

**Cons**:

* Requires careful preprocessing and documentation.
* Simplified geometry cannot preserve every feature of the source data.

## Rationale

Option 3 best matches the thesis stage. The planner needs many controlled episodes more than it needs detailed structural physics. DU provides a familiar and traceable outdoor layout. A real building scan provides interior and exterior geometry without requiring a survey, while synthetic damage makes controlled earthquake episodes possible.

Constructive urban generation is chosen over rejection sampling because official presets must complete predictably. Keeping true metric scale and recording all deterministic imputation protects the interpretation of distances, heights, and later UAV energy calculations.

The first preset uses fixed, conservative modelling assumptions rather than claiming false statistical precision from heterogeneous datasets. Versioning the table as `earthquake.v1` allows later thesis analysis to revise the values without changing the meaning of completed experiments.

## Flight focused geometry update

The current thesis experiment uses UAVs that move through air. Roads are therefore not part of the active flight space and road blocks create visual clutter without constraining the intended route model. The selected approach keeps source roads only as optional local template metadata for a later ground vehicle study. The generated airborne scene contains neither active road geometry nor road blocks.

The earlier rubble and elevated debris representation used low rectangular prisms. That was easy to validate but it made destroyed structures look like a few unrelated boxes. The updated model uses seeded irregular polygon fragments with uneven top profiles. This makes a rubble pile and an elevated broken slab recognisable in the damage view while the collision layer uses the complete enclosing volume. The conservative envelope can block slightly more airspace than the visual fragment, but it avoids presenting a route as safe when it could hit debris.

Destroyed structures remain identifiable through a filled source footprint layer even when no full height building volume survives. This separates the semantic fact that a building existed at that location from the physical fact that its standing volume has collapsed.

## Research interpretation

The sources have different roles and are not treated as interchangeable truth.

* Matterport3D is the primary real building geometry candidate because it provides accurately scaled real meshes. ScanNet is the fallback because it provides real reconstructed indoor scenes with semantic labels.
* University of Dhaka OSM geometry is the primary outdoor layout source.
* xBD informs building footprints and building damage categories across disasters including earthquakes.
* OpenStreetMap and Humanitarian OpenStreetMap inform roads and general urban layout.
* RescueNet informs general post disaster road blockage and damage labelling patterns, but its hurricane context is recorded and not presented as earthquake specific evidence.
* C3DO and 3DAeroRelief inform damaged facade, rubble, and post disaster geometry patterns. They supplement rather than replace earthquake sources.
* 3DIFICE may inform fine structural damage interpretation but is not the primary urban layout source.
* TriSAR informs repeated seeded UAV experiment design rather than scene geometry.

Preset numbers must be stored in versioned data files with comments or metadata linking each parameter group to its evidence and interpretation. The implementation must not invent unsupported precision. Where a source cannot justify a narrow range, the preset should use a documented broad range and the thesis should describe it as a modelling assumption.

## References

### Project sources

* `docs/scope/scope.md`, feature 4 intent and completion boundary.
* `docs/specs/0001-environment-configuration-geometry/index.md`, existing world and geometry contract.
* `.agents/skills/plotly/SKILL.md`, interactive scientific visualization convention.

### Practices and standards

* Constructive generation with early capacity validation for guaranteed built in configurations.
* Seeded deterministic experiments for reproducibility.
* Dataset provenance and explicit transformation manifests for derived research data.
* Additive extension of an existing public model to preserve backward compatibility.

### Links

* xBD building damage dataset paper: https://openaccess.thecvf.com/content_CVPRW_2019/html/cv4gc/Gupta_Creating_xBD_A_Dataset_for_Assessing_Building_Damage_from_Satellite_CVPRW_2019_paper.html
* RescueNet UAV post disaster dataset paper: https://www.nature.com/articles/s41597-023-02799-4
* Humanitarian OpenStreetMap disaster data guidance: https://wiki.openstreetmap.org/wiki/Humanitarian_OSM_Team/HDX_Disaster_Data
* Matterport3D research dataset access: https://matterport.com/partners/meta
* ScanNet indoor reconstruction dataset: https://www.scan-net.org/
* Zillow Indoor Dataset as a floor plan alternative: https://github.com/zillow/zind
* South Napa earthquake LiDAR dataset: https://opentopography.org/node/3550
* C3DO damaged facade point cloud dataset: https://data.mendeley.com/datasets/924cfprrwr/3
* 3DAeroRelief post disaster point cloud dataset: https://github.com/BinaLab/3DAeroRelief
* 3DIFICE synthetic earthquake damage dataset: https://databank.illinois.edu/datasets/IDB-6415287
* TriSAR UAV earthquake simulation protocol: https://arxiv.org/abs/2609.01731

## Migration plan

**Strategy**: additive extension with no data migration.

**Phases**:

1. Preserve the current environment API and add optional relationship fields plus new scene models.
2. Route new disaster scene calls through the new generator while existing callers continue using `generate_environment`.
3. Add the DU outdoor template and synthetic damage layer.
4. Add the real building template and indoor damage and connectivity layer.

**Rollback**: Remove new scene modules and exports. Existing environment code and callers continue unchanged.

**Risks**: Optional fields could accidentally change equality or serialization expectations. Indoor dataset access or redistribution terms may block Matterport use, so the ScanNet fallback must be verified before implementation. New tests must lock the old constructor and output behavior before extension.
