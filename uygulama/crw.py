#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""crw.py - CROOW'UN KENDI DOSYA FORMATI (CRW2). Sadece Python gerekir. Dis sikistirma (zlib vb.) KULLANILMAZ.

Resim CRW'sinden gelen fikirlerin veri hali:
  * 0x80 BITI : her sayi icin 'devami var' biti -> kucuk sayi 1 bayt.
  * TEKRAR    : ayni sayinin art arda tekrari tek kayit olur. Isaret, degerin en alt bitinde: (deger << 1) | tekrar_mi.
  * DELTA     : bir onceki kayda gore fark saklanir (kucuk sayi = az bayt).
  * PALET     : sik olan = kucuk numara (sozluk bolumu).
  * KAYIPSIZ  : her sayi birebir geri gelir; esik / atma yok.
Kayitlar SUTUN SUTUN yazilir: ayni sutundaki sayilar birbirine benzer, tekrar bu sayede yakalanir.

Bir .crw dosyasi BOLUMLERDEN olusur, her bolum PARCA PARCA (blok blok) okunur; dosyanin tamami bellege acilmaz:
  ham    : duz bayt (metin vb.). Istenen yerden istenen kadar okunur.
  tablo  : sirali tam sayi kayitlari; 4096'lik bloklar + blok dizini. Ilk sutuna gore arama.
  sozluk : sirali metin anahtarlar (+ sayilar); 64'luk bloklar + blok dizini. Anahtarla arama.

Yerlesim:
  "CRW2" surum(1)
  [bolum][bolum]...
  [bolum listesi]  liste_konumu(8 bayt)  "CRW2"
