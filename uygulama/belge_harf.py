#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
belge_harf.py - Belgenin KENDİ harflerinden öğrenen ve olasılıkla okuyan Croow okuyucusu.

  1. Belgeden öğretme: sayfa + o sayfanın doğru metni. Her harf kutusu kendi harfiyle eşlenir (satırlar ve harfler
     dinamik hizalamayla; birleşik, bölünmüş, eksik ya da fazla kutular hizalamayı bozmaz).
  2. Sanal silik harfler: öğrenilen her GERÇEK harften silikleşmiş, incelmiş, delinmiş, kırılmış SANAL kopyalar
     üretilir ve AYRI bir depoda tutulur. Motor gerçek ile sanal arasındaki farkı bilir: tanıma iki depodan yapılır,
     ama tamamlama yalnızca GERÇEK harfin kalıbıyla yapılır.
  3. Olasılık sıralaması: her kutu için gerçek, sanal ve genel paletten adaylar, olasılıklarıyla sıralanır.
  4. Yakından bakma: en iyi aday zayıfsa kutu 2 kat büyütülüp piksel piksel yeniden ölçülür; iki bakış birleştirilir.
  5. Bağlam ("bu buraya gelir mi, bu cümlede"): aday harflerden kurulan kelimeler öğretilen metinlerin kelime ve
     kelime-çifti sıklıklarıyla tartılır; cümleye uyan seçilir.

