# Unit Type F – 3D model + phone walkthrough

- `build_unit.py` builds everything from code. Layout is taken from `ref/floorplan.png`; finishes come from the listing photos in `ref/`.
- `out/unit.blend`: the Blender scene. `out/render_*.png`: the preview renders.
- `docs/`: the web walkthrough (`index.html`, `unit.glb`, `collision.json`).

## Rebuild

```
blender --background --python build_unit.py               # .blend + .glb + collision
blender --background --python build_unit.py -- --render   # also the preview renders (Cycles, slow)
```

Without the Blender app installed, `pip install bpy numpy` and then `python3 build_unit.py` works too.

## Walk through it

- **Phone:** use the left joystick to walk and drag anywhere else to look around.
- **Desktop:** use WASD or the arrow keys to walk and drag to look.
- **Local:** run `cd docs && python3 -m http.server 8000`, then open http://localhost:8000. Opening the file directly with file:// won't load the model.
- **Share:** in GitHub, go to Settings → Pages, choose "Deploy from a branch", and pick this branch with the `/docs` folder. The link will be `https://<user>.github.io/<repo>/`.
- **Deep link to a spot:** add `?at=x,z,yaw` in metres, where yaw is in degrees and 0 faces north toward the balcony. For example, `?at=0.9,7.0,-135` opens looking at the kitchen.
