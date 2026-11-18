#!/usr/bin/env python3
# crw_motor.py — Croow motoru: CRW kodlayıcı / açıcı / detaylandırıcı (HTTP sunucusu YOK; yalnızca kütüphane).
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
import io
import struct
import base64
import json
import zlib
import traceback
from PIL import Image
Image.MAX_IMAGE_PIXELS = None          # detaylandırma büyük resimler üretebilir

import os

# Kök hafızası: tek dosya universal_roots.crwm - sınırsız keşif
import heapq
import numpy as np
from roots_memory import RootsMemory, fingerprint, extract_tones
from paths_memory import flow_expand, legacy_filters_from_bytes, LEGACY_KEYS, TAPS, model_to_bytes, model_from_bytes, apply_ops
DETAIL_MARK = 0xFFFE          # CRW7: orijinal + detay adımları + piksel yolları
ROOTS_FILE = os.environ.get("CROOW_ROOTS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "universal_roots.crwm"))
MEMORY = RootsMemory(ROOTS_FILE)
# Uygulama kullanıcı resimlerinden hafızaya öğrenmez: hafıza yalnızca okunur, eğitim egitim/croow_egit.py ile yapılır.
# Açmak için ortama CROOW_SITE_LEARN=1 eklenir.
SITE_LEARNING = os.environ.get("CROOW_SITE_LEARN", "0") == "1"

LUM_THRESHOLD = 0       # detay eşiği: 0 = orijinalden farklı her piksel düzeltilir (v5'te 28)
# Bütün dosyalar CRW6 olarak yazılır (renk sayısı sınırsız). CRW5 dosyaları yalnızca açılır.


# ---------------- Palet çıkarma ----------------
def _median_cut(colors, k):
    """Ağırlıklı median-cut: [(sayı, (r,g,b)), ...] -> en fazla k renk. Renk sayısı sınırı yok."""
    def score(box):
        if len(box) < 2:
            return 0
        rng = max(max(c[1][ch] for c in box) - min(c[1][ch] for c in box) for ch in range(3))
        return rng * sum(c[0] for c in box)

    heap = [(-score(colors), 0, colors)]
    uid = 1
    while len(heap) < k:
        sc, _, box = heapq.heappop(heap)
        if sc == 0:                         # bölünecek kutu kalmadı
            heapq.heappush(heap, (sc, uid, box)); uid += 1
            break
        ch = max(range(3), key=lambda c: max(x[1][c] for x in box) - min(x[1][c] for x in box))
        box = sorted(box, key=lambda x: x[1][ch])
        half, acc, cut = sum(x[0] for x in box) / 2, 0, 1
        for i, x in enumerate(box):
            acc += x[0]
            if acc >= half:
                cut = min(max(1, i + 1), len(box) - 1)
                break
        for part in (box[:cut], box[cut:]):
            heapq.heappush(heap, (-score(part), uid, part)); uid += 1

    palette, index_of = [], {}
    for _, _, box in heap:
        w = sum(x[0] for x in box)
        palette.append(tuple(round(sum(x[0] * x[1][ch] for x in box) / w) for ch in range(3)))
        for x in box:
            index_of[x[1]] = len(palette) - 1
    return palette, index_of


def _pack(arr):
    a = arr.astype(np.uint32)
    return (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]


def _palette_from_memory(rgb, memory):
    """
    Palet .crwm hafızasından okunur: her ton en yakın köke bağlanır, palet o köklerdir.
    rgb: (N, 3) uint8 pikseller. Dönüş: (palet (K, 3) uint8, piksel numaraları (N,))
    """
    tones, inverse = np.unique(_pack(rgb), return_inverse=True)
    cols = np.stack([(tones >> 16) & 255, (tones >> 8) & 255, tones & 255], axis=1)
    roots = np.asarray(memory.nearest_roots(cols.tolist()), dtype=np.int64)
    slots, slot_of_tone = np.unique(roots, return_inverse=True)
    palette = np.array([[max(0, min(255, round(v))) for v in memory.root(int(r))] for r in slots], dtype=np.uint8)
    return palette, slot_of_tone.reshape(-1)[inverse.reshape(-1)]


def _palette_for(base_img, k, base_colors):
    """Taban görüntü için k renklik palet ve piksel numaraları."""
    if k >= len(base_colors):
        # resmin bütün tonları: kayıpsız taban
        palette = [c for _, c in base_colors]
        index_of = {c: i for i, c in enumerate(palette)}
        return palette, [index_of[p] for p in base_img.getdata()]
    if k <= 256:
        # v5'in kendi yöntemi (Pillow median-cut)
        q = base_img.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
        raw = q.getpalette()[:k * 3]
        return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)], list(q.getdata())
    palette, index_of = _median_cut(base_colors, k)
    return palette, [index_of[p] for p in base_img.getdata()]


