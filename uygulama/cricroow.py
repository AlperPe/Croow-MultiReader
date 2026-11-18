#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
cricroow.py - CriCroow7: belge sayfasını adım adım NETLEŞTİRİR, harf deposundan yola çıkarak eksik çizgileri
ÇOK HAFİF TAMAMLAR ve harf olmayan izleri (leke) her adımda biraz SOLDURUR.

Akış:
  0. Netleştirme: sayfa bir kez CRW7'nin yazıdan öğrenilmiş piksel yollarıyla ×2 detaylandırılır (yollar varsa).
  her adımda:
  1. Okuma: harf paleti her harf kutusunu paletteki en yakın köke bağlar (crw_harf).
  2. Tamamlama: emin olunan harflerde (sayfanın en iyi eşleşmeleri), kökün 8x8 doluluk şablonunun dolu olduğu ama sayfada eksik kalan yerlere
     eksiğin yalnızca küçük bir kısmı (alfa) kadar mürekkep eklenir. Var olan mürekkep SİLİNMEZ.
  3. Temizleme: hiçbir harf kutusuna girmeyen izler (leke) her adımda beta oranında soldurulur.
     Bir satırdaki HER harf kutusu korunur (tanınmasa bile): okunamayan yazı asla leke sayılmaz.
     Fren: toplam mürekkebin FREN oranından fazlası soldurulacaksa işlem durur.
  Değişiklik çok küçülünce durur.

