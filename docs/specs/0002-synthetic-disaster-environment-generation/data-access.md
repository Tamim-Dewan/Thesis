# Real Building Template Data Access

The `real_building` mode accepts only a local preprocessed template containing
an exterior shell plus indoor rooms and connections. It intentionally does not
silently substitute synthetic geometry.

The first source candidate is Matterport3D. Its dataset access and any rights
to redistribute a simplified derived template must be confirmed before source
geometry is placed in this repository. ScanNet is the fallback and requires the
same access and licence review. Until one of those reviews is complete, calling
`generate_disaster_scene(SceneConfig(mode="real_building"))` raises a clear
`SceneTemplateError` because the required local asset is absent.

This preserves the thesis claim: the DU outdoor layout is real OSM based, while
the real building mode will become real only after approved source geometry is
available. Earthquake damage remains a separately generated synthetic layer.