# ---------------- Katmanlar ----------------
def _delta_payload(orig_arr, exp_img):
    """
    Detay katmanı (toplu). Etiketler:
      0x00 n         : n piksel değişmez (n <= 255, uzun boşluklar parçalanır)
      0x01 r g b     : fark int8
      0x02 rr gg bb  : fark int16 (büyük farklar, sınır yok)
    """
    exp_arr = np.asarray(exp_img, dtype=np.int16).reshape(-1, 3)
    d = orig_arr - exp_arr
    N = len(d)
    if LUM_THRESHOLD > 0:
        lum = np.abs(0.299 * d[:, 0] + 0.587 * d[:, 1] + 0.114 * d[:, 2])
        hot_mask = lum >= LUM_THRESHOLD
    else:
        hot_mask = np.any(d != 0, axis=1)                 # her fark saklanır
    pos = np.flatnonzero(hot_mask)
    m = len(pos)
    dv = d[pos]
    small = np.all((dv >= -128) & (dv <= 127), axis=1)
    tok = np.where(small, 4, 7)
    prev_end = np.concatenate(([0], pos[:-1] + 1)) if m else np.zeros(0, dtype=np.int64)
    gaps = np.append(pos - prev_end, N - (pos[-1] + 1 if m else 0))
    nfull, rem = gaps // 255, gaps % 255
    nch = nfull + (rem > 0)
    seg = 2 * nch
    seg[:m] += tok
    starts = np.concatenate(([0], np.cumsum(seg)[:-1]))
    out = np.zeros(int(seg.sum()), dtype=np.uint8)
    tot_ch = int(nch.sum())
    if tot_ch:
        owner = np.repeat(np.arange(m + 1), nch)
        k = np.arange(tot_ch) - np.repeat(np.cumsum(nch) - nch, nch)
        out[starts[owner] + 2 * k + 1] = np.where(k < nfull[owner], 255, rem[owner])
    t = starts[:m] + 2 * nch[:m]
    si, bi = np.flatnonzero(small), np.flatnonzero(~small)
    out[t[si]] = 1
    for c in range(3):
        out[t[si] + 1 + c] = dv[si, c].astype(np.int8).view(np.uint8)
    out[t[bi]] = 2
    for c in range(3):
        v = dv[bi, c].astype(np.int16).view(np.uint16)
        out[t[bi] + 1 + 2 * c] = v >> 8
        out[t[bi] + 2 + 2 * c] = v & 255
    return out.tobytes()


def _base_payload_wide(indices, index_bytes):
    """CRW6/7 taban: [tekrar (1..255)][numara (index_bytes bayt)] (toplu)."""
    n = len(indices)
    if n == 0:
        return b""
    change = np.flatnonzero(np.diff(indices)) + 1
    starts = np.concatenate(([0], change))
    lengths = np.diff(np.append(starts, n))
    vals = indices[starts]
    nch = (lengths + 254) // 255
    rep_vals = np.repeat(vals, nch)
    runs = np.full(int(nch.sum()), 255, dtype=np.int64)
    runs[np.cumsum(nch) - 1] = lengths - 255 * (nch - 1)
    out = np.zeros((len(runs), 1 + index_bytes), dtype=np.uint8)
    out[:, 0] = runs
    for k in range(index_bytes):
        out[:, 1 + k] = (rep_vals >> (8 * (index_bytes - 1 - k))) & 255
    return out.tobytes()


def _base_payload(indices, wide, index_bytes):
    out = bytearray()
    bi, total = 0, len(indices)
    while bi < total:
        val = indices[bi]
        run = 1
        limit = 255 if wide else 127
        while bi + run < total and indices[bi + run] == val and run < limit:
            run += 1
        if wide:                            # CRW6: [tekrar][numara (index_bytes bayt)]
            out.append(run)
            out.extend(val.to_bytes(index_bytes, "big"))
        elif run > 1:                       # CRW5: v5 ile aynı
            out.append(0x80 | run)
            out.append(val)
        else:
            out.append(val)
        bi += run
    return out


