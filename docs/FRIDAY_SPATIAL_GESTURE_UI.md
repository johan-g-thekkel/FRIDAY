# FRIDAY Spatial / Gesture Interface

The static page `frontend/static/vision.html` is linked from the command-centre sidebar as **Spatial / Gesture UI**.

## What is implemented

- Procedural Three.js solar system HUD with planets, orbital paths, star field, Saturn ring, orbit camera and planet selection.
- Explicit camera start button, local preview, camera-on indicator and Stop button.
- MediaPipe HandLandmarker loaded in the browser for one-hand gesture input.
- Open palm disables auto-rotation and pans; pinch zooms; fist pauses; point selects a target.
- Mouse, wheel, keyboard and on-screen controls remain available when camera permission is declined or tracking is unavailable.
- Sends a `friday:celestial-select` CustomEvent and a same-origin `postMessage` to an embedding parent when a body is selected.
- Webcam frames are processed in the browser and are not uploaded by this page. Camera is requested only after the user presses Enable camera; stopping the camera stops its media tracks.

## Upstream open-source references to evaluate

These are references for architecture and inspiration, not copied wholesale into FRIDAY. Verify licenses, dependencies and assets before adapting code.

- Gesture solar system example: https://github.com/Shri7ul/Gesture-Controlled-Solar-System-v2
- Browser-only MediaPipe + Three.js hand interaction: https://github.com/n07eo/Earth-in-Your-Hand
- Advanced solar system / hand tracking reference: https://github.com/Sirjon-LahanTi/Virtual_Earth
- Official ECC Skills: https://github.com/affaan-m/ECC
- Official Hermes Agent: https://github.com/NousResearch/hermes-agent
- Official NVIDIA NemoClaw: https://github.com/NVIDIA/NemoClaw
- OpenCode: https://github.com/anomalyco/opencode

## Running and limitations

Serve FRIDAY on localhost or HTTPS; browsers generally restrict webcam access on insecure origins. The first camera start downloads MediaPipe's WASM runtime and hand-landmarker model from their published CDN/model host, so an internet connection is needed. Three.js and MediaPipe are also loaded from a CDN. If these resources fail, use the mouse/keyboard controls.

This is a visual interaction prototype, not yet a control surface for operating system settings, devices, or high-impact actions. Do not wire gestures directly to destructive commands. Add explicit confirmation and permission checks for any future action dispatch. The solar-system positions are illustrative, not a scientifically scaled ephemeris.

## Manual smoke-test checklist

1. Open `/static/vision.html` from the FRIDAY command centre.
2. Confirm camera remains off on initial load.
3. Use mouse drag, wheel, zoom buttons, and Reset view.
4. Click Enable camera and accept permission; verify preview and status.
5. Try open palm, pinch, fist and pointing; verify gesture status and camera stop.
6. Deny permission or block CDN access and confirm manual controls still work.
7. Verify the camera indicator turns off and tracks stop after Stop or page navigation.
