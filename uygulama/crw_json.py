#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
crw_json.py - Croow'un butun kayit dosyalari CRW formatinda. Sadece Python gerekir (JSON ve zlib YAZILMAZ).

Iki tur dosya:
  * KAYIT (.crw)  : sozluk/liste/sayi/metin agaci (eskiden .json). Butun metinler dosyada BIR KEZ yazilir,
                    sik metin = kucuk numara (PALET); agac bu numaralarla kurulur. crw.py konteyneri:
                    yazi (ham) · yazi_yer (tablo) · agac (ham) · meta (ham)
  * GUNLUK (.crwl): satir satir eklenen kayitlar (eskiden .jsonl). Dosya hic bastan yazilmaz, sonuna eklenir:
                    "CRWL" + [uzunluk][kayit] [uzunluk][kayit] ...  (uzunluk 0x80 bitli sayi)
Deger kodlamasi (bayt etiketi + deger):
  0 bos · 1 yanlis · 2 dogru · 3 sayi>=0 · 4 sayi<0 · 5 ondalik (8 bayt) · 6 metin (palet numarasi) ·
  7 liste (adet + ogeler) · 8 sozluk (adet + [anahtar, deger]...) · 9 metin (dosya icinde, gunlukte)

ESKI DOSYALAR: oku("x.json") once x.crw'ye bakar; yoksa x.json varsa onu okur ve x.crw'yi yazar. satirlar("x.jsonl")
ayni sekilde x.crwl'yi kullanir; .jsonl daha yeniyse (baska bir program yazmissa) yeni satirlar aktarilir.
Eski .json / .jsonl dosyalarina DOKUNULMAZ.

Kullanim (modullerde json.load / json.dump yerine):
  import crw_json as CJ
  d = CJ.oku("croow_veri/defter.json", {})          # -> croow_veri/defter.crw
  CJ.yaz("croow_veri/defter.json", d)
  CJ.ekle("croow_veri/sohbet.jsonl", {"rol": "kullanici", "metin": "..."})   # -> sohbet.crwl
  for kayit in CJ.satirlar("croow_veri/sohbet.jsonl"): ...
Icerigi okumak icin: python3 crw_oku.py croow_veri/defter.crw
"""
import json
import os
import struct
import threading

import crw

GUNLUK_MAGIC = b"CRWL"
_KILIT = threading.Lock()


def crw_yolu(yol):
    k, uz = os.path.splitext(yol)
    return k + (".crwl" if uz == ".jsonl" else ".crw") if uz in (".json", ".jsonl") else yol


# ====================================================================== deger kodlama
def _kodla(out, v, palet):
    if v is None:
        out.append(0)
    elif v is True:
        out.append(2)
    elif v is False:
        out.append(1)
    elif isinstance(v, int):
        out.append(3 if v >= 0 else 4)
        crw.varint(out, abs(v))
    elif isinstance(v, float):
        out.append(5)
        out += struct.pack("<d", v)
    elif isinstance(v, str):
        if palet is None:
            b = v.encode("utf-8")
            out.append(9); crw.varint(out, len(b)); out += b
        else:
            out.append(6); crw.varint(out, palet[v])
    elif isinstance(v, dict):
        out.append(8); crw.varint(out, len(v))
        for k, x in v.items():
            _kodla(out, str(k), palet)
            _kodla(out, x, palet)
    elif isinstance(v, (list, tuple, set)):
        out.append(7); crw.varint(out, len(v))
        for x in v:
            _kodla(out, x, palet)
    else:
        _kodla(out, str(v), palet)


def _coz(b, i, yazi):
    t = b[i]; i += 1
    if t == 0:
        return None, i
    if t in (1, 2):
        return t == 2, i
    if t in (3, 4):
        n, i = crw.varint_oku(b, i)
        return (n if t == 3 else -n), i
    if t == 5:
        return struct.unpack("<d", b[i:i + 8])[0], i + 8
    if t == 6:
        n, i = crw.varint_oku(b, i)
        return yazi[n], i
    if t == 9:
        n, i = crw.varint_oku(b, i)
        return b[i:i + n].decode("utf-8"), i + n
    n, i = crw.varint_oku(b, i)
    if t == 7:
        out = []
        for _ in range(n):
            x, i = _coz(b, i, yazi)
            out.append(x)
        return out, i
    if t == 8:
        out = {}
        for _ in range(n):
            k, i = _coz(b, i, yazi)
            x, i = _coz(b, i, yazi)
            out[k] = x
        return out, i
    raise ValueError(f"bilinmeyen etiket {t}")


def _metinler(v, sayac):
    if isinstance(v, str):
        sayac[v] = sayac.get(v, 0) + 1
    elif isinstance(v, dict):
        for k, x in v.items():
            _metinler(str(k), sayac)
            _metinler(x, sayac)
    elif isinstance(v, (list, tuple, set)):
        for x in v:
            _metinler(x, sayac)
    elif v is not None and not isinstance(v, (bool, int, float)):
        _metinler(str(v), sayac)


# ====================================================================== KAYIT (.crw)
def crw_yaz(hedef, veri):
    sayac = {}
    _metinler(veri, sayac)
    palet = sorted(sayac, key=lambda s: (-sayac[s], s))     # sik metin = kucuk numara
    no = {s: i for i, s in enumerate(palet)}
    agac = bytearray()
    _kodla(agac, veri, no)
    os.makedirs(os.path.dirname(os.path.abspath(hedef)), exist_ok=True)
    with crw.Yazici(hedef) as y:
        h = y.ham("yazi")
        yer = []
        for s in palet:
            b = s.encode("utf-8")
            yer.append((h.konum(), len(b)))
            h.yaz(b)
        h.bitir()
        t = y.tablo("yazi_yer", "ffh")
        for i, (k, u) in enumerate(yer):
            t.ekle((i, k, u))
        t.bitir()
        a = y.ham("agac"); a.yaz(bytes(agac)); a.bitir()
        m = y.ham("meta"); m.yaz(b"tur=kayit\nsurum=1\n"); m.bitir()


def crw_oku(kaynak):
    ok = crw.Okuyucu(kaynak)
    try:
        ham = ok.ham("yazi")
        yazi = [ham[k:k + u].decode("utf-8") for _, k, u in ok.tablo("yazi_yer")]
        return _coz(ok.ham("agac"), 0, yazi)[0]
    finally:
        ok.kapat()


def oku(yol, varsayilan=None):
    """x.json -> x.crw'nin icerigi (eski x.json varsa bir kez aktarilir). Hicbiri yoksa varsayilan."""
    hedef = crw_yolu(yol)
    with _KILIT:
        eski = os.path.splitext(hedef)[0] + ".json"
        eski_yeni = os.path.exists(eski) and (not os.path.exists(hedef)
                                              or os.path.getmtime(eski) > os.path.getmtime(hedef))
        if os.path.exists(hedef) and not eski_yeni:      # .json'u henuz CRW'ye gecmemis bir program yazdiysa: yeniden al
            return crw_oku(hedef)
        if eski_yeni:
            try:
                veri = json.load(open(eski, encoding="utf-8"))
            except ValueError:
                return varsayilan
            crw_yaz(hedef, veri)
            return veri
    return varsayilan


