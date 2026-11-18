#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
crw_pdf.py - PDF -> METIN. Sadece Python + sistemdeki iki kucuk arac.

Iki tur PDF vardir:
  1) Metin katmani olan PDF (bilgisayarda yazilmis: kitap, makale). Harfler PDF'in icinde zaten YAZILI durur;
     resimden tahmin etmeye gerek yoktur, birebir cikarilir.        -> pdftotext   (paket: poppler-utils)
  2) Taranmis PDF (fotokopi, fotograf). Icinde yalnizca resim vardir; harfler piksellerden cozulmelidir.
     Bunun icin Croow'un KENDI piksel cozucusu PIKSEL_COZUCU'ya baglanir. OCR / Tesseract KULLANILMAZ.
Kurulum (bir kez):  sudo apt install poppler-utils

Kod icinden:  metin, yontem = crw_pdf.cevir("kitap.pdf", ilerleme=lambda oran, mesaj: ...)
Elle:         python3 crw_pdf.py kitap.pdf [cikti.txt]
"""
import os
import shutil
import subprocess
import sys
import tempfile


def eksik_araclar():
    import pdf_motor
    return [] if pdf_motor.motor() else ["pypdfium2"]


def _sayfa_sayisi(yol):
    import pdf_motor
    try:
        return pdf_motor.sayfa_sayisi(yol)
    except Exception:  # noqa: BLE001
        return None


def metin_katmani(yol):
    import pdf_motor
    return pdf_motor.metin(yol, duzen=True)


PIKSEL_COZUCU = None    # taranmis sayfa icin Croow'un kendi piksel cozucusu buraya baglanacak: f(sayfa_resmi) -> metin


def cevir(yol, ilerleme=None):
    """-> (metin, yontem). Once metin katmani; neredeyse bossa (taranmis PDF) OCR."""
    if ilerleme:
        ilerleme(0, "metin katmanı okunuyor…")
    m = metin_katmani(yol)
    harf = sum(c.isalpha() for c in m)
    n = _sayfa_sayisi(yol) or 1
    if harf >= 50 * n:                                   # sayfa basina en az ~50 harf: gercek metin var
        return m, "metin katmanı (birebir)"
    cozucu = PIKSEL_COZUCU
    if cozucu is None:
        try:
            import crw_harf
            if crw_harf.hazir_mi():
                cozucu = crw_harf.pdf_coz
        except ImportError:
            pass
    if cozucu is not None:
        return cozucu(yol, ilerleme), "Croow piksel çözücü (harf paleti)"
    return m, ("metin katmanı neredeyse boş: taranmış PDF. Harf paleti henüz öğrenilmedi — "
               "Araçlar → 'Harf paletini öğret' ile metinli PDF'lerden öğret")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    metin, yontem = cevir(sys.argv[1], lambda o, msj: print(f"  {msj}", file=sys.stderr))
    hedef = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(sys.argv[1])[0] + ".txt"
    with open(hedef, "w", encoding="utf-8") as f:
        f.write(metin)
    print(f"{hedef} · {len(metin):,} karakter · {yontem}")