Depo dosyaları (~/.croow/): belge_harf.crw (gerçek), belge_harf_sanal.crw (sanal), belge_kelime.crw (bağlam).
"""
import math
import os
import random
import re

import crw_harf as CH

T_OLASILIK = 6.0        # mesafe -> olasılık sıcaklığı (küçük: daha keskin)
ZAYIF = 0.6             # en iyi adayın olasılığı bundan küçükse yakından bakılır
SANAL_KOPYA = 6         # her gerçek harften üretilen sanal silik kopya
BAGLAM = 0.5            # kelime sıklığının harf olasılığına göre ağırlığı
TABAN = 0.003           # aday listesinde olmayan harfin olasılığı
CAPA = 0.8              # olasılığı bundan büyük harf ÇAPAdır: bağlam onu değiştiremez
CAPA_KAT = 3.0          # ... ya da ikinci adayından bu kat üstün olan harf de çapadır
TEMIZ_KELIME = 2        # görüntüden okunan kelime sözlükte en az bu kadar geçiyorsa TEMİZdir: bağlam değiştiremez
CAPA_TABAN = 1e-5       # çapaya uymayan kelimenin o harfteki olasılığı (pratikte: aday değil)
YOL = 32                                # harf yolu (ortak iskelet) çözünürlüğü
SEVIYELER = ("nizami", "orta", "kirli")   # aynı harfin varyasyonları: temiz, orta kirli, kirli
VARYANT_ESIK = (0.12, 0.18)             # çizgi kalınlığı / satır boyu: bunun altı nizami, arası orta, üstü kirli
KALIP = 24              # harf kalıbının çözünürlüğü (orijinal referans görüntü)


def _yol(ad):
    os.makedirs(CH.VERI, exist_ok=True)
    return os.path.join(CH.VERI, ad)


class Depo:
    """Belge harf deposu: gerçek harfler, sanal (silik) harfler, kelime bağlamı."""

    def __init__(self):
        import crw_json as CJ
        self.gercek = CH.Palet(_yol("belge_harf.json"))
        self.sanal = CH.Palet(_yol("belge_harf_sanal.json"))
        v = CJ.oku(_yol("belge_kelime.json"), {}) or {}
        self.kelime = dict(v.get("kelime", {}))
        self.cift = dict(v.get("cift", {}))
        self.metin_sayisi = v.get("metin", 0)
        self.adim = v.get("adim")               # öğretilen daktilonun harf adımı (300 DPI piksel)
        self.kalip = {h: [n, list(d)] for h, (n, d) in v.get("kalip", {}).items()}   # harf -> [örnek, 24x24 ortalama]
        self.hat = {h: [[n, list(d)] for n, d in l] for h, l in v.get("hat", {}).items()}   # harf -> ana hat örnekleri
        self.gen = {h: [n, g] for h, (n, g) in v.get("gen", {}).items()}   # harf -> [örnek, mürekkep genişliği / satır boyu]
        self._hat_m = None
        # varyasyonlar: aile (yazı tipi / belge türü) -> harf -> seviye -> [örnek, 24x24 ortalama şablon, ort. kalınlık]
        self.varyant = {a: {h: {sv: [n, list(d), k] for sv, (n, d, k) in sl.items()} for h, sl in hl.items()}
                        for a, hl in v.get("varyant", {}).items()}
        # harf yolları: aile -> harf -> [örnek, YOLxYOL yumuşak iskelet toplamı (0..100)]; ortak iskelet = ortanca yol
        self.yol = {a: {h: [n, list(d)] for h, (n, d) in hl.items()} for a, hl in v.get("yol", {}).items()}
        self._yol_onb = {}
        self.aile = "genel"                                             # şu an öğretilen yazı ailesi (arayüz belirler)
        self.kutu_duz = [list(x) for x in v.get("kutu_duz", [])]       # [dx0, dx1, dy0, dy1] (satır boyuna oranla)
        self.kutu_olay = dict(v.get("kutu_olay", {}))                  # silinen / eklenen / bölünen / birleşen sayıları
        # elle düzenleme (fırça) örnekleri: {"sil": [özellik sözlükleri], "ciz": [...]} — Croow'un leke azalt / tamamla
        # adımları bunlardan öğrenir
        self.duzenleme = {k: list(l) for k, l in v.get("duzenleme", {}).items()}
        self.duzenleme.setdefault("sil", [])
        self.duzenleme.setdefault("ciz", [])
        self.duzenleme.setdefault("bolge", [])                          # büyük fırçayla temizlenen bölgelerin özellikleri
        self.duzenleme.setdefault("leke_sablon", [])                     # elle silinen izlerin 24x24 şablonları (olumsuz örnek)
        self.duzenleme.setdefault("korunan_sablon", [])                  # 'Metin / karartma / damga / imza' diye öğretilen izlerin şablonları
        self.duzenleme.setdefault("sinif", [])                           # etiketle öğretilen izlerin özellikleri: {'sinif': ad, ...}
        self.duzenleme.setdefault("cizgi", [])                           # 'Alt çizgi' diye öğretilen izlerin özellikleri
        self.duzenleme.setdefault("ozel", [])                            # kullanıcının AÇTIĞI kategoriler: {'ad', 'eylem', 'alan', 'sab'}

    def bos(self):
        return not self.gercek.k

    def kelime_toplam(self):
        if getattr(self, "_top", None) is None or self._top[0] != len(self.kelime):
            self._top = (len(self.kelime), sum(self.kelime.values()) or 1)
        return self._top[1]

    def uzunlukta(self, n):
        """n harfli kelimeler (bir kez dizinlenir)."""
        d = getattr(self, "_uz", None)
        if d is None or d[0] != len(self.kelime):
            dizin = {}
            for w in self.kelime:
                dizin.setdefault(len(w), []).append(w)
            self._uz = d = (len(self.kelime), dizin)
        return d[1].get(n, ())

    def kaydet(self):
        import crw_json as CJ
        self.gercek.kaydet()
        self.sanal.kaydet()
        CJ.yaz(_yol("belge_kelime.json"), {"surum": 1, "kelime": self.kelime, "cift": self.cift,
                                          "metin": self.metin_sayisi, "adim": self.adim,
                                          "kalip": {h: [n, [round(x) for x in d]] for h, (n, d) in self.kalip.items()},
                                          "gen": {h: [n, round(float(g), 4)] for h, (n, g) in self.gen.items()},
                                          "kutu_duz": [[round(float(x), 4) for x in r] for r in self.kutu_duz[-400:]],
                                          "kutu_olay": self.kutu_olay,
                                          "duzenleme": {k: l[-(120 if k in ("leke_sablon", "korunan_sablon", "ozel") else 300):] for k, l in self.duzenleme.items()},
                                          "yol": {a: {h: [n, [int(round(x)) for x in d]] for h, (n, d) in hl.items()}
                                                  for a, hl in self.yol.items()},
                                          "varyant": {a: {h: {sv: [n, [round(x) for x in d], round(float(k), 4)]
                                                              for sv, (n, d, k) in sl.items()}
                                                          for h, sl in hl.items()} for a, hl in self.varyant.items()},
                                          "hat": {h: [[n, [round(float(x), 3) for x in d]] for n, d in l]
                                                  for h, l in self.hat.items()}})

    def anlik_al(self, harfler, sozcukler=()):
        """Verilen harflerin (ve kelimelerin) bütün öğrenilmiş verisinin kopyası: öğretme GERİ ALINABİLSİN diye.
        Palet kökleri, sanal kopyalar, kalıp, ana hat, genişlik, varyasyonlar, yollar ve kelime sayıları."""
        import copy
        h = set(harfler)
        return {"harfler": h,
                "gercek": [copy.deepcopy(r) for r in self.gercek.k if r[0] in h],
                "sanal": [copy.deepcopy(r) for r in self.sanal.k if r[0] in h],
                "kalip": {x: copy.deepcopy(self.kalip[x]) for x in h if x in self.kalip},
                "hat": {x: copy.deepcopy(self.hat[x]) for x in h if x in self.hat},
                "gen": {x: copy.deepcopy(self.gen[x]) for x in h if x in self.gen},
                "varyant": {a: {x: copy.deepcopy(hl[x]) for x in h if x in hl} for a, hl in self.varyant.items()},
                "yol": {a: {x: copy.deepcopy(hl[x]) for x in h if x in hl} for a, hl in self.yol.items()},
                "kelime": {w: self.kelime.get(w) for w in sozcukler}}

    def geri_yukle(self, an):
        """anlik_al ile alınmış görüntüye döner (o harflerin sonradan öğrenilenleri silinir)."""
        h = an["harfler"]
        self.gercek.k[:] = [r for r in self.gercek.k if r[0] not in h] + an["gercek"]
        self.sanal.k[:] = [r for r in self.sanal.k if r[0] not in h] + an["sanal"]
        for sozluk, anahtar in ((self.kalip, "kalip"), (self.hat, "hat"), (self.gen, "gen")):
            for x in h:
                sozluk.pop(x, None)
            sozluk.update(an[anahtar])
        for tablo, anahtar in ((self.varyant, "varyant"), (self.yol, "yol")):
            for a, hl in tablo.items():
                for x in h:
                    hl.pop(x, None)
            for a, d in an[anahtar].items():
                tablo.setdefault(a, {}).update(d)
        for w, v in an["kelime"].items():
            if v is None:
                self.kelime.pop(w, None)
            else:
                self.kelime[w] = v
        self._hat_m = None
        self._yol_onb = {}
        self.kaydet()

    def kutu_duzelt_kaydet(self, ham, son):
        """Kullanıcı Croow'un kutusunu elle düzeltti: ham (Croow'un bulduğu) -> son (kullanıcının çizdiği).
        Fark, satır boyuna oranlanıp kaydedilir; yeterince tutarlıysa sonraki kutulara uygulanır."""
        sb = max(1, ham[5] - ham[4])
        d = [(son[0] - ham[0]) / sb, (son[1] - ham[1]) / sb, (son[2] - ham[2]) / sb, (son[3] - ham[3]) / sb]
        self.kutu_duz.append(d)                     # sıfır fark da kayıttır: "Croow'un kutusu doğruydu"

    def kutu_olayi(self, ad):
        self.kutu_olay[ad] = self.kutu_olay.get(ad, 0) + 1

    def kutu_ayari(self, en_az=3):
        """Kullanıcının düzeltmelerinden öğrenilen SİSTEMATİK kutu kayması: [sol, sağ, üst, alt] (satır boyuna oranla)
        ya da None. Her yön için ortanca alınır; düzeltmeler tutarsızsa (yön yönden farklı) o yön 0 kalır."""
        if len(self.kutu_duz) < en_az:
            return None
        import numpy as np
        a = np.asarray(self.kutu_duz[-200:], dtype=np.float32)
        out = []
        for i in range(4):
            med = float(np.median(a[:, i]))
            ayni_yon = float((np.sign(a[:, i]) == np.sign(med)).mean()) if abs(med) > 1e-6 else 0.0
            out.append(med if abs(med) >= 0.03 and ayni_yon >= 0.7 else 0.0)
        return out if any(out) else None

    def varyant_ekle(self, harf, kap, kutu, seviye=None, aile=None):
        """Harfin bir örneğini varyasyon seviyesine ekler (seviye yoksa çizgi kalınlığından bulunur). -> seviye"""
        import numpy as np
        from PIL import Image
        x0, x1, y0, y1, ust, alt = kutu
        parca = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32)
        kal = cizgi_kalinligi(parca, max(1, alt - ust))
        seviye = seviye or seviye_bul(kal)
        sab = np.asarray(Image.fromarray(parca.clip(0, 255).astype(np.uint8)).resize((KALIP, KALIP), Image.Resampling.BOX),
                         dtype=np.float32).ravel()
        self.yol_ekle(harf, parca, aile, agirlik=3 if seviye == "nizami" else 1)     # nizami işaretlenen örnek yolda 3 kat sayılır
        sl = self.varyant.setdefault(aile or self.aile, {}).setdefault(harf, {})
        if seviye not in sl:
            sl[seviye] = [1, sab.tolist(), kal]
        else:
            n, d, k = sl[seviye]
            w = 1 / (min(n, 200) + 1)
            sl[seviye] = [n + 1, [a + (b - a) * w for a, b in zip(d, sab)], k + (kal - k) * w]
        return seviye

    def yol_ekle(self, harf, parca, aile=None, agirlik=1):
        """Örneğin ANA HATTINI (kalınlıktan bağımsız) harfin yolu toplamına katar."""
        import numpy as np
        m = parca > 110
        if m.sum() < 6:
            return
        from PIL import Image, ImageFilter
        hat = ana_hat(m)
        im = Image.fromarray(hat.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))
        yum = np.asarray(im.resize((YOL, YOL), Image.Resampling.BOX), dtype=np.float32) / 255.0 * 100
        hl = self.yol.setdefault(aile or self.aile, {})
        if harf not in hl:
            hl[harf] = [agirlik, (yum.ravel() * agirlik).tolist()]
        else:
            n, d = hl[harf]
            hl[harf] = [n + agirlik, [a + b * agirlik for a, b in zip(d, yum.ravel())]]
        self._yol_onb.pop((aile or self.aile, harf), None)

    def yol_prototip(self, harf, aile=None, en_az=3):
        """Harfin ortak yolu: örneklerin çoğunda bulunan ana hat noktaları (normalize x, y). Az örnek varsa None."""
        import numpy as np
        anahtar = (aile or self.aile, harf)
        if anahtar in self._yol_onb:
            return self._yol_onb[anahtar]
        v = self.yol.get(anahtar[0], {}).get(harf)
        pts = None
        if v and v[0] >= en_az:
            P = np.asarray(v[1], dtype=np.float32).reshape(YOL, YOL) / (100.0 * v[0])
            esik = max(0.25, 0.5 * float(P.max()))
            maske = P >= esik                                       # örneklerin çoğunda ortak iskelet
            hat = ana_hat(maske)
            ys, xs = np.nonzero(hat)
            if len(xs) >= 6:
                pts = np.stack([(xs + 0.5) / YOL, (ys + 0.5) / YOL], axis=1).astype(np.float32)
        self._yol_onb[anahtar] = pts
        return pts

    def varyant_ozet(self, harf, aile=None):
        """{seviye: örnek sayısı} (yalnızca bu harfin varyasyonları)"""
        return {sv: v[0] for sv, v in self.varyant.get(aile or self.aile, {}).get(harf, {}).items()}

    def varyant_sablon(self, harf, seviye, aile=None):
        """Harfin o seviyedeki 24x24 şablonu (numpy). Nizami için gerçek örnek yoksa bilgisayardaki daktilo yazı
        tipinden çizilmiş nizami referans kullanılır. Yoksa None."""
        import numpy as np
        v = self.varyant.get(aile or self.aile, {}).get(harf, {}).get(seviye)
        if v:
            return np.asarray(v[1], dtype=np.float32).reshape(KALIP, KALIP)
        if seviye == "nizami":
            try:
                import cricroow
                r = cricroow.ince_referans(harf, KALIP * 2, KALIP * 2)
            except Exception:  # noqa: BLE001
                r = None
            if r is not None:
                from PIL import Image
                return np.asarray(Image.fromarray(r.astype(np.uint8) * 255).resize((KALIP, KALIP), Image.Resampling.BOX),
                                  dtype=np.float32)
        return None

    def yeni_simge(self):
        """Henüz kullanılmayan bir bilinmeyen-harf simgesi (U+E000, U+E001, ...)."""
        kullanilan = {r[0] for r in self.gercek.k} | {h for h in self.kalip} | {h for h in self.hat}
        n = 0xE000
        while chr(n) in kullanilan:
            n += 1
        return chr(n)

    def etiket_birlestir(self, eski, yeni):
        """Bir etiketin BÜTÜN örneklerini başka bir etikete katar (bilinmeyen simge bir harfe çevrilince): palet, sanal
        kopyalar, kalıp, ana hat ve genişlik. -> taşınan kök sayısı"""
        if eski == yeni or not eski:
            return 0
        tasinan = 0
        for P in (self.gercek, self.sanal):
            for r in P.k:
                if r[0] == eski:
                    r[0] = yeni
                    tasinan += 1
        if eski in self.kalip:
            n, d = self.kalip.pop(eski)
            if yeni in self.kalip:
                n2, d2 = self.kalip[yeni]
                self.kalip[yeni] = [n + n2, [(a * n + b * n2) / (n + n2) for a, b in zip(d, d2)]]
            else:
                self.kalip[yeni] = [n, d]
        if eski in self.hat:
            self.hat.setdefault(yeni, []).extend(self.hat.pop(eski))
            self._hat_m = None
        for hl in self.yol.values():
            if eski in hl:
                n, d = hl.pop(eski)
                if yeni in hl:
                    n2, d2 = hl[yeni]
                    hl[yeni] = [n + n2, [a + b for a, b in zip(d, d2)]]
                else:
                    hl[yeni] = [n, d]
        self._yol_onb = {}
        for hl in self.varyant.values():
            if eski in hl:
                for sv, (n, d, k) in hl.pop(eski).items():
                    if sv in hl.setdefault(yeni, {}):
                        n2, d2, k2 = hl[yeni][sv]
                        hl[yeni][sv] = [n + n2, [(a * n + b * n2) / (n + n2) for a, b in zip(d, d2)],
                                        (k * n + k2 * n2) / (n + n2)]
                    else:
                        hl[yeni][sv] = [n, d, k]
        if eski in self.gen:
            n, g = self.gen.pop(eski)
            n2, g2 = self.gen.get(yeni, [0, g])
            self.gen[yeni] = [n + n2, (g * n + g2 * n2) / max(1, n + n2)]
        self.kaydet()
        return tasinan

    def gen_ekle(self, harf, oran):
        """Harfin mürekkep genişliği (satır boyuna oranla): kelime genişliğinden harf sayısını bulmak için."""
        h = harf.lower()
        n, v = self.gen.get(h, [0, oran])
        self.gen[h] = [n + 1, v + (oran - v) / (n + 1)]

    def hat_ekle(self, harf, v):
        """Harfin ana hattını ezberler: benzer bir örnek varsa ona katılır, yoksa yeni örnek olur."""
        import numpy as np
        if v is None:
            return
        liste = self.hat.setdefault(harf, [])
        self._hat_m = None
        if liste:
            ben = [float(np.dot(np.asarray(d, dtype=np.float32), v)) for _, d in liste]
            i = int(np.argmax(ben))
            if ben[i] > 0.85 or len(liste) >= HAT_ORNEK:
                n, d = liste[i]
                w = 1 / (min(n, 200) + 1)
                yeni = np.asarray(d, dtype=np.float32) * (1 - w) + v * w
                yeni /= float(np.linalg.norm(yeni)) or 1
                liste[i] = [n + 1, yeni.tolist()]
                return
        liste.append([1, v.tolist()])

    def hat_olasilik(self, v):
        """Kutunun ana hattı ezberdeki hangi harflerin ana hattına benziyor: {harf: olasılık}"""
        import numpy as np
        if v is None or not self.hat:
            return {}
        if self._hat_m is None:
            harfler, satir = [], []
            for h, l in self.hat.items():
                for _, d in l:
                    harfler.append(h); satir.append(d)
            self._hat_m = (harfler, np.asarray(satir, dtype=np.float32))
        harfler, M = self._hat_m
        ben = M @ v
        en = {}
        for h, b in zip(harfler, ben):
            if h not in en or b > en[h]:
                en[h] = float(b)
        ust = max(en.values())
        ag = {h: math.exp(-(ust - b) / HAT_T) for h, b in en.items()}
        top = sum(ag.values())
        return {h: a / top for h, a in ag.items()}

    def kalip_ekle(self, harf, kap, p):
        """Gerçek harfin görüntüsü (kutu, 24x24 kapsama) harfin ortalama kalıbına katılır: orijinal referans."""
        from PIL import Image
        k = kap.crop((p[0], p[2], p[1], p[3])).resize((KALIP, KALIP), Image.Resampling.BOX)
        d = list(k.getdata())
        if harf not in self.kalip:
            self.kalip[harf] = [1, [float(x) for x in d]]
            return
        n, eski = self.kalip[harf]
        w = 1 / (min(n, 500) + 1)
        self.kalip[harf] = [n + 1, [a + (b - a) * w for a, b in zip(eski, d)]]

    def kalip_resmi(self, harf, en, boy):
        """Harfin ortalama kalıbı, verilen kutu boyutunda (kapsama 0..255, numpy) ya da None."""
        import numpy as np
        from PIL import Image
        if harf not in self.kalip:
            return None
        d = np.asarray(self.kalip[harf][1], dtype=np.float32).reshape(KALIP, KALIP)
        return np.asarray(Image.fromarray(d.clip(0, 255).astype(np.uint8)).resize((max(1, en), max(1, boy)),
                                                                                    Image.Resampling.BILINEAR),
                          dtype=np.float32)

    def ozet(self):
        return {"gercek_kok": len(self.gercek.k), "sanal_kok": len(self.sanal.k),
                "harf": self.gercek.harf_sayisi(), "kelime": len(self.kelime), "metin": self.metin_sayisi}

    # ---- bağlam
    def metin_ogren(self, metin):
        kel = kelimeler(metin)
        for w in kel:
            self.kelime[w] = self.kelime.get(w, 0) + 1
        for a, b in zip(kel, kel[1:]):
            k = a + " " + b
            self.cift[k] = self.cift.get(k, 0) + 1
        self.metin_sayisi += 1


def kelimeler(metin):
    return [w.lower() for w in re.findall(r"[^\W_]+(?:'[^\W_]+)?", metin)]


# ====================================================================== 1. HİZALAMA
def _satir_hizala(kutu_say, harf_say, maliyet=None):
    """Sayfa satırları ile metin satırlarını eşler (fazla satır: üstü çizili, leke; eksik satır: okunamayan).
    -> [(sayfa_satiri, metin_satiri)]"""
    n, m = len(kutu_say), len(harf_say)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    geri = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            for di, dj, c in ((1, 1, None), (1, 0, 0.6), (0, 1, 0.6)):
                a, b = i + di, j + dj
                if a > n or b > m:
                    continue
                if c is None:
                    c = maliyet(i, j) if maliyet else abs(kutu_say[i] - harf_say[j]) / max(1, harf_say[j])
                if dp[i][j] + c < dp[a][b]:
                    dp[a][b], geri[a][b] = dp[i][j] + c, (i, j, di, dj)
    out, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj, di, dj = geri[i][j]
        if di and dj:
            out.append((pi, pj, maliyet(pi, pj) if maliyet else abs(kutu_say[pi] - harf_say[pj]) / max(1, harf_say[pj])))
        i, j = pi, pj
    return out[::-1]


def _harf_hizala(kutular, harfler, ipucu=None):
    """Bir satırın kutuları ile harfleri: dinamik hizalama.
    1 kutu = 1 harf | 2 kutu = 1 harf (bölünmüş) | 1 kutu = 2 harf (değen) | fazla kutu (leke) | eksik harf (silik).
    -> [(kutu_listesi, harfler)]  (yalnızca eşleşenler)"""
    n, m = len(kutular), len(harfler)
    if not n or not m:
        return []
    genis = sorted(k[1] - k[0] for k in kutular)
    cw = max(1, genis[len(genis) // 2])
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    geri = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0

    def gen(i, k):
        return kutular[i + k - 1][1] - kutular[i][0]

    def sekil(i, c):
        """Kutunun şekli bu harfe benziyor mu (genel palet ipucu): 0 iyi ... 1 hiç."""
        if not ipucu or ipucu[i] is None:
            return 0.5
        m = ipucu[i].get(c)
        if m is None:
            m = ipucu[i].get(c.swapcase())
            return 1.0 if m is None else min(1.0, m / 50 + 0.2)
        return min(1.0, m / 50)

    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            adim = []
            if i < n and j < m:
                adim.append((1, 1, 0.3 * min(1.0, abs(gen(i, 1) - cw) / cw) + sekil(i, harfler[j])))
            if i + 1 < n and j < m and kutular[i + 1][0] - kutular[i][1] <= 0.2 * cw:
                adim.append((2, 1, 0.9 + min(0.5, 0.5 * abs(gen(i, 2) - cw) / cw)))
            if i < n and j + 1 < m:
                adim.append((1, 2, 0.9 + min(0.5, 0.5 * abs(gen(i, 1) - 2 * cw) / cw)
                             + (2.0 if gen(i, 1) < 1.3 * cw else 0)))
            if i < n:
                adim.append((1, 0, 1.2))
            if j < m:
                adim.append((0, 1, 1.5))
            for di, dj, c in adim:
                if dp[i][j] + c < dp[i + di][j + dj]:
                    dp[i + di][j + dj], geri[i + di][j + dj] = dp[i][j] + c, (i, j, di, dj)
    out, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj, di, dj = geri[i][j]
        if di and dj:
            out.append((kutular[pi:pi + di], harfler[pj:pj + dj], dp[i][j] - dp[pi][pj]))
        i, j = pi, pj
    return out[::-1]


# ====================================================================== 2. SANAL SİLİK HARFLER
def sanal_kopyalar(kap, p, rng, n=SANAL_KOPYA):
    """Bir gerçek harf kutusundan silik kopyalar: (çeşit, kapsama resmi). Kopyalar yalnızca kutunun içini değiştirir."""
    from PIL import Image, ImageFilter
    import numpy as np
    x0, x1, y0, y1 = p[:4]
    a = np.asarray(kap, dtype=np.float32)
    kutu = a[y0:y1, x0:x1]
    h, w = kutu.shape
    cesitler = []
    for t in range(n):
        tur = ("solgun", "ince", "delik", "kirik", "solgun_ince", "delik_solgun")[t % 6]
        k = kutu.copy()
        if "solgun" in tur:
            k *= rng.uniform(0.45, 0.75)
        if "ince" in tur:
            k = np.asarray(Image.fromarray(k.clip(0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)),
                           dtype=np.float32)
        if "delik" in tur:
            for _ in range(max(1, int(w * h / 60))):
                yy, xx = rng.randrange(h), rng.randrange(w)
                k[max(0, yy - 1):yy + 2, max(0, xx - 1):xx + 2] = 0
        if tur == "kirik" and h > 6:
            b = max(1, int(h * rng.uniform(0.1, 0.2)))
            yy = rng.randrange(h - b)
            k[yy:yy + b, :] *= 0.15
        b2 = a.copy()
        b2[y0:y1, x0:x1] = k
        b2[b2 < CH.GURULTU] = 0
        cesitler.append((tur, Image.fromarray(b2.clip(0, 255).astype(np.uint8))))
    return cesitler


# ====================================================================== DAKTİLO IZGARASI
def _sutun_izdusum(kap, ust, alt):
    import numpy as np
    return np.asarray(kap.crop((0, ust, kap.width, alt)), dtype=np.float32).sum(0)


def harf_adimi(kap, satirlar):
    """Sabit aralıklı yazı (daktilo): her harf aynı genişlikte. Satırların sütun izdüşümlerinin ortak dönemini bulur.
    -> (adım_piksel, güç 0..1) ya da (None, 0)"""
    import numpy as np
    if not satirlar:
        return None, 0.0
    sb = sorted(a - u for u, a in satirlar)[len(satirlar) // 2]
    en_kisa, en_uzun = max(6, int(0.3 * sb)), max(8, int(1.6 * sb))
    top = None
    for u, a in satirlar:
        c = _sutun_izdusum(kap, u, a)
        if c.std() == 0:
            continue
        c = c - c.mean()
        r = np.correlate(c, c, "full")[len(c) - 1:][:en_uzun + 2]
        r = r / (r[0] or 1)
        top = r if top is None else top + r
    if top is None:
        return None, 0.0
    top = top / len(satirlar)
    aralik = range(en_kisa, min(en_uzun, len(top) - 1))
    # gerçek tepeler: yerel en büyük ve önündeki vadiden belirgin yüksek (düz azalan eğri tepe değildir)
    tepeler = [(i, float(top[i] - top[en_kisa:i].min())) for i in aralik
               if top[i] >= top[i - 1] and top[i] >= top[i + 1] and i > en_kisa]
    tepeler = [(i, b) for i, b in tepeler if b > 0.05]
    if not tepeler:
        return None, 0.0
    en = max(b for _, b in tepeler)
    t, belirgin = next((i, b) for i, b in tepeler if b >= 0.6 * en)   # ilk belirgin tepe (katları da tepe verir)
    # alt-piksel incelik: tepenin iki komşusuyla parabol
    a, b, c = top[t - 1], top[t], top[t + 1]
    ince = t + (0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else 0)
    return float(ince), belirgin


def izgara_hucreleri(kap, ust, alt, adim):
    """Bir satırı sabit aralıklı hücrelere böler: [(x0, x1, mürekkep_var)].
    Satırın kendi adımı ve fazı ayrıca ince ayarlanır (sınırlarda mürekkep en az); sonra her sınır, birikmiş kaymayı
    önlemek için yakınındaki (±%20) en boş sütuna oturtulur."""
    import numpy as np
    c = _sutun_izdusum(kap, ust, alt)
    if c.max() <= 0:
        return []
    d = np.convolve(c, np.ones(3) / 3, "same")
    dolu = np.nonzero(c > 0.02 * c.max())[0]
    ilk, son = int(dolu[0]), int(dolu[-1])

    def maliyet(a, f):
        sinir = np.arange(f, len(c), a)
        sinir = sinir[(sinir >= ilk - a) & (sinir <= son + a)].astype(int)
        sinir = sinir[(sinir >= 0) & (sinir < len(c))]
        return d[sinir].mean() if len(sinir) else 1e18

    en = None
    for a in np.linspace(adim * 0.97, adim * 1.03, 25):
        for f in np.arange(0, a, 0.5):
            m = maliyet(a, f)
            if en is None or m < en[0]:
                en = (m, float(a), float(f))
    _, adim, faz = en
    esik = 0.08 * float(np.percentile(c[dolu], 90)) * adim
    x = faz + math.floor((ilk - faz) / adim) * adim
    out = []
    oynama = max(1, int(0.2 * adim))
    while x <= son:
        hedef = x + adim
        a0 = int(round(hedef)) - oynama
        a1 = int(round(hedef)) + oynama + 1
        if 0 <= a0 and a1 <= len(d):
            pencere = d[a0:a1]
            yeni = a0 + int(np.argmin(pencere))
            # yalnızca belirgin bir boşluk varsa oturt; düz pencerede beklenen yerde kal
            if pencere.min() < 0.5 * pencere.max():
                hedef = 0.5 * hedef + 0.5 * yeni
        b0, b1 = max(0, int(round(x))), min(len(c), int(round(hedef)))
        if b1 > b0:
            out.append((b0, b1, float(c[b0:b1].sum())))
        x = hedef
    # boş hücre (boşluk) eşiği satırın kendi hücrelerine göre: mürekkebi taşmış daktiloda kelime arası da biraz dolu
    if out:
        murekkep = sorted(m for _, _, m in out)
        tipik = murekkep[int(0.75 * (len(murekkep) - 1))]
        esik = max(esik, 0.3 * tipik)
    return [(b0, b1, m > esik) for b0, b1, m in out]


def _izgara_hizala(hucre_dolu, metin):
    """Hücreler (dolu/boş) ile karakterler (harf/boşluk): Needleman-Wunsch. -> [(hücre_no, karakter)]"""
    n, m = len(hucre_dolu), len(metin)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    geri = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == INF:
                continue
            if i < n and j < m:
                c = 0 if hucre_dolu[i] == (not metin[j].isspace()) else 1
                if dp[i][j] + c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], geri[i + 1][j + 1] = dp[i][j] + c, (i, j)
            atla = 0.1 if i < n and not hucre_dolu[i] else 1   # fazla boş hücre zararsız (satır başı/sonu)
            if i < n and dp[i][j] + atla < dp[i + 1][j]:
                dp[i + 1][j], geri[i + 1][j] = dp[i][j] + atla, (i, j)
            if j < m and dp[i][j] + 1 < dp[i][j + 1]:
                dp[i][j + 1], geri[i][j + 1] = dp[i][j] + 1, (i, j)
    out, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj = geri[i][j]
        if i - pi == 1 and j - pj == 1:
            out.append((pi, metin[pj]))
        i, j = pi, pj
    return out[::-1], dp[n][m] / max(1, m)


def _izgara_satir_esle(H, metin_satir):
    """Sayfa satırları (hücre listeleri) ile metin satırlarını DESEN benzerliğiyle eşler. -> [(i, j, hata)]"""
    from functools import lru_cache
    dolu = [[x[2] for x in h] for h in H]

    @lru_cache(maxsize=None)
    def m(i, j):
        if not dolu[i] or abs(sum(dolu[i]) - sum(not c.isspace() for c in metin_satir[j])) > 0.5 * len(metin_satir[j]):
            return 1.0
        return min(1.0, _izgara_hizala(dolu[i], metin_satir[j])[1])
    return _satir_hizala([len(h) for h in H], [len(t) for t in metin_satir], maliyet=m)


def _hucre_kutusu(kap, h, ust, alt):
    """Izgara hücresi -> harf kutusu (yatay: hücrenin tamamı, dikey: içindeki mürekkep)."""
    return CH._kutu(kap, h[0], h[1], ust, alt)


def _izgara_mi(kap, satirlar, guc_esik=0.15, bilinen=None):
    adim, guc = harf_adimi(kap, satirlar)
    if adim and guc >= guc_esik:
        if bilinen and guc < 0.3 and abs(adim - bilinen) > 0.08 * bilinen:
            return bilinen                       # zayıf ve öğretilenden farklı (çoğu kez katı): öğretilen adım
        return adim
    return bilinen                               # mürekkep harfleri birleştirmiş: öğretilen adım kullanılır


def _tarak(sm, p, n):
    """p (kesirli olabilir) aralıklı tarak: her faz için tepe (satır ortası) - vadi (satırlar arası) ortalaması farkı."""
    import numpy as np
    ks = np.arange(int(n / p) + 2)
    en, faz = -1e18, 0
    for ph in range(int(p) + 1):
        c = np.rint(ph + ks * p).astype(int)
        v = np.rint(ph + p / 2 + ks * p).astype(int)
        gecerli = (v < n) & (c < n)
        if gecerli.sum() < 4:
            continue
        f = float(sm[c[gecerli]].mean() - sm[v[gecerli]].mean())
        if f > en:
            en, faz = f, ph
    return en, faz


def satir_periyodu(izd):
    """Satır aralığı (piksel, KESİRLİ olabilir). Satırlar EŞİT aralıklıdır: satır izdüşümünün (yavaş değişen kısmı
    çıkarılmış) otokorelasyonunda EN YÜKSEK tepe gerçek aralıktır (yarım aralık ve katları daha zayıftır); sonra tarak
    ölçütüyle kesirli ince ayar yapılır. Üstü çizili satırlar, leke ve gürültü bu yöntemi bozmaz.
    -> (p, güven 0..1) ya da (None, 0)"""
    import numpy as np
    a = np.asarray(izd, dtype=np.float64)
    n = len(a)
    if n < 120 or a.sum() <= 0:
        return None, 0.0
    pen = max(41, n // 8) | 1
    yavas = np.convolve(a, np.ones(pen) / pen, "same")                 # metin bloğu / kenar boşluğu gibi yavaş yapı
    d = a - yavas
    r = np.correlate(d, d, "full")[n - 1:]
    if r[0] <= 0:
        return None, 0.0
    r = r / r[0]
    hi = min(n // 5, 220)
    tepe = [t for t in range(6, hi) if r[t] >= r[t - 1] and r[t] >= r[t + 1] and r[t] > 0.08]
    if not tepe:
        return None, 0.0
    t = max(tepe, key=lambda x: r[x])
    guven = float(r[t])
    if guven < 0.22:
        return None, guven
    sm = np.convolve(d, np.ones(3) / 3, "same")
    en, pp = -1e18, float(t)
    for p in np.arange(t - 0.75, t + 0.76, 0.05):                       # kesirli ince ayar
        f = _tarak(sm, float(p), n)[0]
        if f > en:
            en, pp = f, float(p)
    return pp, guven


def cizgi_maskesi(m, pitch):
    """Üstü çizili / altı çizili UZUN yatay çizgilerin maskesi (bool): en az 6 satır aralığı uzunluğunda kesintisiz mürekkep."""
    import numpy as np
    en_az = int(6 * pitch)
    md = m.copy()
    md[1:] |= m[:-1]
    md[:-1] |= m[1:]                                              # elle çizilmiş eğik çizgi kopmasın
    mask = np.zeros_like(m)
    for y in np.nonzero(md.sum(1) >= en_az)[0]:
        d = np.diff(np.concatenate(([0], md[y].astype(np.int8), [0])))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if b - a >= en_az:
                mask[y, a:b] = True
    return mask & m


def cizgisiz(kap):
    """Üstü çizili satırları kaldırılmış kapsama (PIL) ve satır aralığı. Çizgi yoksa kap aynen döner.
    -> (kap_s, pitch ya da None, kaldırılan piksel)"""
    import numpy as np
    from PIL import Image
    a = np.asarray(kap)
    m = a > 110
    izd = m.sum(1)
    pitch, _ = satir_periyodu(izd)
    if not pitch:
        return kap, None, 0
    mask = cizgi_maskesi(m, pitch)
    if mask.sum() < 20:
        return kap, pitch, 0
    b = a.copy()
    b[mask] = 0
    return Image.fromarray(b), pitch, int(mask.sum())


def satirlar_periyodik(kap_s, pitch):
    """Eşit aralıklı satırlar: tarak fazı bulunur, her satırın iki yanındaki en derin vadi sınır olur. -> [(ust, alt)]"""
    import numpy as np
    a = (np.asarray(kap_s) > 110).sum(1).astype(np.float64)
    n = len(a)
    pen_s = max(3, int(round(pitch / 6)))
    sm = np.convolve(a, np.ones(pen_s) / pen_s, "same")
    _, faz = _tarak(sm, pitch, n)
    vadi = []
    pen = max(2, int(0.28 * pitch))
    t = faz + pitch / 2 - pitch
    while t < n + pitch:
        tc = int(round(t))
        lo, hi = max(0, tc - pen), min(n, tc + pen + 1)
        if hi - lo >= 3:
            vadi.append(lo + int(np.argmin(sm[lo:hi])))
        t += pitch
    vadi = sorted(set(vadi))
    bantlar, kutle = [], []
    for u, al in zip(vadi, vadi[1:]):
        parca = a[u:al]
        if parca.sum() <= 0:
            continue
        ys = np.nonzero(parca > 0.12 * parca.max())[0]
        if len(ys) < max(3, 0.25 * pitch):
            continue
        bantlar.append((u + int(ys.min()), u + int(ys.max()) + 1))
        kutle.append(float(parca.sum()))
    if not bantlar:
        return []
    ort = float(np.median(kutle))
    return [b for b, k in zip(bantlar, kutle) if k >= 0.12 * ort]


def satirlar_belge(kap):
    """crw_harf.satirlar + belge temizliği. Önce satır aralığı PERİYODİKLİKTEN bulunur (üstü çizili, lekeli tam sayfalarda
    da çalışır); sayfa çok kısaysa ya da periyot bulunamazsa eski izdüşüm yöntemi: benek bantları atılır, tipik satırdan
    çok uzun bantlar izdüşüm vadilerinden bölünür."""
    import numpy as np
    kap_s, pitch, _ = cizgisiz(kap)
    if pitch:
        bandlar = satirlar_periyodik(kap_s, pitch)
        if len(bandlar) >= 4:
            return bandlar
    b = CH.satirlar(kap)
    if not b:
        return b
    izd = CH._izdusum(kap, True)
    murekkep = [sum(izd[u:a]) for u, a in b]
    orta_m = sorted(murekkep)[len(murekkep) // 2]
    b = [x for x, m in zip(b, murekkep) if m >= 0.15 * orta_m]
    if not b:
        return b
    boy = sorted(a - u for u, a in b)
    orta = boy[len(boy) // 2]
    out = []
    for u, a in b:
        if a - u > 1.45 * orta:
            out += CH._bitisik_bol(izd, u, a, orta)
        else:
            out.append((u, a))
    return out


def kenarsiz(kap):
    """Tarama kenarındaki siyah şeritleri (sayfanın dışı, zımba, gölge) mürekkep saymaz: kenara değen ve sayfanın
    büyük kısmı boyunca uzanan koyu sütun/satır bantları kâğıt yapılır."""
    from PIL import Image
    import numpy as np
    a = np.asarray(kap).copy()
    H, W = a.shape
    dolu = a > 128
    sut, sat = dolu.mean(0), dolu.mean(1)
    for ekseni, oran, n in ((1, sut, W), (0, sat, H)):
        for yon in (1, -1):
            # kenardan içeri, kesintisiz koyu bant (en fazla %8); yazı satırı kenara değmez, şerit değer
            i = 0 if yon == 1 else n - 1
            bosluk = 0
            son_koyu = None
            for _ in range(int(0.08 * n)):
                if oran[i] > 0.6:
                    son_koyu, bosluk = i, 0
                elif son_koyu is not None or bosluk > 3:
                    bosluk += 1
                    if bosluk > 3:
                        break
                else:
                    bosluk += 1
                i += yon
            if son_koyu is not None:
                a0, a1 = (0, son_koyu + 4) if yon == 1 else (son_koyu - 3, n)
                if ekseni:
                    a[:, max(0, a0):a1] = 0
                else:
                    a[max(0, a0):a1, :] = 0
    return Image.fromarray(a)


def adim_metinden(kap, satirlar, metin_satir, ek_aday=None):
    """Harf adımını metinden bulur: hangi adımda sayfa satırlarının hücreleri (dolu/boş) metin satırlarının
    harf/boşluk dizisiyle en iyi hizalanıyorsa o. (Mürekkebi taşmış daktiloda sütun izdüşümü dönem göstermez.)"""
    import numpy as np
    if not metin_satir or not satirlar:
        return None
    sb = sorted(a - u for u, a in satirlar)[len(satirlar) // 2]

    def hata(p):
        H = [izgara_hucreleri(kap, u, a, p) for u, a in satirlar]
        es = _izgara_satir_esle(H, metin_satir)
        if not es:
            return 9.0
        hs = sorted(_izgara_hizala([x[2] for x in H[i]], metin_satir[j])[1] for i, j, _ in es)
        iyi = hs[:max(1, (len(hs) + 1) // 2)]                # en iyi yarı (çizik, leke satırları sayılmaz)
        return sum(iyi) / len(iyi) + 0.5 * (len(metin_satir) - len(es)) / len(metin_satir)
    adaylar = list(np.arange(max(6.0, 0.3 * sb), 1.2 * sb, 1.0))
    for a in ek_aday or ():                                  # görüntüden bulunan adım ve yarısı da sınanır
        if a:
            adaylar += [a, a / 2]
    kaba = min(adaylar, key=hata)
    en = min(np.arange(kaba - 1, kaba + 1.01, 0.25), key=hata)
    return float(en) if hata(en) < 0.3 else None

def ogret(img, metin, depo=None, ilerleme=None, sanal=True, tohum=7, daktilo=None, genel=None):
    """Sayfa resmi + o sayfanın doğru metni -> depo. Dönüş: rapor sözlüğü."""
    depo = depo or Depo()
    g, aci = CH.duzle(img)
    kap = kenarsiz(CH.kapsama(g))
    satirlar = satirlar_belge(kap)
    metin_satir = [s for s in (x.strip() for x in metin.splitlines()) if s]
    kutular = [CH.parcalar(kap, 0, kap.width, u, a) or [] for u, a in satirlar]
    harfler = [[c for c in s if not c.isspace()] for s in metin_satir]
    eslesme = _satir_hizala([len(k) for k in kutular], [len(h) for h in harfler])
    rng = random.Random(tohum)
    gercek = cift = sanal_n = atlanan_satir = 0
    # daktilo: None = kendisi anlar; True = eş aralıklı (daktilo, teleks); False = matbaa yazısı (orantılı)
    adim = None
    if daktilo is not False:                     # metin eldeyken adım metne göre sınanır (görüntüdeki adım katına takılabilir)
        gorulen = _izgara_mi(kap, satirlar)
        adim = adim_metinden(kap, satirlar, metin_satir, [gorulen]) or (gorulen if daktilo else None)
    if adim:
        depo.adim = adim                                     # daktilo: her karakter (boşluk dahil) bir hücre
        hucreler = [izgara_hucreleri(kap, u, a, adim) for u, a in satirlar]
        eslesme = _izgara_satir_esle(hucreler, metin_satir)
    for si, (i, j, maliyet) in enumerate(eslesme):
        if adim:
            if ilerleme:
                ilerleme(si / max(1, len(eslesme)), f"Belgeden öğreniliyor (daktilo ızgarası): satır {si + 1}")
            ust, alt = satirlar[i]
            esler, hata = _izgara_hizala([h[2] for h in hucreler[i]], metin_satir[j])
            if hata > 0.2:
                atlanan_satir += 1
                continue
            for hi, ch in esler:
                if ch.isspace() or not CH.izinli(ch) or not hucreler[i][hi][2]:
                    continue
                k = _hucre_kutusu(kap, hucreler[i][hi], ust, alt)
                if not k:
                    continue
                try:
                    oz = CH.ozellik(kap, k, ust, alt)
                except Exception:  # noqa: BLE001
                    continue
                depo.gercek.ekle(ch, oz)
                depo.kalip_ekle(ch, kap, k)
                depo.hat_ekle(ch, hat_haritasi(kap, k, ust, alt))
                depo.gen_ekle(ch, (k[1] - k[0]) / max(1, alt - ust))
                depo.varyant_ekle(ch, kap, (k[0], k[1], k[2], k[3], ust, alt))
                gercek += 1
                if sanal:
                    for _, kv in sanal_kopyalar(kap, k, rng):
                        try:
                            depo.sanal.ekle(ch, CH.ozellik(kv, k, ust, alt))
                            sanal_n += 1
                        except Exception:  # noqa: BLE001
                            pass
            continue
        if ilerleme:
            ilerleme(si / max(1, len(eslesme)), f"Belgeden öğreniliyor: satır {si + 1}/{len(eslesme)}")
        if maliyet > 0.35:                       # satır ile metin pek tutmuyor: güvenli değil, atla
            atlanan_satir += 1
            continue
        ust, alt = satirlar[i]
        ipucu = None
        if genel is not None and genel.k:        # kutunun şekli hangi harflere benziyor (hizalama ipucu)
            ipucu = []
            for k_ in kutular[i]:
                try:
                    ipucu.append({h: v[0] for h, v in _adaylar(genel, CH.ozellik(kap, k_, ust, alt), "genel", 40).items()})
                except Exception:  # noqa: BLE001
                    ipucu.append(None)
        for kl, hs, mal in _harf_hizala(kutular[i], harfler[j], ipucu):
            if ipucu and (mal > 1.1 or len(hs) != 1 or len(kl) != 1):
                continue                         # şekli harfe benzemeyen ya da birleşik/bölünmüş eşleşme: öğrenilmez
            if len(kl) == 2:                     # bölünmüş harf: iki parça tek kutu
                k = CH._kutu(kap, kl[0][0], kl[1][1], ust, alt)
                if not k:
                    continue
            else:
                k = kl[0]
            etiket = "".join(hs)
            if not CH.izinli(etiket):
                continue
            try:
                oz = CH.ozellik(kap, k, ust, alt)
            except Exception:  # noqa: BLE001 - bozuk kutu
                continue
            depo.gercek.ekle(etiket, oz)
            if len(hs) == 1:
                depo.kalip_ekle(etiket, kap, k)
                depo.hat_ekle(etiket, hat_haritasi(kap, k, ust, alt))
                depo.gen_ekle(etiket, (k[1] - k[0]) / max(1, alt - ust))
                depo.varyant_ekle(etiket, kap, (k[0], k[1], k[2], k[3], ust, alt))
            gercek += len(hs) == 1
            cift += len(hs) == 2
            if sanal and len(hs) == 1:
                for _, kv in sanal_kopyalar(kap, k, rng):
                    try:
                        depo.sanal.ekle(etiket, CH.ozellik(kv, k, ust, alt))
                        sanal_n += 1
                    except Exception:  # noqa: BLE001
                        pass
    depo.metin_ogren(metin)
    depo.kaydet()
    return {"egim": aci, "daktilo_adimi": round(adim, 2) if adim else None, "sayfa_satiri": len(satirlar), "metin_satiri": len(metin_satir),
            "eslesen_satir": len(eslesme) - atlanan_satir, "atlanan_satir": atlanan_satir,
            "gercek_harf": gercek, "degen_cift": cift, "sanal_harf": sanal_n, **depo.ozet()}


# ====================================================================== ANA HAT (harfin orta çizgisi)
HAT = 20                # ana hat haritasının çözünürlüğü
HAT_T = 0.07            # ana hat benzerliği -> olasılık sıcaklığı
HAT_ORNEK = 8           # harf başına en fazla ana hat örneği
HAT_AGIRLIK = 1.0       # ana hat olasılığının üssü (palet olasılığınınki 0.5)
ANA_HAT = True          # False: ana hat kullanılmaz (yalnızca palet)


def ana_hat(maske):
    """Kalın bir şekli kenarlarından kat kat soyarak tek piksellik ORTA ÇİZGİSİNE indirir (bool dizi -> bool dizi).
    Her turda yalnızca şekli koparmayan kenar pikselleri silinir; taşmalar gider, ana hat kalır."""
    import numpy as np
    m = np.pad(maske.astype(bool), 1)
    while True:
        degisti = False
        for tur in (0, 1):
            P2, P3, P4 = np.roll(m, 1, 0), np.roll(np.roll(m, 1, 0), -1, 1), np.roll(m, -1, 1)
            P5, P6, P7 = np.roll(np.roll(m, -1, 0), -1, 1), np.roll(m, -1, 0), np.roll(np.roll(m, -1, 0), 1, 1)
            P8, P9 = np.roll(m, 1, 1), np.roll(np.roll(m, 1, 0), 1, 1)
            kom = [P2, P3, P4, P5, P6, P7, P8, P9]
            B = sum(k.astype(np.int8) for k in kom)
            A = sum((~a & b).astype(np.int8) for a, b in zip(kom, kom[1:] + kom[:1]))
            if tur == 0:
                sil = m & (B >= 2) & (B <= 6) & (A == 1) & ~(P2 & P4 & P6) & ~(P4 & P6 & P8)
            else:
                sil = m & (B >= 2) & (B <= 6) & (A == 1) & ~(P2 & P4 & P8) & ~(P2 & P6 & P8)
            sil[0, :] = sil[-1, :] = sil[:, 0] = sil[:, -1] = False
            if sil.any():
                m &= ~sil
                degisti = True
        if not degisti:
            break
    return m[1:-1, 1:-1]


def hat_haritasi(kap, p, ust, alt):
    """Harf kutusunun ana hattı -> birim uzunlukta vektör (HAT x HAT yumuşak harita + satırdaki dikey konumu)."""
    import numpy as np
    from PIL import Image, ImageFilter
    kutu = np.asarray(kap.crop((p[0], p[2], p[1], p[3])), dtype=np.float32)
    if kutu.size == 0 or (kutu > 110).sum() < 3:
        return None
    h = ana_hat(kutu > 110)
    kalin = max(3, 2 * (max(kutu.shape) // 14) + 1)                  # eşlemede küçük kaymalara hoşgörü
    r = Image.fromarray(h.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(kalin))
    v = np.asarray(r.resize((HAT, HAT), Image.Resampling.BOX), dtype=np.float32).ravel() / 255.0
    sb = max(1, alt - ust)
    konum = np.array([(p[2] - ust) / sb, (p[3] - ust) / sb, min(2.0, (p[1] - p[0]) / max(1, p[3] - p[2]))],
                     dtype=np.float32) * (0.35 * HAT)
    v = np.concatenate([v, konum])
    n = float(np.linalg.norm(v))
    return v / n if n else None


# ====================================================================== 3. OLASILIK SIRALAMASI
def _adaylar(P, oz, kaynak, n=30):
    """Bir paletten harf başına en iyi mesafe: {harf: (mesafe, kaynak, kök)}"""
    out = {}
    if not P or not P.k:
        return out
    for x in sorted(P.k, key=lambda x: CH._kaba_mesafe(x, oz))[:n]:
        m = CH._mesafe(x, oz) + 6 / (x[6] ** 0.5)
        if x[0] not in out or m < out[x[0]][0]:
            out[x[0]] = (m, kaynak, x)
    return out


def siralama(oz, depo, genel=None, hat=None):
    """-> [(harf, olasılık, mesafe, kaynak, gerçek_kök)] olasılığa göre sıralı.
    Kaynak: 'gerçek' (belgenin kendi harfi), 'sanal' (silik kopyası), 'genel' (yazı tiplerinden)."""
    birlesik = {}
    for P, ad in ((depo.gercek, "gerçek"), (depo.sanal, "sanal"), (genel, "genel")):
        for h, (m, k, x) in _adaylar(P, oz, ad).items():
            if h not in birlesik or m < birlesik[h][0]:
                birlesik[h] = (m, k, x if ad != "sanal" else None)
    if not birlesik:
        return []
    en_az = min(v[0] for v in birlesik.values())
    agirlik = {h: math.exp(-(v[0] - en_az) / T_OLASILIK) for h, v in birlesik.items()}
    top = sum(agirlik.values())
    ph = depo.hat_olasilik(hat) if ANA_HAT else {}
    if ph:                                      # ANA HAT: orta çizgisi benzeyen harfler öne geçer
        agirlik = {h: (a / top) ** 0.5 for h, a in agirlik.items()}
        for h in ph:
            if h not in birlesik:
                kok = min((r for r in depo.gercek.k if r[0] == h), key=lambda r: CH._mesafe(r, oz), default=None)
                if kok is None:
                    continue
                birlesik[h] = (CH._mesafe(kok, oz), "ana hat", kok)
                agirlik[h] = 0.02 ** 0.5
        agirlik = {h: a * max(1e-4, ph.get(h, 1e-4)) ** HAT_AGIRLIK for h, a in agirlik.items()}
        top = sum(agirlik.values())
    sinif = len(birlesik)
    if sinif < 6:                               # çok az harf bilinen depoda %100 güven YALANDIR: güven sınıf sayısıyla orantılı
        top = top * 6.0 / max(1, sinif)
    out = []
    for h, (m, k, x) in birlesik.items():
        if x is None:                           # sanal eşleşti: tamamlama kalıbı için harfin GERÇEK kökü
            x = min((r for r in depo.gercek.k if r[0] == h), key=lambda r: CH._mesafe(r, oz), default=None)
        out.append((h, agirlik[h] / top, round(m, 1), k, x))
    return sorted(out, key=lambda t: -t[1])


def _yakindan(g, p, ust, alt, depo, genel, kat=2):
    """Kutuyu (çevresiyle) kat kadar büyütüp yeniden ölçer."""
    from PIL import Image
    pay = max(2, (alt - ust) // 3)
    x0, y0 = max(0, p[0] - pay), max(0, ust - pay)
    x1, y1 = min(g.width, p[1] + pay), min(g.height, alt + pay)
    z = g.crop((x0, y0, x1, y1))
    z = z.resize((z.width * kat, z.height * kat), Image.Resampling.LANCZOS)
    zk = CH.kapsama(z)
    q = ((p[0] - x0) * kat, (p[1] - x0) * kat, (p[2] - y0) * kat, (p[3] - y0) * kat) + tuple(p[4:5])
    try:
        return siralama(CH.ozellik(zk, q, (ust - y0) * kat, (alt - y0) * kat), depo, genel,
                        hat_haritasi(zk, q, (ust - y0) * kat, (alt - y0) * kat) if ANA_HAT else None)
    except Exception:  # noqa: BLE001
        return []


def _birlestir(a, b):
    """İki bakışın olasılıklarını birleştirir (geometrik ortalama, yeniden normalleştirilir)."""
    if not b:
        return a
    pb = {t[0]: t[1] for t in b}
    out = []
    for h, p, m, k, x in a:
        out.append((h, math.sqrt(p * pb.get(h, TABAN)), m, k, x))
    top = sum(t[1] for t in out) or 1
    return sorted(((h, p / top, m, k, x) for h, p, m, k, x in out), key=lambda t: -t[1])


# ====================================================================== 4. OKUMA
def oku_kutular(img, depo=None, genel=None, yakindan=True, duzlendi=False, daktilo=None):
    """Sayfa -> satırlar: [[kutu sözlüğü, ...], ...]. Kutu: {p, ust, alt, adaylar, bosluk_once}.
    img düzlenmiş değilse önce düzlenir."""
    depo = depo or Depo()
    g = img.convert("L") if duzlendi else CH.duzle(img)[0]
    kap = kenarsiz(CH.kapsama(g))
    out = []
    satirlar_ = satirlar_belge(kap)
    adim = None if daktilo is False else _izgara_mi(kap, satirlar_, bilinen=depo.adim)
    for ust, alt in satirlar_:
        if adim:                                  # daktilo: hücre hücre; boş hücre = boşluk
            satir, bosluk = [], False
            for h in izgara_hucreleri(kap, ust, alt, adim):
                if not h[2]:
                    bosluk = bool(satir); continue
                p = _hucre_kutusu(kap, h, ust, alt)
                if not p:
                    bosluk = bool(satir); continue
                try:
                    ad = siralama(CH.ozellik(kap, p, ust, alt), depo, genel,
                                  hat_haritasi(kap, p, ust, alt) if ANA_HAT else None)
                except Exception:  # noqa: BLE001
                    continue
                if not ad:
                    continue
                yakin = False
                if yakindan and ad[0][1] < ZAYIF:
                    ad = _birlestir(ad, _yakindan(g, p, ust, alt, depo, genel)); yakin = True
                satir.append({"p": p, "ust": ust, "alt": alt, "adaylar": ad[:10], "yakindan": yakin,
                              "bosluk_once": bosluk})
                bosluk = False
            out.append(satir)
            continue
        pr = CH.parcalar(kap, 0, kap.width, ust, alt) or []
        if not pr:
            continue
        sb = alt - ust
        araliklar = sorted(b[0] - a[1] for a, b in zip(pr, pr[1:]))
        harf_arasi = araliklar[len(araliklar) // 3] if araliklar else 0
        bosluk = max(2.2 * harf_arasi, 0.22 * sb)
        satir = []
        for i, p in enumerate(pr):
            try:
                ad = siralama(CH.ozellik(kap, p, ust, alt), depo, genel,
                              hat_haritasi(kap, p, ust, alt) if ANA_HAT else None)
            except Exception:  # noqa: BLE001
                continue
            if not ad:
                continue
            yakin = False
            if yakindan and (ad[0][1] < ZAYIF):
                ad = _birlestir(ad, _yakindan(g, p, ust, alt, depo, genel))
                yakin = True
            satir.append({"p": p, "ust": ust, "alt": alt, "adaylar": ad[:10], "yakindan": yakin,
                          "bosluk_once": bool(satir) and p[0] - satir[-1]["p"][1] > bosluk})
        out.append(satir)
    return out, g


def _kelime_sec(kutular, depo, onceki):
    """Bir kelimenin kutuları -> (yazı, kelime_güveni, bağlamla_değişti, sözlükte_mi).
    Temiz (emin) harfler çapa olur: kelime sıklığı x kelime çifti x harf olasılıkları en yüksek olan kelime seçilir;
    şüpheli harfler o kelimenin harfleriyle düzelir."""
    duz = "".join(k["adaylar"][0][0] for k in kutular)
    duz_log = sum(math.log(max(TABAN, k["adaylar"][0][1])) for k in kutular)
    n = len(kutular)
    rakam = sum(k["adaylar"][0][0].isdigit() for k in kutular)
    if not depo.kelime or rakam * 2 >= n:
        return duz, math.exp(duz_log / max(1, n)), False, False
    n_top = depo.kelime_toplam()
    if depo.kelime.get(duz.lower(), 0) >= TEMIZ_KELIME:      # temiz kelime çapadır: risk yalnızca anlamsız çıkanlarda
        return duz, max(0.75, math.exp(duz_log / max(1, n))), False, True

    def kelime_puan(w):
        lp = math.log((depo.kelime.get(w, 0) + 0.1) / n_top)
        if onceki:
            lp += 1.5 * math.log1p(depo.cift.get(onceki + " " + w, 0))
        return lp

    harfler, taban = [], []
    for k in kutular:
        hp = {}
        for t in k["adaylar"]:
            c = t[0].lower()
            hp[c] = max(hp.get(c, 0.0), t[1])
        harfler.append(hp)
        # temiz harf çapadır: risk (TABAN) yalnızca şüpheli konumlarda alınır
        ad_ = k["adaylar"]
        capa = ad_[0][1] >= CAPA or len(ad_) < 2 or ad_[0][1] >= CAPA_KAT * ad_[1][1]
        taban.append(CAPA_TABAN if capa else TABAN)
    puanlar = []
    for w in depo.uzunlukta(n):
        lp = 0.0
        for c, hp, tb in zip(w, harfler, taban):
            lp += math.log(max(tb, hp.get(c, 0.0)))
            if lp < -6.0 * 3:                       # üçten fazla uymayan harf: aday değil
                break
        else:
            puanlar.append((lp + BAGLAM * kelime_puan(w), w, lp))
    duz_puan = duz_log + BAGLAM * kelime_puan(duz.lower())
    puanlar.sort(reverse=True)
    if not puanlar or puanlar[0][0] <= duz_puan:
        return duz, math.exp(duz_log / max(1, n)), False, duz.lower() in depo.kelime
    en_p, en, _ = puanlar[0]
    ikinci = max(duz_puan if duz.lower() != en else -1e9, puanlar[1][0] if len(puanlar) > 1 else -1e9)
    guven = 1 / (1 + math.exp(-(en_p - ikinci)))    # en iyi kelimenin ikinciye üstünlüğü
    yaz = "".join(c.upper() if k["adaylar"][0][0].isupper() else c for c, k in zip(en, kutular))
    return yaz, guven, yaz.lower() != duz.lower(), True


def baglam_uygula(satirlar, depo, baglam=True):
    """Her kutuya kararını yazar: k["harf"], k["guven"], k["baglam"] (bağlam harfi değiştirdi mi).
    -> (metin, kelime ayrıntıları)"""
    yazi, detay = [], []
    for satir in satirlar:
        gruplar, cur = [], []
        for k in satir:
            k["harf"], k["guven"], k["baglam"] = k["adaylar"][0][0], k["adaylar"][0][1], False
            if k["bosluk_once"] and cur:
                gruplar.append(cur); cur = []
            cur.append(k)
        if cur:
            gruplar.append(cur)
        parcalar, onceki = [], None
        for grup in gruplar:
            harf_i = [i for i, k in enumerate(grup) if k["adaylar"][0][0].isalnum()]
            if baglam and harf_i:
                a, b = harf_i[0], harf_i[-1] + 1
                w, guven, deg, sozluk = _kelime_sec(grup[a:b], depo, onceki)
                for c, k in zip(w, grup[a:b]):
                    if sozluk:
                        k["baglam"] = c != k["harf"]
                        k["harf"] = c
                        k["guven"] = max(k["guven"], guven) if not k["baglam"] else guven
                onceki = w.lower()
                detay.append({"kelime": w, "guven": round(guven, 3), "baglamla_degisti": deg,
                              "harfler": [[(h, round(p, 3), kaynak) for h, p, _, kaynak, _ in k["adaylar"][:3]]
                                          for k in grup[a:b]]})
            parcalar.append("".join(k["harf"] for k in grup))
        yazi.append(" ".join(parcalar))
    return "\n".join(yazi), detay


def oku(img, depo=None, genel=None, yakindan=True, baglam=True, ayrinti=False, daktilo=None):
    """Sayfa -> metin (ayrinti=True: (metin, kelime ayrıntıları))."""
    depo = depo or Depo()
    satirlar, _ = oku_kutular(img, depo, genel, yakindan, daktilo=daktilo)
    metin, detay = baglam_uygula(satirlar, depo, baglam)
    return (metin, detay) if ayrinti else metin


def baglam_ogret(yollar, depo=None, ilerleme=None):
    """Düz metin dosyalarından (.txt) kelime ve kelime çifti sıklıklarını öğrenir: cümle bağlamı.
    -> (dosya sayısı, depodaki kelime sayısı)"""
    depo = depo or Depo()
    n = 0
    for i, yol in enumerate(yollar):
        if ilerleme:
            ilerleme(i / max(1, len(yollar)), f"Bağlam öğreniliyor: {os.path.basename(yol)}")
        try:
            with open(yol, encoding="utf-8", errors="ignore") as f:
                depo.metin_ogren(f.read())
            n += 1
        except OSError:
            continue
    depo.kaydet()
    return n, len(depo.kelime)


def cizgi_kalinligi(parca, sb):
    """Bir harf kutusunun çizgi kalınlığı (satır boyuna oranla): mürekkep alanı / ana hat uzunluğu / satır boyu."""
    m = parca > 110
    if m.sum() < 6:
        return 0.0
    hat = int(ana_hat(m).sum())
    return float(m.sum()) / max(1, hat) / max(1, sb)


def seviye_bul(kalinlik, esik=VARYANT_ESIK):
    return SEVIYELER[0] if kalinlik < esik[0] else (SEVIYELER[1] if kalinlik < esik[1] else SEVIYELER[2])


def varyant_bul(parca, harf, depo, aile=None):
    """Kutudaki harf hangi varyasyona benziyor? -> (seviye, {seviye: uzaklık}) ya da (None, {}) (şablon yoksa)"""
    import numpy as np
    from PIL import Image
    cur = np.asarray(Image.fromarray(parca.clip(0, 255).astype(np.uint8)).resize((KALIP, KALIP), Image.Resampling.BOX),
                     dtype=np.float32)
    uz = {}
    for sv in SEVIYELER:
        t = depo.varyant_sablon(harf, sv, aile)
        if t is not None:
            uz[sv] = float(np.mean((cur - t) ** 2))
    if not uz:
        return None, {}
    return min(uz, key=uz.get), uz


def _mesafe_haritasi(K, R=8):
    """İskelet K'ya (bool) uzaklık haritası (piksel, R'de kesilir): yinelemeli genişletme."""
    import numpy as np
    from PIL import Image, ImageFilter
    dt = np.full(K.shape, float(R + 1), dtype=np.float32)
    dt[K] = 0.0
    cur = K.copy()
    for d in range(1, R + 1):
        cur = np.asarray(Image.fromarray(cur.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3)), dtype=bool)
        yeni = cur & (dt > R)
        dt[yeni] = d
    return dt


def yol_hizala(K, pts, olcekler=(0.9, 0.95, 1.0, 1.05, 1.1), kayma=4, dt=None):
    """Harfin ortak yolunu (pts, normalize) kutudaki harfin KENDİ ana hattına (K) oturtur: ölçek ve kaydırma araması.
    -> (skor: yolun noktalarının ana hatta ortalama uzaklığı [piksel], (xi, yi): oturan yol noktaları)"""
    import numpy as np
    h, w = K.shape
    if dt is None:
        dt = _mesafe_haritasi(K)
    en, sonuc = 1e9, None
    for sx in olcekler:
        for sy in olcekler:
            X0 = (pts[:, 0] - 0.5) * w * sx + w / 2 - 0.5
            Y0 = (pts[:, 1] - 0.5) * h * sy + h / 2 - 0.5
            for tx in range(-kayma, kayma + 1):
                xi = np.clip(np.rint(X0 + tx).astype(int), 0, w - 1)
                for ty in range(-kayma, kayma + 1):
                    yi = np.clip(np.rint(Y0 + ty).astype(int), 0, h - 1)
                    sk = float(dt[yi, xi].mean())
                    if sk < en:
                        en, sonuc = sk, (xi, yi)
    return en, sonuc


def yol_en_iyi(parca, adaylar, depo, aile=None, ust_n=3, sinir=3.0, ceza=1.5):
    """Harfin kimliğini YOLLA doğrular: ilk ust_n adayın ortak yolunu kutudaki harfin ana hattına oturtur; hem olasılığı
    hem oturması iyi olanı seçer (puan = log olasılık - ceza x uzaklık). -> (harf, skor, xi, yi) ya da None"""
    import numpy as np
    m = parca > 110
    if m.sum() < 12:
        return None
    K = ana_hat(m)
    if K.sum() < 4:
        return None
    dt = _mesafe_haritasi(K)
    en, sec = -1e9, None
    for h, p in adaylar[:ust_n]:
        pts = depo.yol_prototip(h, aile)
        if pts is None:
            continue
        skor, (xi, yi) = yol_hizala(K, pts, dt=dt)
        if skor > sinir:
            continue
        puan = float(np.log(max(p, 0.02))) - ceza * skor
        if puan > en:
            en, sec = puan, (h, skor, xi, yi)
    return sec


def yol_restore(parca, harf, depo, sb, aile=None, oran=0.6, hiz=0.6, nizami_kal=None, sinir=3.0, koruma=2, tol=1.0,
                hizali=None, ilk=None, kutle_alt=0.45):
    """HARFİN YOLUNA GÖRE inceltme: harfin ortak yolunu (örneklerin ortanca iskeleti) kutudaki harfe oturtur, yolun
    çevresinde bir BANT kurar ve bandın DIŞINDAKİ mürekkebi (taşma, dolmuş göz, leke) siler. Bant her adımda nizami
    kalınlığa doğru daralır (giderek incelir); yol üzerinde mürekkep eksikse hafifçe tamamlanır.
    -> (yeni_parca, bilgi) ya da None (yol yok / oturmuyor / zaten nizami)"""
    import numpy as np
    from PIL import Image, ImageFilter
    pts = depo.yol_prototip(harf, aile)
    if pts is None:
        return None
    m = parca > 110
    if m.sum() < 12:
        return None
    K = ana_hat(m)
    if K.sum() < 4:
        return None
    kal = float(m.sum()) / max(1, int(K.sum())) / max(1, sb)
    if nizami_kal is None:
        v = depo.varyant.get(aile or depo.aile, {}).get(harf, {}).get("nizami")
        nizami_kal = v[2] if v else 0.10
    r_cur, r_nizami = kal * sb / 2, nizami_kal * sb / 2
    band_min = r_nizami + tol
    if r_cur <= band_min:
        return None                                                    # zaten nizami kalınlıkta
    if hizali is not None:
        skor, xi, yi = hizali
    else:
        skor, (xi, yi) = yol_hizala(K, pts)
    if skor > sinir:
        return None                                                    # yol bu harfe oturmuyor: harf yanlış tanınmış olabilir
    br = max(band_min, r_cur - max(1.0, hiz * (r_cur - band_min)))     # bu adımın bant yarıçapı (giderek daralır)
    S = np.zeros(parca.shape, dtype=bool)
    S[yi, xi] = True
    dil = lambda a, r: np.asarray(Image.fromarray(a.astype(np.uint8) * 255).filter(
        ImageFilter.MaxFilter(2 * max(1, int(round(r))) + 1)), dtype=bool)
    bant = dil(S, br) | (dil(K, koruma) if koruma else False)          # harfin kendi ana hattı da korunur
    kaldir = oran * parca * (~bant)
    cekirdek = dil(S, r_nizami)
    yakin = dil(parca > 100, 3)
    ekle = 0.4 * oran * np.clip(200.0 - parca, 0, None) * (cekirdek & yakin)
    # KÜTLE BEKÇİSİ: kutu, ilk kalınlığından nizami kalınlığa inmek için gereken orandan fazla mürekkep kaybedemez
    # (yanlış tanınan / kötü oturan harfte gerçek çizgilerin silinmesini önler)
    if ilk is not None:
        ilk_kutle, ilk_r = ilk
        hedef = ilk_kutle * max(kutle_alt, min(1.0, (r_nizami + tol) / max(ilk_r, 1e-6)))
        simdi = float(parca.sum())
        if simdi <= hedef:
            return None                                                # beklenen inceliğe ulaştı: dur
        yeni_k = float((parca - kaldir + ekle).sum())
        if yeni_k < hedef:
            f = (simdi - hedef) / max(1e-6, simdi - yeni_k)           # silmeyi hedef kütleye kadar ölçekle
            kaldir, ekle = kaldir * f, ekle * f
    yeni = np.clip(parca - kaldir + ekle, 0, 255)
    return yeni, {"seviye": seviye_bul(kal), "hedef": "yol", "kalinlik": round(kal, 3), "bant": round(br, 1),
                  "oturma": round(skor, 2), "kaldirilan": float(kaldir.sum()) / 255, "eklenen": float(ekle.sum()) / 255}


_REF_YOL = {}


def _referans_yol(harf):
    """Harfin daktilo yazı tipinden çizilmiş NİZAMİ referansının ana hattı (normalize x, y) ya da None."""
    import numpy as np
    if harf in _REF_YOL:
        return _REF_YOL[harf]
    pts = None
    try:
        import cricroow
        r = cricroow.ince_referans(harf, 48, 48)
        if r is not None:
            hat = ana_hat(np.asarray(r, dtype=bool))
            ys, xs = np.nonzero(hat)
            if len(xs) >= 6:
                pts = np.stack([(xs + 0.5) / 48, (ys + 0.5) / 48], axis=1).astype(np.float32)
    except Exception:  # noqa: BLE001
        pts = None
    _REF_YOL[harf] = pts
    return pts


def _prototip_ciz(eski, m, pts, r_n, sb):
    """Harfin ortak yolunu (pts) bu kutudaki mürekkebin çerçevesine oturtup NİZAMİ kalınlıkta çizer. Kalın / dolmuş harfte
    (iskelet güvenilmez) de çalışır: yalnızca mürekkebin dış çerçevesine ve kütle merkezine bakar."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    h, w = eski.shape
    ys, xs = np.nonzero(m)
    K = ana_hat(m)
    kal = float(m.sum()) / max(1, int(K.sum()))                       # çizgi kalınlığı (piksel)
    dolu = float(m.mean())                                            # kutunun ne kadarı mürekkep (tamamen dolmuş hücre: ~1)
    gen_, yuk_ = xs.max() + 1 - xs.min(), ys.max() + 1 - ys.min()
    sis = max(0.0, kal / 2 - r_n)                                     # kalınlığın dışa taşırdığı pay: çerçeveyi o kadar daralt
    sis = min(sis, 0.12 * min(gen_, yuk_))                            # iskelet çöktüyse (dolu blok) pay şişmesin: harf noktaya inmesin
    bx0, bx1 = xs.min() + sis, xs.max() + 1 - sis
    by0, by1 = ys.min() + sis, ys.max() + 1 - sis
    if bx1 - bx0 < 2 or by1 - by0 < 2:
        return None
    X, Y = pts[:, 0] * w, pts[:, 1] * h
    px0, px1, py0, py1 = X.min(), X.max(), Y.min(), Y.max()
    sx = (bx1 - bx0) / max(1e-6, px1 - px0)
    sy = (by1 - by0) / max(1e-6, py1 - py0)
    X = bx0 + (X - px0) * sx
    Y = by0 + (Y - py0) * sy
    ky, kx = np.nonzero(K)
    if len(kx) >= 8 and dolu <= 0.55:                                 # ESNET (dolu blokta iskelet güvenilmez: esnetme yok): yolun her noktası harfin kendi ana hattına doğru çekilir
        for _ in range(2):
            P = np.stack([X, Y], 1)
            Q = np.stack([kx + 0.5, ky + 0.5], 1).astype(np.float64)
            d2 = ((P[:, None, :] - Q[None, :, :]) ** 2).sum(2)
            en = d2.argmin(1)
            fark = Q[en] - P
            uz = np.sqrt((fark ** 2).sum(1))
            fark[uz > 0.25 * max(w, h)] = 0                           # çok uzaktaki iskelet başka bir şeydir (leke)
            dp = ((P[:, None, :] - P[None, :, :]) ** 2).sum(2)
            kom = np.argsort(dp, 1)[:, :6]
            duz = fark[kom].mean(1)                                   # komşularla yumuşat: şekil bozulmadan esner
            X, Y = X + 0.6 * duz[:, 0], Y + 0.6 * duz[:, 1]
    cim = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(cim)
    r = max(0.9, r_n, 0.5 * w / YOL * max(sx, 1.0) * 0.7)
    for x_, y_ in zip(X, Y):
        dr.ellipse([x_ - r, y_ - r, x_ + r, y_ + r], fill=255)
    cim = cim.filter(ImageFilter.GaussianBlur(0.5))
    seviye = max(200.0, float(np.percentile(eski[m], 90)))
    return np.asarray(cim, dtype=np.float32) / 255.0 * seviye


