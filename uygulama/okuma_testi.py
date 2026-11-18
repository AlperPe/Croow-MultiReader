#!/usr/bin/env python3
"""Croow okuma testi: ADİL ölçüm (öğretilen satırlar ile sınanan satırlar AYRI).

Kullanım:
  python okuma_testi.py sayfa.png sayfa_dogru_metin.txt            # satırların ilk yarısından öğret, ikinci yarısını oku
  python okuma_testi.py sayfa.png metin.txt --egit 0.3             # ilk %30'undan öğret
  python okuma_testi.py sayfa.png metin.txt --egit 0             # HİÇ öğretme (genel palet / boş depo): en zor test
  python okuma_testi.py sayfa.png metin.txt --metin klasor/        # bağlam için düz metin (.txt) klasörü (sözlük)
  python okuma_testi.py sayfa.png metin.txt --capraz              # satırları sırayla 2 kümeye böl, ikisini de dene

metin.txt: sayfadaki satırlar, her satır bir satır (sayfadaki satır sırasıyla; okunmayan satırı da yazın ya da boş bırakmayın).
Çıktı: karakter doğruluğu ve kelime doğruluğu (düzenleme mesafesi), bağlamsız ve bağlamlı, öğretilmemiş satırlarda.
Hiçbir veri kalıcı yazılmaz (geçici depo)."""
import argparse
import glob
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image  # noqa: E402

import belge_harf as BH  # noqa: E402
import crw_harf as CH  # noqa: E402


def kelime_dogrulugu(dogru, okunan):
    """Kelime düzeyinde 1 - düzenleme mesafesi / kelime sayısı (0..100)."""
    a, b = dogru.split(), okunan.split()
    if not a:
        return 0.0
    onceki = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(onceki[j] + 1, cur[j - 1] + 1, onceki[j - 1] + (x.lower() != y.lower())))
        onceki = cur
    return max(0.0, 100 * (1 - onceki[-1] / len(a)))


def calistir(img, satirlar, egit_idx, test_idx, metin_klasoru, genel):
    """genel: yazı tiplerinden öğrenilmiş genel harf paleti (Araçlar → Harf paletini alfabeden öğret) ya da None."""
    with tempfile.TemporaryDirectory(prefix="croow_test_") as gecici:
        CH.VERI = gecici
        depo = BH.Depo()
        if metin_klasoru:
            dosyalar = sorted(glob.glob(os.path.join(metin_klasoru, "*.txt")))
            if dosyalar:
                BH.baglam_ogret(dosyalar, depo)
                depo = BH.Depo()
        if egit_idx:
            rapor = BH.ogret(img, "\n".join(satirlar[i] for i in egit_idx), depo)
            print(f"  öğretilen satır: {len(egit_idx)} · eşleşen {rapor.get('eslesen_satir')}/{rapor.get('metin_satiri')} · "
                  f"gerçek harf örneği {rapor.get('gercek_harf')}")
        sonuc = {}
        for ad, kw in (("bağlamsız", {"baglam": False}), ("bağlamlı", {})):
            okunan = BH.oku(img, depo, genel, **kw).splitlines()
            okunan = [x for x in okunan if x.strip()] or okunan
            satir_ok = [(i, okunan[i]) for i in test_idx if i < len(okunan)]
            if len(okunan) != len(satirlar):
                print(f"  UYARI ({ad}): Croow {len(okunan)} satır okudu, metinde {len(satirlar)} satır var; "
                      "satırlar sırayla eşleniyor (sapma varsa sonuç düşük çıkar).")
            kd = [BH.karakter_dogrulugu(satirlar[i], o) for i, o in satir_ok]
            wd = [kelime_dogrulugu(satirlar[i], o) for i, o in satir_ok]
            agirlik = [len(satirlar[i]) for i, _ in satir_ok]
            toplam = sum(agirlik) or 1
            sonuc[ad] = (sum(k * w for k, w in zip(kd, agirlik)) / toplam, sum(k * w for k, w in zip(wd, agirlik)) / toplam,
                         satir_ok)
        return sonuc


def main():
    ap = argparse.ArgumentParser(description="Croow okuma testi (öğretilmemiş satırlarda adil ölçüm)")
    ap.add_argument("resim")
    ap.add_argument("metin")
    ap.add_argument("--egit", type=float, default=0.5, help="satırların bu oranı öğretilir (varsayılan 0.5); 0 = hiç öğretme")
    ap.add_argument("--metin", dest="klasor", default=None, help="bağlam için .txt klasörü")
    ap.add_argument("--capraz", action="store_true", help="çift/tek satırlarla iki yönlü dene")
    ap.add_argument("--goster", action="store_true", help="satır satır okunan / doğru metni yaz")
    a = ap.parse_args()
    genel = CH.Palet()                                    # kullanıcının kendi genel paleti (geçici depo ayarlanmadan ÖNCE yüklenir)
    genel = genel if genel.k else None
    print("genel harf paleti:", "var (%d kök)" % len(genel.k) if genel else "YOK (Araçlar → Harf paletini alfabeden öğret ile oluştur; '--egit 0' ancak o zaman anlamlı)")
    img = Image.open(a.resim)
    satirlar = [x.rstrip("\n") for x in open(a.metin, encoding="utf-8")]
    satirlar = [x for x in satirlar if x.strip()]
    n = len(satirlar)
    if a.capraz:
        bolme = [("çift satırlarla öğret → tek satırları oku", [i for i in range(n) if i % 2 == 0], [i for i in range(n) if i % 2 == 1]),
                 ("tek satırlarla öğret → çift satırları oku", [i for i in range(n) if i % 2 == 1], [i for i in range(n) if i % 2 == 0])]
    elif a.egit <= 0:
        bolme = [("HİÇ ÖĞRETİLMEDİ → bütün satırlar", [], list(range(n)))]
    else:
        k = max(1, int(round(n * a.egit)))
        bolme = [(f"ilk {k} satırdan öğret → kalan {n - k} satırı oku", list(range(k)), list(range(k, n)))]
    for ad, egit, test in bolme:
        print(f"\n== {ad} ==")
        s = calistir(img, satirlar, egit, test, a.klasor, genel)
        for kip, (kd, wd, satir_ok) in s.items():
            print(f"  {kip:10s}: karakter doğruluğu %{kd:5.1f} · kelime doğruluğu %{wd:5.1f}  ({len(satir_ok)} satır)")
        if a.goster:
            for i, o in s["bağlamlı"][2][:40]:
                print(f"   [{i + 1}] doğru : {satirlar[i]}\n       okunan: {o}")
    print("\nNot: karakter doğruluğu = 1 - düzenleme mesafesi / doğru metnin uzunluğu. Öğretilen satırlar sayıya KATILMAZ.")


if __name__ == "__main__":
    main()
