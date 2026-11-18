#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""Karga + ceviz logosundan (croow_reader.py içindeki LOGO tarifi) uygulama simgelerini üretir:
ikon.png (1024), ikon.ico (Windows), ikon.icns (macOS)."""
import os
import sys

from PIL import Image, ImageDraw

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BURASI, "..", "uygulama"))
from croow_reader import LOGO  # noqa: E402


def ciz(boy=1024, ornek=4):
    b = boy * ornek
    o = b / 64
    img = Image.new("RGBA", (b, b), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for tur, renk, k in LOGO:
        if tur == "elips":
            d.ellipse(((k[0] - k[2]) * o, (k[1] - k[3]) * o, (k[0] + k[2]) * o, (k[1] + k[3]) * o), fill=renk)
        else:
            d.polygon([(x * o, y * o) for x, y in k], fill=renk)
    return img.resize((boy, boy), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    img = ciz()
    img.save(os.path.join(BURASI, "ikon.png"))
    img.save(os.path.join(BURASI, "ikon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.save(os.path.join(BURASI, "ikon.icns"))
    print("ikon.png, ikon.ico, ikon.icns üretildi")