# ---------------------------------------------------------------- elle düzenlemeden öğrenme (fırça: sil / çiz)
LEKE_EN_AZ = 3        # kural çıkarmak için gereken, elle silinmiş iz sayısı
BENZERLIK_TURUNCU = 0.40   # harf hafızasına bu oranın altında benzeyen iz = turuncu (silinecek aday)
BOLGE_EN_AZ = 2        # bölge kuralı için gereken büyük fırça temizliği sayısı


def bilesenler(m):
    """Bool maskenin 8-komşu bağlı bileşenleri (numpy; çalışma uzunluğu + birleştirme-bulma).
    -> (etiket int32 (0 = arka plan), n, kutu (n+1, 4): x0, x1, y0, y1 (x1/y1 dahil değil), alan (n+1))"""
    import numpy as np
    H, W = m.shape
    pd = np.pad(m.astype(np.int8), ((0, 0), (1, 1)))
    d = np.diff(pd, axis=1)
    ys, xs = np.nonzero(d == 1)
    _, xe = np.nonzero(d == -1)
    n = len(xs)
    etiket = np.zeros((H, W), dtype=np.int32)
    if n == 0:
        return etiket, 0, np.zeros((1, 4), dtype=np.int32), np.zeros(1, dtype=np.int64)
    ust = list(range(n))

    def bul(i):
        while ust[i] != i:
            ust[i] = ust[ust[i]]
            i = ust[i]
        return i
    bas = np.searchsorted(ys, np.arange(H + 1))
    for y in range(1, H):
        a0, a1, b0, b1 = bas[y - 1], bas[y], bas[y], bas[y + 1]
        i, j = a0, b0
        while i < a1 and j < b1:
            if xs[i] <= xe[j] and xs[j] <= xe[i]:                 # çapraz değmeyi de say (8-komşu)
                ri, rj = bul(i), bul(j)
                if ri != rj:
                    ust[rj] = ri
            if xe[i] < xe[j]:
                i += 1
            else:
                j += 1
    kok = np.array([bul(i) for i in range(n)])
    _, kimlik = np.unique(kok, return_inverse=True)
    kimlik = kimlik + 1
    for y, a_, b_, k in zip(ys.tolist(), xs.tolist(), xe.tolist(), kimlik.tolist()):
        etiket[y, a_:b_] = k
    m_ = int(kimlik.max())
    kutu = np.zeros((m_ + 1, 4), dtype=np.int32)
    kutu[:, 0], kutu[:, 2] = 10 ** 9, 10 ** 9
    np.minimum.at(kutu[:, 0], kimlik, xs)
    np.maximum.at(kutu[:, 1], kimlik, xe)
    np.minimum.at(kutu[:, 2], kimlik, ys)
    np.maximum.at(kutu[:, 3], kimlik, ys + 1)
    alan = np.bincount(etiket.ravel(), minlength=m_ + 1).astype(np.int64)
    alan[0] = 0
    return etiket, m_, kutu, alan