ADLİ KULLANIM UYARISI: Tamamlama, motorun TAHMİNİNİ sayfaya yazar. Sonuç bir OKUMA YARDIMIDIR, delil değildir.
Orijinal dosya hiçbir zaman değiştirilmez; her çalıştırma bir değişiklik haritası (mavi: eklenen, kırmızı: soldurulan)
ve orijinalin SHA-256 parmak iziyle bir rapor üretir.
"""
import hashlib
import json
import math
import os
import sys
import time

import numpy as np
from PIL import Image, ImageFilter

import crw_harf as CH

SURUM = "CriCroow7 1.0"
ALFA = 0.12          # her adımda eksiğin bu kadarı tamamlanır (çok hafif)
BETA = 0.25          # her adımda lekenin bu kadarı soldurulur
EMIN_YUZDE = 40      # sayfadaki en iyi eşleşmelerin bu yüzdeliği "emin" sayılır (yalnızca bunlar tamamlanır)
EMIN_TAVAN = 45.0    # ... ama uzaklığı bundan büyük olan asla emin sayılmaz
FREN = 0.25          # toplam mürekkebin bu kadarından fazlası leke diye soldurulacaksa durulur
ADIM = 6
PAY = 1              # harf kutusu çevresinde korunan pay (piksel)


def _kok_bul(P, oz):
    """Palet.bul ile aynı seçim, ama kökün kendisini de döndürür: (harf, uzaklık, kök)."""
    aday = sorted(P.k, key=lambda x: CH._kaba_mesafe(x, oz))[:12]
    en = min(aday, key=lambda x: CH._mesafe(x, oz) + 6 / (x[6] ** 0.5))
    return en[0], CH._mesafe(en, oz), en


LEKE_SATIR = 2       # en fazla bu kadar iz içeren "satır" gerçek bir satır değildir: leke
LEKE_ALAN = 0.15     # tipik harf alanının bu kadarından küçük ve hiçbir harfe benzemeyen iz: leke


def _harfler(kap_img, P):
    """Sayfadaki izler: [(x0, x1, y0, y1, harf, uzaklık, kök_izgarası, satır_no)]"""
    out = []
    for no, (ust, alt) in enumerate(CH.satirlar(kap_img)):
        for p in CH.parcalar(kap_img, 0, kap_img.width, ust, alt) or []:
            try:
                h, m, kok = _kok_bul(P, CH.ozellik(kap_img, p, ust, alt))
            except Exception:  # noqa: BLE001 - bozuk kutu: atla
                continue
            out.append((p[0], p[1], p[2], p[3], h, m, kok[1], no))
    return out


def _lekeler(harfler, esik):
    """Harf olmayan izler: satırında tek başına duranlar (en fazla LEKE_SATIR iz) ya da çok küçük olup
    hiçbir harfe benzemeyenler. -> leke sayılan izlerin sıra numaraları"""
    from collections import Counter
    if not harfler:
        return set()
    satir_say = Counter(h[7] for h in harfler)
    alanlar = sorted((h[1] - h[0]) * (h[3] - h[2]) for h in harfler)
    tipik = alanlar[len(alanlar) // 2] or 1
    out = set()
    for i, (x0, x1, y0, y1, _, m, _, no) in enumerate(harfler):
        if satir_say[no] <= LEKE_SATIR:
            out.add(i)
        elif (x1 - x0) * (y1 - y0) < LEKE_ALAN * tipik and m > esik:
            out.add(i)
    return out


def onar(img, P=None, adim=ADIM, alfa=ALFA, beta=BETA, emin=None, netlestir=True, kaynak_bayt=None,
         ilerleme=None):
    """
    img: PIL resmi (sayfa). -> (onarılmış gri resim, değişiklik haritası (RGB), rapor sözlüğü)
    kaynak_bayt: orijinal dosyanın baytları (rapordaki SHA-256 için).
    """
    P = P or CH.Palet()
    if not P.k:
        raise RuntimeError("Harf paleti boş. Önce Araçlar → 'Harf paletini alfabeden öğret'.")
    t0 = time.time()
    rapor = {"surum": SURUM, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
             "orijinal_sha256": hashlib.sha256(kaynak_bayt).hexdigest() if kaynak_bayt else None,
             "orijinal_boyut": list(img.size), "ayarlar": {"adim": adim, "alfa": alfa, "beta": beta, "emin_yuzde": EMIN_YUZDE, "emin_tavan": EMIN_TAVAN,
                         "fren": FREN},
             "uyari": "Tamamlama motorun tahminidir. Bu görüntü bir okuma yardımıdır, delil değildir. "
                      "Orijinal dosya değiştirilmemiştir.",
             "adimlar": []}
    g, aci = CH.duzle(img)                                  # eğik tarama önce düzlenir
    rapor["egim_duzeltme_derece"] = aci

    # 0. netleştirme (CRW7, yazı yolları)
    model = CH._croow_yol_modeli() if netlestir else None
    if model is not None:
        if ilerleme:
            ilerleme(0, "CriCroow7: CRW7 ile netleştiriliyor…")
        from paths_memory import enhance_strips
        g = enhance_strips(g.convert("RGB"), model).convert("L")
        rapor["netlestirme"] = "CRW7 yazı yolları ×2"
    else:
        rapor["netlestirme"] = "yok (yazı yolları öğrenilmemiş)"
    rapor["calisma_boyutu"] = list(g.size)

    mur, kag = CH.seviyeler(g)
    kap0 = np.asarray(CH.kapsama(g), dtype=np.float32)
    kap = kap0.copy()
    H, W = kap.shape
    ilk_murekkep = float(kap0.sum()) or 1.0
    toplam_soldurulan = 0.0

    for t in range(adim):
        if ilerleme:
            ilerleme((t + 1) / (adim + 1), f"CriCroow7: adım {t + 1}/{adim} (oku · tamamla · temizle)")
        kap_img = Image.fromarray(np.clip(kap, 0, 255).astype(np.uint8))
        harfler = _harfler(kap_img, P)
        korunan = np.zeros((H, W), dtype=bool)
        eklenen = 0.0
        if harfler:
            esik = min(EMIN_TAVAN, float(np.percentile([h[5] for h in harfler], EMIN_YUZDE))) if emin is None else emin
        else:
            esik = -1
        lekeler = _lekeler(harfler, esik)
        taninan = sum(1 for i, h in enumerate(harfler) if h[5] <= esik and i not in lekeler)
        for i, (x0, x1, y0, y1, h, m, d, _) in enumerate(harfler):
            if i in lekeler:
                continue                                  # harf olmayan iz: korunmaz, aşağıda soldurulur
            a0, a1 = max(0, y0 - PAY), min(H, y1 + PAY)
            b0, b1 = max(0, x0 - PAY), min(W, x1 + PAY)
            korunan[a0:a1, b0:b1] = True                  # her harf kutusu korunur (tanınmasa da)
            if m > esik or x1 - x0 < 2 or y1 - y0 < 2:
                continue                                  # emin değil: tamamlanmaz
            # kökün 8x8 doluluk şablonu (0..99) kutu boyutuna büyütülür -> hedef doluluk (0..255)
            sablon = Image.fromarray((np.asarray(d, dtype=np.float32).reshape(CH.IZ, CH.IZ) * 255 / 99).astype(np.uint8))
            hedef = np.asarray(sablon.resize((x1 - x0, y1 - y0), Image.Resampling.BILINEAR), dtype=np.float32)
            parca = kap[y0:y1, x0:x1]
            eksik = np.maximum(0, hedef - parca)          # yalnızca EKSİK: var olan mürekkep silinmez
            ek = alfa * eksik
            parca += ek
            eklenen += float(ek.sum())
        leke = (kap > 0) & ~korunan
        soldurulan = float((kap[leke] * beta).sum())
        if (toplam_soldurulan + soldurulan) / ilk_murekkep > FREN:
            rapor["fren"] = (f"adım {t + 1}: toplam mürekkebin %{100 * FREN:.0f}'inden fazlası leke sayılacaktı; "
                             "işlem durduruldu (harf olarak bulunamayan yazı olabilir)")
            break
        toplam_soldurulan += soldurulan
        kap[leke] *= (1 - beta)
        kap[kap < CH.GURULTU * 0.5] = 0                    # sönen izler kâğıda karışır
        degisim = (eklenen + soldurulan) / 255.0
        rapor["adimlar"].append({"adim": t + 1, "harf_kutusu": len(harfler) - len(lekeler), "leke_izi": len(lekeler),
                                 "taninan": taninan,
                                 "emin_esigi": round(esik, 1),
                                 "eklenen_murekkep_piksel": round(eklenen / 255, 1),
                                 "soldurulan_leke_piksel": round(soldurulan / 255, 1)})
        if t >= 2 and degisim < 0.002 * ilk_murekkep / 255:   # en az 3 adım; sonra değişim çok küçülünce dur
            break

    # kapsama -> gri resim (kâğıt ve mürekkep tonları korunur)
    # yalnızca değişen kadarı uygulanır: dokunulmayan pikseller netleştirilmiş sayfadaki tonunu aynen korur
    g_arr = np.asarray(g, dtype=np.float32)
    out = (g_arr - (kap - kap0) / 255.0 * (kag - mur)).clip(0, 255).astype(np.uint8)
    sonuc = Image.fromarray(out, "L")

    # değişiklik haritası: mavi = eklenen mürekkep, kırmızı = soldurulan leke
    taban = np.stack([out] * 3, axis=2).astype(np.float32) * 0.6 + 100
    ek = (kap - kap0) > 8
    sil = (kap0 - kap) > 8
    taban[ek] = (40, 90, 255)
    taban[sil] = (235, 50, 50)
    harita = Image.fromarray(taban.clip(0, 255).astype(np.uint8), "RGB")

    rapor["toplam"] = {"eklenen_piksel": int(ek.sum()), "soldurulan_piksel": int(sil.sum()),
                       "degisen_oran": round(float((ek | sil).sum()) / (W * H), 5),
                       "sure_sn": round(time.time() - t0, 1)}
    return sonuc, harita, rapor


# ====================================================================== BELGE KİPİ (belgenin kendi harfleriyle)
KUVVET_ESIK = 0.7    # bir harf ancak olasılığı bundan büyükse yerine konur (tamamlanır / içi temizlenir)
KALIP_DOLU = 150     # kalıbın yalnızca bu kadar kesin dolu yerleri tamamlanır (kenar halesi değil)
INCELT = 0.3         # her adımda kalınlaşmış harfin dış katmanının bu kadarı soldurulur (milim milim)
HAT_KALIN = 2        # ana hattın çevresinde korunan yarı kalınlık (piksel): incelmiş harfin çizgi kalınlığı
DOGRULA_ORAN = 0.6    # inceltme sonrası harf olasılığı, öncekinin bu oranının altına düşerse ...
DOGRULA_TAVAN = 0.30  # ... ve bu değerin altındaysa adım geri alınır (harf tanınmaz oldu)
YOL_ORAN = 0.6       # yol bandının dışındaki mürekkebin her adımda silinen oranı (sert: yol harfin gerçek şekli)
VARYANT_GUVEN = 0.35  # varyanta göre dönüştürmek için harfin ana hattından tanınma olasılığı en az bu kadar
INCELT_FREN = 0.4    # toplam mürekkebin en fazla bu kadarı inceltilir
INCELT_ESIK = 0.3    # inceltme için en iyi adayın olasılığı en az bu kadar olmalı
CEKIRDEK = 200       # kalıbın çekirdeği: o harfin her örneğinde kesin dolu çizgi merkezi (inceltme buna dokunmaz)
YAKIN_MUREKKEP = 5   # tamamlanacak piksel, var olan mürekkebe en fazla bu kadar uzak olabilir (kırık/delik doldurma)
GOVDE_PAY = 2        # kalıbın dışına taşan mürekkep sayılırken kalıp bu kadar piksel genişletilir


def _karartmalar(kap):
    """Sansür/karartma kutuları: büyük, dolu, dikdörtgen siyah alanlar. Asla silinmez; maske ve kutu listesi."""
    import numpy as np
    from PIL import Image
    H, W = kap.shape
    k = 8
    kucuk = np.asarray(Image.fromarray(kap.clip(0, 255).astype(np.uint8)).resize((max(1, W // k), max(1, H // k)),
                                                                                  Image.Resampling.BOX))
    dolu = kucuk > 215
    maske = np.zeros_like(kap, dtype=bool)
    kutular = []
    gorulen = np.zeros_like(dolu)
    for y in range(dolu.shape[0]):
        for x in range(dolu.shape[1]):
            if not dolu[y, x] or gorulen[y, x]:
                continue
            # dikdörtgeni sağa ve aşağı büyüt
            x1 = x
            while x1 + 1 < dolu.shape[1] and dolu[y, x1 + 1]:
                x1 += 1
            y1 = y
            while y1 + 1 < dolu.shape[0] and dolu[y1 + 1, x:x1 + 1].mean() > 0.8:
                y1 += 1
            gorulen[y:y1 + 1, x:x1 + 1] = True
            w, h = (x1 - x + 1) * k, (y1 - y + 1) * k
            if w >= 64 and h >= 44 and _keskin_kenar(kap, x * k, y * k, (x1 + 1) * k, (y1 + 1) * k):
                a0, a1, b0, b1 = max(0, y * k - 6), min(H, (y1 + 1) * k + 6), max(0, x * k - 6), min(W, (x1 + 1) * k + 6)
                maske[a0:a1, b0:b1] = True
                kutular.append([int(b0), int(a0), int(b1 - b0), int(a1 - a0)])
    return maske, kutular


def _keskin_kenar(kap, x0, y0, x1, y1, bant=10):
    """Karartma kutusu keskin kenarlıdır: hemen dışındaki şeritlerin çoğu kâğıttır (harfler hariç az mürekkep).
    Yuvarlak mürekkep lekesi ise kenara doğru yavaş yavaş azalır -> karartma sayılmaz."""
    H, W = kap.shape
    seritler = [kap[max(0, y0 - bant - 4):max(0, y0 - 4), x0:x1], kap[min(H, y1 + 4):min(H, y1 + bant + 4), x0:x1],
                kap[y0:y1, max(0, x0 - bant - 4):max(0, x0 - 4)], kap[y0:y1, min(W, x1 + 4):min(W, x1 + bant + 4)]]
    oran = [float((s > 128).mean()) for s in seritler if s.size]
    # içi: neredeyse tamamen dolu olmalı
    ic = float((kap[y0:y1, x0:x1] > 200).mean())
    return ic > 0.9 and oran and sorted(oran)[len(oran) // 2] < 0.3


def _yatay_cizgiler(murekkep, en_az):
    """Uzun yatay çizgiler (alt çizgi, cetvel): korunur. murekkep: bool dizi."""
    import numpy as np
    out = np.zeros_like(murekkep)
    for y in range(murekkep.shape[0]):
        r = murekkep[y]
        if r.sum() < en_az:
            continue
        d = np.diff(np.concatenate(([0], r.astype(np.int8), [0])))
        bas, son = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        for a, b in zip(bas, son):
            if b - a >= en_az:
                out[max(0, y - 2):y + 3, a:b] = True
    return out


KOPRU_TABAN = 2      # risk 0'da köprülenen en uzun boşluk (piksel)
KOPRU_RISK = 9       # risk 1'de buna eklenen uzunluk (piksel)
KOPRU_GUC = 0.5      # her adımda boşluğun bu kadarı doldurulur (milim milim)


def _uc_yonleri(hat):
    """Ana hattın uç noktaları ve çizginin o uçtaki yönü: [(y, x, dy, dx, kalınlık ölçüm geriliği)]. Yön, uçtan geriye 6 piksel izlenerek bulunur."""
    H, W = hat.shape
    ys, xs = np.nonzero(hat)
    nokta = set(zip(ys.tolist(), xs.tolist()))
    kom = lambda y, x: [(y + a, x + b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a or b) and (y + a, x + b) in nokta]
    out = []
    for y, x in nokta:
        if len(kom(y, x)) != 1:
            continue
        iz, gorulen = [(y, x)], {(y, x)}
        while len(iz) < 7:
            sonraki = [q for q in kom(*iz[-1]) if q not in gorulen]
            if len(sonraki) != 1:                      # kavşak ya da çizgi bitti
                break
            iz.append(sonraki[0]); gorulen.add(sonraki[0])
        if len(iz) < 2:                                # tek piksel: yön yok
            continue
        dy, dx = y - iz[-1][0], x - iz[-1][1]
        n = (dy * dy + dx * dx) ** 0.5
        if n:
            out.append((y, x, dy / n, dx / n, min(2, len(iz) - 2)))
    return out


def kopru(parca, serbest, en_uzun, guc=KOPRU_GUC):
    """KOPUK ÇİZGİ TAMAMLAMA: çizgi düz geliyor, boşluk var ve boşluğun ardında mürekkep sürüyorsa boşluk çizginin
    yönünde, çizgi kalınlığında doldurulur. Karşıda mürekkep yoksa hiçbir şey eklenmez.
    parca: kapsama (float, yerinde değişir). -> (eklenen dizi, köprü sayısı)"""
    m = parca > 110
    ek = np.zeros_like(parca)
    if m.sum() < 6:
        return ek, 0
    import belge_harf as BH
    hat = BH.ana_hat(m)
    uzun = int(hat.sum())
    if not uzun:
        return ek, 0
    kalin = max(2, min(8, int(round(m.sum() / uzun))))            # tipik çizgi kalınlığı
    ton = float(parca[m].mean())
    H, W = parca.shape
    say = 0
    for y, x, dy, dx, geri in _uc_yonleri(hat):
        disari, bosluk = False, []
        for s_ in range(1, kalin + en_uzun + 3):
            yy, xx = int(round(y + dy * s_)), int(round(x + dx * s_))
            if not (0 <= yy < H and 0 <= xx < W):
                break
            if m[yy, xx]:
                if disari:                                         # boşluğun ardında mürekkep: köprüle
                    if 0 < len(bosluk) <= en_uzun:
                        # ucun kendi kalınlığı: uçtan 2 piksel geride, çizgiye dik yönde mürekkep uzunluğu
                        gy, gx = y - dy * geri, x - dx * geri
                        yerel = 1
                        for yon in (1, -1):
                            for q in range(1, 9):
                                py, px = int(round(gy - dx * q * yon)), int(round(gx + dy * q * yon))
                                if not (0 <= py < H and 0 <= px < W) or not m[py, px]:
                                    break
                                yerel += 1
                        yar = max(1, min(kalin, yerel)) // 2
                        for by, bx in bosluk:
                            a0, a1, b0, b1 = max(0, by - yar), min(H, by + yar + 1), max(0, bx - yar), min(W, bx + yar + 1)
                            hedef = np.maximum(0, ton - parca[a0:a1, b0:b1]) * guc * serbest[a0:a1, b0:b1]
                            ek[a0:a1, b0:b1] = np.maximum(ek[a0:a1, b0:b1], hedef)
                        say += 1
                    break
                continue                                           # hâlâ kendi mürekkebinin içinde
            disari = True
            bosluk.append((yy, xx))
            if len(bosluk) > en_uzun:
                break
    parca += ek
    return ek, say


def _incelt(parca, cekirdek, goz, serbest, oran):
    """Kalınlaşmış harfi bir kat inceltir: yalnızca kâğıda değen DIŞ katman (çekirdek dışı) ve dolmuş gözün merkezi
    oran kadar soldurulur. -> soldurulan dizi"""
    murekkep = parca > 100
    ic = np.asarray(Image.fromarray(murekkep.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3)), dtype=bool)
    dis_katman = murekkep & ~ic
    maske = ((dis_katman & ~cekirdek) | (goz & murekkep)) & serbest
    return np.where(maske, oran * parca, 0)


_YAZI = {}


def _daktilo_yazi_tipi():
    """İnce referans için bilgisayardaki bir daktilo/eş aralıklı yazı tipi (Courier, FreeMono, Liberation Mono...)."""
    if "f" not in _YAZI:
        tercih = ("cour", "freemono", "liberationmono", "nimbusmono", "dejavusansmono", "mono")
        bulunan = None
        try:
            tipler = CH.yazi_tipleri()
        except Exception:  # noqa: BLE001
            tipler = []
        for t in tercih:
            aday = [f for f in tipler if t in os.path.basename(f).lower().replace(" ", "").replace("-", "")
                    and "bold" not in f.lower() and "italic" not in f.lower() and "oblique" not in f.lower()]
            if aday:
                bulunan = aday[0]
                break
        _YAZI["f"] = bulunan
    return _YAZI["f"]


def ince_referans(harf, en, boy):
    """Harfin İNCE sanal referansı: daktilo yazı tipiyle çizilip kutuya oturtulmuş (bool, boy x en) ya da None.
    Kalınlaşmış belgenin kendi kalıbı da kalındır; incelmenin hedefi bu çizimdir (gözü açık, çizgisi ince)."""
    from PIL import ImageDraw, ImageFont
    yol = _daktilo_yazi_tipi()
    if not yol or not harf.strip():
        return None
    anahtar = (harf, en, boy)
    if anahtar in _YAZI:
        return _YAZI[anahtar]
    try:
        f = ImageFont.truetype(yol, 96, layout_engine=ImageFont.Layout.BASIC)
    except Exception:  # noqa: BLE001
        return None
    im = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(im).text((50, 150), harf, font=f, fill=255, anchor="ls")
    kutu = im.getbbox()
    if not kutu:
        return None
    r = im.crop(kutu).resize((max(1, en), max(1, boy)), Image.Resampling.BILINEAR)
    sonuc = np.asarray(r, dtype=np.float32) > 90
    _YAZI[anahtar] = sonuc
    return sonuc


def _cekirdek(depo, adaylar, en, boy):
    """İlk iki adayın kalıp çekirdeklerinin birleşimi (emin olunmasa da gerçek çizgi korunur) ve en iyi adayın
    kâğıt olması gereken gözü. -> (çekirdek, göz) ya da (None, None)"""
    cek, goz = None, None
    for i, a in enumerate(adaylar[:2]):
        if i and a[1] < 0.15:
            break
        ref = ince_referans(a[0], en, boy)
        K = depo.kalip_resmi(a[0], en, boy)
        if ref is not None:
            c = ref                                        # ince sanal referans: hedef bu çizgi
        elif K is not None:
            c = K > CEKIRDEK
        else:
            continue
        cek = c if cek is None else cek | c
        if i == 0:
            goz = ~ref if ref is not None else (K < 25)
    if cek is None:
        return None, None
    cek = np.asarray(Image.fromarray(cek.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3)), dtype=bool)
    return cek, goz & ~cek


def onar_belge(img, depo, P=None, adim=ADIM, alfa=None, beta=0.3, incelt=None, risk=0.0, ogren=True, kalici=False, kaynak_bayt=None, ilerleme=None):
    """
    Belgenin kendi harf deposuyla CriCroow7. Her adım: OKU (olasılık + bağlam) -> KUVVETLİ harfi YERİNE KOY
    (kalıbının eksik yerleri hafifçe doldurulur, kalıp dışına taşan mürekkep hafifçe soldurulur) -> harf olmayan izleri
    soldur -> yeniden oku ve KARŞILAŞTIR (harfi değişen kutunun eklemesi geri alınır, kutu kilitlenir).
    -> (onarılmış gri resim, değişiklik haritası, rapor)
    """
    import belge_harf as BH
    # risk 0..1: yükseldikçe bağlam daha baskın (anahtar harfler kelimeyi belirler), inceltme ve tamamlama daha cesur
    risk = max(0.0, min(1.0, risk))
    alfa_sabit, incelt_sabit, incelt_acik = alfa, incelt, incelt != 0
    eski_baglam = (BH.BAGLAM, BH.TABAN)

    def ayarla(r_):
        """Risk düzeyine göre eşikler. Oturan (doğrulanan) harf arttıkça r_ yükselir: motor cesaretlenir."""
        # risk YALNIZCA eksik kısmı tamamlamayı etkiler (kopuk çizgi köprüleme uzunluğu ve tamamlama gücü);
        # bağlam, inceltme ve oturma eşikleri hep sıkı kalır
        return (KUVVET_ESIK,
                (0.2 + 0.15 * r_) if alfa_sabit is None else alfa_sabit,
                (INCELT if incelt_sabit is None else incelt_sabit) if incelt_acik else 0,
                INCELT_FREN, 0.12, 0.7)
    kuvvet, alfa, incelt, incelt_fren, otur_disari, otur_dolu = ayarla(risk)
    t0 = time.time()
    g, aci = CH.duzle(img)
    mur, kag = CH.seviyeler(g)
    g_arr = np.asarray(g, dtype=np.float32)
    kap0 = np.asarray(CH.kapsama(g), dtype=np.float32)
    kap = kap0.copy()
    H, W = kap.shape
    karartma, karartma_kutu = _karartmalar(kap0)
    kenar = np.asarray(BH.kenarsiz(Image.fromarray(kap0.astype(np.uint8))), dtype=np.float32) == 0
    kenar &= kap0 > 0                                       # tarama kenarı şeridi: dokunulmaz
    rapor = {"surum": SURUM + " (belge kipi)", "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
             "orijinal_sha256": hashlib.sha256(kaynak_bayt).hexdigest() if kaynak_bayt else None,
             "orijinal_boyut": list(img.size), "egim_duzeltme_derece": aci,
             "ayarlar": {"adim": adim, "alfa": alfa, "beta": beta, "kuvvet_esik": round(kuvvet, 2), "risk": risk, "kalip_dolu": KALIP_DOLU,
                         "yakin_murekkep": YAKIN_MUREKKEP, "incelt": incelt, "cekirdek": CEKIRDEK,
                         "fren": FREN},
             "depo": depo.ozet(), "karartma_kutulari": karartma_kutu,
             "uyari": "Tamamlama ve temizleme motorun tahminidir. Bu görüntü bir okuma yardımıdır, delil değildir. "
                      "Karartma (sansür) kutularına dokunulmamıştır. Orijinal dosya değiştirilmemiştir.",
             "adimlar": [], "celiskiler": []}
    ilk_murekkep = float(kap0.sum()) or 1.0
    toplam_soldurulan = toplam_incelen = 0.0
    oturan = set()
    eklenen_kutu = {}                                        # kutu anahtarı -> (harf, eklenen dizi, dilim)
    kilitli = set()
    onceki_harf = {}
    son_okuma = ""
    kap0_img = Image.fromarray(kap0.clip(0, 255).astype(np.uint8))
    rapor["ogrenilen"] = []
    kutu_sayisi = 0
    for t in range(adim):
        if ilerleme:
            ilerleme(t / (adim + 1), f"CriCroow7: adım {t + 1}/{adim} (oku · yerine koy · temizle · karşılaştır)")
        # oturan harfler doğrulamadır: oranı arttıkça risk yükselir
        etkin_risk = min(1.0, risk + 1.5 * len(oturan) / max(1, kutu_sayisi))
        kuvvet, alfa, incelt, incelt_fren, otur_disari, otur_dolu = ayarla(etkin_risk)
        gri = Image.fromarray((kag - kap / 255.0 * (kag - mur)).clip(0, 255).astype(np.uint8))
        satirlar, _ = BH.oku_kutular(gri, depo, P, yakindan=True, duzlendi=True)
        okuma_metni, _ = BH.baglam_uygula(satirlar, depo)      # cümle: temiz harfler çapa, şüpheliler düzelir
        korunan = np.zeros((H, W), dtype=bool)
        eklenen = soldurulan_ic = incelen = 0.0
        yerine = celiski = oturdu = kopru_say = 0
        kopru_uzun = int(round(KOPRU_TABAN + KOPRU_RISK * etkin_risk))
        okuma_satir = []
        boylar = sorted(k["p"][3] - k["p"][2] for s_ in satirlar for k in s_)
        tipik_boy = boylar[len(boylar) // 2] if boylar else 0
        yakin = np.asarray(Image.fromarray((kap > 100).astype(np.uint8) * 255).filter(
            ImageFilter.MaxFilter(2 * YAKIN_MUREKKEP + 1)), dtype=bool)
        kutu_sayisi = sum(len(s_) for s_ in satirlar)
        for satir in satirlar:
            okuma_satir.append("".join((" " if k["bosluk_once"] else "") + k["harf"] for k in satir))
            anahtarlar = [(round((k["p"][2] + k["p"][3]) / 2 / 8), round((k["p"][0] + k["p"][1]) / 2 / 8)) for k in satir]
            for ki, k in enumerate(satir):
                x0, x1, y0, y1 = k["p"][:4]
                anahtar = anahtarlar[ki]
                h, p = k["harf"], k["guven"]                    # bağlamın (cümlenin) kararı
                # oturan (temiz) bir harfin kelimedeki komşusu: eşik düşer, bir temiz harf çevresini açar
                komsu = (ki > 0 and not k["bosluk_once"] and anahtarlar[ki - 1] in oturan) or \
                        (ki + 1 < len(satir) and not satir[ki + 1]["bosluk_once"] and anahtarlar[ki + 1] in oturan)
                kuvvet_k = kuvvet - (0.15 if komsu else 0)
                korunan[max(0, y0 - PAY):y1 + PAY, max(0, x0 - PAY):x1 + PAY] = True
                # KARŞILAŞTIR: daha önce yerine konan harf değiştiyse o eklemeyi geri al, kutuyu kilitle
                if anahtar in eklenen_kutu and eklenen_kutu[anahtar][0] != h and anahtar not in kilitli:
                    eh, ek_dizi, dil = eklenen_kutu.pop(anahtar)
                    kap[dil] -= ek_dizi
                    kilitli.add(anahtar)
                    celiski += 1
                    rapor["celiskiler"].append({"adim": t + 1, "kutu": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                                                "once": eh, "sonra": h})
                if x1 - x0 < 3 or y1 - y0 < 3 or y1 - y0 > 1.3 * tipik_boy:
                    continue
                # KOPUK ÇİZGİ TAMAMLAMA (risk burada): harf ne olursa olsun, düz gelen çizginin boşluğu doldurulur
                if anahtar not in oturan:
                    dk = (slice(y0, y1), slice(x0, x1))
                    ek_k, n_k = kopru(kap[dk], ~karartma[dk] & ~kenar[dk], kopru_uzun)
                    kopru_say += n_k
                    eklenen += float(ek_k.sum())
                # İNCELT: kalınlaşmış harfin dış katmanı çekirdeğe doğru adım adım (kilitli kutular da)
                if anahtar in oturan:
                    continue                                    # sanal referansına oturdu: artık değişmez
                if incelt:
                    hedefler = [(h, p)]
                    if p < 0.8 and k["adaylar"][0][0] != h:      # bağlam emin değilse görünen harf de korunur
                        hedefler.append((k["adaylar"][0][0], 1.0))
                    elif p < 0.8 and len(k["adaylar"]) > 1:
                        hedefler.append((k["adaylar"][1][0], k["adaylar"][1][1]))
                    cek, goz = _cekirdek(depo, hedefler, x1 - x0, y1 - y0)
                    # ANA HAT: harfin kendi orta çizgisi her zaman korunur (harf ne olursa olsun)
                    oz_hat = BH.ana_hat(kap[y0:y1, x0:x1] > 110)
                    oz_hat = np.asarray(Image.fromarray(oz_hat.astype(np.uint8) * 255).filter(
                        ImageFilter.MaxFilter(2 * HAT_KALIN + 1)), dtype=bool)
                    if cek is None or p < 0.8:
                        cek, goz = oz_hat, np.zeros_like(oz_hat)      # emin değil: yalnızca kendi ana hattına incelt
                    else:
                        cek = cek | oz_hat
                    if cek is not None and p >= kuvvet_k:
                        # BENZEYİNCE OTUR: mürekkebin neredeyse tamamı referansın içinde ve referans dolu
                        m_ = kap[y0:y1, x0:x1] > 100
                        ref_ = ince_referans(h, x1 - x0, y1 - y0)
                        if ref_ is not None and m_.sum() > 0:
                            disari = float((m_ & ~cek).sum()) / float(m_.sum())
                            dolu = float((m_ & ref_).sum()) / float(max(1, ref_.sum()))
                            if disari < otur_disari and dolu > otur_dolu:
                                oturan.add(anahtar)
                                oturdu += 1
                                if ogren:                       # YOLU ÖĞREN: harfin sayfadaki ilk (kalın) hâli bu harfin örneğidir
                                    try:
                                        depo.gercek.ekle(h, CH.ozellik(kap0_img, k["p"], k["ust"], k["alt"]))
                                        depo.hat_ekle(h, BH.hat_haritasi(kap0_img, k["p"], k["ust"], k["alt"]))
                                        rapor["ogrenilen"].append({"adim": t + 1, "harf": h,
                                                                   "kutu": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]})
                                    except Exception:  # noqa: BLE001
                                        pass
                                continue
                    if cek is not None:
                        dil_ = (slice(y0, y1), slice(x0, x1))
                        sil_ = _incelt(kap[dil_], cek, goz if p >= kuvvet_k else np.zeros_like(cek),
                                       ~karartma[dil_] & ~kenar[dil_], incelt * max(p, 0.5))
                        kap[dil_] -= sil_
                        incelen += float(sil_.sum())
                if anahtar in kilitli or p < kuvvet_k:
                    continue
                K = depo.kalip_resmi(h, x1 - x0, y1 - y0)
                if K is None:
                    continue
                dil = (slice(y0, y1), slice(x0, x1))
                parca = kap[dil]
                serbest = ~karartma[dil] & ~kenar[dil]
                # yerine koy: kalıbın dolu olup sayfada eksik kalan yerleri (kuvvet kadar) hafifçe doldur
                soluk = parca.mean() < 0.9 * K.mean()           # yalnızca kalıbından AÇIK (solmuş) harf tamamlanır
                ek = alfa * p * np.maximum(0, K - parca) * (serbest & (K > KALIP_DOLU) & yakin[dil]) * soluk
                # kalıp dışına taşan mürekkep (dolmuş göz, harfe değen leke): hafifçe soldur
                Kg = np.asarray(Image.fromarray(K.astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * GOVDE_PAY + 1)),
                                dtype=np.float32)
                tasan = (Kg < 40) & (parca > 0) & serbest
                sil = np.where(tasan, beta * p * parca, 0)
                parca += ek - sil
                eklenen += float(ek.sum()); soldurulan_ic += float(sil.sum())
                onceki = eklenen_kutu.get(anahtar)
                birikmis = onceki[1] + ek if onceki and onceki[2] == dil else ek   # kutu kaydıysa yeni kayıt
                eklenen_kutu[anahtar] = (h, birikmis, dil)
                yerine += 1
                onceki_harf[anahtar] = h
        # harf olmayan izler: kutu dışı, karartma ve kenar dışı, uzun yatay çizgi dışı -> soldur
        murekkep = kap > 0
        cizgi = _yatay_cizgiler(murekkep & ~korunan, int(3 * (depo.adim or 25)))
        leke = murekkep & ~korunan & ~karartma & ~kenar & ~cizgi
        soldurulan = float((kap[leke] * beta).sum())
        toplam_incelen += incelen
        if incelt and toplam_incelen / ilk_murekkep > incelt_fren:
            incelt_acik = False
            incelt = 0                                      # inceltme sınırı: bundan sonra yalnızca tamamla/temizle
            rapor["inceltme_freni"] = f"adım {t + 1}: mürekkebin %{100 * incelt_fren:.0f}'i inceltildi; inceltme durdu"
        if (toplam_soldurulan + soldurulan + soldurulan_ic) / ilk_murekkep > FREN:
            rapor["fren"] = f"adım {t + 1}: toplam mürekkebin %{100 * FREN:.0f}'inden fazlası silinecekti; durduruldu"
            break
        toplam_soldurulan += soldurulan + soldurulan_ic
        kap[leke] *= (1 - beta)
        kap[kap < CH.GURULTU * 0.5] = 0
        np.clip(kap, 0, 255, out=kap)
        son_okuma = okuma_metni
        rapor["adimlar"].append({"adim": t + 1, "harf_kutusu": sum(len(s) for s in satirlar), "yerine_konan": yerine,
                                 "celiski_geri_alinan": celiski, "eklenen_murekkep_piksel": round(eklenen / 255, 1),
                                 "harf_ici_soldurulan_piksel": round(soldurulan_ic / 255, 1),
                                 "inceltilen_piksel": round(incelen / 255, 1),
                                 "oturan_harf": oturdu, "toplam_oturan": len(oturan),
                                 "etkin_risk": round(etkin_risk, 2), "kopru": kopru_say, "kopru_en_uzun": kopru_uzun, "ogrenilen_toplam": len(rapor["ogrenilen"]),
                                 "baglamla_duzelen": sum(k["baglam"] for s_ in satirlar for k in s_),
                                 "leke_soldurulan_piksel": round(soldurulan / 255, 1)})
        if t >= 2 and (eklenen + soldurulan + soldurulan_ic + incelen) / 255 < 0.002 * ilk_murekkep / 255:
            break
    BH.BAGLAM, BH.TABAN = eski_baglam
    if ogren and kalici and rapor["ogrenilen"]:
        depo.kaydet()                                       # öğrenilen yollar sonraki sayfalar için saklanır
    out = (g_arr - (kap - kap0) / 255.0 * (kag - mur)).clip(0, 255).astype(np.uint8)
    sonuc = Image.fromarray(out, "L")
    taban = np.stack([out] * 3, axis=2).astype(np.float32) * 0.6 + 100
    ek = (kap - kap0) > 8
    sil = (kap0 - kap) > 8
    taban[ek] = (40, 90, 255)
    taban[sil] = (235, 50, 50)
    taban[karartma & (kap0 > 128)] = (60, 60, 60)
    harita = Image.fromarray(taban.clip(0, 255).astype(np.uint8), "RGB")
    rapor["son_okuma"] = son_okuma
    rapor["toplam"] = {"eklenen_piksel": int(ek.sum()), "soldurulan_piksel": int(sil.sum()),
                       "degisen_oran": round(float((ek | sil).sum()) / (W * H), 5),
                       "karartma": len(karartma_kutu), "celiski": len(rapor["celiskiler"]),
                       "sure_sn": round(time.time() - t0, 1)}
    return sonuc, harita, rapor


ALT_CIZGI_HARF = 4     # alt çizgi en az bu kadar harf genişliğinde olmalı
ALT_CIZGI_KALIN = 9    # ... ve en fazla bu kadar piksel kalın
ALT_CIZGI_DELTA = 2.0  # alt kenarın doğrudan en fazla sapması (piksel)
ALT_CIZGI_DUZ = 0.65   # sütunların en az bu kadarı o sapmanın içinde kalmalı
ALT_CIZGI_INCE = 7     # alt çizgi en az bu kadar piksel kalın bir banttır
ALT_CIZGI_DOLU = 0.88  # çizgi bandının en az bu kadarı mürekkep olmalı (boşluksuz); altı: kelime, inceltilir
ALT_CIZGI_GUC = 1.0    # her geçişte alt çizginin bu kadarı silinir (lekeden daha sert)


def alt_cizgiler(kap, satirlar, harf_eni):
    """Harflerin ALTINDAKİ düz çizgiler (altı çizili yazı): silinecek piksellerin maskesi.
    Çizgi bir BANT olarak aranır: uzun (en az ALT_CIZGI_HARF harf), birkaç satır kalın, yazı satırının alt kısmında ya
    da altında, ve üstünün büyük kısmı boş kâğıt (harfler çizgiye yalnızca yer yer değer). Çizgiyi dar bir yerden kesip
    aşağı inen harf kuyrukları korunur. Yazının ortasından geçen (üstü çizme) çizgiler alınmaz."""
    m = kap > 110
    H, W = m.shape
    en_az = int(ALT_CIZGI_HARF * harf_eni)
    md = m.copy()
    md[1:] |= m[:-1]
    md[:-1] |= m[1:]                                            # hafif eğik çizgi satır değiştirirken kopmasın
    L = np.zeros_like(m)
    kosular = []                                                # (y, a, b)
    for y in np.nonzero(md.sum(1) >= en_az)[0]:
        d = np.diff(np.concatenate(([0], md[y].astype(np.int8), [0])))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a >= en_az and m[y, a:b].mean() >= 0.6:
                L[y, a:b] = m[y, a:b]
                kosular.append((int(y), int(a), int(b)))
    # alt çizgi ÜST KENARINDAN yakalanır: üstü (2-3 piksel) çoğunlukla boş kâğıt olan uzun koşu = çizginin ilk satırı;
    # oradan aşağı, altı yeniden boşalana kadar inilir. (Kalın yazıda kelimenin kendi satırları da uzun koşudur, ama
    # onların üstü mürekkeptir; kelimenin tepesindeki koşular ise satırın üst kısmındadır, konum şartına takılır.)
    satirda = {}
    for y, a, b in kosular:
        satirda.setdefault(y, []).append((a, b))
    maske = np.zeros_like(m)
    islenen = np.zeros_like(m)
    kelimeler = []                                              # çizgi sanılıp kelime çıkan bölgeler: (y0, y1, x0, x1)
    for y, a, b in kosular:
        if islenen[y, a:b].mean() > 0.5:
            continue
        icinde = next(((u, al) for u, al in satirlar if u <= y < al), None)
        if icinde:
            oran_ = (y - icinde[0]) / max(1, icinde[1] - icinde[0])
            if 0.25 <= oran_ < 0.55:
                continue                                        # harf gövdesi kuşağı: harf tepesi ya da üstü çizme
        sut = np.arange(a, b)
        # çizginin hemen üstü (2-3 piksel) bir miktar boş kâğıt olmalı: kelimenin kendi gövde satırları elenir
        ust_bos = ~m[max(0, y - 2), a:b] & ~m[max(0, y - 3), a:b]
        if ust_bos.mean() < 0.15:
            continue
        # aşağı in
        y1, bitti = y, False
        ga, gb = a, b                                           # çizginin en geniş hâli
        for yy in range(y, min(H, y + ALT_CIZGI_KALIN + 5)):
            ort = [(p, q) for p, q in satirda.get(yy, ()) if min(q, b) - max(p, a) >= 0.5 * (b - a)]
            if not ort:
                y1, bitti = yy - 1, True
                break
            y1 = yy
            if yy - y >= 2:                                     # ilk satırlar üstteki harflere bulaşık olabilir
                ga, gb = min(ga, min(p for p, _ in ort)), max(gb, max(q for _, q in ort))
            alt_bos = ~m[min(H - 1, yy + 2), a:b] & ~m[min(H - 1, yy + 3), a:b]
            if alt_bos.mean() >= 0.4:
                bitti = True
                break
        if not bitti or y1 - y + 1 < ALT_CIZGI_INCE:            # birkaç satırlık düz parça: harf tabanı, çizgi değil
            continue
        # DÜZLÜK (delta): çizginin ALT KENARI uzun bir mesafe boyunca tek bir doğrudan sapmıyorsa cetvelle çekilmiş
        # çizgidir. Harf tabanları harf aralarında kesilir ve oynar: sapma büyük çıkar.
        alt_blok = m[y:min(H, y1 + 4), a:b]
        var = alt_blok[:y1 - y + 1].any(0)
        kenar = alt_blok.shape[0] - 1 - np.argmax(alt_blok[::-1], axis=0)     # her sütunda en alttaki mürekkep satırı
        xs = np.arange(b - a)
        iyi = var.copy()
        for _ in range(3):                                      # sağlam doğru: sapanları atarak yeniden oturt
            if iyi.sum() < 10:
                break
            egim, kesim = np.polyfit(xs[iyi], kenar[iyi], 1)
            sapma = np.abs(kenar - (egim * xs + kesim))
            iyi = var & (sapma <= ALT_CIZGI_DELTA)
        if iyi.sum() < 10 or iyi.mean() < ALT_CIZGI_DUZ:
            continue
        # BOŞLUKSUZLUK: çizginin içi doludur. İçinde yoğun boşluk olan düz parça birleşmiş harflerdir (kelime):
        # silinmez, inceltilmek üzere ayrılır.
        if m[y:y1 + 1, ga:gb].mean() < ALT_CIZGI_DOLU:
            kelimeler.append((max(0, y - max(6, int(1.2 * harf_eni))), min(H, y1 + 3), ga, gb))
            islenen[y:y1 + 1, a:b] = True
            continue
        islenen[y:y1 + 1, a:b] = True
        ustte = m[max(0, y - 2), a:b] & m[max(0, y - 4), a:b]
        altta = m[min(H - 1, y1 + 2), a:b] & m[min(H - 1, y1 + 4), a:b]
        gecis = ustte & altta
        koru = np.zeros_like(gecis)
        d = np.diff(np.concatenate(([0], gecis.astype(np.int8), [0])))
        for p, q in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if q - p <= 10:                                     # dar geçiş: çizgiyi kesen harf kuyruğu
                koru[p:q] = True
        maske[y:y1 + 1, a:b] |= m[y:y1 + 1, a:b] & ~koru[None, :]
    return maske, kelimeler


# ====================================================================== AYRI TUŞLAR (her basış tek geçiş)
class Oturum:
    """CriCroow7'nin adım adım kullanımı. Her işlev TEK GEÇİŞ yapar; tekrar çağrıldıkça biraz daha ilerler.
    Hiçbiri harf okumaz (hızlı): yalnızca satır ve harf kutularına dayanır.
      leke_azalt()   harf kutularının dışındaki izleri biraz soldurur
      tamamla(risk)  kopuk çizgileri, çizginin yönünde köprüler (risk: köprülenen en uzun boşluk)
      netlestir()    kalınlaşmış harfi kendi ana hattına doğru bir kat inceltir
    Orijinal değişmez; sonuc(), harita() ve rapor() her an alınabilir."""

    def __init__(self, img, depo=None, kaynak_bayt=None):
        import belge_harf as BH
        self.BH, self.depo = BH, depo
        self.g, self.aci = CH.duzle(img)
        self.mur, self.kag = CH.seviyeler(self.g)
        self.g_arr = np.asarray(self.g, dtype=np.float32)
        self.kap0 = np.asarray(CH.kapsama(self.g), dtype=np.float32)
        self.kap = self.kap0.copy()
        self.karartma, self.karartma_kutu = _karartmalar(self.kap0)
        kenarsiz = np.asarray(BH.kenarsiz(Image.fromarray(self.kap0.astype(np.uint8))), dtype=np.float32)
        self.kenar = (kenarsiz == 0) & (self.kap0 > 0)
        self.ilk_murekkep = float(self.kap0.sum()) or 1.0
        self.silinen = 0.0
        self.t0 = time.time()
        self.tani_liste, self.tani_izgara = [], {}   # kutu kimlikleri (ilk okuma): merkez yakınlığıyla aranır
        self.kutle_onbellek = {}     # kutu -> (ilk mürekkep kütlesi, ilk çizgi yarıçapı): fazla silmeyi önler
        self.p_onbellek = {}         # kutu -> son doğrulanan harf olasılığı
        self.kilitli = set()         # inceltme harfi bozduğu için durdurulan kutular
        self.bolge = None            # (x0, y0, x1, y1): işlem yalnızca bu dikdörtgende (görüntüdeki koordinat)
        self.gosterildi = False      # düzlenmiş sonuç ekranda mı (bölge koordinatları ona göre çevrilir)
        self.kayit = {"surum": SURUM + " (adım adım)", "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "orijinal_sha256": hashlib.sha256(kaynak_bayt).hexdigest() if kaynak_bayt else None,
                      "orijinal_boyut": list(img.size), "egim_duzeltme_derece": self.aci,
                      "karartma_kutulari": self.karartma_kutu,
                      "uyari": "Tamamlama, leke azaltma ve netleştirme motorun işlemidir. Bu görüntü bir okuma yardımıdır, "
                               "delil değildir. Karartma (sansür) kutularına dokunulmamıştır. Orijinal dosya "
                               "değiştirilmemiştir.",
                      "islemler": []}

    # ---- BÖLGE RİSKLİ TEMİZLE (seçilenin içi ya da dışı)
    def riskli_temizle(self, ic=True):
        """Seçili bölgenin İÇİNİ (ic=True) ya da DIŞINI riskli temizler; yazı mı leke mi olduğunu anlar. Karartma (sansür)
        ve tarama kenarı korunur. Geri alınabilir (adım öncesi kopya uygulamada tutulur)."""
        if not self.bolge:
            return self._yaz("bölge riskli temizle", durdu="Önce 'Bölge seç' aracıyla bir bölge seç")
        x0, y0, x1, y1 = self.bolge
        H, W = self.kap.shape
        hedef = np.zeros((H, W), dtype=bool)
        hedef[y0:y1, x0:x1] = True
        if getattr(self, "bolge_maske", None) is not None:
            hedef = self.bolge_maske.copy()
        if not ic:
            hedef = ~hedef
        hedef &= ~self.karartma & ~self.kenar
        bant_, sb_ = self.BH.satir_olcusu(self.kap)
        sil, tani = self.BH.riskli_temizle(self.kap, hedef, bant_, sb_, depo=getattr(self, "harf_depo", None))
        self.silinen += float(self.kap[sil].sum())
        self.kap[sil] = 0
        return self._yaz("bölge riskli temizle", alan="içi" if ic else "dışı", bolge=[x0, y0, x1 - x0, y1 - y0],
                         hedef_iz=tani["hedef_iz"], yazi_gibi_iz=tani["yazi_gibi"], silinen_iz=tani["silinen_iz"],
                         yazi_orani=tani["yazi_orani"], sonuc=tani["sonuc"])

    # ---- adım geri alma
    def anlik(self):
        """Adımdan önce çalışma durumunun kopyası (geri alma için)."""
        return {"kap": self.kap.copy(), "silinen": self.silinen, "kayit": len(self.kayit["islemler"]),
                "kilitli": set(self.kilitli), "alt_maske": getattr(self, "alt_maske", None)}

    def anliga_don(self, an):
        self.kap[:] = an["kap"]
        self.silinen = an["silinen"]
        del self.kayit["islemler"][an["kayit"]:]
        self.kilitli = set(an["kilitli"])
        if an["alt_maske"] is None and hasattr(self, "alt_maske"):
            del self.alt_maske
        elif an["alt_maske"] is not None:
            self.alt_maske = an["alt_maske"]

    # ---- bölge: işlem yalnızca seçili dikdörtgende
    def bolge_ayarla(self, dikdortgen, poly=None):
        """dikdortgen: ekrandaki görüntünün (x0, y0, x1, y1) koordinatı ya da None (bütün sayfa). Ekranda henüz düzlenmiş
        sonuç yoksa görüntü ORİJİNALDİR; eğik taramada koordinatlar düzleştirme açısıyla çevrilir."""
        self.bolge_maske = None
        if not dikdortgen:
            self.bolge = None
            return
        x0, y0, x1, y1 = dikdortgen
        if not self.gosterildi and abs(self.aci) > 1e-6:
            H, W = self.kap0.shape
            cx, cy = W / 2, H / 2
            th = math.radians(self.aci)
            nok = [(cx + (x - cx) * math.cos(th) + (y - cy) * math.sin(th),
                    cy - (x - cx) * math.sin(th) + (y - cy) * math.cos(th)) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
            x0, x1 = min(p[0] for p in nok), max(p[0] for p in nok)
            y0, y1 = min(p[1] for p in nok), max(p[1] for p in nok)
        H, W = self.kap0.shape
        self.bolge = (max(0, int(x0)), max(0, int(y0)), min(W, int(math.ceil(x1))), min(H, int(math.ceil(y1))))
        if self.bolge[2] - self.bolge[0] < 8 or self.bolge[3] - self.bolge[1] < 8:
            self.bolge = None
        elif poly:                                           # esnek (çok noktalı) bölge: işlem yalnızca çokgenin içinde
            H, W = self.kap0.shape
            nok = [(x, y) for x, y in poly]
            if not self.gosterildi and abs(self.aci) > 1e-6:
                cx, cy = W / 2, H / 2
                th = math.radians(self.aci)
                nok = [(cx + (x - cx) * math.cos(th) + (y - cy) * math.sin(th),
                        cy - (x - cx) * math.sin(th) + (y - cy) * math.cos(th)) for x, y in nok]
            self.bolge_maske = self.BH.poligon_maskesi(nok, W, H)

    def _bolgeli(self, islem, *a, **k):
        if not self.bolge:
            return islem(*a, **k)
        x0, y0, x1, y1 = self.bolge
        eski = self.kap.copy()
        silinen0 = self.silinen
        r = islem(*a, **k)
        dis = np.ones(self.kap.shape, dtype=bool)
        dis[y0:y1, x0:x1] = False
        if getattr(self, "bolge_maske", None) is not None:
            dis = ~self.bolge_maske
        self.kap[dis] = eski[dis]                         # bölge dışına hiçbir şey yazılmaz
        r["bolge"] = [x0, y0, x1 - x0, y1 - y0]
        self.kayit["islemler"][-1] = r
        return r

    def leke_azalt(self, *a, **k):
        return self._bolgeli(self._leke_azalt, *a, **k)

    def tamamla(self, *a, **k):
        return self._bolgeli(self._tamamla, *a, **k)

    def netlestir(self, *a, **k):
        return self._bolgeli(self._netlestir, *a, **k)

    # ---- harf kutuları (okuma yok)
    def _kutular(self):
        """-> (işlenecek kutular, bütün kutular, harf adımı, kapsama resmi). Kutu: (x0, x1, y0, y1, ust, alt)"""
        kap_img = Image.fromarray(np.clip(self.kap, 0, 255).astype(np.uint8))
        kap_t, out, adim = self._kutular_kap(kap_img)
        boy = sorted(k[3] - k[2] for k in out)
        tipik = boy[len(boy) // 2] if boy else 0
        return ([k for k in out if k[1] - k[0] >= 3 and k[3] - k[2] >= 3 and k[3] - k[2] <= 1.3 * tipik], out, adim,
                kap_t)

    def _kutular_kap(self, kap_img):
        BH = self.BH
        kap_t = BH.kenarsiz(kap_img)
        satirlar = BH.satirlar_belge(kap_t)
        adim = BH._izgara_mi(kap_t, satirlar, bilinen=self.depo.adim if self.depo else None)
        out = []
        for ust, alt in satirlar:
            if adim:
                for h in BH.izgara_hucreleri(kap_t, ust, alt, adim):
                    if h[2]:
                        k = BH._hucre_kutusu(kap_t, h, ust, alt)
                        if k:
                            out.append((k[0], k[1], k[2], k[3], ust, alt))
            else:
                out += [(p[0], p[1], p[2], p[3], ust, alt) for p in (CH.parcalar(kap_t, 0, kap_t.width, ust, alt) or [])]
        return kap_t, out, adim

    def _serbest(self, dil):
        return ~self.karartma[dil] & ~self.kenar[dil]

    def _yaz(self, ad, **bilgi):
        bilgi = {"islem": ad, "sira": len(self.kayit["islemler"]) + 1, **bilgi}
        self.kayit["islemler"].append(bilgi)
        return bilgi

    # ---- LEKE AZALT
    def _leke_azalt(self, beta=BETA, alt_cizgi=True, risk=0.5):
        """Harf kutularının dışındaki izleri beta oranında soldurur (karartma ve kenar korunur).
        Harflerin altındaki düz çizgiler (altı çizili yazı) daha sert silinir."""
        # 1. ALT ÇİZGİ: önce silinir, çünkü harf kutularını ve satırları bozar
        alt_sil = kelime_ince = 0.0
        if alt_cizgi:
            kap_img = Image.fromarray(np.clip(self.kap, 0, 255).astype(np.uint8))
            kap_t0 = self.BH.kenarsiz(kap_img)
            satir0 = self.BH.satirlar_belge(kap_t0)
            adim0 = self.BH._izgara_mi(kap_t0, satir0, bilinen=self.depo.adim if self.depo else None)
            if satir0:
                boy0 = 0.55 * sorted(a - u for u, a in satir0)[len(satir0) // 2]
                adim0 = min(adim0, boy0) if adim0 else boy0       # harf adımı katına takılmış olabilir
                yeni, kelime_bolge = alt_cizgiler(self.kap, satir0, adim0)
                yeni &= ~self.karartma & ~self.kenar
                for ky0, ky1, kx0, kx1 in kelime_bolge:         # düz ama boşluklu: kelime -> silme, bir kat incelt
                    dil = (slice(ky0, ky1), slice(kx0, kx1))
                    mk = self.kap[dil] > 110
                    if mk.sum() < 8:
                        continue
                    cek = np.asarray(Image.fromarray(self.BH.ana_hat(mk).astype(np.uint8) * 255).filter(
                        ImageFilter.MaxFilter(2 * HAT_KALIN + 1)), dtype=bool)
                    sil_k = _incelt(self.kap[dil], cek, np.zeros_like(cek), self._serbest(dil), INCELT)
                    self.kap[dil] -= sil_k
                    kelime_ince += float(sil_k.sum())
                self.alt_maske = yeni | getattr(self, "alt_maske", np.zeros_like(yeni))   # bulunan çizgi hatırlanır
                cz = self.alt_maske & (self.kap > 0)
                alt_sil = float((self.kap[cz] * ALT_CIZGI_GUC).sum())
                self.kap[cz] *= (1 - ALT_CIZGI_GUC)
                self.kap[self.kap < CH.GURULTU * 0.5] = 0
                self.silinen += alt_sil
        # 1b. ELLE SİLİNENLERDEN ÖĞRENİLEN LEKE KURALI: kullanıcının fırçayla sildiği izlere (boyut, doluluk, yalnızlık,
        # satır içi yükseklik) benzeyen izler, harf kutularının koruması altında olsa bile silinir
        ogr_say = bolge_say = 0
        ogr = getattr(self, "duzenleme", None)
        if ogr:
            kural = self.BH.leke_kurali(ogr.get("sil", [])[-80:], gevsek=max(0.0, min(1.0, (risk - 0.5) * 2)))   # normal (risk 0.5): sıkı kural; riskli (1.0): esnek silme
            if kural:
                bant_, sb_ = self.BH.satir_olcusu(self.kap)
                bul, et = self.BH.leke_bul(self.kap, kural, bant_, sb_, yasak=self.karartma | self.kenar,
                                           depo=getattr(self, "harf_depo", None))
                for x0_, x1_, y0_, y1_, id_ in bul:
                    mk = et[y0_:y1_, x0_:x1_] == id_
                    alt = self.kap[y0_:y1_, x0_:x1_]
                    self.silinen += float(alt[mk].sum())
                    alt[mk] = 0
                    ogr_say += 1
            # 1b2. BÜYÜK FIRÇA İLE TEMİZLENEN BÖLGELERE BENZEYEN BÖLGELER (yalnızca riskli: risk >= 0.75): karodaki harfe
            # benzemeyen izler silinir, harfe benzeyenler korunur
            if risk >= 0.75:
                bk = self.BH.bolge_kurali(ogr.get("bolge", [])[-40:])
                if bk:
                    _, sb2_ = self.BH.satir_olcusu(self.kap)
                    karolar, plan, et2 = self.BH.bolge_bul(self.kap, bk, sb2_, depo=getattr(self, "harf_depo", None),
                                                           yasak=self.karartma | self.kenar)
                    for (tx, ty), ids in plan.items():
                        T = self.BH.bolge_karosu(sb2_)
                        sub = self.kap[ty:ty + T, tx:tx + T]
                        lab = et2[ty:ty + T, tx:tx + T]
                        sil_mk = np.isin(lab, ids)
                        self.silinen += float(sub[sil_mk].sum())
                        sub[sil_mk] = 0
                        bolge_say += 1
        # 1b3. 'ALT ÇİZGİ' diye öğretilen yatay çizgilere benzeyen izler silinir
        cizgi_say = 0
        if ogr:
            ck = self.BH.cizgi_kurali(ogr.get("cizgi", [])[-40:])
            if ck:
                _, sb3_ = self.BH.satir_olcusu(self.kap)
                bul3, et3 = self.BH.cizgi_bul(self.kap, ck, sb3_, yasak=self.karartma | self.kenar)
                for x0_, x1_, y0_, y1_, id_ in bul3:
                    mk = et3[y0_:y1_, x0_:x1_] == id_
                    alt3 = self.kap[y0_:y1_, x0_:x1_]
                    self.silinen += float(alt3[mk].sum())
                    alt3[mk] = 0
                    cizgi_say += 1
        # 1c. SİYAH LEKE (yüzdesel dolu, koyu, küçük): referans harfe benzerliğe göre incelt / sil / geç (risk ölçekler)
        sil_n = ince_n = gec_n = 0
        bant_, sb_ = self.BH.satir_olcusu(self.kap)
        eylem, et_, tani_ = self.BH.siyah_leke_tara(self.kap, bant_, sb_, risk=risk, yasak=self.karartma | self.kenar,
                                                         depo=getattr(self, "harf_depo", None))
        for x0_, x1_, y0_, y1_, id_, benz_, tur_, guc_ in eylem:
            mk = et_[y0_:y1_, x0_:x1_] == id_
            alt = self.kap[y0_:y1_, x0_:x1_]
            if tur_ == "sil":
                self.silinen += float(alt[mk].sum()) * guc_
                alt[mk] *= (1 - guc_)
                sil_n += 1
            elif tur_ == "incelt":                                  # dış kabuk: bir piksel soyulur
                ic = np.asarray(Image.fromarray(mk.astype(np.uint8) * 255).filter(ImageFilter.MinFilter(3)), dtype=bool)
                halka = mk & ~ic
                self.silinen += float(alt[halka].sum()) * guc_
                alt[halka] *= (1 - guc_)
                ince_n += 1
            else:
                gec_n += 1
        _, hepsi, adim, _ = self._kutular()
        H, W = self.kap.shape
        korunan = np.zeros((H, W), dtype=bool)
        for x0, x1, y0, y1, ust, alt in hepsi:
            korunan[max(0, y0 - PAY):y1 + PAY, max(0, x0 - PAY):x1 + PAY] = True
        # yazı satırının içi (ilk harften son harfe) tümüyle korunur: nokta, virgül, kesme lekedir sanılmasın
        satir_uc = {}
        for x0, x1, y0, y1, ust, alt in hepsi:
            a, b = satir_uc.get((ust, alt), (x0, x1))
            satir_uc[(ust, alt)] = (min(a, x0), max(b, x1))
        for (ust, alt), (a, b) in satir_uc.items():
            korunan[ust:alt, max(0, a - 2 * PAY):b + int(1.5 * (adim or 25))] = True
        murekkep = self.kap > 0
        cizgi = _yatay_cizgiler(murekkep & ~korunan, int(3 * (adim or 25)))
        leke = murekkep & ~korunan & ~self.karartma & ~self.kenar & ~cizgi
        sil = float((self.kap[leke] * beta).sum())
        if (self.silinen + sil) / self.ilk_murekkep > FREN:
            return self._yaz("leke azalt", durdu=f"toplam mürekkebin %{100 * FREN:.0f}'inden fazlası silinecekti; yapılmadı")
        self.silinen += sil
        self.kap[leke] *= (1 - beta)
        self.kap[self.kap < CH.GURULTU * 0.5] = 0
        return self._yaz("leke azalt", ogrenilen_leke_silinen=ogr_say, ogrenilen_bolge_temizlenen=bolge_say, ogrenilen_cizgi_silinen=cizgi_say,
                         siyah_leke_silinen=sil_n, siyah_leke_inceltilen=ince_n,
                         siyah_leke_supheli_gecilen=gec_n, toz_silinen=tani_["toz_silinen"],
                         ogrenilen_ornek=len((getattr(self, "duzenleme", None) or {}).get("sil", [])),
                         elenen_tani=" ".join(f"{k.replace('elenen_', '')}={v}" for k, v in tani_.items()
                                              if k.startswith("elenen_") and v),
                         harf_kutusu=len(hepsi),
                         alt_cizgi_silinen_piksel=round(alt_sil / 255, 1),
                         kelime_sayilip_inceltilen_piksel=round(kelime_ince / 255, 1),
                         soldurulan_piksel=round(sil / 255, 1),
                         kalan_leke_piksel=int((self.kap[leke] > 0).sum()))

    # ---- TAMAMLA (kopuk çizgi)
    def _tamamla(self, risk=0.3):
        """Kopuk çizgileri köprüler: çizgi düz geliyor ve boşluğun ardında mürekkep sürüyorsa boşluk doldurulur."""
        kutular, _, _, _ = self._kutular()
        en_uzun = int(round(KOPRU_TABAN + KOPRU_RISK * max(0.0, min(1.0, risk))))
        ogr_bosluk = None
        ogr = getattr(self, "duzenleme", None)
        if ogr:                                                    # elle çizilen köprülerden öğrenilen boşluk uzunluğu
            kk = self.BH.kopru_kurali(ogr.get("ciz", [])[-80:])
            if kk:
                _, sb_ = self.BH.satir_olcusu(self.kap)
                ogr_bosluk = int(min(25, round(kk["bosluk"] * sb_)))
                en_uzun = max(en_uzun, ogr_bosluk)
        say = 0
        ek_top = 0.0
        for x0, x1, y0, y1, _, _ in kutular:
            dil = (slice(y0, y1), slice(x0, x1))
            ek, n = kopru(self.kap[dil], self._serbest(dil), en_uzun)
            say += n
            ek_top += float(ek.sum())
        np.clip(self.kap, 0, 255, out=self.kap)
        return self._yaz("tamamla", risk=round(risk, 2), ogrenilen_bosluk=ogr_bosluk, en_uzun_bosluk=en_uzun, harf_kutusu=len(kutular), kopru=say,
                         eklenen_piksel=round(ek_top / 255, 1))

    # ---- kutu kimlikleri (adımlar arasında sabit): merkez yakınlığıyla bulunur
    def _tani_al(self, x0, x1, y0, y1, kap_t, ust, alt):
        BH = self.BH
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        bx, by = int(cx // 10), int(cy // 10)
        en = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for e in self.tani_izgara.get((bx + dx, by + dy), ()):
                    d = abs(e["cx"] - cx) + abs(e["cy"] - cy)
                    if d <= 10 and (en is None or d < en[0]):
                        en = (d, e)
        if en:
            return en[1]
        try:
            ad = BH.kutu_okuma(kap_t, [(x0, x1, y0, y1, ust, alt)], self.depo, None)[0]
        except Exception:  # noqa: BLE001
            ad = []
        e = {"id": len(self.tani_liste), "cx": cx, "cy": cy, "ad": ad}
        self.tani_liste.append(e)
        self.tani_izgara.setdefault((bx, by), []).append(e)
        return e

    def tani_onbellegi(self):
        """Bütün harf kutularını (kirli, ilk hâliyle) okuyup kimliklerini saklar. Genel inceltmeden ÖNCE çağrılır."""
        kutular, _, _, kap_t = self._kutular()
        for x0, x1, y0, y1, ust, alt in kutular:
            self._tani_al(x0, x1, y0, y1, kap_t, ust, alt)
        return len(self.tani_liste)

    def netlestir_zincir(self, genel=10, yol=3):
        """Önce GENEL inceltme (genel adım), üstüne harfin YOLUNA göre inceltme (yol adım). Harfler kirli hâliyle
        okunur; genel adımlar kalın kütleyi indirir, yol bunun üstünde şekli oturtur ve doğrular."""
        n = self.tani_onbellegi()
        r = None
        for _ in range(max(0, genel)):
            r = self.netlestir(varyant=False)
        reddedilen = yola = 0
        for _ in range(max(0, yol)):
            r = self.netlestir(varyant=True)
            reddedilen += r.get("harfi_bozdugu_icin_geri_alinan", 0) or 0
            yola += r.get("varyanta_gore", 0) or 0
        r = dict(r or {})
        r.update(zincir=f"genel x{genel} + yol x{yol}", tanindi=n, yola_gore_toplam=yola, geri_alinan_toplam=reddedilen)
        return r

    # ---- NETLEŞTİR (incelt)
    def _netlestir(self, oran=INCELT, fazla="iat", fazla_kat=1.8, varyant=False):
        """Kalınlaşmış harfi kendi ana hattına doğru bir kat inceltir.
        - Sayfanın tipik çizgi kalınlığından kalın kutu daha çok, ince kutu daha az incelir.
        - fazla: her zaman kalın basılan harfler (varsayılan i, a, t). Kutunun ana hattı depodaki bu harflerden birine
          benziyorsa o kutu fazla_kat kadar daha çok ve daha ince çekirdeğe doğru inceltilir (depo gerekir).
        - varyant: harfi (ana hattından hızlıca) tanır, KENDİ varyasyon seviyesini ölçer (kirli / orta / nizami) ve bir üst
          (daha temiz) seviyenin şablonuna doğru dönüştürür. Harfin şablonu yoksa genel inceltmeye döner."""
        BH = self.BH
        kutular, _, _, kap_t = self._kutular()
        hazir = []
        for x0, x1, y0, y1, ust, alt in kutular:
            m = self.kap[y0:y1, x0:x1] > 110
            if m.sum() < 8:
                continue
            hat = BH.ana_hat(m)
            uzun = int(hat.sum())
            if uzun:
                hazir.append(((x0, x1, y0, y1, ust, alt), hat, m.sum() / uzun))
        if not hazir:
            return self._yaz("netleştir", harf_kutusu=len(kutular), inceltilen_kutu=0)
        kal = sorted(h[2] for h in hazir)
        tipik = kal[len(kal) // 2]
        fazla = (fazla or "").lower()
        tanir = bool(fazla and self.depo is not None and self.depo.hat)
        ince_top, islenen, fazla_say, varyantla, reddedilen = 0.0, 0, 0, 0, 0
        seviyeler = {}
        for (x0, x1, y0, y1, ust, alt), hat, kalinlik in hazir:
            ozel, h, pg = False, None, 0.0
            if tanir:
                ph = self.depo.hat_olasilik(BH.hat_haritasi(kap_t, (x0, x1, y0, y1), ust, alt))
                if ph:
                    h = max(ph, key=ph.get)
                    pg = ph[h]
                    ozel = h.lower() in (fazla or "") and pg >= 0.4
            if varyant:                                                 # harfi TAM tanı (palet + ana hat), yolla doğrula
                e_ = self._tani_al(x0, x1, y0, y1, kap_t, ust, alt)       # kimlik ilk (kirli) okumadan; kutu kaysa da bulunur
                anahtar_, adaylar_ = e_["id"], e_["ad"]
                dil = (slice(y0, y1), slice(x0, x1))
                parca = self.kap[dil]
                sec = BH.yol_en_iyi(parca, adaylar_, self.depo, self.depo.aile) if adaylar_ else None
                r = None
                if sec is not None:                                    # harfin YOLU: oturt, bandın dışını sil
                    if anahtar_ not in self.kutle_onbellek:            # kutunun ilk kütlesi ve çizgi yarıçapı (kütle bekçisi için)
                        m_ = parca > 110
                        k_ = int(BH.ana_hat(m_).sum()) if m_.sum() >= 6 else 0
                        self.kutle_onbellek[anahtar_] = (float(parca.sum()),
                                                         (m_.sum() / max(1, k_) / 2.0) if k_ else 1.0)
                    r = BH.yol_restore(parca.copy(), sec[0], self.depo, alt - ust, aile=self.depo.aile,
                                       oran=YOL_ORAN, hizali=sec[1:], ilk=self.kutle_onbellek[anahtar_])
                if r is not None and anahtar_ in self.kilitli:
                    r = None                                           # daha önce harfi bozduğu için kilitlendi
                if r is not None:
                    yeni, b = r
                    yeni = np.where(self._serbest(dil), yeni, parca)
                    # KARŞILAŞTIR: işlemden sonra harf hâlâ o harf mı? Tanınmaz olduysa adım geri alınır, kutu kilitlenir.
                    h_sec = sec[0]
                    if anahtar_ not in self.p_onbellek:
                        self.p_onbellek[anahtar_] = dict(BH.parca_okuma(parca, self.depo, ust - y0, alt - y0)).get(h_sec, 0.0)
                    p_ref = self.p_onbellek[anahtar_]
                    p_yeni = dict(BH.parca_okuma(yeni, self.depo, ust - y0, alt - y0)).get(h_sec, 0.0)
                    if p_yeni < DOGRULA_ORAN * p_ref and p_yeni < DOGRULA_TAVAN:
                        self.kilitli.add(anahtar_)
                        reddedilen += 1
                        continue
                    self.p_onbellek[anahtar_] = p_yeni
                    sil_v = float(np.clip(parca - yeni, 0, None).sum())
                    if (self.silinen + sil_v) / self.ilk_murekkep > INCELT_FREN + FREN:
                        return self._yaz("netleştir", durdu="inceltme sınırına gelindi; durdu", inceltilen_kutu=islenen)
                    parca[:] = yeni
                    self.silinen += sil_v
                    ince_top += sil_v
                    islenen += 1
                    varyantla += 1
                    seviyeler[b["seviye"]] = seviyeler.get(b["seviye"], 0) + 1
                    continue
            if kalinlik <= 2 * HAT_KALIN + 1.5 and not ozel:           # çizgi zaten ince
                continue
            kat = max(0.6, min(1.6, kalinlik / tipik)) * (fazla_kat if ozel else 1.0)
            yari = max(1, HAT_KALIN - 1) if ozel else HAT_KALIN
            dil = (slice(y0, y1), slice(x0, x1))
            parca = self.kap[dil]
            cek = np.asarray(Image.fromarray(hat.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(2 * yari + 1)),
                             dtype=bool)
            sil = _incelt(parca, cek, np.zeros_like(cek), self._serbest(dil), min(0.9, oran * kat))
            if (self.silinen + float(sil.sum())) / self.ilk_murekkep > INCELT_FREN + FREN:
                return self._yaz("netleştir", durdu="inceltme sınırına gelindi; durdu", inceltilen_kutu=islenen)
            parca -= sil
            self.silinen += float(sil.sum())
            ince_top += float(sil.sum())
            islenen += 1
            fazla_say += ozel
        self.kap[self.kap < CH.GURULTU * 0.5] = 0
        return self._yaz("netleştir", harf_kutusu=len(kutular), inceltilen_kutu=islenen,
                         fazla_inceltilen=f"{fazla_say} ({fazla})" if tanir else "yok (depoda ana hat örneği yok)",
                         varyanta_gore=varyantla, varyant_seviyeleri=seviyeler, harfi_bozdugu_icin_geri_alinan=reddedilen,
                         tipik_kalinlik=round(float(tipik), 1), inceltilen_piksel=round(ince_top / 255, 1))

    # ---- çıktılar
    def sonuc(self):
        self.gosterildi = True
        out = (self.g_arr - (self.kap - self.kap0) / 255.0 * (self.kag - self.mur)).clip(0, 255).astype(np.uint8)
        return Image.fromarray(out, "L")

    def harita(self):
        out = np.asarray(self.sonuc(), dtype=np.float32)
        taban = np.stack([out] * 3, axis=2) * 0.6 + 100
        taban[(self.kap - self.kap0) > 8] = (40, 90, 255)
        taban[(self.kap0 - self.kap) > 8] = (235, 50, 50)
        taban[self.karartma & (self.kap0 > 128)] = (60, 60, 60)
        return Image.fromarray(taban.clip(0, 255).astype(np.uint8), "RGB")

    def rapor(self):
        ek, sil = (self.kap - self.kap0) > 8, (self.kap0 - self.kap) > 8
        r = dict(self.kayit)
        r["toplam"] = {"eklenen_piksel": int(ek.sum()), "soldurulan_piksel": int(sil.sum()),
                       "degisen_oran": round(float((ek | sil).sum()) / ek.size, 5),
                       "karartma": len(self.karartma_kutu), "islem_sayisi": len(self.kayit["islemler"])}
        return r


def rapor_yaz(rapor, yol):
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Kullanım: python cricroow.py sayfa.png  -> sayfa_cricroow.png, sayfa_cricroow_harita.png, "
                 "sayfa_cricroow_rapor.json")
    yol = sys.argv[1]
    with open(yol, "rb") as f:
        bayt = f.read()
    import io
    s, h, r = onar(Image.open(io.BytesIO(bayt)), kaynak_bayt=bayt,
                   ilerleme=lambda o, m: print(f"  {m}", file=sys.stderr))
    on = os.path.splitext(yol)[0] + "_cricroow"
    s.save(on + ".png"); h.save(on + "_harita.png"); rapor_yaz(r, on + "_rapor.json")
    print(json.dumps(r["toplam"], ensure_ascii=False))
