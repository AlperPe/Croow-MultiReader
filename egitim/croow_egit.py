#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
CROOW hızlı eğitim: bir klasördeki fotoğraflarla kök hafızasını (universal_roots.crwm) öğretir.

Kullanım:
    python croow_egit.py <foto_klasoru>
    python croow_egit.py <foto_klasoru> --hafiza yol/universal_roots.crwm

- Her fotoğrafın BÜTÜN tonları öğrenilir (sitedeki motorla aynı yöntem, sınır yok).
- Daha önce öğretilmiş fotoğraflar atlanır (parmak izi: universal_roots.crwm içinde).
- Her fotoğraftan sonra ilerleme ve kalan süre yazılır.
- Hafıza 30 saniyede bir kaydedilir; Ctrl+C ile durdurursan o ana kadar öğrenilenler kaydedilir.
- Gereken: Python 3, Pillow ve numpy  (pip install pillow numpy)
"""
import argparse
import io
import os
import sys
import time
from multiprocessing import Pool, cpu_count, freeze_support

import numpy as np
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                                   # roots_memory.py yanındaysa
sys.path.insert(0, os.path.join(_HERE, "..", "motor"))      # depo düzeninde: ../motor
from roots_memory import RootsMemory, fingerprint  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
SAVE_SECONDS = 30


def find_photos(folder):
    for root, _, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in EXTS:
                yield os.path.join(root, name)


def extract(path):
    """
    Fotoğrafın BÜTÜN tonları, sıkıştırılmış olarak:
    (yol, ton_baytları, sayı_baytları, piksel) ya da (yol, None, hata, 0)
    Ton = r<<16 | g<<8 | b (uint32). Bellekte ve süreçler arasında az yer tutar.
    """
    try:
        img = Image.open(path).convert("RGB")
        a = np.asarray(img, dtype=np.uint32).reshape(-1, 3)
        packed = (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]
        tones, counts = np.unique(packed, return_counts=True)
        return path, tones.astype(np.uint32).tobytes(), counts.astype(np.uint32).tobytes(), None
    except Exception as e:
        return path, None, str(e), None


def unpack(tone_bytes, count_bytes):
    t = np.frombuffer(tone_bytes, dtype=np.uint32).tolist()
    return [(v >> 16, (v >> 8) & 255, v & 255) for v in t], np.frombuffer(count_bytes, dtype=np.uint32).tolist()


def fmt_time(sec):
    sec = int(sec)
    if sec >= 3600:
        return f"{sec // 3600} sa {sec % 3600 // 60} dk"
    if sec >= 60:
        return f"{sec // 60} dk {sec % 60} sn"
    return f"{sec} sn"


def main():
    ap = argparse.ArgumentParser(description="CROOW kök hafızasını fotoğraflarla eğitir.")
    ap.add_argument("klasor", help="fotoğrafların bulunduğu klasör (alt klasörler dahil)")
    ap.add_argument("--hafiza", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "universal_roots.crwm"),
                    help="universal_roots.crwm yolu (varsayılan: betiğin yanındaki)")
    ap.add_argument("--cekirdek", type=int, default=max(1, min(4, cpu_count() - 1)),
                    help="ton çıkarmada kullanılacak çekirdek (öğrenme tek çekirdekte yapılır)")
    args = ap.parse_args()

    if not os.path.isdir(args.klasor):
        sys.exit(f"Klasör bulunamadı: {args.klasor}")

    mem = RootsMemory(args.hafiza)
    s0 = mem.summary()
    print(f"[HAFIZA] {args.hafiza}")
    print(f"         {s0['roots']}/{s0['capacity']} kök, seviye {s0['level']}, bilinen dosya {s0['known_files']}")

    # Daha önce öğretilmiş fotoğrafları baştan ayıkla
    photos, keys, skipped = [], {}, 0
    for p in sorted(find_photos(args.klasor)):
        try:
            with open(p, "rb") as f:
                k = fingerprint(f.read())
        except OSError:
            continue
        if mem.is_seen(k):
            skipped += 1
        else:
            photos.append(p)
            keys[p] = k
    if not photos:
        sys.exit(f"Öğretilecek yeni fotoğraf yok ({skipped} tanesi daha önce öğretilmiş).")
    print(f"[EĞİTİM] {len(photos)} yeni fotoğraf ({skipped} tanesi daha önce öğretilmiş, atlandı)\n", flush=True)

    t0 = time.time()
    last_save = time.time()
    learned = failed = new_total = tones_total = 0
    batch = max(1, args.cekirdek)
    groups = [photos[i:i + batch] for i in range(0, len(photos), batch)]
    done = 0
    try:
        with Pool(args.cekirdek) as pool:
            pending = pool.map_async(extract, groups[0])
            for gi in range(len(groups)):
                results = pending.get()
                # bir sonraki grubu şimdiden çıkar; bellekte en fazla iki grup olur
                if gi + 1 < len(groups):
                    pending = pool.map_async(extract, groups[gi + 1])
                for path, tone_b, count_b, pstats in results:
                    done += 1
                    name = os.path.basename(path)
                    if tone_b is None:
                        failed += 1
                        print(f"  [{done}/{len(photos)}] ✖ okunamadı: {name} ({count_b})", flush=True)
                        continue
                    t1 = time.time()
                    tones, counts = unpack(tone_b, count_b)
                    _, rep = mem.learn(tones, counts, source="train", key=keys[path], save=False)
                    mem.learn_paths(Image.open(path).convert("RGB"))   # yollar: bulanıklaştır, aç, öğren
                    learned += 1
                    new_total += rep["new"]
                    tones_total += rep["tones"]
                    el = time.time() - t0
                    eta = el / done * (len(photos) - done)
                    lv = f"  ★ kapasite {rep['capacity']}" if rep["level_up"] else ""
                    print(f"  [{done}/{len(photos)}] {name}: {rep['tones']:,} ton, {rep['new']:,} yeni "
                          f"({time.time() - t1:.0f} sn) | hafıza {rep['roots']:,} kök | kalan ~{fmt_time(eta)}{lv}",
                          flush=True)
                    if time.time() - last_save >= SAVE_SECONDS:
                        mem.save()
                        last_save = time.time()
    except KeyboardInterrupt:
        print("\n[DURDURULDU] O ana kadar öğrenilenler kaydediliyor...", flush=True)
    mem.save()

    s1 = mem.summary()
    print("\n" + "=" * 56)
    print(f"  Öğretilen yeni foto : {learned}")
    print(f"  Daha önce görülmüş  : {skipped} (atlandı)")
    print(f"  Okunamayan          : {failed}")
    print(f"  İncelenen ton       : {tones_total:,}")
    print(f"  Keşfedilen yeni ton : {new_total:,}")
    print(f"  Hafıza              : {s0['roots']:,} -> {s1['roots']:,} kök (kapasite {s1['capacity']:,}, seviye {s1['level']})")
    print(f"  Piksel yolları      : {s1['paths']:,} yol (derinlik {s1['path_depth']}, {s1['path_splits']:,} bölünme), {s1['path_images']} resimden")
    print(f"  Süre                : {fmt_time(time.time() - t0)}")
    print("=" * 56)
    print("\nSunucuya yüklenecek dosya:")
    print("  " + os.path.splitext(args.hafiza)[0] + ".crwm")


if __name__ == "__main__":
    freeze_support()   # Windows için gerekli
    main()