def satir_olcusu(kap):
    """Sayfa kapsamasından (PIL L ya da numpy) satır bantları ve ortanca satır boyu: ([(ust, alt)], sb)"""
    import numpy as np
    from PIL import Image
    img = kap if hasattr(kap, "crop") else Image.fromarray(np.clip(kap, 0, 255).astype(np.uint8))
    try:
        satir = satirlar_belge(kenarsiz(img))
    except Exception:  # noqa: BLE001
        satir = []
    if not satir:
        return [], 30
    return satir, max(8, sorted(a - u for u, a in satir)[len(satir) // 2])


def _ozellikler(etiket, kutu, alan, kap, idler, bantlar, sb):
    """Bileşenlerin boyuta (sb) göre özellikleri: alan, genişlik, yükseklik, doluluk, satır içi yükseklik, yalnızlık, ton."""
    import numpy as np
    agirlik = np.bincount(etiket.ravel(), weights=np.asarray(kap, dtype=np.float64).ravel(), minlength=len(alan))
    x0, x1, y0, y1 = kutu[:, 0], kutu[:, 1], kutu[:, 2], kutu[:, 3]
    out = []
    for i in idler:
        w, h = int(x1[i] - x0[i]), int(y1[i] - y0[i])
        cy = (y0[i] + y1[i]) / 2
        if bantlar:
            u, a = min(bantlar, key=lambda b: 0 if b[0] <= cy <= b[1] else min(abs(cy - b[0]), abs(cy - b[1])))
            yuk = (cy - u) / max(1, a - u)
        else:
            yuk = 0.5
        gx = np.maximum(0, np.maximum(x0, x0[i]) - np.minimum(x1, x1[i]))
        gy = np.maximum(0, np.maximum(y0, y0[i]) - np.minimum(y1, y1[i]))
        uz = np.sqrt(gx.astype(np.float64) ** 2 + gy.astype(np.float64) ** 2)
        uz[i] = 1e9
        uz[0] = 1e9
        izole = float(uz.min()) / sb
        out.append({"alan": float(alan[i]) / (sb * sb), "w": w / sb, "h": h / sb, "dolu": float(alan[i]) / max(1, w * h),
                    "yuk": float(yuk), "izole": min(izole, 5.0), "ton": float(agirlik[i]) / max(1, alan[i]) / 255.0})
    return out


def leke_kaydi(kap_once, kap_sonra, bolge, bantlar, sb, esik=110, depo=None):
    """Fırçayla SİLİNEN izlerin özellikleri: bolge (x0, y0, x1, y1) fırça darbesinin sınırı. Bir iz, mürekkebinin en az %60'ı
    silindiyse 'elle silinen leke' sayılır; kısmen silinen (harfin parçası) sayılmaz. -> [özellik sözlüğü]"""
    import numpy as np
    x0, y0, x1, y1 = bolge
    pay = int(3 * sb)
    H, W = kap_once.shape
    a0, b0, a1, b1 = max(0, x0 - pay), max(0, y0 - pay), min(W, x1 + pay), min(H, y1 + pay)
    once = np.asarray(kap_once)[b0:b1, a0:a1]
    sonra = np.asarray(kap_sonra)[b0:b1, a0:a1]
    mo = once > esik
    if mo.sum() < 3:
        return []
    et, n, kutu, alan = bilesenler(mo)
    sil = np.bincount(et.ravel(), weights=(mo & (sonra <= esik)).ravel().astype(np.float64), minlength=n + 1)
    idler = [i for i in range(1, n + 1)
             if alan[i] >= 3 and sil[i] / alan[i] >= 0.5
             and kutu[i, 0] > 0 and kutu[i, 2] > 0 and kutu[i, 1] < mo.shape[1] and kutu[i, 3] < mo.shape[0]]
    bant_yerel = [(u - b0, a - b0) for u, a in bantlar]
    oz = _ozellikler(et, kutu, alan, once, idler, bant_yerel, sb)
    for i, f in zip(idler, oz):                                    # silinen izin şablonu + Croow'un onu neye benzettiği (silmeden ÖNCE)
        xx0, xx1, yy0, yy1 = (int(v) for v in kutu[i])
        parca = np.where(et[yy0:yy1, xx0:xx1] == i, once[yy0:yy1, xx0:xx1], 0)
        f["sab"] = iz_sablonu(parca)
        f["benz_once"], f["harf_once"] = referans_benzerligi(parca, depo)
    return oz


def leke_kurali(kayitlar, gevsek=0.0):
    """Elle silinen izlerin özelliklerinden kural çıkarır (en az LEKE_EN_AZ örnek). Aralıklar ÖRNEKLERİN İÇİNDEN ve
    biraz payla alınır; noktalama (satır altı) ve 'i' noktası (gövdeye yakın) dışarıda kalacak şekilde sıkıdır."""
    import numpy as np
    if len(kayitlar) < LEKE_EN_AZ:
        return None
    A = {k: np.array([r[k] for r in kayitlar], dtype=np.float64) for k in ("alan", "dolu", "yuk", "izole")}
    yuk_ust = float(np.percentile(A["yuk"], 95)) + 0.2
    if float(np.mean(A["yuk"] > 0.8)) < 0.3:                       # satır tabanı = nokta / virgül: silinenler orada değilse korunur
        yuk_ust = min(yuk_ust, 0.8)
    # az örnekten aşırı daraltılmış kural çıkmasın: boyutta ~1.8 kat alan payı, yalnızlıkta en az 0.3 satır boyu ('i' noktası
    # gövdeye daha yakındır, noktalama satır tabanındadır: ikisi de dışarıda kalır)
    g = max(0.0, min(1.0, gevsek))                                 # esneklik: 0 = örneklere sıkı, 1 = gevşek (silmeyi esnet)
    return {"alan_ust": min(max((1.4 + 0.6 * g) * float(np.percentile(A["alan"], 90)), 0.08 + 0.04 * g), 0.25),
            "dolu_alt": max(0.2, (0.9 - 0.2 * g) * float(np.percentile(A["dolu"], 10))),
            "izole_alt": max(0.0, 0.7 * float(np.percentile(A["izole"], 10)) * (1 - 0.4 * g)),   # kullanıcı harfe yakın izi sildiyse eşik de düşer
            "yuk_alt": float(np.percentile(A["yuk"], 5)) - 0.1 - 0.15 * g, "yuk_ust": yuk_ust + 0.05 * g,
            "ornek": len(kayitlar), "gevsek": g}


def leke_bul(kap, kural, bantlar, sb, yasak=None, esik=110, depo=None, benz_ust=BENZERLIK_TURUNCU):
    """Sayfada (kapsama) kurala uyan izleri bulur: [(x0, x1, y0, y1, id)] ve etiket dizisi. yasak: dokunulmayacak bool maske
    (karartma, tarama kenarı)."""
    import numpy as np
    if not kural:
        return [], None
    m = np.asarray(kap) > esik
    et, n, kutu, alan = bilesenler(m)
    if n == 0:
        return [], et
    idler = [i for i in range(1, n + 1) if 2 <= alan[i] <= kural["alan_ust"] * sb * sb * 1.01]
    oz = _ozellikler(et, kutu, alan, kap, idler, bantlar, sb)
    out = []
    for i, f in zip(idler, oz):
        if (f["alan"] <= kural["alan_ust"] and f["dolu"] >= kural["dolu_alt"] and f["izole"] >= kural["izole_alt"]
                and kural["yuk_alt"] <= f["yuk"] <= kural["yuk_ust"]):
            if yasak is not None and yasak[kutu[i, 2]:kutu[i, 3], kutu[i, 0]:kutu[i, 1]].any():
                continue
            if benz_ust is not None and _iz_benzerligi(et, kutu, i, kap, depo) >= benz_ust:
                continue                                           # harf hafızasına %40+ benziyor: harf olabilir, turuncu değil
            out.append((int(kutu[i, 0]), int(kutu[i, 1]), int(kutu[i, 2]), int(kutu[i, 3]), i))
    return out, et


BENZERLIK_ALT = 0.20   # referans harfe bu benzerlik ve üstü: hafif incelt; altında: benzerlik 0'a yaklaştıkça silmeye doğru
_SABLON = {}


def _harf_sablonlari():
    """Alfabenin (a-z, A-Z, 0-9) daktilo yazı tipinden çizilmiş nizami referansları: {harf: 24x24 sıfır ortalamalı birim vektör}."""
    import numpy as np
    from PIL import Image
    if _SABLON:
        return _SABLON
    try:
        import cricroow
    except Exception:  # noqa: BLE001
        return _SABLON
    for h in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        r = cricroow.ince_referans(h, 48, 48)
        if r is None:
            continue
        t = np.asarray(Image.fromarray(np.asarray(r, dtype=np.uint8) * 255).resize((KALIP, KALIP), Image.Resampling.BOX),
                       dtype=np.float32) / 255.0
        t = t - t.mean()
        n = float(np.sqrt((t * t).sum()))
        if n > 1e-6:
            _SABLON[h] = (t / n).ravel()
    return _SABLON


_HAF_ONB = {}


def harf_hafizasi(depo=None):
    """Harf hafızası: alfabenin yazı tipi referansları + (varsa) deponun ÖĞRENİLMİŞ harf kalıpları (kirli de olsa o belgenin
    harfi). {anahtar: 24x24 sıfır ortalamalı birim vektör}"""
    import numpy as np
    S = dict(_harf_sablonlari())
    if depo is not None and getattr(depo, "kalip", None):
        anah = (id(depo), len(depo.kalip), sum(v[0] for v in depo.kalip.values()))
        if anah not in _HAF_ONB:
            _HAF_ONB.clear()
            ek = {}
            for h, (n, d) in depo.kalip.items():
                t = np.asarray(d, dtype=np.float32) / 255.0
                if t.size != KALIP * KALIP:
                    continue
                t = t - t.mean()
                nn = float(np.sqrt((t * t).sum()))
                if nn > 1e-6:
                    ek["ö:" + h] = (t / nn).ravel()
            _HAF_ONB[anah] = ek
        S.update(_HAF_ONB[anah])
    return S


def referans_benzerligi(parca, depo=None):
    """Bir izin (kapsama parçası, 0..255) harf hafızasındaki harflerden en çok hangisine ne kadar benzediği:
    (benzerlik 0..1, harf). Boyuta bağlı değil: iz 24x24'e oturtulup ilinti (korelasyon) alınır."""
    import numpy as np
    from PIL import Image
    S = harf_hafizasi(depo)
    if not S:
        return 0.0, None
    a = np.asarray(Image.fromarray(np.clip(parca, 0, 255).astype(np.uint8)).resize((KALIP, KALIP), Image.Resampling.BOX),
                   dtype=np.float32) / 255.0
    a = a - a.mean()
    n = float(np.sqrt((a * a).sum()))
    if n < 1e-6:
        return 0.0, None
    a = (a / n).ravel()
    K = korunan_vektorleri(depo)
    if K is not None and float((K @ a).max()) >= 0.8:             # 'Metin / karartma / damga / imza' diye öğretilene benziyor: KORUNUR
        return 1.0, "korunan"
    en, hh = 0.0, None
    for h, t in S.items():
        c = float(a @ t)
        if c > en:
            en, hh = c, h
    N = leke_sablon_vektorleri(depo)
    if N is not None:                                              # SİLDİKÇE ÖĞRENİR: silinen izlere benzeyen şekil, o harfe artık
        ls = float((N @ a).max())                                   # benzemiş sayılmaz (benzerlik silinen şekle yakınlık kadar düşer)
        en = en - max(0.0, ls - en)                                 # yalnızca silinen şekle harflerden DAHA çok benziyorsa düşer
    return max(0.0, en), hh.replace("ö:", "") if hh else None


_LS_ONB = {}


def leke_sablon_vektorleri(depo):
    """Elle silinen izlerin şablonları: (N, 576) sıfır ortalamalı birim vektörler ya da None."""
    import numpy as np
    if depo is None:
        return None
    L = getattr(depo, "duzenleme", {}).get("leke_sablon", [])
    if not L:
        return None
    anah = (id(depo), len(L), int(L[-1][0]) if L[-1] else 0, int(sum(L[-1][:48])) if L[-1] else 0)
    if anah not in _LS_ONB:
        _LS_ONB.clear()
        V = []
        for r in L:
            t = np.asarray(r, dtype=np.float32) / 255.0
            if t.size != KALIP * KALIP:
                continue
            t = t - t.mean()
            n = float(np.sqrt((t * t).sum()))
            if n > 1e-6:
                V.append(t / n)
        _LS_ONB[anah] = np.stack(V) if V else None
    return _LS_ONB[anah]


_KR_ONB = {}


def korunan_vektorleri(depo):
    """'Metin / karartma / damga / imza' diye öğretilen izlerin şablonları: (N, 576) birim vektörler ya da None."""
    import numpy as np
    if depo is None:
        return None
    L = getattr(depo, "duzenleme", {}).get("korunan_sablon", [])
    if not L:
        return None
    anah = (id(depo), len(L), int(sum(L[-1][:48])) if L[-1] else 0)
    if anah not in _KR_ONB:
        _KR_ONB.clear()
        V = []
        for r in L:
            t = np.asarray(r, dtype=np.float32) / 255.0
            if t.size != KALIP * KALIP:
                continue
            t = t - t.mean()
            n = float(np.sqrt((t * t).sum()))
            if n > 1e-6:
                V.append(t / n)
        _KR_ONB[anah] = np.stack(V) if V else None
    return _KR_ONB[anah]


def cizgi_kurali(kayitlar):
    """'Alt çizgi' diye öğretilen izlerden: yatay uzun ince iz kuralı (satır boyuna oranla) ya da None."""
    import numpy as np
    if not kayitlar:
        return None
    w = np.array([r["w"] for r in kayitlar], dtype=np.float64)
    h = np.array([r["h"] for r in kayitlar], dtype=np.float64)
    return {"w_alt": 0.8 * float(w.min()), "h_ust": 1.3 * float(h.max()), "en_boy": 5.0, "ornek": len(kayitlar)}


def cizgi_bul(kap, kural, sb, yasak=None, esik=110):
    """Kurala uyan yatay çizgi izleri: [(x0, x1, y0, y1, id)] ve etiket dizisi."""
    import numpy as np
    if not kural:
        return [], None
    et, n, kutu, alan = bilesenler(np.asarray(kap) > esik)
    out = []
    for i in range(1, n + 1):
        x0, x1, y0, y1 = (int(v) for v in kutu[i])
        w, h = x1 - x0, max(1, y1 - y0)
        if w >= kural["w_alt"] * sb and h <= kural["h_ust"] * sb and w / h >= kural["en_boy"]:
            if yasak is not None and yasak[y0:y1, x0:x1].any():
                continue
            out.append((x0, x1, y0, y1, i))
    return out, et


def ozel_bul(kap, depo, sb, esik=0.5, esik_cos=0.5):
    """Kullanıcının AÇTIĞI kategorilere benzeyen izler: her iz için kategori başına olasılık (en benzeyen örneğin 24x24
    ilintisi ve boyut yakınlığından). -> [(x0, x1, y0, y1, ad, olasılık, eylem)] olasılığa göre azalan (en çok 600)."""
    import numpy as np
    ornek = getattr(depo, "duzenleme", {}).get("ozel", [])
    if not ornek:
        return []
    V, M = [], []
    for r in ornek:
        t = np.asarray(r["sab"], dtype=np.float32) / 255.0
        t = t - t.mean()
        n = float(np.sqrt((t * t).sum()))
        if n > 1e-6:
            V.append(t / n)
            M.append((r["ad"], r.get("eylem", "isaretle"), max(1e-4, float(r.get("alan", 0.05)))))
    if not V:
        return []
    V = np.stack(V)
    et, n, kutu, alan = bilesenler(np.asarray(kap) > 110)
    out = []
    for i in range(1, n + 1):
        if not (3 <= alan[i] <= 4 * sb * sb):
            continue
        x0, x1, y0, y1 = (int(v) for v in kutu[i])
        parca = np.where(et[y0:y1, x0:x1] == i, np.asarray(kap)[y0:y1, x0:x1], 0)
        from PIL import Image
        a = np.asarray(Image.fromarray(np.clip(parca, 0, 255).astype(np.uint8)).resize((KALIP, KALIP), Image.Resampling.BOX),
                       dtype=np.float32) / 255.0
        a = a - a.mean()
        nn = float(np.sqrt((a * a).sum()))
        if nn < 1e-6:
            continue
        c = V @ (a / nn).ravel()
        eniyi = {}
        for k, (ad, ey, al) in enumerate(M):
            boyut = min(alan[i] / (sb * sb), al) / max(alan[i] / (sb * sb), al)        # alan oranı yakınlığı (1 = aynı boyut)
            p = max(0.0, (float(c[k]) - esik_cos) / (1 - esik_cos)) * (0.4 + 0.6 * boyut)
            if p > eniyi.get(ad, (0, ey))[0]:
                eniyi[ad] = (p, ey)
        if not eniyi:
            continue
        ad, (p, ey) = max(eniyi.items(), key=lambda kv: kv[1][0])
        if p >= esik * 0.5:
            out.append((x0, x1, y0, y1, ad, min(1.0, p), ey))
    out.sort(key=lambda r: -r[5])
    return out[:600]


def iz_sablonu(parca):
    """Bir izin (kapsama parçası) 24x24 şablonu: 576 tamsayı (0..255)."""
    import numpy as np
    from PIL import Image
    return [int(v) for v in np.asarray(Image.fromarray(np.clip(parca, 0, 255).astype(np.uint8)).resize(
        (KALIP, KALIP), Image.Resampling.BOX), dtype=np.uint8).ravel()]


def _iz_benzerligi(et, kutu, i, kap, depo=None):
    import numpy as np
    x0, x1, y0, y1 = (int(v) for v in kutu[i])
    parca = np.where(et[y0:y1, x0:x1] == i, np.asarray(kap)[y0:y1, x0:x1], 0)
    return referans_benzerligi(parca, depo)[0]


BOLGE_EN_AZ = 2        # bölge kuralı için gereken büyük fırça temizliği sayısı
BENZERLIK_TURUNCU = 0.40   # harf hafızasına bu oranın altında benzeyen iz = turuncu (silinecek aday)


def bolge_kaydi(kap_once, kap_sonra, maske, kutu, sb, depo=None, esik=110):
    """BÜYÜK fırçayla temizlenen bölgenin özellikleri (fırça maskesi içinde): mürekkep yoğunluğu, bileşen yoğunluğu, büyük
    (kocaman birleşik) izlerin mürekkep payı, HARFE BENZEYEN izlerin mürekkep payı. -> sözlük ya da None (anlamlı değil)"""
    import numpy as np
    x0, y0, x1, y1 = kutu
    once = np.asarray(kap_once)[y0:y1, x0:x1]
    mo = (once > esik)
    mk = np.asarray(maske, dtype=bool)
    if mk.sum() < (1.5 * sb) ** 2 or (mo & mk).sum() < 0.01 * mk.sum():
        return None                                                  # küçük alan ya da zaten boş kâğıt
    sonra = np.asarray(kap_sonra)[y0:y1, x0:x1] > esik
    silinen = float((mo & mk & ~sonra).sum()) / max(1.0, float((mo & mk).sum()))
    if silinen < 0.5:
        return None
    et, n, kt, alan = bilesenler(mo)
    mur = np.bincount(et[mk].ravel(), minlength=n + 1).astype(np.float64)
    top = float(mur[1:].sum()) or 1.0
    buyuk = float(mur[1:][alan[1:] > 1.0 * sb * sb].sum()) / top
    harf = 0.0
    for i in range(1, n + 1):
        if mur[i] <= 0:
            continue
        if 0.1 * sb * sb <= alan[i] <= 1.5 * sb * sb and _iz_benzerligi(et, kt, i, once, depo) >= BENZERLIK_TURUNCU:
            harf += mur[i]
    sayi = int((mur[1:] > 0).sum())
    return {"yog": float((mo & mk).sum()) / float(mk.sum()), "bilesen": sayi / max(1.0, float(mk.sum()) / (sb * sb)),
            "buyuk": buyuk, "harf": harf / top}


def bolge_kurali(kayitlar):
    """Büyük fırça temizliklerinden: hangi tür bölgeler (yoğun, büyük birleşik izli, harfe benzemeyen) temizlenir."""
    import numpy as np
    if len(kayitlar) < BOLGE_EN_AZ:
        return None
    A = {k: np.array([r[k] for r in kayitlar], dtype=np.float64) for k in ("yog", "buyuk", "harf")}
    return {"yog_alt": 0.75 * float(np.percentile(A["yog"], 10)), "buyuk_alt": 0.7 * float(np.percentile(A["buyuk"], 10)),
            "harf_ust": min(0.5, max(0.2, 1.5 * float(np.percentile(A["harf"], 90)))), "ornek": len(kayitlar)}


def riskli_temizle(kap, hedef, bantlar, sb, depo=None, esik=110):
    """Seçili alanı (hedef: bool maske) RİSKLİ temizler. İçinde YAZI mı LEKE mi olduğunu anlar:
    - yazı gibi izler (harf hafızasına >= %40 benzeyen harf boyutlu izler ya da satır içindeki kelime bloğu boyutlu izler)
      alanın mürekkebinin %8'inden azsa alan düpedüz lekedir: HEPSİ silinir;
    - yazı varsa yazı gibi izler KORUNUR, diğer izler (leke, toz, kocaman birleşik karartma) silinir.
    Hedefin kenarını aşan iz bütün olarak değerlendirilir, yalnızca hedefin içindeki pikselleri silinir.
    -> (silinecek bool maske, tanı sözlüğü)"""
    import numpy as np
    m = np.asarray(kap) > esik
    sil = np.zeros(m.shape, dtype=bool)
    et, n, kutu, alan = bilesenler(m)
    tani = {"hedef_iz": 0, "yazi_gibi": 0, "silinen_iz": 0, "yazi_orani": 0.0, "sonuc": "alanda mürekkep yok"}
    if n == 0:
        return sil, tani
    ic = np.bincount(et[hedef & m].ravel(), minlength=n + 1)
    ids = [i for i in range(1, n + 1) if ic[i] > 0]
    tani["hedef_iz"] = len(ids)
    if not ids:
        return sil, tani

    def yazimi(i):
        x0, x1, y0, y1 = (int(v) for v in kutu[i])
        w, h, a = x1 - x0, y1 - y0, float(alan[i])
        if 0.1 * sb * sb <= a <= 1.5 * sb * sb and _iz_benzerligi(et, kutu, i, kap, depo) >= BENZERLIK_TURUNCU:
            return True                                                    # harf hafızasına benziyor
        cy = (y0 + y1) / 2
        for u, a_ in bantlar:                                              # YAZI SATIRI: izin ortası bir satır bandında,
            bh = a_ - u                                                    # yüksekliği bandı çok aşmıyor (satırlar arası lekeler aşar)
            if u - 0.15 * bh <= cy <= a_ + 0.15 * bh:
                return bool(h <= 1.4 * bh and w <= 14 * sb and a / float(max(1, w * h)) <= 0.55)
        return False
    yazi = [i for i in ids if yazimi(i)]
    if yazi:                                                                # yazıya bitişik küçük iz = noktalama / 'i' noktası: koru
        yx0, yx1, yy0, yy1 = kutu[yazi, 0], kutu[yazi, 1], kutu[yazi, 2], kutu[yazi, 3]
        kume = set(yazi)
        for i in ids:
            if i in kume or alan[i] > 0.35 * sb * sb:
                continue
            gx = np.maximum(0, np.maximum(yx0, kutu[i, 0]) - np.minimum(yx1, kutu[i, 1]))
            gy = np.maximum(0, np.maximum(yy0, kutu[i, 2]) - np.minimum(yy1, kutu[i, 3]))
            if float(np.sqrt(gx.astype(np.float64) ** 2 + gy.astype(np.float64) ** 2).min()) <= 0.8 * sb:
                yazi.append(i)
    toplam = float(ic[ids].sum())
    oran = float(ic[yazi].sum()) / toplam if yazi else 0.0
    tani.update(yazi_gibi=len(yazi), yazi_orani=round(oran, 3))
    if oran < 0.08:
        sil = hedef & m
        tani.update(silinen_iz=len(ids), sonuc="alanda yazı yok: hepsi leke sayıldı ve silindi")
    else:
        sil = hedef & m & ~np.isin(et, yazi)
        tani.update(silinen_iz=len(ids) - len(yazi), sonuc="alanda yazı var: yazı gibi izler korundu, diğerleri silindi")
    return sil, tani


def sekizgen_noktalar(maske):
    """Bool maskedeki izi saran SIKI SEKİZGEN: 8 yönde (0, 45, ..., 315 derece) iz noktalarının en uç çizgileri alınır, komşu
    çizgilerin kesişimi köşe olur. -> [(x, y)] 8 köşe (maske koordinatı) ya da None (iz yok)."""
    import numpy as np
    ys, xs = np.nonzero(maske)
    if len(xs) < 3:
        return None
    X, Y = xs + 0.5, ys + 0.5
    N = [(np.cos(a), np.sin(a)) for a in np.arange(8) * np.pi / 4]
    h = [float((n[0] * X + n[1] * Y).max()) + 0.5 for n in N]       # her yönde en uç çizgi (yarım piksel pay)
    pts = []
    for k in range(8):
        n1, n2 = N[k], N[(k + 1) % 8]
        A = np.array([[n1[0], n1[1]], [n2[0], n2[1]]])
        try:
            x, y = np.linalg.solve(A, np.array([h[k], h[(k + 1) % 8]]))
        except np.linalg.LinAlgError:
            return None
        pts.append((float(x), float(y)))
    return pts


def poligon_maskesi(poly, genislik, yukseklik, ox=0, oy=0):
    """Çokgenin (resim koordinatı) bool maskesi: (yukseklik, genislik) boyutunda, (ox, oy) başlangıçlı yerel koordinatla."""
    import numpy as np
    from PIL import Image, ImageDraw
    m = Image.new("L", (int(genislik), int(yukseklik)), 0)
    ImageDraw.Draw(m).polygon([(x - ox, y - oy) for x, y in poly], fill=255)
    return np.asarray(m, dtype=bool)


def bolge_karosu(sb):
    """Bölge taramasında karo kenarı (piksel): bir satır boyu."""
    return max(12, int(sb))


def bolge_bul(kap, kural, sb, depo=None, yasak=None, esik=110):
    """Sayfada, temizlenen bölgelere benzeyen karoları bulur (karo = 1 satır boyu). Karoda harfe benzeyen iz payı sınırı
    aşarsa yazı sayılır, dokunulmaz. -> ([(x0, y0, x1, y1)], {karo: silinecek iz kimlikleri}, etiket dizisi)"""
    import numpy as np
    if not kural:
        return [], {}, None
    m = np.asarray(kap) > esik
    H, W = m.shape
    T = bolge_karosu(sb)
    et, n, kutu, alan = bilesenler(m)
    harf_flag = {}

    def harfmi(i):
        if i not in harf_flag:
            harf_flag[i] = bool(0.1 * sb * sb <= alan[i] <= 1.5 * sb * sb and
                                _iz_benzerligi(et, kutu, i, kap, depo) >= BENZERLIK_TURUNCU)
        return harf_flag[i]
    out, plan = [], {}
    for ty in range(0, H, T):
        for tx in range(0, W, T):
            sub = et[ty:ty + T, tx:tx + T]
            mm = sub > 0
            top = int(mm.sum())
            if top < 0.05 * T * T or top / float(sub.size) < 0.8 * kural["yog_alt"]:
                continue
            if yasak is not None and yasak[ty:ty + T, tx:tx + T].any():
                continue
            say = np.bincount(sub[mm].ravel(), minlength=n + 1)
            ids = np.nonzero(say)[0]
            ids = ids[ids > 0]
            buyuk = float(sum(say[i] for i in ids if alan[i] > 1.0 * sb * sb)) / top
            harf = float(sum(say[i] for i in ids if harfmi(int(i)))) / top
            if buyuk >= kural["buyuk_alt"] and harf <= kural["harf_ust"]:
                out.append((tx, ty, min(W, tx + T), min(H, ty + T)))
                plan[(tx, ty)] = [int(i) for i in ids if not harfmi(int(i))]
    return out, plan, et


def siyah_leke_tara(kap, bantlar, sb, risk=0.5, yasak=None, esik=110, depo=None):
    """SİYAH LEKE / TOZ. İki sınıf:
    1) TOZ: noktalamadan (nokta, 'i' noktası) da küçük izler (alan <= 0.04 sb^2). Yalnızca BÜYÜK izlerden (harf gövdesi)
       uzak olmaları (>= 0.8 sb: bir harf adımı; noktalama harfin yanındadır) gerekir; başka tozlara yakınlık sorun değil. Silinir (güç risk ile ölçeklenir).
    2) SİYAH LEKE: yüzdesel olarak dolu (>= %60), koyu, harfe bitişik olmayan küçük iz. Referans harflere benzerlik >=
       BENZERLIK_ALT -> hafif INCELT; altında -> benzerlik 0'a yaklaştıkça silmeye yaklaşan güç. ŞÜPHELİYSE GEÇ: satır
       tabanındaki nokta, harf boyutunda dolu ve hiçbir harfe benzemeyen iz.
    -> ([(x0, x1, y0, y1, id, benzerlik, 'sil'|'incelt'|'gec', güç)], etiket dizisi, tanı sözlüğü)"""
    import numpy as np
    risk = max(0.0, min(1.0, risk))
    m = np.asarray(kap) > esik
    et, n, kutu, alan = bilesenler(m)
    tani = {"iz": int(n), "toz_silinen": 0, "elenen_koyu_dolu_degil": 0, "elenen_harfe_bitisik": 0, "elenen_noktalama": 0,
            "elenen_yasak_bolge": 0, "elenen_buyuk": 0}
    if n == 0:
        return [], et, tani
    sb2 = float(sb) * sb
    buyuk = alan > 0.05 * sb2                                       # toz ve noktalamadan büyük: harf gövdesi / çizgi
    bx0, bx1, by0, by1 = kutu[:, 0], kutu[:, 1], kutu[:, 2], kutu[:, 3]
    idler = [i for i in range(1, n + 1) if 3 <= alan[i] <= 0.9 * sb2]
    tani["elenen_buyuk"] = int(n) - len(idler)
    oz = _ozellikler(et, kutu, alan, kap, idler, bantlar, sb)
    out = []
    for i, f in zip(idler, oz):
        x0, x1, y0, y1 = (int(v) for v in kutu[i])
        if yasak is not None and yasak[y0:y1, x0:x1].any():
            tani["elenen_yasak_bolge"] += 1
            continue
        if f["alan"] <= 0.04 and f["ton"] >= 0.5:                   # TOZ: büyük izlere yakın değilse sil
            gx = np.maximum(0, np.maximum(bx0, x0) - np.minimum(bx1, x1))
            gy = np.maximum(0, np.maximum(by0, y0) - np.minimum(by1, y1))
            uz = np.sqrt(gx.astype(np.float64) ** 2 + gy.astype(np.float64) ** 2)
            uz[~buyuk] = 1e9
            uz[0] = 1e9
            if float(uz.min()) >= 0.8 * sb:                         # noktalama harfin hemen yanındadır; toz ondan uzaktır
                out.append((x0, x1, y0, y1, i, 0.0, "sil", 0.6 + 0.4 * risk))
                tani["toz_silinen"] += 1
            else:
                tani["elenen_harfe_bitisik"] += 1
            continue
        if f["dolu"] < 0.6 or f["ton"] < 0.75:                      # siyah leke değil (harf gibi ince çizgili)
            tani["elenen_koyu_dolu_degil"] += 1
            continue
        if 0.78 <= f["yuk"] <= 1.15 and f["alan"] <= 0.3:           # satır tabanındaki küçük nokta: noktalama / virgül
            tani["elenen_noktalama"] += 1
            continue
        if f["izole"] < 0.3:                                        # harfe bitişik / 'i' noktası
            tani["elenen_harfe_bitisik"] += 1
            continue
        parca = np.where(et[y0:y1, x0:x1] == i, np.asarray(kap)[y0:y1, x0:x1], 0)
        benz, _ = referans_benzerligi(parca, depo)
        if f["alan"] > 0.35 and benz < BENZERLIK_ALT:               # harf boyutunda dolu ve hiçbir harfe benzemiyor: şüpheli, geç
            out.append((x0, x1, y0, y1, i, benz, "gec", 0.0))
        elif benz >= BENZERLIK_ALT:
            out.append((x0, x1, y0, y1, i, benz, "incelt", 0.25 + 0.5 * risk))
        else:
            out.append((x0, x1, y0, y1, i, benz, "sil", (1.0 - benz / BENZERLIK_ALT) * (0.5 + 0.5 * risk)))
    return out, et, tani


def kopru_kaydi(kap_once, kap_sonra, bolge, sb, esik=110):
    """Fırçayla ÇİZİLEN köprünün özelliği: çizilen mürekkebin iki ucu eski mürekkebe değiyorsa boşluk uzunluğu (sb'ye oranla).
    -> özellik sözlüğü ya da None"""
    import numpy as np
    x0, y0, x1, y1 = bolge
    pay = 3
    H, W = kap_once.shape
    a0, b0, a1, b1 = max(0, x0 - pay), max(0, y0 - pay), min(W, x1 + pay), min(H, y1 + pay)
    once = np.asarray(kap_once)[b0:b1, a0:a1] > esik
    sonra = np.asarray(kap_sonra)[b0:b1, a0:a1] > esik
    yeni = sonra & ~once
    if yeni.sum() < 3 or once.sum() < 6:
        return None
    ys, xs = np.nonzero(yeni)
    uzun = float(max(xs.max() - xs.min(), ys.max() - ys.min()) + 1)
    from PIL import Image, ImageFilter
    dil = np.asarray(Image.fromarray(once.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5)), dtype=bool)
    degen = int((yeni & dil).sum())
    if degen < 2:
        return None                                                # eski mürekkebe hiç değmiyor: köprü değil, yeni çizgi
    return {"bosluk": uzun / sb, "kalinlik": float(yeni.sum()) / max(1.0, uzun) / sb}


def kopru_kurali(kayitlar):
    """Çizilen köprülerden: en uzun köprülenebilecek boşluk (sb'ye oranla) ya da None."""
    import numpy as np
    if len(kayitlar) < LEKE_EN_AZ:
        return None
    return {"bosluk": min(float(np.percentile([r["bosluk"] for r in kayitlar], 85)), 0.6), "ornek": len(kayitlar)}


def _komsu_parcalar(eski, m):
    """Kutunun sol/sağ kenarına DEĞEN ve ağırlığı o kenara yakın olan mürekkep bileşenleri (komşu harfin taşan parçası):
    bool maske. Bunlar nizami dönüşümde silinmez."""
    import numpy as np
    h, w = m.shape
    etiket = np.zeros(m.shape, dtype=np.int32)
    n = 0
    for sy in range(h):
        for sx in range(w):
            if m[sy, sx] and etiket[sy, sx] == 0:
                n += 1
                yig = [(sy, sx)]
                etiket[sy, sx] = n
                while yig:
                    y, x = yig.pop()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and etiket[yy, xx] == 0:
                                etiket[yy, xx] = n
                                yig.append((yy, xx))
    out = np.zeros(m.shape, dtype=bool)
    for i in range(1, n + 1):
        ys, xs = np.nonzero(etiket == i)
        if len(xs) < 4:
            continue
        sol = xs.min() == 0 and xs.mean() < 0.2 * w
        sag = xs.max() == w - 1 and xs.mean() > 0.8 * w
        if sol or sag:
            out |= etiket == i
    return out


def nizami_yap(kap, kutu, harf, depo, aile=None, tur=4):
    """Kullanıcının ONAYLADIĞI harfi, o konumda NİZAMİ (temiz) hâle getirir: harfin ortak yolu mürekkebin çerçevesine
    oturtulup nizami kalınlıkta yeniden çizilir (kalın/dolmuş harf siyah noktaya DÖNMEZ). Yol yoksa harfin kendi ana
    hattından çizilir. Sonuç KORUYUCUDAN geçer: harf yeniden okununca aynı çıkmalı ve çizim eski mürekkebin üstüne
    oturmalı; geçmezse hiçbir şey değiştirilmez.
    -> (eski_parca, yeni_parca, bilgi) | (eski, None, {"yontem": "reddedildi", ...}) | None (zaten nizami / boş)"""
    import numpy as np
    from PIL import Image, ImageFilter
    x0, x1, y0, y1, ust, alt = kutu
    sb = max(1, alt - ust)
    eski = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32)
    m = eski > 110
    if m.sum() < 12:
        return None
    K = ana_hat(m)
    if K.sum() < 2:
        return None
    v = depo.varyant.get(aile or depo.aile, {}).get(harf, {}).get("nizami")
    nk = v[2] if v else 0.10
    r_n = max(0.5, nk * sb / 2)
    kal = float(m.sum()) / max(1, int(K.sum()))
    if kal / 2 <= r_n + 0.6:
        return None                                                   # zaten nizami kalınlıkta
    pts = depo.yol_prototip(harf, aile)
    adaylar = []
    gercek_nizami = bool(depo.varyant.get(aile or depo.aile, {}).get(harf, {}).get("nizami"))
    ref = _referans_yol(harf)                                         # daktilo yazı tipinden NİZAMİ referansın ana hattı
    if ref is not None and not gercek_nizami:                         # öğretilen örneklerin hepsi kirliyse yol da kirlidir:
        c = _prototip_ciz(eski, m, ref, r_n, sb)                      # önce temiz REFERANSA benzet
        if c is not None:
            adaylar.append(("referans çizimi", c))
    if pts is not None:
        c = _prototip_ciz(eski, m, pts, r_n, sb)
        if c is not None:
            adaylar.append(("yol çizimi", c))
    if ref is not None and gercek_nizami:
        c = _prototip_ciz(eski, m, ref, r_n, sb)
        if c is not None:
            adaylar.append(("referans çizimi", c))
    if K.sum() >= 8 and float(m.mean()) <= 0.55:                      # kendi ana hattından nizami kalınlıkta (dolu blokta değil)
        yuv = Image.fromarray(K.astype(np.uint8) * 255).filter(
            ImageFilter.MaxFilter(2 * max(1, int(round(r_n))) + 1))
        adaylar.append(("ana hat", np.asarray(yuv, dtype=np.float32) / 255.0 * max(200.0, float(np.percentile(eski[m], 90)))))
    ust_g = ust - y0
    dil = np.asarray(Image.fromarray(m.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5)), dtype=bool)
    neden = "uygun çizim yok"
    for ad, cur in adaylar:
        cur = np.clip(cur, 0, 255)
        cm = cur > 110
        if cm.sum() < 6:
            neden = "çizim boş"
            continue
        oturma = float((cm & dil).sum()) / float(cm.sum())            # çizimin ne kadarı eski mürekkebin üstünde
        if oturma < 0.6:
            neden = f"çizim eski harfe oturmadı (%{100 * oturma:.0f})"
            continue
        ag = parca_okuma(cur, depo, ust_g, ust_g + sb)
        if ad == "referans çizimi":                                   # temiz çizimi kirli örneklerle okutmak adil değil:
            kotu = bool(ag) and ag[0][0] != harf and ag[0][1] >= 0.6 and harf not in [h for h, _ in ag[:3]]
        else:                                                         # harf yeniden okununca BİRİNCİ aday olmalı
            kotu = not ag or ag[0][0] != harf
        if kotu:
            neden = f"yeniden okununca “{ag[0][0] if ag else '?'}” çıktı"
            continue
        kom = _komsu_parcalar(eski, m)                                # komşu harfin kutuya taşan kırıntısı korunur
        cur = np.maximum(cur, eski * kom)                             # (arka plan lekesi ve taşma ise silinmiş olur)
        return eski, cur, {"yontem": ad, "oturma": round(oturma, 2), "once": float(eski.sum()) / 255,
                           "sonra": float(cur.sum()) / 255, "leke_silinen": float((eski * (~kom & (eski <= 110))).sum()) / 255}
    return eski, None, {"yontem": "reddedildi", "neden": neden}


