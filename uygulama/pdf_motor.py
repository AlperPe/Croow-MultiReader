#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
pdf_motor.py - PDF işlemlerinin tek kapısı. Her sistemde çalışır.

poppler (pdftotext, pdftoppm, pdfinfo) kuruluysa onu kullanır; değilse uygulamanın içinde gelen
pypdfium2 ile aynı sonuçları üretir. Böylece Windows ve macOS'ta ek kurulum gerekmez.

  sayfa_sayisi(pdf)                      -> int
  ciz(pdf, k, dpi, kirp=None)            -> gri (L) PIL resmi; kirp=(x, y, w, h) piksel, o dpi'de
  kelimeler(pdf, k, dpi)                 -> [(x0, y0, x1, y1, kelime)] piksel, o dpi'de
  metin(pdf, k=None, duzen=True)         -> sayfanın (k) ya da tüm PDF'in metin katmanı (sayfalar \\f ile ayrılır)
  motor()                                -> "poppler" | "pdfium" | None
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

_PDFIUM = None
_YEREL_POPPLER = os.environ.get("CROOW_POPPLER", "1") != "0"   # 0: poppler kurulu olsa da pdfium kullan


def _sessiz():
    """Windows'ta alt süreç için konsol penceresi açılmasın."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"startupinfo": si, "creationflags": 0x08000000}
    return {}


def _poppler(ad):
    return _YEREL_POPPLER and shutil.which(ad) is not None


def _pdfium():
    global _PDFIUM
    if _PDFIUM is None:
        try:
            import pypdfium2 as pdfium
            _PDFIUM = pdfium
        except ImportError:
            _PDFIUM = False
    return _PDFIUM or None


def motor():
    if _poppler("pdftoppm") and _poppler("pdftotext") and _poppler("pdfinfo"):
        return "poppler"
    return "pdfium" if _pdfium() else None


def _gerekli():
    if not _pdfium():
        raise RuntimeError("PDF okuyucu bulunamadı. Kurulum:  pip install pypdfium2   "
                           "(ya da poppler: sudo apt install poppler-utils)")
    return _pdfium()


# ====================================================================== sayfa sayısı
def sayfa_sayisi(pdf):
    if _poppler("pdfinfo"):
        r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, **_sessiz())
        for s in r.stdout.splitlines():
            if s.startswith("Pages:"):
                return int(s.split()[1])
    pdfium = _gerekli()
    belge = pdfium.PdfDocument(pdf)
    try:
        return len(belge)
    finally:
        belge.close()


# ====================================================================== çizim
def ciz(pdf, k, dpi, kirp=None):
    """k. sayfayı (1'den başlar) dpi çözünürlükte gri olarak çizer. kirp: o çözünürlükte (x, y, w, h)."""
    from PIL import Image
    if _poppler("pdftoppm"):
        with tempfile.TemporaryDirectory(prefix="croow_ciz_") as kl:
            on = os.path.join(kl, "s")
            komut = ["pdftoppm", "-r", str(dpi), "-gray", "-png", "-f", str(k), "-l", str(k)]
            if kirp:
                x, y, w, h = (int(round(v)) for v in kirp)
                komut += ["-x", str(x), "-y", str(y), "-W", str(w), "-H", str(h)]
            subprocess.run(komut + [pdf, on], capture_output=True, **_sessiz())
            y = next((os.path.join(kl, f) for f in os.listdir(kl) if f.endswith(".png")), None)
            if not y:
                return None
            img = Image.open(y).convert("L")
            img.load()
            return img
    pdfium = _gerekli()
    belge = pdfium.PdfDocument(pdf)
    try:
        if not 1 <= k <= len(belge):
            return None
        sayfa = belge[k - 1]
        olcek = dpi / 72.0
        if kirp:
            gw, gh = sayfa.get_size()                    # nokta (1/72 inç)
            x, y, w, h = kirp
            sol, ust = x / olcek, y / olcek
            sag = max(0.0, gw - (x + w) / olcek)
            alt = max(0.0, gh - (y + h) / olcek)
            img = sayfa.render(scale=olcek, grayscale=True, crop=(sol, alt, sag, ust)).to_pil()
        else:
            img = sayfa.render(scale=olcek, grayscale=True).to_pil()
        return img.convert("L")
    finally:
        belge.close()


# ====================================================================== kelime kutuları
def kelimeler(pdf, k, dpi):
    """Metin katmanındaki kelimeler ve kutuları (piksel, o dpi'de). poppler'ın -bbox çıktısıyla aynı düzen."""
    s = dpi / 72.0
    out = []
    if _poppler("pdftotext"):
        r = subprocess.run(["pdftotext", "-bbox", "-f", str(k), "-l", str(k), pdf, "-"], capture_output=True, **_sessiz())
        for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
                             r.stdout.decode("utf-8", "replace")):
            x0, y0, x1, y1 = (float(m.group(i)) * s for i in range(1, 5))
            out.append((int(x0) - 1, int(y0), int(x1) + 2, int(y1), html.unescape(m.group(5))))
        return out
    pdfium = _gerekli()
    belge = pdfium.PdfDocument(pdf)
    try:
        if not 1 <= k <= len(belge):
            return out
        sayfa = belge[k - 1]
        _, gh = sayfa.get_size()
        tp = sayfa.get_textpage()
        n = tp.count_chars()
        kelime, kutu = [], None
        onceki = None

        def bitir():
            if kelime and kutu:
                x0, y0, x1, y1 = kutu
                out.append((int(x0 * s) - 1, int((gh - y1) * s), int(x1 * s) + 2, int((gh - y0) * s), "".join(kelime)))

        for i in range(n):
            c = tp.get_text_range(i, 1)
            if not c or c.isspace() or c in "\r\n\x02":
                bitir(); kelime, kutu, onceki = [], None, None
                continue
            sol, alt, sag, ust = tp.get_charbox(i, loose=True)     # yazı tipine göre kutu (poppler gibi)
            if onceki is not None:
                # satır değiştiyse ya da harfler arasında belirgin boşluk varsa yeni kelime
                yuk = max(1e-6, ust - alt, onceki[3] - onceki[1])
                if abs(alt - onceki[1]) > 0.5 * yuk or sol - onceki[2] > 0.25 * yuk:
                    bitir(); kelime, kutu = [], None
            kelime.append(c)
            kutu = (sol, alt, sag, ust) if kutu is None else (min(kutu[0], sol), min(kutu[1], alt),
                                                              max(kutu[2], sag), max(kutu[3], ust))
            onceki = (sol, alt, sag, ust)
        bitir()
        tp.close()
        return out
    finally:
        belge.close()


# ====================================================================== metin katmanı
def metin(pdf, k=None, duzen=True):
    """Metin katmanı. k verilirse yalnızca o sayfa; verilmezse tüm sayfalar (\\f ile ayrılır)."""
    if _poppler("pdftotext"):
        komut = ["pdftotext"] + (["-layout"] if duzen else []) + ["-enc", "UTF-8"]
        if k:
            komut += ["-f", str(k), "-l", str(k)]
        r = subprocess.run(komut + [pdf, "-"], capture_output=True, **_sessiz())
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or "pdftotext hata verdi")
        return r.stdout.decode("utf-8", "replace").rstrip("\f")
    pdfium = _gerekli()
    belge = pdfium.PdfDocument(pdf)
    try:
        aralik = [k] if k else range(1, len(belge) + 1)
        parcalar = []
        for i in aralik:
            if not 1 <= i <= len(belge):
                continue
            tp = belge[i - 1].get_textpage()
            parcalar.append(tp.get_text_bounded().replace("\r\n", "\n").replace("\r", "\n"))
            tp.close()
        return "\f".join(parcalar)
    finally:
        belge.close()
