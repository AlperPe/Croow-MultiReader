#!/usr/bin/env bash
# Croow MultiReader: Linux x86_64 AppImage'ı KENDİ bilgisayarında derler (GitHub'a gerek yok).
# Kullanım (depo kökünde):   bash paketleme/derle_linux.sh
# Çıktı: dist/CroowMultiReader-x86_64.AppImage
#
# Gerekenler: python3 (tkinter dahil), curl. Arch: sudo pacman -S python tk
#                                         Debian/Ubuntu: sudo apt install python3-venv python3-tk
# appimagetool: elinde varsa  APPIMAGETOOL=/yol/appimagetool  ile ver; yoksa resmi sürümden bir kez indirilir
#   (araç yalnızca paketleme için; kodun hiçbir yere gönderilmez).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
SURUM="${CROOW_SURUM:-$(sed -n 's/^SURUM = "\(.*\)"/\1/p' uygulama/croow_reader.py | head -1)}"
export CROOW_SURUM="${SURUM:-1.0.0}"
ARCH_ADI="$(uname -m)"
[ "$ARCH_ADI" = "x86_64" ] || { echo "Bu betik x86_64 içindir (bu makine: $ARCH_ADI)."; exit 1; }

echo "== 1/6 tkinter kontrolü"
"$PY" -c "import tkinter, platform; print('Python', platform.python_version(), '| Tk', tkinter.TkVersion)" \
  || { echo "tkinter yok. Arch: sudo pacman -S tk   Debian/Ubuntu: sudo apt install python3-tk"; exit 1; }

echo "== 2/6 geçici sanal ortam (.derle-venv)"
rm -rf .derle-venv && "$PY" -m venv .derle-venv
# shellcheck disable=SC1091
. .derle-venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet pillow==11.0.0 numpy==2.1.3 pypdfium2==4.30.0 pyinstaller==6.20.0 \
  || { echo "(sabit sürümler bu Python'a uymadı, güncel sürümler deneniyor)"; pip install --quiet pillow numpy pypdfium2 pyinstaller; }

echo "== 3/6 simgeler"
python paketleme/ikon.py

echo "== 4/6 uygulama (PyInstaller)"
rm -rf build dist
pyinstaller --noconfirm paketleme/croow_reader.spec

echo "== 5/6 AppDir"
rm -rf AppDir && mkdir -p AppDir/usr/bin dist
cp -r dist/CroowMultiReader AppDir/usr/bin/
cp paketleme/linux/AppRun AppDir/AppRun && chmod +x AppDir/AppRun
cp paketleme/linux/croow-multireader.desktop AppDir/
cp paketleme/ikon.png AppDir/croow-multireader.png

echo "== 6/6 AppImage"
ARAC="${APPIMAGETOOL:-}"
if [ -z "$ARAC" ]; then
  ARAC="$(command -v appimagetool || true)"
fi
if [ -z "$ARAC" ]; then
  ARAC=".derle-appimagetool"
  [ -x "$ARAC" ] || { curl -fsSL -o "$ARAC" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" && chmod +x "$ARAC"; }
fi
ARCH=x86_64 "$ARAC" --appimage-extract-and-run AppDir "dist/CroowMultiReader-x86_64.AppImage"
deactivate || true
rm -rf AppDir
echo
echo "Hazır: dist/CroowMultiReader-x86_64.AppImage"
sha256sum dist/CroowMultiReader-x86_64.AppImage