def parca_okuma(parca, depo, ust_g, alt_g, n=6):
    """Bir harf parçasını (kapsama, float) tek başına okur: [(harf, olasılık)]. ust_g/alt_g: satır bandının parçaya göre
    y konumu. Kutu işlemden sonra hâlâ o harf mı diye doğrulamak için."""
    import numpy as np
    from PIL import Image
    img = Image.fromarray(np.clip(parca, 0, 255).astype(np.uint8))
    h, w = parca.shape
    kutu = (0, w, 0, h)
    try:
        ad = siralama(CH.ozellik(img, kutu, ust_g, alt_g), depo, None,
                      hat_haritasi(img, kutu, ust_g, alt_g) if ANA_HAT else None)
    except Exception:  # noqa: BLE001
        return []
    return [(t[0], t[1]) for t in ad[:n]]


def varyanta_incelt(parca, harf, depo, oran=0.3, sb=None, aile=None, hedef=None, uzaklik_sinir=None, koru=None, olcum=None):
    """Harfi KENDİ nizami hâline doğru bir kat dönüştürür (genel inceltme değil): hangi varyasyonda olduğunu bulur
    (kirli/orta/nizami), bir üst (daha temiz) seviyenin şablonuna bakar; şablonun mürekkebi olmayan yerlerdeki fazlalığı
    oran kadar soldurur ve şablonda kesin mürekkep olup eksik kalan yeri (mevcut mürekkebin yakınında) hafifçe tamamlar.
    parca: kapsama (0..255, float). -> (yeni_parca, bilgi) ya da None (dönüştürülecek temiz seviye yok)"""
    import numpy as np
    from PIL import Image, ImageFilter
    en_yakin, uz = varyant_bul(parca, harf, depo, aile)
    kal = cizgi_kalinligi(olcum if olcum is not None else parca, sb) if sb else None   # seviye ilk (işlenmemiş) kutudan ölçülür
    sev = seviye_bul(kal) if kal is not None else en_yakin               # mevcut seviye: ölçülen çizgi kalınlığından
    if sev is None or not uz:
        return None
    if uzaklik_sinir and min(uz.values()) > uzaklik_sinir:               # hiçbir şablona benzemiyor: harf yanlış tanınmış olabilir
        return None
    if hedef is None:
        idx = SEVIYELER.index(sev)
        temiz = [x for x in SEVIYELER[:idx] if depo.varyant_sablon(harf, x, aile) is not None]
        hedef = temiz[-1] if temiz else ("nizami" if idx > 0 else None)  # bir üst (daha temiz) seviye
    if hedef is None or hedef == sev:
        return None
    T = depo.varyant_sablon(harf, hedef, aile)
    if T is None:
        return None
    h, w = parca.shape
    Tb = np.asarray(Image.fromarray(T.clip(0, 255).astype(np.uint8)).resize((w, h), Image.Resampling.BILINEAR),
                    dtype=np.float32)
    Td = np.asarray(Image.fromarray(Tb.astype(np.uint8)).filter(ImageFilter.MaxFilter(3)), dtype=np.float32)
    # silme ağırlığı: şablonda mürekkep OLMAYAN yerde 1, şablonun mürekkebi olan yerde 0 (harfin gerçek çizgisi korunur);
    # koru: harfin kendi ana hattı (çevresiyle) da asla silinmez
    agirlik = np.clip(1.0 - Td / 160.0, 0.0, 1.0)
    if koru is not None:
        agirlik = agirlik * (~koru)
    kaldir = oran * parca * agirlik
    yakin = np.asarray(Image.fromarray(((parca > 100) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)), dtype=bool)
    ekle = 0.5 * oran * np.clip(Tb - parca, 0, None) * ((Tb > 180) & yakin)
    yeni = np.clip(parca - kaldir + ekle, 0, 255)
    return yeni, {"seviye": sev, "hedef": hedef, "kalinlik": round(kal, 3) if kal is not None else None,
                  "uzaklik": round(min(uz.values()), 1),
                  "kaldirilan": float(kaldir.sum()) / 255, "eklenen": float(ekle.sum()) / 255}


