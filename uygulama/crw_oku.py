#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
crw_oku.py - CRW OKUMA MOTORU: her .crw dosyasini METIN olarak gosterir. Sadece Python gerekir.
Dosya parca parca okunur; ne kadar buyuk olursa olsun bellege acilmaz.

Taninan dosyalar:
  * dil modeli    (ngram_ai4: model_crw/ngram3_base.crw, deltalar)
  * kitap dizini  (croow_dizin: kitap_dizin.crw, kitap_dizin.ek0001.crw)
  * her CRW2 dosyasi (bolumleri ham / tablo / sozluk olarak)
  * kayit dosyalari (crw_json: defter.crw, konular.crw ...)  -> agac olarak; alt dal:  DOSYA kayitlar/12
  * gunluk dosyalari (.crwl: sohbet.crwl ...)                 -> her kayit bir satir
  * ESKI zlib'li model dosyalari (ngram3_base.crw "CRW6") - yalnizca okunur, dokunulmaz

Kullanim:
  python3 crw_oku.py DOSYA                      -> ozet: ne dosyasi, bolumler, kayit sayilari
  python3 crw_oku.py DOSYA kelimeler            -> model: kelimeler (numara, kelime, adet)
  python3 crw_oku.py DOSYA ngram [1|2|3]        -> model: "onceki kelimeler -> sonraki  adet"
  python3 crw_oku.py DOSYA kelime fizik         -> model: kelimenin sayilari, oncesi/sonrasi, iliskileri
  python3 crw_oku.py DOSYA basliklar | dosyalar | isimler
  python3 crw_oku.py DOSYA parca 120            -> kitap dizini: 120. parcanin metni
  python3 crw_oku.py DOSYA metin                -> kitap dizini: butun metin (paragraf paragraf)
  python3 crw_oku.py DOSYA kok fizik            -> kitap dizini: bu kokun gectigi parcalar
  python3 crw_oku.py DOSYA bolum ADI            -> herhangi bir bolumu duz metin olarak
Secenekler:
  --ilk 100    listelerde ilk 100 satir (varsayilan 50)
  --hepsi      sinir yok (dosyaya yazmak icin:  python3 crw_oku.py DOSYA ngram 2 --hepsi > ngram2.txt)
