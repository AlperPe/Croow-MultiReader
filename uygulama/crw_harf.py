#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
crw_harf.py - CROOW HARF PALETI: sayfadaki yaziyi PIKSEL ANALIZIYLE cozer. OCR / Tesseract KULLANILMAZ.

Mantik, crw_swarm.py'nin renk paletinin (universal_roots.bin) aynisi; renk yerine HARF ogrenilir:
  1. KAPSAMA  : her piksel siyah/beyaz diye KESILMEZ; pikselin yuzde kaci murekkeple dolu, o tutulur (0-99).
                Ince bir cizginin yarisi bir piksele dusuyorsa o piksel %50 doludur: gri gorunur ama orada murekkep
                VARDIR. Kagit ve murekkep tonlari sayfanin kendi yogunluk dagilimindan bulunur.
  2. BOSLUK   : bir sutunun toplam kapsamasi sifirsa orasi bosluktur: harfleri, buyuk bosluklar kelimeleri,
                satir arasi bosluklar satirlari ayirir. %30 dolu ince bir baglanti harfi bir arada tutar.
  3. ZOOM     : bir satirda YARI DOLU piksellerin orani yuksekse ya da harfler kotu eslesiyorsa orasi hassastir:
                satir PDF'ten 2 kat cozunurlukte yeniden cizilir ve yakindan okunur, iyi olan secilir.
  4. HARF KIMLIGI: her harf su olculerle tanimlanir:
                - 8x8 kapsama izgarasi (hucre basina ortalama doluluk %; A D J M K koklerine de cevrilir)
                - TEPELER: 8 satir ve 8 sutunda cizgi merkezleri. Yogunluk cizginin ortasinda en yuksek, iki yana
                  SIMETRIK azalir (1 2 3 4 3 2 1); merkez = 4. 'r'nin alt satirlari tek tepe (govde), 'n' iki, 'm' uc.
                - PROFILLER: harfin sutun toplamlari (x ekseni) ve satir toplamlari (y ekseni), 16 basamak.
                  Her cizgi simetrik bir tepe verir: 'm' x'te 0 1 2 3 2 1 0 0 1 2 3 2 1 0 ... = 3 tepe, y'de 1 tepe;
                  'n' (2, 1), 'i' (1, 2: nokta + govde), 'E' (1, 3). Tepe sayisi ve yerleri karsilastirilir.
                - GECIS KODLARI: 3 yatay + 3 dikey tarama cizgisinde ton sirasi (A D K J A ..., tekrar tek harf)
                - YOGUNLUK MERKEZI (b/d/p/q'yu ayirir) ve SAG-SOL / UST-ALT SIMETRI (u/n, c/o)
                - en/boy orani, satirdaki yeri, dikey parca sayisi (i: nokta + govde = 2, l: 1)
  5. HARF PALETI: her harf icin en fazla 24 kok izgara. Bir kutu paletteki EN YAKIN koke baglanir.
  6. ONARIM   : bolunmus harf (yan yana iki dar parca) birlestirilir, degen iki harf bolunur; kelime Croow'un
                dil modelinde yoksa tek harf farkla en sik kelimeye duzeltilir (--ham ile kapatilir).
OGRENME kendiliginden ve dogrulanmis: metin katmanli PDF'te kelimenin parca sayisi harf sayisina esitse her parca o
harf olarak ogrenilir; esit degilse atlanir. Yanlis ornek ogrenilmez.

Palet: harf_koklari_v6.crw (CRW, crw_json.py). Eski paletler (harf_koklari.crw, _v3, _v4, _v5) SILINMEZ,
kullanilmaz; bu surum yeniden ogretilmelidir. Gerekenler: Pillow ve pypdfium2 (poppler-utils kuruluysa o kullanilir).

Kullanim:
  python3 crw_harf.py alfabe                 -> bilgisayardaki BUTUN yazi tiplerinde alfabeyi sira sira cizip ogrenir
  python3 crw_harf.py alfabe yazi.ttf ...    -> yalnizca bu yazi tipleri  (LaTeX gorunumu: sudo apt install fonts-lmodern)
  python3 crw_harf.py ogren kitap1.pdf kitap2.pdf ...   (ya da bir klasor: icindeki butun PDF'ler)
  python3 crw_harf.py coz tarama.pdf [cikti.txt]
  python3 crw_harf.py coz sayfa.png
  python3 crw_harf.py bilgi
  python3 crw_harf.py sina gorulmemis.pdf [--sayfa 5] [--kirli]
Sinirlar (durust): ogrenilmemis yazi tipleri, el yazisi ve cok kirli tarama hata uretir.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from operator import sub

KOK = os.path.dirname(os.path.abspath(__file__))
VERI = os.environ.get("CROOW_VERI", os.path.join(os.path.expanduser("~"), ".croow"))   # kullanıcının veri klasörü


def _palet_yolu():
    """Harf paleti: CROOW_HARF ortam değişkeni > programın yanındaki eski palet > ~/.croow/ (yazılabilir)."""
    if os.environ.get("CROOW_HARF"):
        return os.environ["CROOW_HARF"]
    eski = os.path.join(KOK, "harf_koklari_v6.json")
    if any(os.path.exists(os.path.splitext(eski)[0] + u) for u in (".crw", ".json")):
        return eski
    os.makedirs(VERI, exist_ok=True)
    return os.path.join(VERI, "harf_koklari_v6.json")


PALET = _palet_yolu()                                    # crw_json bunu harf_koklari_v6.crw olarak yazar
DPI = 300
YAKIN = 2                                                # hassas satirlarda zoom kati (600 DPI)
GURULTU = 38                                             # %15'ten az dolu piksel: kagit lekesi
IZ = 8
EN_COK = 24
BIRLES = 12.0
EMIN = float(os.environ.get("CROOW_EMIN", "inf"))     # varsayilan: her zaman en yakin harfi yaz (· yok)
KOKLER = "ADJMK"
NET_OGREN = os.environ.get("CROOW_NET_OGREN", "0") == "1"   # eski crw_net (kullanılmıyor)   # yazi ogrenirken gecis paletine de ogret (kardes bag)


def _net_ogret(img):
    """KARDES BAG yazi -> resim: ogrenilen sayfa/alfabe goruntusunun acilis yolu gecis paletine (crw_net) gider."""
    if not NET_OGREN:
        return
    try:
        import crw_net
        crw_net.yoldan_ogren(img)
    except Exception:  # noqa: BLE001 - crw_net yoksa ya da Pillow sorunu: yazi ogrenimi yine surer
        pass


def _net_kaydet():
    try:
        import crw_net
        crw_net.kaydet()
    except Exception:  # noqa: BLE001
        pass


_YOL_MODELI = None


def yazi_yollari_yolu():
    """Yazıdan öğrenilmiş piksel yolları. Fotoğraftan öğrenilen Croow hafızası yazıya zarar verebildiği
    (ölçümde %94 -> %48) için okuyucu yalnızca bu ayrı dosyayı kullanır."""
    return os.environ.get("CROOW_YAZI_YOLLARI", os.path.join(VERI, "yazi_yollari.crwm"))


def _croow_yol_modeli():
    """Yazıdan öğrenilmiş piksel yolları (CRW7). Yoksa None: hassas satır yakınlaştırılmadan okunur."""
    global _YOL_MODELI
    if _YOL_MODELI is None:
        _YOL_MODELI = False
        try:
            api = os.path.join(KOK, "..", "motor")       # depo düzeninde Croow motoru
            if os.path.isdir(api) and os.path.abspath(api) not in sys.path:
                sys.path.insert(0, os.path.abspath(api))
            from roots_memory import RootsMemory
            yol = yazi_yollari_yolu()
            if os.path.exists(yol):
                m = RootsMemory(yol)
                if m.paths.images > 0:                   # yollar öğrenilmişse
                    _YOL_MODELI = m.paths.model()
        except Exception:  # noqa: BLE001 - motor yoksa hassas satır yakınlaştırılmadan okunur
            _YOL_MODELI = False
    return _YOL_MODELI or None


def _net_yakinlastirici(img):
    """Resimde (PDF yok) hassas satır: bölge CRW7'nin öğrenilmiş piksel yollarıyla ×2 detaylandırılıp yeniden okunur.
    (Eski crw_net geçiş paletinin yerini aldı.) Öğrenilmiş yol yoksa None: satır olduğu gibi okunur."""
    model = _croow_yol_modeli()
    if model is None:
        return None
    from paths_memory import enhance_strips

    def f(x0, y0, x1, y1):
        bolge = img.crop((int(x0), int(y0), int(x1), int(y1))).convert("RGB")
        return enhance_strips(bolge, model).convert("L")
    return f


def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        raise RuntimeError("Pillow gerekli:  sudo apt install python3-pil")


def _arac(ad):
    if not shutil.which(ad):
        raise RuntimeError(f"{ad} yok. Kurulum:  sudo apt install poppler-utils")


# ====================================================================== 1. KAPSAMA
def esik(img):
    """Kagit / murekkep tonlarini ayiran deger (yogunluk dagilimindaki iki grubu en iyi ayiran)."""
    h = img.histogram()[:256]
    top = sum(h)
    if not top:
        return 128
    t_hepsi = sum(i * h[i] for i in range(256))
    w0 = s0 = 0
    en_iyi, e = 0, 128
    for i in range(256):
        w0 += h[i]
        if not w0:
            continue
        w1 = top - w0
        if not w1:
            break
        s0 += i * h[i]
        v = w0 * w1 * (s0 / w0 - (t_hepsi - s0) / w1) ** 2
        if v > en_iyi:
            en_iyi, e = v, i
    return e


def seviyeler(img):
    """-> (murekkep_tonu, kagit_tonu): iki grubun ortalamasi."""
    e = esik(img)
    h = img.histogram()[:256]
    a, u = sum(h[:e + 1]), sum(h[e + 1:])
    mur = sum(i * h[i] for i in range(e + 1)) / a if a else 0
    kag = sum(i * h[i] for i in range(e + 1, 256)) / u if u else 255
    if kag - mur < 30:                                   # neredeyse tek renk sayfa
        mur, kag = 0, 255
    return mur, kag


def kapsama(img):
    """Gri resim -> KAPSAMA haritasi: her piksel 0 (bos kagit) ... 255 (tam dolu murekkep). Kesme yok."""
    img = img.convert("L")
    mur, kag = seviyeler(img)
    fark = max(1.0, kag - mur)
    tablo = []
    for v in range(256):
        k = (kag - v) * 255 / fark
        tablo.append(0 if k < GURULTU else min(255, int(k)))
    return img.point(tablo)


def _izdusum(kap, yatay):
    """Her satirin (yatay) ya da sutunun TOPLAM kapsamasi (tam dolu piksel cinsinden)."""
    Image = _pil()
    w, h = kap.size
    f = kap.convert("F")
    if yatay:
        return [v * w / 255 for v in f.resize((1, h), Image.Resampling.BOX).getdata()]
    return [v * h / 255 for v in f.resize((w, 1), Image.Resampling.BOX).getdata()]


def _bantlar(degerler, en_az=0.25):
    out, bas = [], None
    for i, v in enumerate(degerler):
        if v >= en_az and bas is None:
            bas = i
        elif v < en_az and bas is not None:
            out.append((bas, i)); bas = None
    if bas is not None:
        out.append((bas, len(degerler)))
    return out


# ====================================================================== 2. BOSLUK
def egim(img, aci=3.0, adim=0.1):
    """Sayfanin egimi (derece). Satirlar yataya en cok oturdugunda yatay izdusum en KESKIN olur (tepeler yuksek,
    vadiler derin): bu keskinligi (kareler toplami) en buyuten aci aranir. Kucultulmus kapsama uzerinde calisir."""
    Image = _pil()
    import numpy as np
    k = kapsama(img)
    olcek = min(1.0, 800 / max(k.size))
    if olcek < 1:
        k = k.resize((max(1, int(k.width * olcek)), max(1, int(k.height * olcek))), Image.Resampling.BOX)

    def keskinlik(d):
        a = np.asarray(k.rotate(d, resample=Image.Resampling.BILINEAR, fillcolor=0), dtype=np.float64).sum(1)
        return float((np.diff(a) ** 2).sum())
    en = max((i * adim for i in range(-int(aci / adim), int(aci / adim) + 1)), key=keskinlik)
    ince = max((en + i * adim / 5 for i in range(-5, 6)), key=keskinlik)
    return round(ince, 2)


def duzle(img, en_az=0.15):
    """Egik sayfayi duzeltir: (duz gri resim, aci). Aci cok kucukse resme dokunmaz."""
    Image = _pil()
    g = img.convert("L")
    d = egim(g)
    if abs(d) < en_az:
        return g, 0.0
    _, kag = seviyeler(g)
    return g.rotate(d, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=int(kag)), d


def _satir_adimi(izd):
    """Satir araligi (piksel): yatay izdusumun kendisiyle ilintisinin ilk belirgin tepesi. Bulunamazsa None."""
    import numpy as np
    a = np.asarray(izd, dtype=np.float64)
    if len(a) < 40 or a.std() == 0:
        return None
    a = a - a.mean()
    r = np.correlate(a, a, "full")[len(a) - 1:]
    r = r / (r[0] or 1)
    tepeler = [t for t in range(8, len(r) - 1) if r[t] > 0.2 and r[t] >= r[t - 1] and r[t] >= r[t + 1]]
    if not tepeler:
        return None
    en = max(r[t] for t in tepeler)
    return next(t for t in tepeler if r[t] >= 0.6 * en)   # ilk BELİRGİN tepe (harf içi çizgiler de küçük tepe verir)


def _bitisik_bol(izd, u, a, adim_):
    """Bos satir birakmadan bitisik dizilmis satirlari (daktilo, sik aralik) izdusum VADILERINDEN boler."""
    import numpy as np
    d = np.convolve(np.asarray(izd[u:a], dtype=np.float64), np.ones(5) / 5, "same")
    out, bas = [], 0
    while (a - u) - bas > 1.5 * adim_:
        p0, p1 = bas + int(0.6 * adim_), min(len(d), bas + int(1.4 * adim_))
        if p1 <= p0:
            break
        kes = p0 + int(np.argmin(d[p0:p1]))
        out.append((u + bas, u + kes))
        bas = kes
    out.append((u + bas, a))
    return out


def satirlar(kap):
    """-> [(ust, alt)]. Ince bantlar (i noktasi, sapka, virgul) komsu satira katilir.
    Satirlar arasinda bos piksel satiri yoksa (daktilo, sik aralik) uzun bant izdusum vadilerinden bolunur."""
    izd = _izdusum(kap, True)
    b = _bantlar(izd, 1.0)
    if not b:
        return []
    adim_ = _satir_adimi(izd)
    if adim_:
        bol = []
        for u, a in b:
            bol += _bitisik_bol(izd, u, a, adim_) if a - u > 1.8 * adim_ else [(u, a)]
        b = bol
    boylar = sorted(a - u for u, a in b)
    orta = boylar[len(boylar) // 2]
    out = []
    for u, a in b:
        if out and (a - u < 0.4 * orta or out[-1][1] - out[-1][0] < 0.4 * orta) and u - out[-1][1] < 0.5 * orta:
            out[-1] = (out[-1][0], a)
        else:
            out.append((u, a))
    return [x for x in out if x[1] - x[0] >= 3]


def _kutu(kap, x0, x1, ust, alt):
    """[x0,x1) araligini TEK parca sayar: (x0, x1, y0, y1, dikey_parca) ya da None."""
    dikey = _bantlar(_izdusum(kap.crop((x0, ust, x1, alt)), True))
    if not dikey:
        return None
    return (x0, x1, ust + dikey[0][0], ust + dikey[-1][1], min(3, len(dikey)))


MUTLAK_BEYAZ = 5                                         # sutun derinligi bunun altindaysa: kesin bosluk
DERINLIK = 0.5                                           # vadi, iki yanindaki tepelerin en az yarisi kadar coktuyse: kes


def sutun_derinligi(kirp):
    """Her sutunun DERINLIGI 0..100: sutundaki EN DOLU pikselin yuzdesi. Harfin icinden gecen her sutunda en az bir
    tam dolu cizgi pikseli vardir (100'e yakin); iki harf arasinda sutunlar vadi gibi coker (yalnizca soluk hale)."""
    w, h = kirp.size
    piks = kirp.tobytes()
    return [max(piks[x::w]) * 100 // 255 for x in range(w)]


def _vadiler(c, a, b):
    """[a,b) araligindaki derin vadiler (kesim noktalari). Derinlik GORECELI: vadinin iki yanindaki en yuksek
    tepelerin kucugune gore ne kadar coktugu. Soluk taramada tepeler 60 olsa da dibi 25'teki vadi derindir."""
    kes, x = [], a + 1
    while x < b - 1:
        if c[x] <= c[x - 1] and c[x] <= c[x + 1]:
            y = x
            while y + 1 < b and c[y + 1] == c[x]:        # duz dip: ortasini al
                y += 1
            orta = (x + y) // 2
            sol = max(c[a:x]) if x > a else 0
            sag = max(c[y + 1:b]) if y + 1 < b else 0
            kucuk = min(sol, sag)
            if kucuk >= 20 and kucuk - c[orta] >= DERINLIK * kucuk:
                kes.append(orta)
            x = y + 1
        else:
            x += 1
    return kes


def parcalar(kap, x0, x1, ust, alt):
    """Satirin [x0,x1) araligindaki harf parcalari: [(px0, px1, py0, py1, dikey_parca)].
    KESIM: sutun derinligi (0..100). Mutlak beyaz sutun ya da DERIN vadi = iki harf arasi (f ile l arasindaki ince
    beyaz, soluk hale olsa da). Sig cokuntu (u'nun dibi) kesilmez. SEKIL: kutunun icinde butun tonlar kullanilir."""
    c = sutun_derinligi(kap.crop((x0, ust, x1, alt)))
    out = []
    for a, b in _bantlar(c, MUTLAK_BEYAZ):
        sinir = [a] + _vadiler(c, a, b) + [b]
        for i in range(len(sinir) - 1):
            s0 = sinir[i] + (1 if i else 0)              # vadi sutunu iki harfin hicbirine ait degil
            s1 = sinir[i + 1]
            if s1 - s0 < 1:
                continue
            k = _kutu(kap, x0 + s0, x0 + s1, ust, alt)
            if k:
                out.append(k)
    return out


def hassaslik(kap, ust, alt):
    """Satirdaki murekkepli piksellerin yuzde kaci YARI DOLU (gri hissi veren): yuksekse zoom gerekir."""
    h = kap.crop((0, ust, kap.width, alt)).histogram()
    dolu = sum(h[1:])
    return sum(h[64:192]) / dolu if dolu else 0.0


# ====================================================================== 4. KOK IZGARA
TARAMA = (0.25, 0.5, 0.75)                               # gecis kodu icin tarama cizgileri (kutunun orani)


def _gecis(degerler):
    """Bir tarama cizgisindeki ton sirasi: kokler (A D J M K), art arda ayni kok TEK harf (RLE mantigi).
    'o'nun ortasi: A D K J A J K D A  (kenarda yukselen, icte bosalan, karsi kenarda yine yukselen ton)."""
    s = []
    for v in degerler:
        c = KOKLER[min(4, v * 99 // 255 // 20)]
        if not s or s[-1] != c:
            s.append(c)
    return "".join(s)[:24]


TEPE_ESIK = 51                                           # %20 dolu: ince cizgiler de ('e'nin ortasi) sayilir


def _tepeler(degerler):
    """Bir satir/sutundaki CIZGI MERKEZLERI. Yogunluk cizginin ortasinda en yuksek, kenarlara dogru simetrik azalir
    (1 2 3 4 3 2 1). %30'u asan her bolge bir cizgi; merkezi = bolgenin yogunluk agirlik merkezi (ornekte 4).
    -> konumlar 0..99 (satir/sutun boyuna gore)."""
    n = len(degerler)
    out, bas = [], None
    for i, v in enumerate(list(degerler) + [0]):
        if v >= TEPE_ESIK and bas is None:
            bas = i
        elif v < TEPE_ESIK and bas is not None:
            bolge = degerler[bas:i]
            top = sum(bolge) or 1
            merkez = sum((bas + j) * x for j, x in enumerate(bolge)) / top
            out.append(round(merkez * 99 / max(1, n - 1)))
            bas = None
    return tuple(out[:6])


def _tepe_farki(A, B):
    """16 tarama cizgisinde tepe sayisi ve yerlerinin farki (0 ayni ... 1 tamamen farkli)."""
    top = 0.0
    for a, b in zip(A, B):
        if len(a) != len(b):
            top += 1.0                                   # cizgi sayisi farkli: n ile m, r ile n
        elif a:
            top += min(1.0, 3 * sum(abs(p - q) for p, q in zip(a, b)) / (99 * len(a)))
    return top / max(1, len(A))


def ozellik(kap, p, ust, alt):
    """Harf kutusu -> (izgara64, kaba16, oran, ust, alt, dikey_parca, gecis_kodlari6, merkez_x, merkez_y,
    simetri_sag_sol, simetri_ust_alt). Izgara: hucre basina ortalama doluluk %."""
    Image = _pil()
    px0, px1, py0, py1 = p[:4]
    kutu = kap.crop((px0, py0, px1, py1))
    w, h = kutu.size
    d = tuple(round(v * 99 / 255) for v in kutu.resize((IZ, IZ), Image.Resampling.BOX).getdata())
    sb = max(1, alt - ust)
    nb = p[4] if len(p) > 4 else 1
    piks = list(kutu.getdata())                          # tarama cizgileri TAM cozunurlukte (ortalama yok)
    g = tuple(_gecis(piks[min(h - 1, int(h * f)) * w:(min(h - 1, int(h * f)) + 1) * w]) for f in TARAMA) + \
        tuple(_gecis(piks[min(w - 1, int(w * f))::w]) for f in TARAMA)
    top = sum(d) or 1                                    # yogunluk merkezi: -0.5 (sol/ust) ... +0.5 (sag/alt)
    mx = sum((i % 8) * v for i, v in enumerate(d)) / top / 7 - 0.5
    my = sum((i // 8) * v for i, v in enumerate(d)) / top / 7 - 0.5
    ss = 1 - sum(abs(d[r * 8 + c] - d[r * 8 + 7 - c]) for r in range(8) for c in range(4)) / (32 * 99)
    su = 1 - sum(abs(d[r * 8 + c] - d[(7 - r) * 8 + c]) for r in range(4) for c in range(8)) / (32 * 99)
    satir_y = [min(h - 1, int(h * (k + 0.5) / 8)) for k in range(8)]
    sutun_x = [min(w - 1, int(w * (k + 0.5) / 8)) for k in range(8)]
    t = tuple(_tepeler(piks[y * w:(y + 1) * w]) for y in satir_y) + tuple(_tepeler(piks[x::w]) for x in sutun_x)
    ps, pr = _profil(_izdusum(kutu, False)), _profil(_izdusum(kutu, True))
    pt = (_tepeler([v * 255 // 99 for v in ps]), _tepeler([v * 255 // 99 for v in pr]))
    return (d, _kaba(d), min(5.0, (px1 - px0) / max(1, py1 - py0)), (py0 - ust) / sb, (py1 - ust) / sb, nb,
            g, mx, my, ss, su, t, ps, pr, pt)


PROFIL = 16


def _profil(toplamlar):
    """Sutun (ya da satir) toplam yogunluklari -> 16 basamak, harfin kendi en yuksek degerine gore 0..99.
    'm': her bacak simetrik bir tepe (0 1 2 3 2 1 0), aralarda kemerin alcak tabani."""
    n = len(toplamlar)
    if not n:
        return (0,) * PROFIL
    b = []
    for k in range(PROFIL):
        a, z = k * n // PROFIL, max(k * n // PROFIL + 1, (k + 1) * n // PROFIL)
        b.append(sum(toplamlar[a:z]) / (z - a))
    en = max(b) or 1
    return tuple(round(v * 99 / en) for v in b)


def koklere(d):
    return "".join(KOKLER[min(4, v // 20)] for v in d)


def _kaba(d):
    return tuple((d[r * 8 + c] + d[r * 8 + c + 1] + d[r * 8 + 8 + c] + d[r * 8 + 9 + c]) // 4
                 for r in range(0, 8, 2) for c in range(0, 8, 2))


def _fark(a, b):
    """Iki gecis kodu arasindaki fark (0 ayni ... 1 tamamen farkli): kac kok eklenip/silinip/degismeli."""
    if a == b:
        return 0.0
    onceki = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        simdi = [i]
        for j, y in enumerate(b, 1):
            simdi.append(min(onceki[j] + 1, simdi[j - 1] + 1, onceki[j - 1] + (x != y)))
        onceki = simdi
    return onceki[-1] / max(len(a), len(b), 1)


def _kaba_mesafe(x, oz):
    """Hizli on eleme: kaba izgara + oran + yer + dikey parca + merkez."""
    return (sum(map(abs, map(sub, x[2], oz[1]))) / 16 + 30 * abs(x[3] - oz[2]) + 80 * (abs(x[4] - oz[3])
            + abs(x[5] - oz[4])) + 25 * abs(x[7] - oz[5]) + 80 * (abs(x[9] - oz[7]) + abs(x[10] - oz[8]))
            + 20 * abs(len(x[16][0]) - len(oz[14][0])))  # sutun profilindeki tepe sayisi: m 3, n 2, r 1


def _mesafe(x, oz):
    """Tam mesafe: izgara + oran + yer + dikey parca + gecis kodlari + merkez + simetri + tepeler."""
    d, _, o, u, a, b, g, mx, my, ss, su, t, ps, pr, pt = oz
    return (sum(map(abs, map(sub, x[1], d))) / 64 + 30 * abs(x[3] - o) + 80 * (abs(x[4] - u) + abs(x[5] - a))
            + 25 * abs(x[7] - b) + 10 * sum(_fark(p, q) for p, q in zip(x[8], g)) / 6
            + 80 * (abs(x[9] - mx) + abs(x[10] - my)) + 25 * (abs(x[11] - ss) + abs(x[12] - su))
            + 55 * _tepe_farki(x[13], t)              # satir/sutun tepeleri: n/u, 6/9/0
            + 30 * (sum(map(abs, map(sub, x[14], ps))) + sum(map(abs, map(sub, x[15], pr)))) / (2 * PROFIL * 99)
            + 35 * _tepe_farki(x[16], pt))


# ====================================================================== 5. HARF PALETI
ALFABE = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
             "çğıöşüâîûÇĞİÖŞÜÂÎÛéèêáàäëíóúñÉ"
             "0123456789"
             ".,;:!?'\"()[]{}-+=/%&*@#$<>_|~^’‘“”–—…•·°§"
             "→←↑↓↔∆Δ×−≤≥±∞∑√∈≈≠")


def simge_mi(c):
    """Bilinmeyen harf simgesi mi (eski yazılarda adı bilinmeyen harf: özel kullanım alanı U+E000...)."""
    return bool(c) and all("\ue000" <= x <= "\uf8ff" for x in c)


def izinli(c):
    """Tek harf ya da birim ('fi', 'Tr'): butun harfleri alfabede mi (ya da bilinmeyen harf simgesi)."""
    return bool(c) and all(x in ALFABE or "\ue000" <= x <= "\uf8ff" for x in c)


# Tek parca gorunen harf birimleri: LaTeX ve cogu yazi tipi bunlari BIRLESIK sekil (ligatur) olarak basar ya da harfler
# birbirine deger. Ogrenirken parca sayisi tutmazsa bunlar birlestirilerek yeniden denenir; okurken 'fi' diye yazilir.
LIGATUR = {"ﬃ": "ffi", "ﬄ": "ffl", "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl"}
DEGEN = ["ffi", "ffl", "ff", "fi", "fl", "ft", "fo", "fe", "fr", "fa", "fy", "Tr", "To", "Te", "Ta", "Ty", "Tu", "Tw",
         "Wa", "We", "Wo", "Va", "Ve", "Yo", "Ya", "rt", "rf", "tt", "ry", "rv", "gy", "gj"]


def _hizala(harfler, pr):
    """Parca sayisi harf sayisindan azsa bilinen birimleri birlestirip esler. Birlesen parca gercekten genis
    olmali. -> birim listesi (pr ile ayni uzunlukta) ya da None."""
    if len(harfler) == len(pr):
        return harfler
    fazla = len(harfler) - len(pr)
    if fazla <= 0 or fazla > 3:
        return None
    tok = list(harfler)
    for u in DEGEN:
        i = 0
        while i < len(tok) and fazla > 0:
            parca = tok[i:i + len(u)]
            if len(parca) == len(u) and all(len(t) == 1 for t in parca) and "".join(parca) == u:
                tok[i:i + len(u)] = [u]
                fazla -= len(u) - 1
            i += 1
        if fazla == 0:
            break
    if fazla:
        return None
    tek = sorted(p[1] - p[0] for t, p in zip(tok, pr) if len(t) == 1)
    orta = tek[len(tek) // 2] if tek else 0
    if orta and any(len(t) > 1 and (p[1] - p[0]) < 1.25 * orta for t, p in zip(tok, pr)):
        return None                                      # "birlesik" dedigimiz parca genis degil: yanlis hizalama
    return tok


class Palet:
    def __init__(self, yol=PALET):
        import crw_json as CJ
        self.yol = yol
        v = CJ.oku(yol, {}) or {}
        self.kaynaklar = v.get("kaynaklar", [])
        self.ornek = v.get("ornek", 0)
        # kok: [harf, d, kaba, oran, ust, alt, n, dikey_parca, gecis6, mx, my, ss, su, tepeler16,
        #       sutun_profili16, satir_profili16, (x_tepeleri, y_tepeleri)]
        self.k, self.disarida = [], []
        for h, liste in v.get("harfler", {}).items():
            for x in liste:
                d = tuple(x["d"])
                kok = [h, d, _kaba(d), x["o"] / 100, x["u"] / 100, x["a"] / 100, x["n"], x.get("b", 1),
                       tuple(x.get("g", [""] * 6)), x.get("m", [0, 0])[0] / 100, x.get("m", [0, 0])[1] / 100,
                       x.get("s", [100, 100])[0] / 100, x.get("s", [100, 100])[1] / 100,
                       tuple(tuple(c) for c in x.get("t", [[]] * 16)),
                       tuple(x.get("px", [0] * PROFIL)), tuple(x.get("py", [0] * PROFIL)),
                       tuple(tuple(c) for c in x.get("pt", [[], []]))]
                (self.k if izinli(h) else self.disarida).append(kok)

    def kaydet(self):
        import crw_json as CJ
        harfler = {}
        for h, d, _, o, u, a, n, b, g, mx, my, ss, su, t, ps, pr, pt in self.k + self.disarida:
            harfler.setdefault(h, []).append({
                "d": list(d), "kok": koklere(d), "o": round(o * 100), "u": round(u * 100), "a": round(a * 100),
                "n": n, "b": b, "g": list(g), "m": [round(mx * 100), round(my * 100)],
                "s": [round(ss * 100), round(su * 100)], "t": [list(c) for c in t],
                "px": list(ps), "py": list(pr), "pt": [list(c) for c in pt]})
        CJ.yaz(self.yol, {"surum": 4, "olcu": "kapsama+gecis+merkez+simetri+tepe+profil", "izgara": IZ, "dpi": DPI,
                          "harfler": harfler, "kaynaklar": self.kaynaklar[-500:], "ornek": self.ornek})

    def ekle(self, harf, oz):
        d, kaba, o, u, a, b, g, mx, my, ss, su, t, ps, pr, pt = oz
        ayni = [x for x in self.k if x[0] == harf and x[7] == b]
        if ayni:
            en = min(ayni, key=lambda x: _mesafe(x, oz))
            if _mesafe(en, oz) < BIRLES or len(ayni) >= EN_COK:   # yakin kok: ortalamaya kat
                n = en[6]
                w = 1 / (min(n, 1000) + 1)
                en[1] = tuple(round(p + (q - p) * w) for p, q in zip(en[1], d))
                en[2] = _kaba(en[1])
                en[3] += (o - en[3]) * w; en[4] += (u - en[4]) * w; en[5] += (a - en[5]) * w
                en[9] += (mx - en[9]) * w; en[10] += (my - en[10]) * w
                en[11] += (ss - en[11]) * w; en[12] += (su - en[12]) * w
                en[14] = tuple(round(p + (q - p) * w) for p, q in zip(en[14], ps))
                en[15] = tuple(round(p + (q - p) * w) for p, q in zip(en[15], pr))
                en[6] = n + 1                            # gecis kodlari ve tepe yerleri ilk ornekten kalir
                return
        self.k.append([harf, d, kaba, o, u, a, 1, b, g, mx, my, ss, su, t, ps, pr, pt])

    def bul(self, oz):
        """-> (harf, mesafe). Once hizli on eleme ile 12 aday, sonra tam mesafe."""
        aday = sorted(self.k, key=lambda x: _kaba_mesafe(x, oz))[:12]
        en = min(aday, key=lambda x: _mesafe(x, oz) + 6 / (x[6] ** 0.5))
        return en[0], _mesafe(en, oz)

    def harf_sayisi(self):
        return len({x[0] for x in self.k})


# ====================================================================== PDF yardimcilari
def sayfa_sayisi(pdf):
    import pdf_motor
    return pdf_motor.sayfa_sayisi(pdf)


def _ciz(pdf, k, klasor, dpi, on, kirp=None):
    """k. sayfayı çizer (poppler varsa onunla, yoksa pypdfium2 ile; bkz. pdf_motor.py)."""
    import pdf_motor
    return pdf_motor.ciz(pdf, k, dpi, kirp)


def sayfa_resmi(pdf, k, klasor):
    return _ciz(pdf, k, klasor, DPI, f"s{k}_")


def yakinlastirici(pdf, k, klasor, kirli=False):
    """Hassas bolge icin: sayfanin (x0,y0,x1,y1) bolgesini YAKIN kat cozunurlukte yeniden cizer."""
    def f(x0, y0, x1, y1):
        img = _ciz(pdf, k, klasor, DPI * YAKIN, "z_",
                   (x0 * YAKIN, y0 * YAKIN, (x1 - x0) * YAKIN, (y1 - y0) * YAKIN))
        return _kirlet(img) if (img is not None and kirli) else img
    return f


def sayfa_kelimeleri(pdf, k):
    import pdf_motor
    return pdf_motor.kelimeler(pdf, k, DPI)


_AYRIK = {"¸": "\u0327", "¨": "\u0308", "˘": "\u0306", "´": "\u0301", "`": "\u0300", "ˆ": "\u0302", "˙": "\u0307"}


def _birlestir(s):
    """LaTeX PDF'lerindeki ayrik aksan harften ONCE gelir: 'Pekta¸s' -> 'Pektaş'."""
    import unicodedata
    out, bekleyen = [], None
    for c in s:
        if c in _AYRIK:
            bekleyen = _AYRIK[c]
        elif bekleyen and c.isalpha():
            out.append(unicodedata.normalize("NFC", c + bekleyen)); bekleyen = None
        else:
            out.append(c); bekleyen = None
    return unicodedata.normalize("NFC", "".join(out))


# ====================================================================== OGRENME
def ogren(pdfler, ilerleme=None, en_cok_sayfa=None):
    """Metin katmanli PDF'lerden harf paleti ogrenir. -> (ogrenilen_harf_ornegi, atlanan_kelime)."""
    P = Palet()
    ogrenilen = atlanan = onceki = 0
    import signal
    try:                                                 # kapatma sinyali de Ctrl+C gibi davransin: kaydedip cik
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    except ValueError:                                   # ana is parcacigi degil (MultiReader): gerek yok
        pass
    try:
        _ogren_dongu(P, pdfler, ilerleme, en_cok_sayfa, [ogrenilen, atlanan, onceki])
    except KeyboardInterrupt:
        print("\nDurduruldu; o ana kadar öğrenilen harfler kaydediliyor...", file=sys.stderr, flush=True)
    sayac = P._sayac
    P.ornek += sayac[0] - sayac[2]
    P.kaydet()
    _net_kaydet()
    return sayac[0], sayac[1]


def _ogren_dongu(P, pdfler, ilerleme, en_cok_sayfa, sayac):
    """sayac: [ogrenilen, atlanan, son_kayittaki_ogrenilen] - Ctrl+C'de de guncel kalir."""
    P._sayac = sayac
    with tempfile.TemporaryDirectory(prefix="croow_harf_") as gecici:
        for pi, pdf in enumerate(pdfler):
            n = sayfa_sayisi(pdf)
            if en_cok_sayfa:
                n = min(n, en_cok_sayfa)
            for k in range(1, n + 1):
                if ilerleme:
                    ilerleme((pi + (k - 1) / max(1, n)) / len(pdfler),
                             f"{os.path.basename(pdf)} · sayfa {k}/{n} · {sayac[0]:,} harf örneği")
                kelimeler = sayfa_kelimeleri(pdf, k)
                if not kelimeler:
                    continue
                img = sayfa_resmi(pdf, k, gecici)
                if img is None:
                    continue
                _net_ogret(img)                          # kardes bag: sayfanin acilis yolu da ogrenilir
                kap = kapsama(img)
                bantlar = satirlar(kap)
                for x0, y0, x1, y1, yazi in kelimeler:
                    yazi = _birlestir(yazi)
                    harfler = [c for c in yazi if not c.isspace()]
                    if not harfler or not all(izinli(c) for c in harfler):
                        sayac[1] += 1
                        continue
                    orta = (y0 + y1) / 2
                    bant = next((b for b in bantlar if b[0] <= orta <= b[1]), None)
                    if bant is None:
                        continue
                    pr = parcalar(kap, max(0, x0), min(kap.width, x1), bant[0], bant[1])
                    birimler = _hizala(harfler, pr)      # 'first' 5 harf / 4 parca: 'fi' tek birim
                    if birimler is None:
                        sayac[1] += 1
                        continue
                    for c, p in zip(birimler, pr):
                        P.ekle(c, ozellik(kap, p, bant[0], bant[1]))
                        sayac[0] += 1
            P.kaynaklar.append(os.path.basename(pdf))  # yalnizca TAMAMLANAN PDF kaynak sayilir
            P.ornek += sayac[0] - sayac[2]
            sayac[2] = sayac[0]
            P.kaydet()                                   # her PDF'ten sonra


# ====================================================================== ALFABE ILE OGRENME
# Her satirin basinda REFERANS 'l' (yukari uzanan) ve 'p' (asagi uzanan): satir yuksekligi gercek metindeki gibi
# olculur. Yoksa 'O' ve '0' satiri bastan sona dolduruyormus gibi ogrenilir ve kucuk 'o' ile karisir.
ALFABE_SATIRLARI = ["lpabcdefghijklmnopqrstuvwxyz", "lpABCDEFGHIJKLMNOPQRSTUVWXYZ", "lpçğıöşüÇĞİÖŞÜâîû",
                    "lp0123456789", "lp.,;:!?'()[]-+=/%&*", "lp→←↑↓∆×−≤≥±∞≈≠"]   # " iki parca oldugu icin yok


def yazi_tipleri():
    """Bilgisayardaki yazı tipi dosyaları. Linux: fc-list; Windows ve macOS: sistem yazı tipi klasörleri taranır.
    Latin Modern (LaTeX) için Linux'ta: sudo apt install fonts-lmodern"""
    out = set()
    if shutil.which("fc-list"):
        r = subprocess.run(["fc-list", ":", "file"], capture_output=True, text=True)
        out |= {s.strip().rstrip(":") for s in r.stdout.splitlines()}
    klasorler = []
    if sys.platform == "win32":
        klasorler += [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
                      os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
    elif sys.platform == "darwin":
        klasorler += ["/System/Library/Fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    else:
        klasorler += ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.local/share/fonts"),
                      os.path.expanduser("~/.fonts")]
    for kl in klasorler:
        if kl and os.path.isdir(kl):
            for kok, _, dosyalar in os.walk(kl):
                out |= {os.path.join(kok, f) for f in dosyalar}
    return sorted(f for f in out if f.lower().endswith((".ttf", ".otf")))


def _cizim(font, c):
    from PIL import Image, ImageDraw
    img = Image.new("L", (int(font.size * 2), int(font.size * 2)), 255)
    ImageDraw.Draw(img).text((font.size // 2, int(font.size * 1.4)), c, font=font, fill=0, anchor="ls")
    return img.tobytes()


def alfabe_ogren(fontlar=None, boyutlar=(10, 11, 12, 14, 20, 22, 24, 28), ilerleme=None):
    """10-14 punto: normal okuma (300 DPI); 20-28 punto: hassas satirlardaki 2 kat zoom'un boyutu."""
    """Her yazi tipinde alfabe SIRA SIRA cizilir; her harf dogrudan ogrenilir (kelime bolme yok, hata yok).
    -> (ogrenilen_harf_ornegi, kullanilan_yazi_tipi)."""
    from PIL import Image, ImageDraw, ImageFont
    fontlar = fontlar or yazi_tipleri()
    if not fontlar:
        raise RuntimeError("Yazı tipi bulunamadı (fc-list yok ya da boş).")
    P = Palet()
    ogrenilen = kullanilan = 0
    try:
        for fi, yol in enumerate(fontlar):
            if ilerleme:
                ilerleme(fi / len(fontlar), f"{os.path.basename(yol)} · {ogrenilen:,} harf örneği")
            ise_yaradi = False
            for pt in boyutlar:
                px = round(pt * DPI / 72)
                try:                                     # BASIC: libraqm (karmasik yazi duzeni) gerekmez; Latin icin yeterli
                    font = ImageFont.truetype(yol, px, layout_engine=ImageFont.Layout.BASIC)
                    font.getlength("a")
                except Exception:  # noqa: BLE001 - acilamayan / bozuk yazi tipi: atla
                    break
                try:
                    yok = _cizim(font, "\U000E0000")         # yazi tipinde olmayan harfin cizimi (bos kutu)
                    for satir in ALFABE_SATIRLARI:
                        harfler = [c for c in satir if _cizim(font, c) != yok]
                        if not harfler:
                            continue
                        bosluk = px // 2
                        en = sum(int(font.getlength(c)) + bosluk for c in harfler) + px
                        img = Image.new("L", (en, px * 3), 255)
                        ciz = ImageDraw.Draw(img)
                        x = px // 2
                        for c in harfler:                    # hepsi ayni taban cizgisinde, aralikli
                            ciz.text((x, px * 2), c, font=font, fill=0, anchor="ls")
                            x += int(font.getlength(c)) + bosluk
                        if pt == 12:                         # kardes bag: harf kenarlarinin acilis yolu
                            _net_ogret(img)                  # (tek boyutta: alfabe hizli kalsin)
                        kap = kapsama(img)
                        bantlar = satirlar(kap)
                        if not bantlar:
                            continue
                        ust, alt = min(b[0] for b in bantlar), max(b[1] for b in bantlar)
                        pr = parcalar(kap, 0, kap.width, ust, alt)
                        if len(pr) != len(harfler):          # bir harf iki parcaysa (" gibi) satiri atla
                            continue
                        for c, p in zip(harfler, pr):
                            P.ekle(c, ozellik(kap, p, ust, alt))
                            ogrenilen += 1
                        ise_yaradi = True
                except Exception as e:  # noqa: BLE001 - bu yazi tipi cizilemedi: atla
                    print(f"  atlandı: {os.path.basename(yol)} ({e})", file=sys.stderr)
                    break
                try:                                     # birlesik sekiller + degen ciftler: her biri kendi satirinda
                    for birim in list(LIGATUR) + DEGEN:
                        etiket = LIGATUR.get(birim, birim)
                        if any(_cizim(font, c) == yok for c in birim):
                            continue                     # yazi tipinde yok
                        img = Image.new("L", (px * 8, px * 3), 255)
                        ciz = ImageDraw.Draw(img)
                        ciz.text((px // 2, px * 2), "l", font=font, fill=0, anchor="ls")
                        x = px // 2 + int(font.getlength("l")) + px // 2
                        ciz.text((x, px * 2), birim, font=font, fill=0, anchor="ls")
                        x += int(font.getlength(birim)) + px // 2
                        ciz.text((x, px * 2), "p", font=font, fill=0, anchor="ls")
                        kap = kapsama(img)
                        bantlar = satirlar(kap)
                        if not bantlar:
                            continue
                        ust, alt = min(b[0] for b in bantlar), max(b[1] for b in bantlar)
                        pr = parcalar(kap, 0, kap.width, ust, alt)
                        if len(pr) == 3:                 # l + TEK PARCA birim + p: gercekten birlesik/degen
                            P.ekle(etiket, ozellik(kap, pr[1], ust, alt))
                            ogrenilen += 1
                except Exception:  # noqa: BLE001
                    pass
            if ise_yaradi:
                kullanilan += 1
                P.kaynaklar.append("font:" + os.path.basename(yol))
            if fi % 20 == 19:
                P.kaydet()
    except KeyboardInterrupt:
        print("\nDurduruldu; öğrenilen harfler kaydediliyor...", file=sys.stderr, flush=True)
    P.ornek += ogrenilen
    P.kaydet()
    _net_kaydet()
    return ogrenilen, kullanilan


# ====================================================================== COZME
def _bol(kap, p, ust, alt, P, m0):
    """Degen iki harf: en az dolu sutundan ikiye bolmeyi dener. -> [(kutu, harf, mesafe)] x2 ya da None."""
    px0, px1 = p[0], p[1]
    w = px1 - px0
    kolon = _izdusum(kap.crop((px0, ust, px1, alt)), False)
    adaylar = sorted(range(max(1, int(w * 0.3)), min(w - 1, int(w * 0.7)) + 1), key=lambda c: kolon[c])[:3]
    en_iyi = None
    for c in adaylar:
        sol, sag = _kutu(kap, px0, px0 + c, ust, alt), _kutu(kap, px0 + c, px1, ust, alt)
        if not sol or not sag:
            continue
        h1, m1 = P.bul(ozellik(kap, sol, ust, alt))
        h2, m2 = P.bul(ozellik(kap, sag, ust, alt))
        if (m1 + m2) / 2 < 0.75 * m0 and (en_iyi is None or m1 + m2 < en_iyi[0]):
            en_iyi = (m1 + m2, [(sol, h1, m1), (sag, h2, m2)])
    return en_iyi[1] if en_iyi else None


def _satir(kap, ust, alt, P):
    """Bir satiri cozer. -> (metin, toplam_mesafe, harf_sayisi)."""
    pr = parcalar(kap, 0, kap.width, ust, alt)
    if not pr:
        return "", 0.0, 0
    sb = alt - ust
    es = [P.bul(ozellik(kap, p, ust, alt)) for p in pr]
    genis = sorted(p[1] - p[0] for p in pr)
    orta_en = genis[len(genis) // 2]
    sonuc, i = [], 0                                     # [(kutu, harf, mesafe)]
    while i < len(pr):
        p, (h, m) = pr[i], es[i]
        if i + 1 < len(pr):                              # bolunmus harf: iki dar, neredeyse bitisik parca
            q, (h2, m2) = pr[i + 1], es[i + 1]
            if q[0] - p[1] <= max(1, 0.05 * sb) and max(m, m2) > 14 and q[1] - p[0] <= 1.6 * orta_en:
                bir = _kutu(kap, p[0], q[1], ust, alt)
                if bir:
                    hb, mb = P.bul(ozellik(kap, bir, ust, alt))
                    if mb < 0.8 * (m + m2) / 2:
                        sonuc.append((bir, hb, mb)); i += 2
                        continue
        if m > 18 and p[1] - p[0] > 1.25 * orta_en:      # degen iki harf
            iki = _bol(kap, p, ust, alt, P, m)
            if iki:
                sonuc += iki; i += 1
                continue
        sonuc.append((p, h, m)); i += 1
    araliklar = sorted(b[0][0] - a[0][1] for a, b in zip(sonuc, sonuc[1:]))
    harf_arasi = araliklar[len(araliklar) // 3] if araliklar else 0
    bosluk = max(2.2 * harf_arasi, 0.22 * sb)
    yazi = []
    for j, (k, h, m) in enumerate(sonuc):
        if j and k[0] - sonuc[j - 1][0][1] > bosluk:
            yazi.append(" ")
        yazi.append(h if m < EMIN else "·")
    return "".join(yazi), sum(m for _, _, m in sonuc), len(sonuc)


def yazi_yollari_ogren(pdfler, ilerleme=None, dpi=300):
    """Metinli PDF'lerin sayfalarından CRW7 piksel yollarını öğretir (yazıya özel; ~/.croow/yazi_yollari.crwm).
    Okuyucu bu yolları hassas satırları detaylandırıp yeniden okumak için kullanır."""
    global _YOL_MODELI
    import pdf_motor
    api = os.path.join(KOK, "..", "motor")
    if os.path.isdir(api) and os.path.abspath(api) not in sys.path:
        sys.path.insert(0, os.path.abspath(api))
    from roots_memory import RootsMemory
    os.makedirs(VERI, exist_ok=True)
    m = RootsMemory(yazi_yollari_yolu())
    sayfalar = [(p, k) for p in pdfler for k in range(1, pdf_motor.sayfa_sayisi(p) + 1)]
    for i, (p, k) in enumerate(sayfalar):
        if ilerleme:
            ilerleme(i / max(1, len(sayfalar)), f"yazı yolları öğreniliyor: {os.path.basename(p)} s.{k}")
        img = pdf_motor.ciz(p, k, dpi)
        if img is not None:
            m.learn_paths(img.convert("RGB"))
    m.save()
    _YOL_MODELI = None                                   # yeni yollar bir sonraki okumada kullanılır
    return len(sayfalar), m.paths.summary()


def resim_coz(img, P=None, duzelt=True, yakinlas=None):
    """Sayfa resmi (PIL) -> metin. yakinlas: hassas satirlari daha yuksek cozunurlukte yeniden ciz (PDF'te var)."""
    P = P or Palet()
    if not P.k:
        raise RuntimeError("Harf paleti boş. Önce öğret:  python3 crw_harf.py ogren <metinli PDF'ler>")
    if yakinlas is None:                                 # resim (PDF yok): hassas satir gecis paletiyle acilir
        yakinlas = _net_yakinlastirici(img)
    img, _ = duzle(img)                                   # egik tarama: once duzlenir
    kap = kapsama(img)
    out = []
    for ust, alt in satirlar(kap):
        yazi, top, n = _satir(kap, ust, alt, P)
        if yakinlas and n and (top / n > 16 or hassaslik(kap, ust, alt) > 0.35):
            pay = int(0.15 * (alt - ust))
            z = yakinlas(0, max(0, ust - pay), kap.width, min(kap.height, alt + pay))
            if z is not None:
                zk = kapsama(z)
                b = satirlar(zk)
                if b:
                    zu, za = max(b, key=lambda x: x[1] - x[0])
                    y2, t2, n2 = _satir(zk, zu, za, P)
                    if n2 and t2 / n2 < top / n:
                        yazi = y2
        out.append(yazi)
    metin = "\n".join(out)
    return Duzeltici.ortak().duzelt(metin) if duzelt else metin


def sayfa_coz(pdf, k, gecici, P, duzelt=True, kirli=False):
    img = sayfa_resmi(pdf, k, gecici)
    if img is None:
        return ""
    if kirli:
        img = _kirlet(img)
    return resim_coz(img, P, duzelt, yakinlastirici(pdf, k, gecici, kirli))


def pdf_coz(pdf, ilerleme=None):
    """PDF -> metin (sayfalar \\f ile ayrilir). crw_pdf.PIKSEL_COZUCU buna baglidir."""
    P = Palet()
    n = sayfa_sayisi(pdf)
    sayfalar = []
    with tempfile.TemporaryDirectory(prefix="croow_harf_") as gecici:
        for k in range(1, n + 1):
            if ilerleme:
                ilerleme((k - 1) / max(1, n), f"sayfa {k}/{n} çözülüyor (piksel analizi)…")
            sayfalar.append(sayfa_coz(pdf, k, gecici, P))
    return "\f".join(sayfalar)


# ====================================================================== 6. KELIME ONARIMI
class Duzeltici:
    """Pikselden okunan kelime Croow'un DIL MODELINDE yoksa: kelime icindeki suphe isaretleri (~ ? ( ) ...)
    bilinmeyen harf sayilir ve modeldeki en sik uyan kelime aranir; yoksa tek harf farkla en sik kelime.
    Rakam agirlikli kelimelerde I/l/î -> 1, O/Ö/Ü -> 0. Model yoksa hicbir sey yapmaz."""
    _tek = None
    HARFLER = "abcdefghijklmnopqrstuvwxyzçğıöşü"
    SUPHE = set("·~?()[]{}!|*")

    @classmethod
    def ortak(cls):
        if cls._tek is None:
            cls._tek = cls()
        return cls._tek

    def __init__(self):
        self.modeller = {}
        try:
            import ngram_crw
            for dil, ad in (("en", "ngram3_en_base.crw"), ("tr", "ngram3_base.crw")):
                y = os.path.join(KOK, "model_crw", ad)
                if os.path.exists(y):
                    self.modeller[dil] = ngram_crw._Parca(y)
        except Exception:  # noqa: BLE001
            self.modeller = {}

    def _sayi(self, p, w):
        i = p.id(w)
        if i is None:
            return 0
        r = p.t["sonraki0"].bul(i)
        return r[1] if r else 0

    def _en_sik(self, p, adaylar):
        en, en_s = None, 0
        for x in adaylar:
            s = self._sayi(p, x)
            if s > en_s:
                en, en_s = x, s
        return en

    def _tek_fark(self, w):
        uret = set()
        for i in range(len(w) + 1):
            a, b = w[:i], w[i:]
            if b:
                uret.add(a + b[1:])
                uret.update(a + c + b[1:] for c in self.HARFLER)
            if len(b) > 1:
                uret.add(a + b[1] + b[0] + b[2:])
            uret.update(a + c + b for c in self.HARFLER)
        return uret

    def _bilinmeyenli(self, w):
        """'w~th~n' -> 'within': bilinmeyen (·) yerlerine harf koyar (en fazla 2 bilinmeyen)."""
        yer = [i for i, c in enumerate(w) if c == "·"]
        adaylar = [w]
        for i in yer:
            adaylar = [x[:i] + c + x[i + 1:] for x in adaylar for c in self.HARFLER]
        return adaylar

    def _onar(self, p, w):
        k = w.lower()
        harf = sum(c.isalpha() for c in k)
        rakam = sum(c.isdigit() for c in k)
        if rakam and rakam >= harf:                      # sayi: benzeyen harfleri rakama cevir
            return w.translate(str.maketrans("IlîıÎ|OoÖÜüSZ", "1111110000032"))
        if harf < 2:
            return w
        if p.id(k) is not None:
            return w
        govde = "".join("·" if (c in self.SUPHE and 0 < i < len(k) - 1) else c for i, c in enumerate(k))
        y = None
        if 0 < govde.count("·") <= 2 and all(c.isalpha() or c == "·" for c in govde):
            y = self._en_sik(p, self._bilinmeyenli(govde))
        if not y and govde.isalpha() and len(govde) >= 3:
            y = self._en_sik(p, self._tek_fark(govde))
        if not y:
            return w
        return y.capitalize() if w[:1].isupper() else y

    def duzelt(self, metin):
        if not self.modeller:
            return metin
        kelimeler = re.findall(r"\w+", metin.lower())
        if not kelimeler:
            return metin
        dil = max(self.modeller, key=lambda d: sum(1 for w in kelimeler[:300] if self.modeller[d].id(w) is not None))
        p = self.modeller[dil]

        def degistir(m):
            bas, govde, son = m.group(1), m.group(2), m.group(3)
            return bas + self._onar(p, govde) + son
        return re.sub(r"([\"'(\[“‘]*)(\S+?)([.,;:!?\"')\]”’]*)(?=\s|$)", degistir, metin)


# ====================================================================== SINAMA
def _kirlet(img):
    from PIL import Image, ImageFilter
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    gurultu = Image.effect_noise(img.size, 18).convert("L")
    img = Image.blend(img, gurultu, 0.12)
    return img.point(lambda v: 40 + v * 0.75)


def sina(pdf, en_cok_sayfa=5, kirli=False, ilerleme=None):
    """PDF'in GORUNTUSUNU cozer, PDF'in KENDI metniyle karsilastirir. -> rapor satirlari."""
    import difflib
    import time
    P = Palet()
    if not P.k:
        raise RuntimeError("Harf paleti boş. Önce öğret:  python3 crw_harf.py ogren <metinli PDF'ler>")
    rapor = []
    if os.path.basename(pdf) in P.kaynaklar:
        rapor.append("UYARI: bu PDF öğretimde kullanılmış; sonuç olduğundan iyi çıkar.")
    n = min(sayfa_sayisi(pdf), en_cok_sayfa)
    top_harf = hata = top_kelime = dogru_kelime = emin_degil = 0
    karisan, sure, ornekler = {}, 0.0, []
    with tempfile.TemporaryDirectory(prefix="croow_sina_") as gecici:
        for k in range(1, n + 1):
            if ilerleme:
                ilerleme((k - 1) / max(1, n), f"sayfa {k}/{n} sınanıyor…")
            import pdf_motor
            ham = _birlestir(pdf_motor.metin(pdf, k, duzen=False))
            dogru = " ".join(ham.split())
            if len(dogru) < 50:
                continue
            t = time.time()
            cozulen_ham = sayfa_coz(pdf, k, gecici, P, True, kirli)
            sure += time.time() - t
            cozulen = " ".join(cozulen_ham.split())
            emin_degil += cozulen.count("·")
            sm = difflib.SequenceMatcher(None, dogru, cozulen, autojunk=False)
            for op, a0, a1, b0, b1 in sm.get_opcodes():
                if op == "equal":
                    continue
                hata += max(a1 - a0, b1 - b0)
                if op == "replace" and a1 - a0 == b1 - b0:
                    for x, y in zip(dogru[a0:a1], cozulen[b0:b1]):
                        karisan[(x, y)] = karisan.get((x, y), 0) + 1
            top_harf += len(dogru)
            dk, ck = dogru.split(), cozulen.split()
            top_kelime += len(dk)
            dogru_kelime += sum(b.size for b in difflib.SequenceMatcher(None, dk, ck, autojunk=False).get_matching_blocks())
            for d, c in zip(ham.splitlines(), cozulen_ham.splitlines()):
                if d.strip() and len(ornekler) < 6:
                    ornekler.append((d.strip()[:90], c.strip()[:90]))
    if not top_harf:
        return rapor + ["Bu PDF'te metin katmanı yok; ölçmek için metinli bir PDF gerekir."]
    rapor += [
        f"Sınanan: {os.path.basename(pdf)} · {n} sayfa" + (" · TARAMA BENZERİ BOZULMA İLE" if kirli else ""),
        f"Harf doğruluğu : %{100 * max(0, 1 - hata / top_harf):.1f}   ({hata:,} hata / {top_harf:,} harf)",
        f"Kelime doğruluğu: %{100 * dogru_kelime / max(1, top_kelime):.1f}   ({dogru_kelime:,} / {top_kelime:,} kelime)",
        f"Emin olunmayan  : {emin_degil:,} harf (·)",
        f"Hız             : sayfa başına {sure / max(1, n):.1f} sn",
        "", "En çok karışan harfler (doğrusu → okunan):"]
    rapor += [f"  {a!r} → {b!r}   {c:,} kez" for (a, b), c in sorted(karisan.items(), key=lambda x: -x[1])[:15]] or ["  -"]
    rapor += ["", "Örnek satırlar (üstte doğrusu, altta Croow'un okuduğu):"]
    for d, c in ornekler:
        rapor += [f"  D: {d}", f"  C: {c}", ""]
    return rapor


def hazir_mi():
    import crw_json as CJ
    return CJ.var_mi(PALET)


# ====================================================================== komut satiri
def main():
    a = sys.argv[1:]
    if not a:
        return print(__doc__)
    yaz = lambda o, m: print(f"  %{o * 100:.0f} {m}", file=sys.stderr)
    if a[0] == "ogren":
        pdfler = []
        for y in a[1:]:
            if os.path.isdir(y):
                pdfler += sorted(os.path.join(k, f) for k, _, fs in os.walk(y) for f in fs if f.lower().endswith(".pdf"))
            elif y.lower().endswith(".pdf"):
                pdfler.append(y)
        if not pdfler:
            return print("PDF ver: python3 crw_harf.py ogren kitap.pdf  (ya da bir klasör)")
        n, atla = ogren(pdfler, yaz)
        P = Palet()
        print(f"{n:,} harf örneği öğrenildi ({atla:,} kelime atlandı). Palet: {P.harf_sayisi()} farklı harf, "
              f"{len(P.k):,} kök ızgara.")
    elif a[0] == "coz" and len(a) > 1:
        if a[1].lower().endswith(".pdf"):
            metin = pdf_coz(a[1], yaz)
        else:
            metin = resim_coz(_pil().open(a[1]))
        hedef = a[2] if len(a) > 2 else os.path.splitext(a[1])[0] + ".txt"
        with open(hedef, "w", encoding="utf-8") as f:
            f.write(metin)
        print(f"{hedef} · {len(metin):,} karakter")
    elif a[0] == "alfabe":
        fontlar = [x for x in a[1:] if x.lower().endswith((".ttf", ".otf"))] or None
        n, f = alfabe_ogren(fontlar, ilerleme=yaz)
        P = Palet()
        print(f"{n:,} harf örneği, {f} yazı tipinden öğrenildi. Palet: {P.harf_sayisi()} farklı harf, "
              f"{len(P.k):,} kök ızgara.")
    elif a[0] == "sina" and len(a) > 1:
        sayfa = int(a[a.index("--sayfa") + 1]) if "--sayfa" in a else 5
        print("\n".join(sina(a[1], sayfa, "--kirli" in a, yaz)))
    elif a[0] == "bilgi":
        P = Palet()
        sayac = {}
        for x in P.k:
            sayac[x[0]] = sayac.get(x[0], 0) + x[6]
        print(f"{P.harf_sayisi()} harf · {len(P.k):,} kök ızgara · {P.ornek:,} örnek · {len(P.kaynaklar)} PDF")
        print("  " + " ".join(f"{h}({n})" for h, n in sorted(sayac.items(), key=lambda x: -x[1])[:60]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