def sik_kutu(kap, dikdortgen, esik=80):
    """Kullanıcının çizdiği dikdörtgenin içindeki mürekkebin SIKI kutusu: (x0, x1, y0, y1) ya da None."""
    import numpy as np
    x0, y0, x1, y1 = (int(v) for v in dikdortgen)
    a = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32) > esik
    if a.sum() < 4:
        return None
    ys, xs = np.nonzero(a)
    return (x0 + int(xs.min()), x0 + int(xs.max()) + 1, y0 + int(ys.min()), y0 + int(ys.max()) + 1)


def bolgeyi_kutulara(kap, dikdortgen, n):
    """Bir harf ya da kelime bölgesini n harf kutusuna böler: [(x0, x1, y0, y1)] ya da []. Önce Croow'un harf kesmesi;
    parça sayısı n değilse bölgenin ortalama harf aralığı çevresindeki EN DERİN VADİLERDEN bölünür (yapışık harfler)."""
    import numpy as np
    sk = sik_kutu(kap, dikdortgen)
    if sk is None:
        return []
    x0, x1, y0, y1 = sk
    if n <= 1:
        return [sk]
    try:
        auto = CH.parcalar(kap, x0, x1, y0, y1) or []
    except Exception:  # noqa: BLE001
        auto = []
    if len(auto) == n:
        return [(p[0], p[1], p[2], p[3]) for p in auto]
    sut = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32).sum(0)
    w = len(sut)
    adim = w / n
    kes = []
    for i in range(1, n):
        c = int(round(i * adim))
        a, b = max(1, int(c - 0.35 * adim)), min(w - 1, max(2, int(c + 0.35 * adim)))
        kes.append(a + int(np.argmin(sut[a:b])) if b > a else c)
    sinir = [0] + sorted(kes) + [w]
    out = []
    for a, b in zip(sinir, sinir[1:]):
        t = sik_kutu(kap, (x0 + a, y0, x0 + b, y1))
        if t:
            out.append(t)
    return out if len(out) == n else []


