# Unit Type F — 3D model and walkthrough

2 bed / 2 bath apartment rebuilt from `ref/floorplan.png` and the listing photos in `ref/`.

## What's here

| Path | What it is |
|---|---|
| `build_unit.py` | Builds the whole model from scratch. Every room, door and fixture is defined here in plan feet. |
| `out/unit_type_f.blend` | Editable Blender project (textures in `textures/`). |
| `out/unit_type_f.fbx` | Export for Unreal Engine. |
| `out/unit_type_f.glb` | Export for the web and other viewers. |
| `out/top_down.png`, `out/compare_plan_vs_model.png`, `out/view_*.png` | Preview renders. |
| `web/` | First-person walkthrough (phone and desktop). |
| `unreal/import_unit.py` | Imports the FBX into an Unreal project with collision. |

## Rebuild

```
blender --background --python build_unit.py            # model + exports
blender --background --python build_unit.py -- --render # also preview renders (~6 min on CPU)
```

The build checks itself: it reopens the saved `.blend` and re-imports the `.glb` and stops with an error if any mesh or texture is missing.

## Unreal Engine (on your own computer)

1. Install Unreal Engine 5 from the Epic Games Launcher.
2. Create a new project: **Games > First Person**, Blueprint, no starter content.
3. Open a new empty level (**File > New Level > Basic**) and delete its floor.
4. **Tools > Execute Python Script…** and pick `unreal/import_unit.py`.
5. Move the **Player Start** to just inside the front door (bottom-left of the plan), facing up the hallway. Make the capsule radius about 25 cm if it feels tight in doorways.
6. Press **Play** to walk around. To ship it: **Platforms > Windows > Package Project**.

The Unreal steps have not been tested yet, because the build environment has no Unreal Engine.
