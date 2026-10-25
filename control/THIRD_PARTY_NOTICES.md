# VIC Control G05 dependencies

This local Release uses PySide6 / Shiboken6 / Qt 6.8.3, Python 3.12,
PyInstaller 6.16.0, OpenCV 4.12.0 and the existing signed TAP-Windows6 9.27
installation. The TAP driver is NOT installed or redistributed by this GUI.

- PySide6 / Shiboken6 / Qt: LGPLv3 / GPLv3 / commercial options; this build
  uses dynamic libraries. Keep the entire `_internal` directory and its license
  metadata. Qt source and license: https://code.qt.io/qt/qtbase.git/?h=6.8.3
  and https://doc.qt.io/qtforpython-6/licenses.html .
- Python: PSF license, https://docs.python.org/3/license.html .
- PyInstaller: GPLv2 with bootloader exception allowing bundled applications,
  https://pyinstaller.org/en/v6.16.0/license.html .
- OpenCV: Apache-2.0, https://github.com/opencv/opencv/blob/4.12.0/LICENSE .
  The FFmpeg video plugin may have additional bundled notices; see the existing
  project dependency packages before redistributing a Release.
- TAP-Windows6: GPLv2, https://github.com/OpenVPN/tap-windows6 . Public driver
  header and provenance remain in `third_party` in the project.

This is a local development delivery, not an audited public redistribution.
Keep the project source and dependency packages retained by the project backup.
Cognex VisionPro is separately installed and licensed, not bundled.