def benzer_bul(depo, kap, kutular, harf, atla=(), en_cok=80, genislik=None, ilerleme=None):
    """Öğretilen harfe BENZEYEN diğer kutular. [(puan, kutu)] en benzerden başlayarak. atla: öğretilmiş kutular.
    1) Ucuz eleme: ana hat benzerliğinde harf ilk 3'e girenler (kirli sayfada olasılıklar düzdür, sıra daha güvenilirdir).
    2) Tam okuma (palet + ana hat): harf ilk sırada (>= %30) ya da ikinci sırada (>= %20) olanlar.
    3) Harfin ortak yolu varsa yol oturması (<= 2.5 piksel) ile doğrulanır."""
    import numpy as np
    atla = {tuple(a) for a in atla}
    ham = []
    for n_, k in enumerate(kutular):
        if tuple(k) in atla:
            continue
        x0, x1, y0, y1, ust, alt = k
        if genislik and not 0.6 * genislik <= (x1 - x0) <= 1.5 * genislik:
            continue
        try:
            ph = depo.hat_olasilik(hat_haritasi(kap, (x0, x1, y0, y1), ust, alt))
        except Exception:  # noqa: BLE001
            continue
        if not ph or harf not in ph:
            continue
        sira = sorted(ph.values(), reverse=True).index(ph[harf])
        if sira < 3:
            ham.append((sira, -ph[harf], k))
    ham.sort(key=lambda t: (t[0], t[1]))
    ham = ham[:max(60, en_cok * 3)]
    pts = depo.yol_prototip(harf)
    out = []
    for n_, (_, _, k) in enumerate(ham):
        if ilerleme and n_ % 10 == 0:
            ilerleme(n_ / max(1, len(ham)), f"Benzer harfler aranıyor… {n_}/{len(ham)}")
        ad = kutu_okuma(kap, [k], depo, None)[0]
        puan = {h: p for h, p in ad[:2]}.get(harf, 0.0)
        ilk = bool(ad) and ad[0][0] == harf
        if not ((ilk and puan >= 0.30) or (not ilk and puan >= 0.20)):
            continue
        if pts is not None:
            x0, x1, y0, y1, ust, alt = k
            m = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32) > 110
            K = ana_hat(m) if m.sum() >= 8 else None
            if K is None or K.sum() < 4 or yol_hizala(K, pts)[0] > 2.5:
                continue
        out.append((puan, k))
    out.sort(key=lambda t: -t[0])
    return out[:en_cok]