Dosya once .gecici adla yazilir, bitince yer degistirilir: elektrik kesilirse eski dosya bozulmaz,
yarim kalan dosya sondaki "CRW2" isareti olmadigi icin taninir.
"""
import bisect
import os
import struct
import threading

MAGIC = b"CRW2"
SURUM = 1
_PREAD = hasattr(os, "pread")
HAM, TABLO, SOZLUK = 0, 1, 2
FARK, GRUP_FARKI, DUZ = "f", "g", "h"     # sutun yazim bicimleri


# ====================================================================== sayi katmani
def varint(out, n):
    while n >= 0x80:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    out.append(n)


def varint_oku(buf, i):
    b = buf[i]
    if b < 0x80:
        return b, i + 1
    n, s = b & 0x7F, 7
    i += 1
    while True:
        b = buf[i]; i += 1
        n |= (b & 0x7F) << s
        if b < 0x80:
            return n, i
        s += 7


def _zz(n):            # isaretli -> isaretsiz (-1 -> 1, 1 -> 2): negatif farklar da kucuk kalsin
    return (n << 1) if n >= 0 else ((-n << 1) - 1)


def _zz_geri(n):
    return (n >> 1) if not n & 1 else -((n + 1) >> 1)


# ====================================================================== tekrar katmani
def tekrar_yaz(out, degerler):
    i, n = 0, len(degerler)
    while i < n:
        v = degerler[i]
        r = 1
        while i + r < n and degerler[i + r] == v:
            r += 1
        if r >= 3:
            varint(out, (v << 1) | 1); varint(out, r)
            i += r
        else:
            varint(out, v << 1)
            i += 1


def tekrar_oku(buf, i, adet):
    out = []
    ekle, uzat = out.append, out.extend
    while len(out) < adet:
        t, i = varint_oku(buf, i)
        if t & 1:
            r, i = varint_oku(buf, i)
            uzat([t >> 1] * r)
        else:
            ekle(t >> 1)
    return out, i


def blok_kodla(kayitlar, bicim):
    out = bytearray()
    for s, b in enumerate(bicim):
        col = [k[s] for k in kayitlar]
        if b == FARK:
            col = [_zz(col[0])] + [_zz(col[j] - col[j - 1]) for j in range(1, len(col))]
        elif b == GRUP_FARKI:
            col = [_zz(col[j] - col[j - 1]) if j and kayitlar[j][0] == kayitlar[j - 1][0] else _zz(col[j])
                   for j in range(len(col))]
        tekrar_yaz(out, col)
    return bytes(out)


def blok_coz(buf, adet, bicim):
    cols, i = [], 0
    for _ in bicim:
        col, i = tekrar_oku(buf, i, adet)
        cols.append(col)
    for s, b in enumerate(bicim):
        col = cols[s]
        if b == FARK:
            v = _zz_geri(col[0]); col[0] = v
            for j in range(1, adet):
                v += _zz_geri(col[j]); col[j] = v
        elif b == GRUP_FARKI:
            c0 = cols[0]                      # sutun 0 bu noktada cozulmus olmali (GRUP_FARKI yalnizca s>0'da)
            for j in range(adet):
                d = _zz_geri(col[j])
                col[j] = col[j - 1] + d if j and c0[j] == c0[j - 1] else d
    return list(zip(*cols))


# ====================================================================== yazma
class _HamYazici:
    def __init__(self, ana, ad):
        self.ana, self.ad, self.bas = ana, ad, ana.f.tell()

    def yaz(self, b):
        self.ana.f.write(b)

    def konum(self):
        return self.ana.f.tell() - self.bas

    def bitir(self):
        self.ana._bolum(self.ad, HAM, self.bas, self.konum(), b"")


class _TabloYazici:
    def __init__(self, ana, ad, bicim, blok):
        self.ana, self.ad, self.bicim, self.blok = ana, ad, bicim, blok
        self.bas, self.tampon, self.dizin, self.son = ana.f.tell(), [], [], None

    def ekle(self, kayit):
        if self.son is not None and kayit < self.son:
            raise ValueError(f"{self.ad}: kayitlar sirali gelmeli ({kayit} < {self.son})")
        self.son = kayit
        self.tampon.append(kayit)
        if len(self.tampon) >= self.blok:
            self._bosalt()

    def _bosalt(self):
        if not self.tampon:
            return
        veri = blok_kodla(self.tampon, self.bicim)
        self.dizin.append((self.tampon[0][0], self.ana.f.tell() - self.bas, len(veri), len(self.tampon)))
        self.ana.f.write(veri)
        self.tampon = []

    def bitir(self):
        self._bosalt()
        d = bytearray()
        varint(d, len(self.dizin))
        for x in self.dizin:
            for v in x:
                varint(d, v)
        dk = self.ana.f.tell() - self.bas
        self.ana.f.write(d)
        ek = bytearray(); varint(ek, dk)
        ek += self.bicim.encode("ascii")
        self.ana._bolum(self.ad, TABLO, self.bas, self.ana.f.tell() - self.bas, bytes(ek))


class _SozlukYazici:
    """anahtar (metin) -> sayilar. Anahtarlar sirali gelmeli."""
    BLOK = 64

    def __init__(self, ana, ad, alan):
        self.ana, self.ad, self.alan = ana, ad, alan
        self.bas, self.tampon, self.dizin, self.son = ana.f.tell(), [], [], None

    def ekle(self, anahtar, *sayilar):
        if self.son is not None and anahtar <= self.son:
            raise ValueError(f"{self.ad}: anahtarlar sirali ve tekil olmali")
        self.son = anahtar
        self.tampon.append((anahtar, sayilar))
        if len(self.tampon) >= self.BLOK:
            self._bosalt()

    def _bosalt(self):
        if not self.tampon:
            return
        b = bytearray()
        for a, sy in self.tampon:
            ab = a.encode("utf-8")
            varint(b, len(ab)); b += ab
            for v in sy:
                varint(b, v)
        self.dizin.append((self.tampon[0][0], self.ana.f.tell() - self.bas, len(b), len(self.tampon)))
        self.ana.f.write(b)
        self.tampon = []

    def bitir(self):
        self._bosalt()
        d = bytearray()
        varint(d, len(self.dizin))
        for a, k, u, n in self.dizin:
            ab = a.encode("utf-8")
            varint(d, len(ab)); d += ab
            varint(d, k); varint(d, u); varint(d, n)
        dk = self.ana.f.tell() - self.bas
        self.ana.f.write(d)
        ek = bytearray(); varint(ek, dk); varint(ek, self.alan)
        self.ana._bolum(self.ad, SOZLUK, self.bas, self.ana.f.tell() - self.bas, bytes(ek))


class Yazici:
    """with Yazici("x.crw") as y:  m = y.ham("metin"); m.yaz(b"..."); m.bitir()
                                   t = y.tablo("t", "fgh"); t.ekle((1, 2, 3)); t.bitir()
                                   s = y.sozluk("s", 2); s.ekle("kelime", 5, 7); s.bitir()
    Bolumler sirayla yazilir (ayni anda tek bolum acik)."""

    def __init__(self, yol):
        self.yol, self.gecici = yol, yol + ".gecici"
        self.f = open(self.gecici, "wb")
        self.f.write(MAGIC + bytes((SURUM,)))
        self.bolumler = []

    def _bolum(self, ad, tur, bas, uzun, ek):
        self.bolumler.append((ad, tur, bas, uzun, ek))

    def ham(self, ad):
        return _HamYazici(self, ad)

    def tablo(self, ad, bicim, blok=4096):
        return _TabloYazici(self, ad, bicim, blok)

    def sozluk(self, ad, alan):
        return _SozlukYazici(self, ad, alan)

    def kapat(self):
        lk = self.f.tell()
        d = bytearray()
        varint(d, len(self.bolumler))
        for ad, tur, bas, uzun, ek in self.bolumler:
            ab = ad.encode("utf-8")
            varint(d, len(ab)); d += ab
            varint(d, tur); varint(d, bas); varint(d, uzun)
            varint(d, len(ek)); d += ek
        self.f.write(d + struct.pack("<Q", lk) + MAGIC)
        self.f.flush(); os.fsync(self.f.fileno()); self.f.close()
        os.replace(self.gecici, self.yol)

    def iptal(self):
        try:
            self.f.close(); os.remove(self.gecici)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, t, *_):
        self.iptal() if t else self.kapat()


# ====================================================================== okuma (parca parca)
class _Onbellek(dict):
    def __init__(self, en_cok):
        super().__init__(); self.en_cok = en_cok

    def koy(self, k, v):
        if len(self) >= self.en_cok:
            self.pop(next(iter(self)))
        self[k] = v
        return v


class TabloOkuyucu:
    def __init__(self, ana, bas, uzun, ek, onbellek=256):
        self.ana, self.bas = ana, bas
        dk, i = varint_oku(ek, 0)
        self.bicim = ek[i:].decode("ascii")
        d = ana._oku(bas + dk, uzun - dk)
        n, i = varint_oku(d, 0)
        self.ilk, self.yer = [], []
        for _ in range(n):
            a, i = varint_oku(d, i); k, i = varint_oku(d, i); u, i = varint_oku(d, i); c, i = varint_oku(d, i)
            self.ilk.append(a); self.yer.append((k, u, c))
        self._ob = _Onbellek(onbellek)

    def __len__(self):
        return sum(y[2] for y in self.yer)

    def blok(self, no):
        k = self._ob.get(no)
        if k is None:
            konum, uzun, adet = self.yer[no]
            k = self._ob.koy(no, blok_coz(self.ana._oku(self.bas + konum, uzun), adet, self.bicim))
        return k

    def onekli(self, a):
        """ilk sutunu a olan butun kayitlar."""
        if not self.ilk:
            return []
        bas = max(0, bisect.bisect_left(self.ilk, a) - 1)
        son = bisect.bisect_right(self.ilk, a)
        out = []
        for no in range(bas, max(son, bas + 1)):
            bl = self.blok(no)
            j = bisect.bisect_left(bl, (a,))
            while j < len(bl) and bl[j][0] == a:
                out.append(bl[j]); j += 1
        return out

    def bul(self, a):
        """ilk sutunu a olan ilk kayit (yoksa None)."""
        if not self.ilk:
            return None
        no = max(0, bisect.bisect_right(self.ilk, a) - 1)
        bl = self.blok(no)
        j = bisect.bisect_left(bl, (a,))
        return bl[j] if j < len(bl) and bl[j][0] == a else None

    def __iter__(self):
        for no in range(len(self.yer)):
            yield from self.blok(no)


class SozlukOkuyucu:
    def __init__(self, ana, bas, uzun, ek, onbellek=512):
        self.ana, self.bas = ana, bas
        dk, i = varint_oku(ek, 0)
        self.alan, _ = varint_oku(ek, i)
        d = ana._oku(bas + dk, uzun - dk)
        n, i = varint_oku(d, 0)
        self.ilk, self.yer = [], []
        for _ in range(n):
            u, i = varint_oku(d, i)
            self.ilk.append(d[i:i + u].decode("utf-8")); i += u
            k, i = varint_oku(d, i); b, i = varint_oku(d, i); c, i = varint_oku(d, i)
            self.yer.append((k, b, c))
        self._ob = _Onbellek(onbellek)

    def _blok(self, no):
        k = self._ob.get(no)
        if k is None:
            konum, uzun, adet = self.yer[no]
            d, i, k = self.ana._oku(self.bas + konum, uzun), 0, {}
            for _ in range(adet):
                u, i = varint_oku(d, i)
                a = d[i:i + u].decode("utf-8"); i += u
                sy = []
                for _ in range(self.alan):
                    v, i = varint_oku(d, i); sy.append(v)
                k[a] = tuple(sy)
            self._ob.koy(no, k)
        return k

    def get(self, anahtar):
        no = bisect.bisect_right(self.ilk, anahtar) - 1
        return None if no < 0 else self._blok(no).get(anahtar)

    def __len__(self):
        return sum(y[2] for y in self.yer)

    def __iter__(self):
        for no in range(len(self.yer)):
            yield from self._blok(no).items()


class Okuyucu:
    def __init__(self, yol):
        self.yol = yol
        self.f = open(yol, "rb")
        if self.f.read(5)[:4] != MAGIC:
            raise ValueError(f"{yol}: CRW2 dosyasi degil")
        self.f.seek(-12, 2)
        lk, son = struct.unpack("<Q4s", self.f.read(12))
        if son != MAGIC:
            raise ValueError(f"{yol}: dosya yarim kalmis (son isaret yok)")
        self.f.seek(lk)
        d = self.f.read()
        n, i = varint_oku(d, 0)
        self.bolumler = {}
        for _ in range(n):
            u, i = varint_oku(d, i)
            ad = d[i:i + u].decode("utf-8"); i += u
            tur, i = varint_oku(d, i); bas, i = varint_oku(d, i); uzun, i = varint_oku(d, i)
            e, i = varint_oku(d, i)
            self.bolumler[ad] = (tur, bas, uzun, d[i:i + e]); i += e
        self._acik = {}
        self.fd, self._kilit = self.f.fileno(), threading.Lock()

    def _oku(self, konum, uzun):
        if _PREAD:                                   # konumlu okuma: ayni dosyayi birden cok is parcacigi okuyabilir
            return os.pread(self.fd, uzun, konum)
        with self._kilit:
            self.f.seek(konum)
            return self.f.read(uzun)

    def __contains__(self, ad):
        return ad in self.bolumler

    def ham(self, ad, bas=0, uzun=None):
        tur, b, u, _ = self.bolumler[ad]
        if uzun is None:
            uzun = u - bas
        return self._oku(b + bas, uzun)

    def tablo(self, ad, onbellek=256):
        """onbellek: bellekte acik tutulacak blok sayisi (blok basina 4096 kayit)."""
        if ad not in self._acik:
            tur, b, u, ek = self.bolumler[ad]
            self._acik[ad] = TabloOkuyucu(self, b, u, ek, onbellek)
        return self._acik[ad]

    def sozluk(self, ad, onbellek=512):
        if ad not in self._acik:
            tur, b, u, ek = self.bolumler[ad]
            self._acik[ad] = SozlukOkuyucu(self, b, u, ek, onbellek)
        return self._acik[ad]

    def kapat(self):
        self.f.close()
