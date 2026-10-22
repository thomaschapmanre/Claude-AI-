"""Import Unit Type F into an open Unreal Engine 5 project and place it in the current level.

Run inside the Unreal Editor: Tools > Execute Python Script... > pick this file.
(Needs the "Python Editor Script Plugin" enabled; it is on by default in UE 5.)

shortcut: written against the UE 5 Python API but not run here (no Unreal in the build
environment); if a call errors, paste the Output Log message back to Claude.
"""
import os
import unreal

FBX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "unit_type_f.fbx")
DEST = "/Game/UnitTypeF"

opts = unreal.FbxImportUI()
opts.import_mesh = True
opts.import_materials = True
opts.import_textures = True
opts.import_as_skeletal = False
opts.mesh_type_to_import = unreal.FBXImportType.FBXIT_STATIC_MESH
sm = opts.static_mesh_import_data
sm.combine_meshes = False                 # keep walls, doors, furniture as separate actors
sm.auto_generate_collision = False        # collision comes from the render mesh below
sm.transform_vertex_to_absolute = True    # every piece imports already in place

task = unreal.AssetImportTask()
task.filename = os.path.normpath(FBX)
task.destination_path = DEST
task.automated = True
task.replace_existing = True
task.save = True
task.options = opts
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

placed = 0
for path in task.imported_object_paths:
    asset = unreal.load_asset(path)
    if not isinstance(asset, unreal.StaticMesh):
        continue
    # boxes are simple shapes, so per-triangle collision is cheap and exact (no walking through walls)
    body = asset.get_editor_property("body_setup")
    body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    unreal.EditorLevelLibrary.spawn_actor_from_object(asset, unreal.Vector(0, 0, 0))
    placed += 1
unreal.log(f"Unit Type F: placed {placed} meshes from {FBX}")