def kutu_ayarla(kutu, ayar, genislik, yukseklik):
    """Öğrenilen kutu ayarını (sol, sağ, üst, alt) bir kutuya uygular."""
    x0, x1, y0, y1, ust, alt = kutu
    sb = max(1, alt - ust)
    a0, a1 = int(round(x0 + ayar[0] * sb)), int(round(x1 + ayar[1] * sb))
    b0, b1 = int(round(y0 + ayar[2] * sb)), int(round(y1 + ayar[3] * sb))
    a0, a1 = max(0, min(a0, a1 - 2)), min(genislik, max(a1, a0 + 2))
    b0, b1 = max(0, min(b0, b1 - 2)), min(yukseklik, max(b1, b0 + 2))
    return (a0, a1, b0, b1, ust, alt)


def kutular_bul(img, depo=None, duzlendi=False, ayarla=True):
    """Sayfadaki harf kutuları (okuma yok): -> (düz gri resim, kapsama, [(x0, x1, y0, y1, ust, alt)], harf adımı).
    ayarla: kullanıcının geçmiş düzeltmelerinden öğrenilen sistematik kutu kayması uygulanır."""
    g = img.convert("L") if duzlendi else CH.duzle(img)[0]
    kap, _pitch, _cizgi = cizgisiz(kenarsiz(CH.kapsama(g)))        # üstü çizili satırlar kutu bulmayı bozmasın
    satirlar = satirlar_belge(kap)
    adim = _izgara_mi(kap, satirlar, bilinen=depo.adim if depo else None)
    out = []
    for ust, alt in satirlar:
        if adim:
            for h in izgara_hucreleri(kap, ust, alt, adim):
                if h[2]:
                    k = _hucre_kutusu(kap, h, ust, alt)
                    if k:
                        out.append((k[0], k[1], k[2], k[3], ust, alt))
        else:
            out += [(p[0], p[1], p[2], p[3], ust, alt) for p in (CH.parcalar(kap, 0, kap.width, ust, alt) or [])]
    ay = depo.kutu_ayari() if (depo is not None and ayarla) else None
    if ay:
        out = [kutu_ayarla(k, ay, kap.width, kap.height) for k in out]
    return g, kap, out, adim


def kutu_tahmini(kap, kutu, depo, genel=None, n=3):
    """Bir kutu için Croow'un adayları: [(harf, olasılık)]"""
    x0, x1, y0, y1, ust, alt = kutu
    try:
        ad = siralama(CH.ozellik(kap, (x0, x1, y0, y1), ust, alt), depo, genel,
                      hat_haritasi(kap, (x0, x1, y0, y1), ust, alt) if ANA_HAT else None)
    except Exception:  # noqa: BLE001
        return []
    return [(t[0], round(t[1], 2)) for t in ad[:n]]


def elle_ogret(kap, kutu, harf, depo, sanal=True, kaydet=True, seviye=None):
    """Kullanıcının gösterdiği harf ("bu t"): kutu o harfin GERÇEK referansı olarak depoya girer
    (palet kökü, kalıp, ana hat ve silik sanal kopyalar). -> depodaki o harfin kök sayısı"""
    x0, x1, y0, y1, ust, alt = kutu
    k = (x0, x1, y0, y1)
    oz = CH.ozellik(kap, k, ust, alt)
    depo.gercek.ekle(harf, oz)
    if len(harf) == 1:
        depo.kalip_ekle(harf, kap, k)
        depo.hat_ekle(harf, hat_haritasi(kap, k, ust, alt))
        depo.gen_ekle(harf, (x1 - x0) / max(1, alt - ust))
        depo.varyant_ekle(harf, kap, kutu, seviye)
        if sanal:
            for _, kv in sanal_kopyalar(kap, k, random.Random(x0 * 7919 + y0)):
                try:
                    depo.sanal.ekle(harf, CH.ozellik(kv, k, ust, alt))
                except Exception:  # noqa: BLE001
                    pass
    if kaydet:
        depo.kaydet()
    return sum(1 for r in depo.gercek.k if r[0] == harf)


# ====================================================================== KELİME ÇÖZÜCÜ (yan panel)
# Okunamayan bir kelime için: harf sayısı kelimenin genişliğinden bulunur, kilit harfler (Croow'un emin olduğu ya da
# kullanıcının yazdığı) konumlarıyla bir kalıp oluşturur (U__m__t), sözlük bu kalıba göre süzülür ve sıralanır.
# Kullanıcı doğrusunu seçince Croow o kelimenin harflerini kutulardan öğrenir.
def kelime_kutulari(kutular, adim):
    """kutular_bul çıktısını satır satır KELİMELERE böler. -> [[kutu, ...], ...] (soldan sağa)"""
    satirlar = {}
    for k in kutular:
        satirlar.setdefault((k[4], k[5]), []).append(k)
    out = []
    for (ust, alt), ks in sorted(satirlar.items()):
        ks.sort(key=lambda k: k[0])
        if adim:
            esik = 0.5 * adim                                    # boş hücre = kelime arası
        else:
            ar = sorted(b[0] - a[1] for a, b in zip(ks, ks[1:]))
            esik = max(2.2 * (ar[len(ar) // 3] if ar else 0), 0.22 * (alt - ust))
        cur = [ks[0]]
        for a, b in zip(ks, ks[1:]):
            if b[0] - a[1] > esik:
                out.append(cur)
                cur = []
            cur.append(b)
        out.append(cur)
    return out


def kutu_okuma(kap, kutular, depo, genel=None, n=10):
    """Her kutu için Croow'un adayları: [[(harf, olasılık), ...], ...]"""
    out = []
    for x0, x1, y0, y1, ust, alt in kutular:
        try:
            ad = siralama(CH.ozellik(kap, (x0, x1, y0, y1), ust, alt), depo, genel,
                          hat_haritasi(kap, (x0, x1, y0, y1), ust, alt) if ANA_HAT else None)
        except Exception:  # noqa: BLE001
            ad = []
        out.append([(t[0], t[1]) for t in ad[:n]])
    return out


def _ort_ilerleme(depo, sb):
    g = [v for _, v in depo.gen.values()] if depo is not None and depo.gen else []
    return ((sum(g) / len(g)) if g else 0.45) * sb + 0.10 * sb


def _ilerleme_fn(depo, adim, sb):
    """Bir harfin yatayda kapladığı yer (harf + boşluk payı)."""
    if adim:
        return lambda c: adim
    gen = depo.gen if depo is not None else {}
    ort = _ort_ilerleme(depo, sb) - 0.10 * sb
    return lambda c: (gen.get(c.lower(), [0, ort / sb])[1] + 0.10) * sb


def tahmin_uzunluk(kutular, depo, adim):
    """Kelimedeki harf sayısı: kelimenin genişliği / harf adımı (daktilo) ya da ortalama harf genişliği."""
    n = len(kutular)
    w = kutular[-1][1] - kutular[0][0]
    if adim:
        return max(n, int(round(w / adim)))
    if depo is not None and depo.gen:
        return max(1, int(round(w / _ort_ilerleme(depo, max(1, kutular[0][5] - kutular[0][4])))))
    return n


def _yuvalar(kutular, L, ilerlemeler=None):
    """Her kutu hangi harf yuvasına (0..L-1) düşüyor. ilerlemeler: yuva genişlikleri (yoksa eşit)."""
    wx0 = kutular[0][0]
    w = max(1, kutular[-1][1] - wx0)
    g = [w / L] * L if not ilerlemeler else [a * w / sum(ilerlemeler) for a in ilerlemeler]
    sinir = [wx0]
    for x in g:
        sinir.append(sinir[-1] + x)
    merkez = [(sinir[j] + sinir[j + 1]) / 2 for j in range(L)]
    out, onceki = [], -1
    for k in kutular:
        cx = (k[0] + k[1]) / 2
        j = min(range(L), key=lambda j: abs(cx - merkez[j]))
        j = max(j, onceki + 1)                                    # sıra bozulmaz, iki kutu aynı yuvaya girmez
        if j >= L:
            out.append(None)
            continue
        out.append(j)
        onceki = j
    return out


def noktalama_kirp(kutular, okuma):
    """Kelimenin başındaki/sonundaki noktalama kutularını (, . " ' ...) ayırır. -> (a, b): kutular[a:b] harf kısmıdır."""
    a, b = 0, len(kutular)
    ok = lambda i: bool(okuma[i]) and (okuma[i][0][0].isalnum() or okuma[i][0][1] < 0.4)
    while a < b and not ok(a):
        a += 1
    while b > a and not ok(b - 1):
        b -= 1
    return a, b


def desen_ara(kutular, okuma, depo, adim=None, kilit=None, uzunluk=None, onceki=None, en_cok=40):
    """Okunamayan kelime için sözlük süzme.
    kutular: kelimenin harf kutuları (noktalama ayrılmış); okuma: kutu_okuma çıktısı (aynı sırada).
    kilit: {yuva: harf} kullanıcının yazdıkları (kesin). uzunluk: harf sayısı (yoksa genişlikten bulunur).
    -> {"uzunluk", "desen": [harf ya da None] * L, "kilitli": [bool] * L, "aday": [(kelime, puan, sözlük_sayısı)]}
    Desen: Croow'un EMİN olduğu harfler konumlarıyla (U__m__t); sözlük o kalıba ve geri kalan harflerin olasılıklarına
    (son harf 1.5 kat ağır) ve kelime sıklığına göre sıralanır."""
    n = len(kutular)
    sb = max(1, kutular[0][5] - kutular[0][4])
    L = int(uzunluk) if uzunluk else tahmin_uzunluk(kutular, depo, adim)
    L = max(1, L)
    kilit = {int(j): c for j, c in (kilit or {}).items() if c and 0 <= int(j) < L}
    yuva0 = _yuvalar(kutular, L)
    desen, capa = [None] * L, [False] * n
    for i, j in enumerate(yuva0):
        ad = okuma[i]
        if j is None or not ad:
            continue
        capa[i] = ad[0][1] >= CAPA or len(ad) < 2 or ad[0][1] >= CAPA_KAT * ad[1][1]
        if capa[i]:
            desen[j] = ad[0][0]
    for j, c in kilit.items():
        desen[j] = c
    sonuc = {"uzunluk": L, "desen": desen, "kilitli": [j in kilit for j in range(L)], "aday": []}
    if depo is None or not depo.kelime:
        return sonuc
    n_top = depo.kelime_toplam()
    hp = []
    for ad in okuma:
        d = {}
        for h, p in ad:
            d[h.lower()] = max(d.get(h.lower(), 0.0), p)
        hp.append(d)

    def kelime_puan(w):
        lp = math.log((depo.kelime.get(w, 0) + 0.1) / n_top)
        if onceki:
            lp += 1.5 * math.log1p(depo.cift.get(onceki + " " + w, 0))
        return lp
    orantili = not adim and bool(depo.gen)
    ilerleme = _ilerleme_fn(depo, adim, sb)
    w_obs = max(1, kutular[-1][1] - kutular[0][0])
    sirali = []
    for w in depo.uzunlukta(L):
        if any(w[j] != c.lower() for j, c in kilit.items()):
            continue
        yuva = yuva0
        if orantili:                                              # harflerin gerçek genişlikleriyle yuvalar
            adv = [ilerleme(c) for c in w]
            if not 0.75 <= w_obs / sum(adv) <= 1.33:
                continue
            yuva = _yuvalar(kutular, L, adv)
        lp, uygun = 0.0, True
        for i, j in enumerate(yuva):
            if j is None or j in kilit:
                continue
            v = math.log(max(CAPA_TABAN if capa[i] else TABAN, hp[i].get(w[j], 0.0)))
            lp += v * (1.5 if i == n - 1 else 1.0)                # SON HARF daha ağır
            if lp < -18:
                uygun = False
                break
        if uygun:
            sirali.append((lp + BAGLAM * kelime_puan(w), w))
    sirali.sort(reverse=True)
    sonuc["aday"] = [(w, round(p, 2), depo.kelime.get(w, 0)) for p, w in sirali[:en_cok]]
    return sonuc


def kasa_uyarla(kelime, okuma):
    """Sözlükteki (küçük harfli) kelimeyi SAYFANIN harf büyüklüğüne uydurur. Büyük harf şeklini küçük harf diye
    öğretmek paleti bozar: sayfa BÜYÜK HARFSE kelime büyük, küçükse küçük; baş harf kutusu büyük okunuyorsa baş harf büyük."""
    emin = [ad[0][0] for ad in okuma if ad and ad[0][1] >= 0.4 and ad[0][0].isalpha()]
    if not emin:
        return kelime
    if sum(c.isupper() for c in emin) >= 0.6 * len(emin):
        return kelime.upper()
    out = kelime.lower()
    if okuma and okuma[0] and okuma[0][0][0].isupper() and okuma[0][0][1] >= 0.4:
        out = out[:1].upper() + out[1:]
    return out


def kelime_ogret(kap, kutular, kelime, depo, adim=None, onceki=None, sonraki=None, seviye=None):
    """Kullanıcı "bu kelime şu" dedi: kelimenin her harfi kendi kutusundan öğrenilir (palet, kalıp, ana hat, sanal
    kopyalar, genişlik) ve kelime sözlüğe, komşularıyla birlikte eklenir. -> öğrenilen harf sayısı"""
    L = len(kelime)
    sb = max(1, kutular[0][5] - kutular[0][4])
    ilerleme = _ilerleme_fn(depo, adim, sb)
    adv = None if adim or not depo.gen else [ilerleme(c) for c in kelime]
    yuva = _yuvalar(kutular, L, adv)
    ogrenilen = 0
    for k, j in zip(kutular, yuva):
        if j is None or not CH.izinli(kelime[j]):
            continue
        ogrenilen += 1 if _kutu_ogret(kap, k, kelime[j], depo, seviye) else 0
    w = kelime.lower()
    depo.kelime[w] = depo.kelime.get(w, 0) + 3                    # kullanıcı onayı: sıklığa ağır katkı
    if onceki:
        depo.cift[onceki + " " + w] = depo.cift.get(onceki + " " + w, 0) + 2
    if sonraki:
        depo.cift[w + " " + sonraki] = depo.cift.get(w + " " + sonraki, 0) + 2
    depo.kaydet()
    return ogrenilen


def _kutu_ogret(kap, kutu, harf, depo, seviye=None):
    try:
        elle_ogret(kap, kutu, harf, depo, kaydet=False, seviye=seviye)
        return True
    except Exception:  # noqa: BLE001
        return False


def simge_goster(metin):
    """Bilinmeyen harf simgelerini ekranda okunur yazar: U+E000 -> ‹1›, U+E001 -> ‹2› ..."""
    return "".join(f"‹{ord(c) - 0xE000 + 1}›" if CH.simge_mi(c) else c for c in metin)


def karakter_dogrulugu(dogru, okunan):
    """1 - düzenleme mesafesi / doğru metnin uzunluğu (boşluklar tekleştirilir). 0..100"""
    a, b = " ".join(dogru.split()), " ".join(okunan.split())
    if not a:
        return 0.0
    onceki = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(onceki[j] + 1, cur[j - 1] + 1, onceki[j - 1] + (x != y)))
        onceki = cur
    return max(0.0, 100 * (1 - onceki[-1] / len(a)))