def yaz(yol, veri):
    """x.json -> x.crw (once gecici dosya, sonra yer degistirir)."""
    with _KILIT:
        crw_yaz(crw_yolu(yol), veri)


def var_mi(yol):
    hedef = crw_yolu(yol)
    return os.path.exists(hedef) or os.path.exists(os.path.splitext(hedef)[0] + ".json")


# ====================================================================== GUNLUK (.crwl)
def _gunluk_ac(hedef):
    yeni = not os.path.exists(hedef) or os.path.getsize(hedef) == 0
    f = open(hedef, "ab")
    if yeni:
        f.write(GUNLUK_MAGIC)
    return f


def _kayit_bayt(kayit):
    b = bytearray()
    _kodla(b, kayit, None)
    out = bytearray()
    crw.varint(out, len(b))
    return out + b


def _eskiyi_aktar(hedef):
    """x.jsonl'de x.crwl'de olmayan satirlar varsa (baska bir program yazdiysa) sona ekler. Ilerleme meta dosyasinda."""
    eski = os.path.splitext(hedef)[0] + ".jsonl"
    if not os.path.exists(eski):
        return
    iz = hedef + ".aktarilan"
    try:
        bas = int(open(iz).read().strip() or 0)
    except (OSError, ValueError):
        bas = 0
    boy = os.path.getsize(eski)
    if boy <= bas:
        return
    with open(eski, "rb") as f, _gunluk_ac(hedef) as g:
        f.seek(bas)
        for satir in f:
            if not satir.endswith(b"\n"):              # yarim satir: sonra
                break
            bas += len(satir)
            try:
                g.write(_kayit_bayt(json.loads(satir)))
            except ValueError:
                continue
    with open(iz + ".tmp", "w") as f:
        f.write(str(bas))
    os.replace(iz + ".tmp", iz)


def ekle(yol, kayit):
    """x.jsonl -> x.crwl'nin sonuna bir kayit ekler."""
    hedef = crw_yolu(yol)
    with _KILIT:
        os.makedirs(os.path.dirname(os.path.abspath(hedef)), exist_ok=True)
        _eskiyi_aktar(hedef)
        with _gunluk_ac(hedef) as f:
            f.write(_kayit_bayt(kayit))


def gunluk_oku(hedef):
    with open(hedef, "rb") as f:
        if f.read(4) != GUNLUK_MAGIC:
            raise ValueError(f"{hedef}: CRWL dosyasi degil")
        tampon, i = f.read(1 << 20), 0
        while True:
            if len(tampon) - i < 10:
                tampon = tampon[i:] + f.read(1 << 20); i = 0
                if not tampon:
                    return
            n, j = crw.varint_oku(tampon, i)
            while len(tampon) - j < n:
                ek = f.read(max(1 << 20, n))
                if not ek:
                    return                               # yarim kalmis son kayit
                tampon = tampon[i:] + ek; j -= i; i = 0
            yield _coz(tampon, j, None)[0]
            i = j + n


def satirlar(yol):
    """x.jsonl -> x.crwl'deki kayitlar sirayla (eski .jsonl satirlari once aktarilir)."""
    hedef = crw_yolu(yol)
    with _KILIT:
        if os.path.exists(os.path.splitext(hedef)[0] + ".jsonl"):
            _eskiyi_aktar(hedef)
    if os.path.exists(hedef):
        yield from gunluk_oku(hedef)
