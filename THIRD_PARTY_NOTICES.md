# Third-party notices

Sift is MIT-licensed (see LICENSE). The Windows app `Sift.exe` bundles the open-source
components below, each under its own license. They are unmodified. Sift is not affiliated
with or endorsed by Google; "Google Photos" and "Google Takeout" are trademarks of Google LLC.

## Data

| Component | License | Notes |
|---|---|---|
| GeoNames cities1000 place data (via reverse_geocoder) | CC BY 4.0 | Place names © GeoNames, https://www.geonames.org |

## Software

| Component | Version | License | Source |
|---|---|---|---|
| Python | 3.13 | PSF License | https://www.python.org |
| OpenCV (opencv-python-headless) | 4.14 | Apache-2.0 | https://github.com/opencv/opencv-python |
| FFmpeg (opencv_videoio_ffmpeg DLL, inside OpenCV) | bundled with OpenCV 4.14 | LGPL-2.1-or-later | https://github.com/opencv/opencv_3rdparty/tree/ffmpeg/master |
| YuNet face detection model (face_detection_yunet_2023mar) | 2023mar | MIT | https://github.com/opencv/opencv_zoo |
| NumPy | 2.5 | BSD-3-Clause (and bundled 0BSD, MIT, Zlib, CC0-1.0 parts) | https://github.com/numpy/numpy |
| SciPy | 1.18 | BSD-3-Clause | https://github.com/scipy/scipy |
| Pillow | 13.0 | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| pi-heif | 1.4 | BSD-3-Clause | https://github.com/bigcat88/pillow_heif |
| libheif (inside pi-heif) | 1.18.1 | LGPL-3.0 | https://github.com/strukturag/libheif/tree/v1.18.1 |
| libde265 (inside pi-heif) | 1.0.15 | LGPL-3.0 | https://github.com/strukturag/libde265/tree/v1.0.15 |
| reverse_geocoder | 1.5.1 | LGPL-2.1 | https://github.com/thampiman/reverse-geocoder |
| PyInstaller bootloader | 6.22 | GPL-2.0-or-later with the PyInstaller bootloader exception (allows distributing apps built with it) | https://github.com/pyinstaller/pyinstaller |
| Pixelify Sans font | 3 | SIL Open Font License 1.1 | https://github.com/eifetx/Pixelify-Sans |
| pixelarticons icon font | 1.8.1 | MIT | https://github.com/halfmage/pixelarticons |

## About the LGPL components

FFmpeg, libheif, libde265 and reverse_geocoder are used unmodified as separate libraries.
Their full source code is available at the links above. You may replace them with your own
builds: Sift's source is MIT-licensed and the app can be rebuilt with your versions using
PyInstaller. The full license texts are available at:

- LGPL-2.1: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html
- LGPL-3.0: https://www.gnu.org/licenses/lgpl-3.0.html
- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- OFL-1.1: https://openfontlicense.org
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/

THE BUNDLED COMPONENTS ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
