# JPEG live preview proof of concept

Shows detector preview frames that arrive JPEG-compressed, next to the same frames as raw counts.

- `ophyd_devices.sim.sim_jpeg_camera.SimJpegCamera` (ophyd_devices branch `feat/jpeg-preview-poc`)
  streams frames through its `preview` signal as JPEG bytes (`encoding: "jpeg"` in the message
  metadata) or as raw uint16. Size, encoding, JPEG quality, rate and the 8-bit scaling change
  live: `dev.jpeg_cam.configure_stream(width=4096, height=4096, encoding="jpeg_gray")`.
- The Image widget decodes JPEG previews on the thread that receives Redis messages
  (`BECDispatcher.connect_slot(..., preprocess=decode_jpeg_preview)`) and keeps only the newest
  frame when it falls behind (`latest_only=True`). Everything else in the widget is unchanged and
  works on the decoded 0–255 values.
- `jpeg_view.JpegView` is the picture-only path: Qt decodes the JPEG into a QImage off the GUI
  thread and the view draws it as a pixmap. No levels, histogram, ROI or pixel values.
- `demo.py` puts both views side by side with live camera controls, a statistics table and a
  benchmark sweep (sizes x encodings x views, saved as CSV and JSON).
- `test_offline_benchmark.py` measures the same path without Redis.

Install `simplejpeg` (`pip install -e .[jpeg]`) for the fast decoder; without it the widgets fall
back to Qt's JPEG plugin and the camera to Pillow.

Run, with the camera loaded from `ophyd_devices/configs/jpeg_camera_example.yaml`:

```bash
python -m bec_widgets.examples.jpeg_preview.demo --device jpeg_cam
python -m bec_widgets.examples.jpeg_preview.demo --device jpeg_cam --benchmark --out /tmp/jpeg_bench
QT_QPA_PLATFORM=offscreen python -m pytest -s -p no:randomly \
    bec_widgets/examples/jpeg_preview/test_offline_benchmark.py
```