def _build(orig_arr, size, base_img, base_colors, k, memory, flow=None):
    orig_w, orig_h = size
    base_w, base_h = base_img.size
    if memory is not None and memory.n > 0 and k is None:
        rgb = np.asarray(base_img, dtype=np.uint8).reshape(-1, 3)
        pal_arr, indices = _palette_from_memory(rgb, memory)                     # palet .crwm'den
        del rgb
    elif k is None:
        # hafıza yok/boş: palet resmin kendi tonları (kayıpsız)
        rgb = np.asarray(base_img, dtype=np.uint8).reshape(-1, 3)
        tones, inv = np.unique(_pack(rgb), return_inverse=True)
        pal_arr = np.stack([(tones >> 16) & 255, (tones >> 8) & 255, tones & 255], axis=1).astype(np.uint8)
        indices = inv.reshape(-1).astype(np.int64)
        del rgb
    else:
        palette, idx_list = _palette_for(base_img, k or len(base_colors), base_colors)
        if memory is not None:
            palette = memory.map_palette(palette)
        pal_arr = np.array(palette, dtype=np.uint8).reshape(-1, 3)
        indices = np.asarray(idx_list, dtype=np.int64)

    index_bytes = max(1, ((len(pal_arr) - 1).bit_length() + 7) // 8)
    base_payload = _base_payload_wide(indices, index_bytes)

    rec_base = Image.fromarray(pal_arr[indices].reshape(base_h, base_w, 3), "RGB")
    del indices
    if flow is not None:
        exp_img = flow_expand(rec_base, (orig_w, orig_h), flow)
    else:
        exp_img = rec_base.resize((orig_w, orig_h), Image.Resampling.BILINEAR)
    delta_payload = _delta_payload(orig_arr, exp_img)

    raw_body = struct.pack(">I", len(base_payload)) + base_payload + struct.pack(">I", len(delta_payload)) + delta_payload
    del base_payload, delta_payload
    body = zlib.compress(raw_body, level=9)
    del raw_body
    if flow is not None:
        header = b"CRW7" + struct.pack(">IIIIIB", orig_w, orig_h, base_w, base_h, len(pal_arr), index_bytes)
        header += pal_arr.tobytes()
        header += struct.pack(">HB", 0, 0)      # taban orijinal boyutta: açılışta büyütme yok
    else:
        header = b"CRW6" + struct.pack(">HHHHIB", orig_w, orig_h, base_w, base_h, len(pal_arr), index_bytes)
        header += pal_arr.tobytes()
    return header + body, pal_arr, exp_img


def encode_image_to_crw5(image_bytes, max_colors=None, memory=MEMORY):
    """
    Resmi CRW7'ye çevirir. Taban orijinal fotoğrafın kendisidir; detay katmanı
    orijinalden farklı her pikseli düzeltir (eşik 0). Palet .crwm hafızasından okunur: taban görüntüdeki her ton
    hafızadaki en yakın köke bağlanır, palet kullanılan köklerden oluşur. Kullanılan köklerin
    o anki renkleri dosyaya da yazılır (dosya hafızadan bağımsız açılır).
    max_colors verilirse eski yöntem (median-cut) o kadar renkle kullanılır (deneme amaçlı).
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size

    # Hafıza: resmin BÜTÜN tonları öğrenilir (aynı dosya ikinci kez öğretilmez) - yalnızca öğrenme açıksa
    memory_report = None
    if memory is not None and SITE_LEARNING:
        tones, counts = extract_tones(img)
        _, memory_report = memory.learn(tones, counts, key=fingerprint(image_bytes))
        if not memory_report.get("skipped"):
            memory.learn_paths(img)              # kapanış: küçükten büyüğe yolları öğren

    orig_arr = np.asarray(img, dtype=np.int16).reshape(-1, 3)
    # Palet .crwm'den: hafıza zenginleştikçe kullanılan kök çeşitliliği artar.
    flow = memory.flow_model() if memory is not None else None
    # Taban her zaman orijinal fotoğrafın kendisi: bulanık bir özetten değil,
    # gerçek piksellerden başlanır. (Netleştirme Detaylandır ile yapılır.)
    widths = [orig_w]
    tried, best, worse = [], None, 0
    for bw in widths:
        bh = max(1, round(orig_h * (bw / orig_w)))
        base_img = img if bw == orig_w else img.resize((bw, bh), Image.Resampling.BILINEAR)
        base_colors = base_img.getcolors(base_img.width * base_img.height) if max_colors else None
        res = _build(orig_arr, (orig_w, orig_h), base_img, base_colors, max_colors, memory, flow)
        tried.append([bw, len(res[0])])
        if best is None or len(res[0]) < len(best[0][0]):
            best, worse = (res, bw), 0
        else:
            worse += 1
            if worse >= 2:
                break
    (crw_bytes, palette, exp_img), base_width = best
    if memory is not None and SITE_LEARNING:
        memory.mark_seen(fingerprint(crw_bytes))    # bu dosya açılınca tekrar öğretilmesin

    preview_buf = io.BytesIO()
    exp_img.save(preview_buf, format="PNG")
    return {
        "width": orig_w,
        "height": orig_h,
        "raw_size": len(image_bytes),
        "crw_size": len(crw_bytes),
        "savings": round((1 - (len(crw_bytes) / len(image_bytes))) * 100, 1),
        "format": crw_bytes[:4].decode(),
        "palette_size": len(palette),
        "roots_used": len(palette),
        "memory_roots": memory.n if memory is not None else 0,
        "base_width": base_width,
        "tried": tried,
        "palette": palette[:256].tolist(),
        "memory": memory_report,
        "crw_base64": base64.b64encode(crw_bytes).decode(),
        "preview_url": f"data:image/png;base64,{base64.b64encode(preview_buf.getvalue()).decode()}"
    }


def crw_detail_offset(crw_data):
    """CRW7 dosyasında paletten sonraki işaretin konumu ve değeri: (konum, işaret) ya da (None, None)."""
    if crw_data[:4] != b"CRW7" or len(crw_data) < 28:
        return None, None
    pal_len = struct.unpack(">I", crw_data[20:24])[0]
    off = 25 + pal_len * 3
    return off, struct.unpack(">H", crw_data[off:off + 2])[0]


def decode_crw_image(crw_data, apply_detail=True):
    """
    CRW5/6/7 dosyasını açar: (PIL resim, bilgi) ya da None.
    Detaylı CRW7'de orijinal açıldıktan sonra dosyadaki adımlar dosyadaki yollarla uygulanır.
    """
    magic = crw_data[:4]
    if magic == b"CRW5" and len(crw_data) >= 14:
        orig_w, orig_h, base_w, base_h, pal_len = struct.unpack(">HHHHB", crw_data[4:13])
        off, index_bytes = 13, 1
    elif magic == b"CRW6" and len(crw_data) >= 18:
        orig_w, orig_h, base_w, base_h, pal_len, index_bytes = struct.unpack(">HHHHIB", crw_data[4:17])
        off = 17
    elif magic == b"CRW7" and len(crw_data) >= 26:
        orig_w, orig_h, base_w, base_h, pal_len, index_bytes = struct.unpack(">IIIIIB", crw_data[4:25])
        off = 25
    else:
        return None

    pal_arr = np.frombuffer(crw_data, dtype=np.uint8, count=pal_len * 3, offset=off).reshape(-1, 3)
    off += pal_len * 3
    flow = None
    ops, detail_model = "", None
    if magic == b"CRW7":
        keys, taps = struct.unpack(">HB", crw_data[off:off + 3])
        off += 3
        if keys == LEGACY_KEYS and taps == TAPS:        # önceki sürümün dosyası: sabit 384 yol
            flow = legacy_filters_from_bytes(crw_data[off:off + keys * taps * 2])
            off += keys * taps * 2
        elif keys == DETAIL_MARK and taps == TAPS:      # detaylı CRW: adımlar + piksel yolları
            nops = crw_data[off]
            ops = crw_data[off + 1: off + 1 + nops].decode()
            detail_model, off = model_from_bytes(crw_data, off + 1 + nops)
        elif keys != 0:
            return None
    body = zlib.decompress(crw_data[off:])

    base_len = struct.unpack(">I", body[0:4])[0]
    base_payload = body[4:4 + base_len]
    o = 4 + base_len
    delta_len = struct.unpack(">I", body[o:o + 4])[0]
    delta_payload = body[o + 4:o + 4 + delta_len]
    del body

    # Taban katmanı
    total_base = base_w * base_h
    if magic == b"CRW5":
        bp, bi = [], 0
        while bi < len(base_payload) and len(bp) < total_base:
            b = base_payload[bi]
            bi += 1
            if b & 0x80:
                bp.extend([base_payload[bi]] * (b & 0x7F))
                bi += 1
            else:
                bp.append(b)
        base_pixels = np.asarray(bp, dtype=np.int64)
    else:
        step = 1 + index_bytes
        arr = np.frombuffer(base_payload, dtype=np.uint8, count=(len(base_payload) // step) * step).reshape(-1, step)
        vals = np.zeros(len(arr), dtype=np.int64)
        for k in range(index_bytes):
            vals = (vals << 8) | arr[:, 1 + k]
        base_pixels = np.repeat(vals, arr[:, 0].astype(np.int64))
    base_pixels = base_pixels[:total_base]
    if len(base_pixels) < total_base:
        base_pixels = np.concatenate((base_pixels, np.zeros(total_base - len(base_pixels), dtype=np.int64)))
    rec_base = Image.fromarray(pal_arr[base_pixels].reshape(base_h, base_w, 3), "RGB")
    del base_pixels
    if flow is not None:
        exp_img = flow_expand(rec_base, (orig_w, orig_h), flow)     # akışkan açılış (eski CRW7)
    elif (base_w, base_h) == (orig_w, orig_h):
        exp_img = rec_base
    else:
        exp_img = rec_base.resize((orig_w, orig_h), Image.Resampling.BILINEAR)

    # Detay katmanı: değişen pikseller toplanır, sonra topluca uygulanır
    total_pixels = orig_w * orig_h
    pos_list, d_list = [], []
    dp = delta_payload
    di = pi = 0
    L = len(dp)
    while di < L and pi < total_pixels:
        tag = dp[di]
        if tag == 0x00:
            pi += dp[di + 1]
            di += 2
        elif tag == 0x01:
            pos_list.append(pi)
            d_list.append(struct.unpack_from("bbb", dp, di + 1))
            di += 4
            pi += 1
        elif tag == 0x02:
            pos_list.append(pi)
            d_list.append(struct.unpack_from(">hhh", dp, di + 1))
            di += 7
            pi += 1
        else:
            break
    final = np.asarray(exp_img, dtype=np.int16).reshape(-1, 3).copy()
    if pos_list:
        final[np.asarray(pos_list, dtype=np.int64)] += np.asarray(d_list, dtype=np.int16)
    final_img = Image.fromarray(np.clip(final, 0, 255).astype(np.uint8).reshape(orig_h, orig_w, 3), "RGB")
    del final, pos_list, d_list
    info = {"base_width": orig_w, "base_height": orig_h, "format": magic.decode(),
            "palette_size": pal_len, "ops": ops}
    if ops and apply_detail:
        final_img = apply_ops(final_img, ops, detail_model)
    info["width"], info["height"] = final_img.width, final_img.height
    return final_img, info


def decode_crw5_bytes(crw_data, memory=MEMORY):
    """Sitenin hızlı yolu: açar ve önizlemeyi döndürür (detaylı CRW'ler sırayla açılır)."""
    res = decode_crw_image(crw_data)
    if res is None:
        return None
    final_img, info = res
    out_buf = io.BytesIO()
    final_img.save(out_buf, format="PNG")

    # Başarılı açma: açılan resmin bütün tonları öğretilir (detay katmanının tonları dahil).
    # Açma her zaman dosyanın kendi paletiyle yapılır; hafıza sonucu değiştirmez.
    memory_report = None
    if memory is not None and SITE_LEARNING:
        try:
            tones, counts = extract_tones(final_img)
            _, memory_report = memory.learn(tones, counts, source="decode", key=fingerprint(crw_data))
        except Exception:
            traceback.print_exc()

    return {
        "width": info["width"],
        "height": info["height"],
        "size": len(crw_data),
        "format": info["format"],
        "palette_size": info["palette_size"],
        "ops": info["ops"],
        "memory": memory_report,
        "preview_url": f"data:image/png;base64,{base64.b64encode(out_buf.getvalue()).decode()}"
    }

def make_detail_crw(crw_data, ops, model):
    """
    Detaylı CRW: kaynak CRW7'nin (orijinal, kayıpsız) içine detay adımları ve piksel yolları yazılır.
    Açıcı adımları aynı yollarla tekrar üretir; sonuç ekranda görülenle aynıdır.
    """
    off, mark = crw_detail_offset(crw_data)
    if off is None:
        raise ValueError("detayli CRW icin kaynak dosya CRW7 olmali")
    if mark == DETAIL_MARK:                       # zaten detaylı: eski adımların üstüne eklenir
        nops = crw_data[off + 3]
        old_ops = crw_data[off + 4: off + 4 + nops].decode()
        _, end = model_from_bytes(crw_data, off + 4 + nops)
        ops = old_ops + ops
    elif mark == 0:
        end = off + 3
    else:
        raise ValueError("bu CRW7 dosyasina detay eklenemez")
    if not ops or len(ops) > 255 or set(ops) - {"U", "R"}:
        raise ValueError("gecersiz detay adimlari")
    block = struct.pack(">HB", DETAIL_MARK, TAPS) + bytes([len(ops)]) + ops.encode() + model_to_bytes(model)
    return crw_data[:off] + block + crw_data[end:]