"""
import json
import os
import sys

_BURASI = os.path.dirname(os.path.abspath(__file__))
for _k in (_BURASI, os.path.dirname(_BURASI)):           # model_crw/ icinden calistirilsa da crw.py bulunsun
    if os.path.exists(os.path.join(_k, "crw.py")) and _k not in sys.path:
        sys.path.insert(0, _k)

import crw  # noqa: E402

KOMUTLAR = {
    "model": "kelimeler · ngram 1|2|3 · kelime KELIME · basliklar · dosyalar · isimler · bolum ADI",
    "dizin": "parca NO · metin · kok KOK · bolum ADI",
    "crw2": "bolum ADI",
}

ILK = 50


def _cik(satirlar):
    """Satirlari yazar; --ilk sinirina ve '| head' kapanmasina dayanikli."""
    n = 0
    try:
        for s in satirlar:
            if ILK and n >= ILK:
                print(f"... (daha fazlası için --ilk {ILK * 10} ya da --hepsi)")
                return
            print(s)
            n += 1
    except BrokenPipeError:
        sys.stderr.close()


def _boy(n):
    return f"{n / 1e6:,.1f} MB" if n >= 1e6 else f"{n / 1e3:,.1f} KB" if n >= 1e3 else f"{n} B"


# ====================================================================== tur bulma
def tur_bul(yol):
    with open(yol, "rb") as f:
        bas = f.read(4)
    if bas == crw.MAGIC:
        ok = crw.Okuyucu(yol)
        if "kelime" in ok and "sonraki0" in ok:
            return "model", ok
        if "gecis" in ok and "parca" in ok:
            return "dizin", ok
        if "agac" in ok:
            return "kayit", ok
        return "crw2", ok
    if bas == b"CRWL":
        return "gunluk", None
    if bas in (b"CRW1", b"CRW4"):
        return "resim", None
    try:
        import zlib                                      # yalnizca ESKI dosyalari tanimak icin
        with open(yol, "rb") as f:
            if zlib.decompressobj().decompress(f.read(65536))[:4] == b"CRW6":
                return "eski", None
    except Exception:  # noqa: BLE001
        pass
    return "bilinmiyor", None


# ====================================================================== genel CRW2
TURLER = {crw.HAM: "ham", crw.TABLO: "tablo", crw.SOZLUK: "sözlük"}


def ozet_genel(ok):
    for ad, (tur, _, uzun, _) in ok.bolumler.items():
        ek = ""
        if tur == crw.TABLO:
            ek = f" · {len(ok.tablo(ad)):,} kayıt · biçim {ok.tablo(ad).bicim}"
        elif tur == crw.SOZLUK:
            ek = f" · {len(ok.sozluk(ad)):,} anahtar"
        yield f"  {ad:14s} {TURLER.get(tur, tur):6s} {_boy(uzun):>10s}{ek}"


def bolum_metin(ok, ad):
    if ad not in ok:
        yield f"'{ad}' adında bölüm yok. Bölümler: {', '.join(ok.bolumler)}"
        return
    tur = ok.bolumler[ad][0]
    if tur == crw.TABLO:
        for r in ok.tablo(ad):
            yield "\t".join(map(str, r))
    elif tur == crw.SOZLUK:
        for k, v in ok.sozluk(ad):
            yield k + "\t" + "\t".join(map(str, v))
    else:
        uzun, bas, parca = ok.bolumler[ad][2], 0, b""
        while bas < uzun:                                # 1 MB'lik parcalarla
            parca += ok.ham(ad, bas, min(1 << 20, uzun - bas))
            bas += 1 << 20
            *satirlar, parca = parca.split(b"\n")
            for s in satirlar:
                yield s.decode("utf-8", "replace")
        if parca:
            yield parca.decode("utf-8", "replace")


# ====================================================================== dil modeli
def _model(yol):
    import ngram_crw
    return ngram_crw._Parca(yol)


def model_ozet(ok, yol):
    p = _model(yol)
    m = p.meta
    yield f"DİL MODELİ (ngram_ai4) · N={m.get('N')} · {p.V:,} kelime · {p.tot0:,} kelime geçişi"
    for k in range(m.get("N", 3)):
        yield f"  {k + 1}-gram kaydı: {len(p.t[f'sonraki{k}']):,}"
    yield (f"  cümle imzası: {len(p.t['imza']):,} · ilişki: {len(p.t['iliski']):,} · "
           f"başlık: {len(m.get('titles', [])):,} · okunan dosya: {len(m.get('files', {})):,}")
    if m.get("merged"):
        yield f"  tabana birleştirilmiş deltalar: {', '.join(m['merged'])}"
    yield "Bölümler:"
    yield from ozet_genel(ok)


def model_kelimeler(yol):
    p = _model(yol)
    for i, v in p.t["sonraki0"]:
        yield f"{i}\t{p.kelime(i)}\t{v}"


def model_ngram(yol, n):
    import ngram_crw
    p = _model(yol)
    k = n - 1
    if k == 0:
        for i, v in p.t["sonraki0"]:
            yield f"→ {p.kelime(i)}\t{v}"
        return
    for key, w, v in p.t[f"sonraki{k}"]:
        ctx = " ".join(p.kelime(i) for i in ngram_crw._coz_anahtar(key, k, p.V))
        yield f"{ctx} → {p.kelime(w)}\t{v}"


def model_kelime(yol, w):
    import ngram_crw
    p = _model(yol)
    i = p.id(w)
    if i is None:
        yield f"'{w}' bu dosyada yok."
        return
    adet = p.t["sonraki0"].bul(i)
    kon = p.t["konum"].bul(i)
    yield f"'{w}' · numara {i} · {adet[1] if adet else 0:,} kez geçti"
    if kon and kon[1]:
        yield f"  ortalama cümle içi konum: {ngram_crw._i2f(kon[2]) / kon[1]:.2f} (0 = baş, 1 = son)"
    sonra = sorted(((v, p.kelime(x)) for _, x, v in p.t["sonraki1"].onekli(i)), reverse=True)
    yield "  sonrasında: " + (", ".join(f"{s}({v})" for v, s in sonra[:15]) or "-")
    il = sorted(((v, p.kelime(b)) for _, b, v in p.t["iliski"].onekli(i)), reverse=True)
    yield "  bu kelimeli cümleden sonra gelenler: " + (", ".join(f"{s}({v})" for v, s in il[:15]) or "-")
    c = p.t["cevap"].bul(i)
    if c:
        yield f"  bir sorunun cevabında {c[1]} kez kullanıldı"


MODEL_BASLIK = {
    "konum": "kelime\tkaç kez\tortalama yeri (0 = cümle başı, 1 = sonu)",
    "iliski": "bu kelimeli cümleden sonra → gelen kelime\tkaç kez",
    "cevap": "kelime\tbir sorunun cevabında kaç kez",
    "kucuk": "küçük harfle de geçen kelime (özel isim değil)",
    "imza": "cümle imzası (eğitimdeki cümlenin 32 bitlik parmak izi; kopya kontrolü için)",
    "kelime_yer": "numara\tkelime\t(dosyadaki yeri, uzunluğu)",
}


def model_bolum(yol, ad):
    """Model bolumlerini numara yerine kelimeyle, cozulmus degerlerle gosterir."""
    import ngram_crw
    p = _model(yol)
    if ad.startswith("sonraki") and ad[7:].isdigit():
        yield from model_ngram(yol, int(ad[7:]) + 1)
        return
    if ad == "kelime":
        for w, (i,) in p.kel:
            yield f"{w}\t{i}"
        return
    if ad not in MODEL_BASLIK:
        yield from bolum_metin(p.ok, ad)
        return
    yield "# " + MODEL_BASLIK[ad]
    t = p.ok.tablo(ad)
    for r in t:
        if ad == "konum":
            i, n, bit = r
            yield f"{p.kelime(i)}\t{n}\t{ngram_crw._i2f(bit) / n:.2f}" if n else f"{p.kelime(i)}\t0\t-"
        elif ad == "iliski":
            yield f"{p.kelime(r[0])} → {p.kelime(r[1])}\t{r[2]}"
        elif ad == "cevap":
            yield f"{p.kelime(r[0])}\t{r[1]}"
        elif ad == "kucuk":
            yield p.kelime(r[0])
        elif ad == "imza":
            yield f"{r[0]:08x}"
        elif ad == "kelime_yer":
            yield f"{r[0]}\t{p.kelime(r[0])}\t({r[1]}, {r[2]})"


def model_meta(yol, alan):
    m = _model(yol).meta
    if alan == "basliklar":
        yield from m.get("titles", [])
    elif alan == "dosyalar":
        yield from (f"{k}\t{v}" for k, v in m.get("files", {}).items())
    elif alan == "isimler":
        for t, c in m.get("names", {}).items():
            for ad, v in sorted(c.items(), key=lambda x: -x[1]):
                yield f"{t}\t{ad}\t{v}"


# ====================================================================== kitap dizini
def dizin_ozet(ok):
    m = dict(s.split("=", 1) for s in ok.ham("meta").decode("utf-8").splitlines() if "=" in s)
    dosya = ok.ham("dosya").decode("utf-8").count("\n")
    yield (f"KİTAP DİZİNİ (croow_dizin) · {int(m.get('parca_sayisi', 0)):,} parça · {dosya:,} dosya · "
           f"{len(ok.sozluk('terim')):,} kök · kuruluş {m.get('kurulus', '?')}")
    yield "Bölümler:"
    yield from ozet_genel(ok)


def _dosyalar(ok):
    return [s.split("\t", 1)[0] for s in ok.ham("dosya").decode("utf-8").splitlines()]


def dizin_parca(ok, i):
    r = ok.tablo("parca").bul(i)
    if not r:
        yield f"{i}. parça bu dosyada yok."
        return
    _, d, bas, boy = r
    yield f"[{i}] {_dosyalar(ok)[d]}"
    yield ok.ham("metin", bas, boy).decode("utf-8", "replace")


def dizin_kok(ok, w):
    v = ok.sozluk("terim").get(w)
    if not v:
        yield f"'{w}' kökü yok (kökler ilk 5 harftir, küçük harf: 'fizik', 'kuant')."
        return
    yield f"'{w}' · {v[1]:,} parçada geçiyor"
    dosyalar = _dosyalar(ok)
    for _, pn, c in ok.tablo("gecis").onekli(v[0]):
        _, d, bas, boy = ok.tablo("parca").bul(pn)
        yield f"[{pn}] ({c} kez) {os.path.basename(dosyalar[d])}: {ok.ham('metin', bas, min(boy, 160)).decode('utf-8', 'replace')}…"


# ====================================================================== eski (zlib'li) model
def eski_ozet(yol, istek):
    import ngram_crw
    r = ngram_crw._EskiAkis(yol)
    r.raw(4)
    N = r.get()
    nv, bl = r.get(), r.get()
    vocab = r.raw(bl).decode("utf-8").split("\n") if nv else []
    if istek == "kelimeler":
        for i, w in enumerate(vocab):
            yield f"{i}\t{w}"
        return
    if istek and istek.startswith("ngram"):
        hedef = int(istek[5:] or 2) - 1
        for k in range(N):
            for _ in range(r.get()):
                ctx = " ".join(vocab[r.get()] for _ in range(k))
                prev = 0
                for _ in range(r.get()):
                    prev += r.get()
                    v = r.get()
                    if k == hedef:
                        yield f"{ctx} → {vocab[prev]}\t{v}".lstrip()
            if k == hedef:
                return
        return
    yield f"ESKİ DİL MODELİ (zlib'li CRW6, yalnızca okunuyor) · N={N} · {len(vocab):,} kelime"
    yield "  İçeriği görmek için: kelimeler · ngram 1|2|3   (CRW'ye aktarılmış kopyası model_crw/ içindedir)"


# ====================================================================== kayit agaci (crw_json)
def _agac_metin(v, girinti=0):
    bosluk = "  " * girinti
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, (dict, list)) and x:
                yield f"{bosluk}{k}:"
                yield from _agac_metin(x, girinti + 1)
            else:
                yield f"{bosluk}{k}: {x}"
    elif isinstance(v, list):
        for i, x in enumerate(v):
            if isinstance(x, (dict, list)) and x:
                yield f"{bosluk}[{i}]"
                yield from _agac_metin(x, girinti + 1)
            else:
                yield f"{bosluk}- {x}"
    else:
        yield f"{bosluk}{v}"


# ====================================================================== komut satiri
def main():
    global ILK
    arg = sys.argv[1:]
    if "--hepsi" in arg:
        arg.remove("--hepsi"); ILK = 0
    if "--ilk" in arg:
        i = arg.index("--ilk"); ILK = int(arg[i + 1]); del arg[i:i + 2]
    if not arg:
        return print(__doc__)
    yol, komut, deger = arg[0], (arg[1] if len(arg) > 1 else ""), " ".join(arg[2:])
    if not os.path.exists(yol):
        return print(f"Dosya yok: {yol}")
    tur, ok = tur_bul(yol)
    print(f"{yol} · {_boy(os.path.getsize(yol))}", file=sys.stderr)

    if tur in ("kayit", "gunluk"):
        import crw_json as CJ
        if tur == "kayit":
            veri = CJ.crw_oku(yol)
            if komut:                                    # alt dal:  python3 crw_oku.py defter.crw kayitlar
                for parca in (komut + (" " + deger if deger else "")).split("/"):
                    veri = veri[int(parca)] if isinstance(veri, list) else veri.get(parca) if isinstance(veri, dict) else None
            return _cik(_agac_metin(veri))
        return _cik(" · ".join(f"{k}: {v}" for k, v in r.items()) if isinstance(r, dict) else str(r)
                    for r in CJ.gunluk_oku(yol))
    if tur == "eski":
        return _cik(eski_ozet(yol, komut + deger.replace(" ", "")))
    if tur == "resim":
        return print("Bu bir CRW RESİM dosyası (CRW1/CRW4); metin içermez. Görmek için: crw4.py / crw_codec.py")
    if tur == "bilinmiyor":
        return print("Bu dosya CRW olarak tanınmadı.")
    if komut == "bolum":
        return _cik(model_bolum(yol, deger) if tur == "model" else bolum_metin(ok, deger))

    if tur == "model":
        if not komut:
            return _cik(model_ozet(ok, yol))
        if komut == "kelimeler":
            return _cik(model_kelimeler(yol))
        if komut == "ngram":
            return _cik(model_ngram(yol, int(deger or 2)))
        if komut == "kelime" and deger:
            return _cik(model_kelime(yol, deger.lower()))
        if komut in ("basliklar", "dosyalar", "isimler"):
            return _cik(model_meta(yol, komut))
    elif tur == "dizin":
        if not komut:
            return _cik(dizin_ozet(ok))
        if komut == "parca" and deger.isdigit():
            return _cik(dizin_parca(ok, int(deger)))
        if komut == "metin":
            return _cik(bolum_metin(ok, "metin"))
        if komut == "kok" and deger:
            return _cik(dizin_kok(ok, deger.lower()[:5]))
    else:
        if not komut:
            print("CRW2 dosyası. Bölümler:")
            return _cik(ozet_genel(ok))
    ad = {"model": "dil modeli", "dizin": "kitap dizini", "crw2": "CRW2"}[tur]
    print(f"'{komut}' bu dosyada çalışmaz: bu bir {ad} dosyası.")
    if tur == "model" and komut == "metin":
        print("Dil modeli metnin kendisini saklamaz; kelimelerin hangi sırayla, kaç kez geldiğini saklar.\n"
              "Kitapların metni kitap dizinindedir:  python3 crw_oku.py ../kitap_dizin.crw metin")
    print(f"Bu dosyada kullanılabilenler: {KOMUTLAR[tur]}")


if __name__ == "__main__":
    main()
