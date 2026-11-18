#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
CROOW Piksel Yolu Hafızası - ikiye bölünerek sınırsız büyüyen yollar.

Öğrenme: her resim ×2 küçültülüp tekrar büyütülür (bulanıklaştır-aç); büyütülmüş görüntüdeki
her pikselin 5x5 komşuluğu ile gerçek pikseli arasındaki ilişki, pikselin yoluna göre biriktirilir.

Yol ağacı:
  - Başlangıçta alt-piksel konumu başına bir yol vardır (4 kök yol).
  - Her pikselin üç özelliği vardır: kenar yönü, kenar gücü, kenar netliği (hepsi 0..1).
  - Bir yol yeterince örnek görünce sıradaki eksende (yön -> güç -> netlik -> yön ...) ortadan
    İKİYE bölünür. Alt yollar da öğrendikçe bölünür; derinlik sınırı yoktur.
  - Derin yolların bölünmesi için daha çok örnek gerekir (her üç bölünmede iki katı).
  - Az örnek görmüş yol, üstündeki yolun süzgecini kullanır.

Detaylandırma: resim ×2 büyütülür, her piksel kendi yolunun süzgeciyle yeniden hesaplanır.
Parlaklık (Y) öğrenilmiş yollarla, renk (Cb, Cr) yumuşak büyütmeyle işlenir.
"""
import struct

import numpy as np
from PIL import Image

R = 2                        # 5x5 komşuluk
TAPS = (2 * R + 1) ** 2
ROOTS = 4                    # alt-piksel konumu başına bir kök yol
DIMS = 3                     # yön, güç, netlik
STRENGTH_SCALE = 10.0
SPLIT_BASE = 32768           # bölünme için gereken örnek (her 3 derinlikte iki katı)
MIN_SAMPLES = 256            # bu kadar örnek görmemiş yol üstündekini kullanır
REG = 1e-3
TILE_ROWS = 256              # yalnızca eski CRW7 dosyaları için (aynı döşeme gerekir)
TILE_PIXELS = 131072         # bellek dostu döşeme: her seferde bu kadar piksel
MAGIC = b"PTH2"

# ---- önceki sürümün sabit 384 yolu (yalnızca eski CRW7 dosyalarını açmak için) ----
_L_ANGLES, _L_STRENGTHS, _L_COHERENCES = 8, 4, 3
LEGACY_KEYS = _L_ANGLES * _L_STRENGTHS * _L_COHERENCES * 4
_L_STRENGTH_EDGES = (3.0, 10.0, 30.0)
_L_COHERENCE_EDGES = (0.25, 0.5)


# ---------------- Ortak yardımcılar ----------------
def _upscale2(ch):
    h, w = ch.shape
    return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize((w * 2, h * 2), Image.Resampling.BILINEAR))


def _resize_f(ch, w, h):
    return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize((w, h), Image.Resampling.BILINEAR))


def _box3(a):
    p = np.pad(a, 1, mode="edge")
    return sum(p[dy:dy + a.shape[0], dx:dx + a.shape[1]] for dy in range(3) for dx in range(3))


def _structure(U):
    gy, gx = np.gradient(U)
    gxx, gyy, gxy = _box3(gx * gx), _box3(gy * gy), _box3(gx * gy)
    tr = gxx + gyy
    disc = np.sqrt(np.maximum((gxx - gyy) ** 2 + 4 * gxy * gxy, 0))
    l1, l2 = (tr + disc) / 2, np.maximum((tr - disc) / 2, 0)
    s1, s2 = np.sqrt(l1), np.sqrt(l2)
    angle = (0.5 * np.arctan2(2 * gxy, gxx - gyy) + np.pi / 2) / np.pi          # 0..1
    coh = np.where(s1 + s2 > 1e-6, (s1 - s2) / (s1 + s2 + 1e-12), 0)
    return angle, s1, coh


def _features(U, y0):
    """(özellikler N x 3 [yön, güç, netlik] 0..1, alt-piksel konumu N)"""
    angle, s1, coh = _structure(U)
    feats = np.stack([np.minimum(angle, 0.999999), s1 / (s1 + STRENGTH_SCALE), np.minimum(coh, 0.999999)],
                     axis=-1).reshape(-1, DIMS)
    yy, xx = np.mgrid[y0:y0 + U.shape[0], 0:U.shape[1]]
    phase = ((yy % 2) * 2 + (xx % 2)).reshape(-1)
    return feats, phase


CTX = 4                      # kenar hesabında döşemenin üst/altından bakılan satır (dikiş izi olmasın)


def _features_ctx(U, r0, r1):
    """[r0, r1) satırlarının özellikleri, komşu satırlar da hesaba katılarak (döşeme sınırında dikiş yok)."""
    c0, c1 = max(0, r0 - CTX), min(U.shape[0], r1 + CTX)
    feats, phase = _features(U[c0:c1], c0)
    W = U.shape[1]
    lo, hi = (r0 - c0) * W, (r1 - c0) * W
    return feats[lo:hi], phase[lo:hi]


def _patches(Up, r0, r1, w):
    cols = [Up[r0 + dy: r1 + dy, dx: dx + w].reshape(-1) for dy in range(2 * R + 1) for dx in range(2 * R + 1)]
    return np.stack(cols, axis=1)


def _luma(img):
    return np.asarray(img.convert("YCbCr"), dtype=np.float32)[:, :, 0]


def _split_need(depth):
    return SPLIT_BASE * (2 ** (int(depth) // DIMS))


# ---------------- Yol ağacı (öğrenme ve kullanım) ----------------
class FlowModel:
    """Yol ağacının çözülmüş hali: her pikseli yaprağına götürür, süzgecini uygular."""

    def __init__(self, child, lo, hi, depth, filters):
        self.child, self.lo, self.hi, self.depth, self.filters = child, lo, hi, depth, filters

    def route(self, feats, phase):
        node = phase.astype(np.int64)
        while True:
            ch = self.child[node, 0]
            idx = np.flatnonzero(ch >= 0)
            if len(idx) == 0:
                return node
            nd = node[idx]
            d = self.depth[nd] % DIMS
            mid = (self.lo[nd, d] + self.hi[nd, d]) / 2
            go = (feats[idx, d] >= mid).astype(np.int64)
            node[idx] = self.child[nd, go]

    def up2(self, Y):
        """Parlaklığı ×2 büyütür: her piksel 2x2'ye bölünür, değerler yolların süzgeçlerinden."""
        U = _upscale2(Y)
        H, W = U.shape
        Up = np.pad(U, R, mode="edge")
        out = np.empty_like(U)
        rows = max(4, TILE_PIXELS // W)
        for r0 in range(0, H, rows):
            r1 = min(H, r0 + rows)
            feats, phase = _features_ctx(U, r0, r1)
            leaf = self.route(feats, phase)
            A = _patches(Up, r0, r1, W)
            out[r0:r1] = np.einsum("nt,nt->n", A, self.filters[leaf]).reshape(r1 - r0, W)
        return out


class PathMemory:
    def __init__(self):
        self.n = ROOTS
        cap = 64
        self.child = np.full((cap, 2), -1, dtype=np.int64)
        self.parent = np.full(cap, -1, dtype=np.int64)
        self.depth = np.zeros(cap, dtype=np.int64)
        self.lo = np.zeros((cap, DIMS))
        self.hi = np.ones((cap, DIMS))
        self.ata = np.zeros((cap, TAPS, TAPS))
        self.atb = np.zeros((cap, TAPS))
        self.cnt = np.zeros(cap, dtype=np.int64)
        self.images = 0
        self.splits = 0
        self._model = None

    # ---- kapasite: düğüm dizileri dolunca ikiye katlanır ----
    def _grow(self, need):
        cap = len(self.cnt)
        if need <= cap:
            return
        while cap < need:
            cap *= 2
        def ext(a, fill):
            b = np.full((cap,) + a.shape[1:], fill, dtype=a.dtype)
            b[:len(a)] = a
            return b
        self.child, self.parent, self.depth = ext(self.child, -1), ext(self.parent, -1), ext(self.depth, 0)
        self.lo, self.hi = ext(self.lo, 0.0), ext(self.hi, 1.0)
        self.ata, self.atb, self.cnt = ext(self.ata, 0.0), ext(self.atb, 0.0), ext(self.cnt, 0)

    def _split(self, node):
        """Yolu sıradaki eksende ortadan ikiye böler."""
        self._grow(self.n + 2)
        d = int(self.depth[node]) % DIMS
        mid = (self.lo[node, d] + self.hi[node, d]) / 2
        for side in (0, 1):
            c = self.n
            self.n += 1
            self.parent[c] = node
            self.depth[c] = self.depth[node] + 1
            self.lo[c], self.hi[c] = self.lo[node], self.hi[node]
            if side == 0:
                self.hi[c, d] = mid
            else:
                self.lo[c, d] = mid
            self.child[node, side] = c
        self.splits += 1

    def _arrays(self):
        n = self.n
        return self.child[:n], self.lo[:n], self.hi[:n], self.depth[:n]

    # ---- öğrenme: bulanıklaştır, aç, gerçekle karşılaştır ----
    def learn(self, img):
        Y = _luma(img)
        h, w = (Y.shape[0] // 2) * 2, (Y.shape[1] // 2) * 2
        if h < 8 or w < 8:
            return
        HR = Y[:h, :w]
        LR = HR.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3))
        U = _upscale2(LR)
        Up = np.pad(U, R, mode="edge")
        rows = max(4, TILE_PIXELS // w)
        for r0 in range(0, h, rows):
            r1 = min(h, r0 + rows)
            feats, phase = _features_ctx(U, r0, r1)
            child, lo, hi, depth = self._arrays()
            leaf = FlowModel(child, lo, hi, depth, None).route(feats, phase)
            A = _patches(Up, r0, r1, w).astype(np.float64)
            b = HR[r0:r1].reshape(-1).astype(np.float64)
            order = np.argsort(leaf, kind="stable")
            ks, A, b = leaf[order], A[order], b[order]
            bounds = np.flatnonzero(np.diff(ks)) + 1
            for s, e in zip(np.concatenate(([0], bounds)), np.concatenate((bounds, [len(ks)]))):
                k = ks[s]
                As = A[s:e]
                self.ata[k] += As.T @ As
                self.atb[k] += As.T @ b[s:e]
                self.cnt[k] += e - s
            # yeterince öğrenmiş yapraklar ikiye bölünür (sınırsız)
            for k in np.unique(ks).tolist():
                if self.child[k, 0] < 0 and self.cnt[k] >= _split_need(self.depth[k]):
                    self._split(k)
        self.images += 1
        self._model = None

    # ---- süzgeçler ----
    def model(self):
        if self._model is None:
            n = self.n
            own = np.zeros((n, TAPS), dtype=np.float32)
            usable = self.cnt[:n] >= MIN_SAMPLES
            ident = np.zeros(TAPS, dtype=np.float32)
            ident[TAPS // 2] = 1.0
            for k in np.flatnonzero(usable):
                a = self.ata[k]
                lam = REG * (np.trace(a) / TAPS + 1.0)
                try:
                    own[k] = np.linalg.solve(a + lam * np.eye(TAPS), self.atb[k])
                except np.linalg.LinAlgError:
                    usable[k] = False
            resolved = np.zeros((n, TAPS), dtype=np.float32)
            for k in range(n):                      # ebeveynler her zaman çocuklardan önce gelir
                if usable[k]:
                    resolved[k] = own[k]
                elif self.parent[k] >= 0:
                    resolved[k] = resolved[self.parent[k]]
                else:
                    resolved[k] = ident             # hiç öğrenilmemiş: yumuşak büyütme
            child, lo, hi, depth = self._arrays()
            self._model = FlowModel(child.copy(), lo.copy(), hi.copy(), depth.copy(), resolved)
        return self._model

    def summary(self):
        n = self.n
        leaves = int((self.child[:n, 0] < 0).sum())
        return {
            "path_images": self.images,
            "paths": leaves,
            "paths_learned": int(((self.child[:n, 0] < 0) & (self.cnt[:n] >= MIN_SAMPLES)).sum()),
            "path_nodes": n,
            "path_depth": int(self.depth[:n].max()),
            "path_splits": self.splits,
        }

    # ---- detaylandırma ----
    def enhance(self, img):
        return flow_expand(img, (img.width * 2, img.height * 2), self.model())

    # ---- .crwm içindeki bölüm ----
    def to_bytes(self):
        n = self.n
        return (MAGIC + struct.pack("<IIQQ", n, TAPS, self.images, self.splits)
                + self.child[:n].astype("<i8").tobytes() + self.parent[:n].astype("<i8").tobytes()
                + self.depth[:n].astype("<i8").tobytes() + self.lo[:n].astype("<f8").tobytes()
                + self.hi[:n].astype("<f8").tobytes() + self.ata[:n].astype("<f8").tobytes()
                + self.atb[:n].astype("<f8").tobytes() + self.cnt[:n].astype("<i8").tobytes())

    @classmethod
    def from_bytes(cls, d, off):
        """(PathMemory, yeni_off). Bölüm yoksa ya da eski sürümse boş hafıza (yollar baştan öğrenilir)."""
        pm = cls()
        if d[off:off + 4] != MAGIC:
            return pm, off
        n, taps, images, splits = struct.unpack_from("<IIQQ", d, off + 4)
        if taps != TAPS:
            return pm, off
        o = off + 4 + 24
        pm._grow(n)
        def take(dtype, shape):
            nonlocal o
            count = int(np.prod(shape))
            a = np.frombuffer(d, dtype, count, o).reshape(shape).copy()
            o += count * np.dtype(dtype).itemsize
            return a
        pm.child[:n] = take("<i8", (n, 2))
        pm.parent[:n] = take("<i8", (n,))
        pm.depth[:n] = take("<i8", (n,))
        pm.lo[:n] = take("<f8", (n, DIMS))
        pm.hi[:n] = take("<f8", (n, DIMS))
        pm.ata[:n] = take("<f8", (n, TAPS, TAPS))
        pm.atb[:n] = take("<f8", (n, TAPS))
        pm.cnt[:n] = take("<i8", (n,))
        pm.n, pm.images, pm.splits = n, images, splits
        return pm, o


# ---------------- Büyütme ----------------
def flow_expand(img, size, flow):
    """
    Görüntüyü hedef boyuta adım adım büyütür: her adımda her piksel 2x2'ye bölünür
    (parlaklık öğrenilmiş yollarla, renk yumuşak büyütmeyle); kalan kesirli oran tek yumuşak adımla.
    flow: FlowModel (yol ağacı) ya da eski CRW7 dosyalarının 384 x 25 süzgeç dizisi.
    """
    W, H = size
    if (img.width, img.height) == (W, H):
        return img.copy()
    up = flow.up2 if isinstance(flow, FlowModel) else (lambda Y: _legacy_up2(Y, flow))
    ycc = np.asarray(img.convert("YCbCr"), dtype=np.float32)
    Y, Cb, Cr = ycc[:, :, 0], ycc[:, :, 1], ycc[:, :, 2]
    while Y.shape[1] * 2 <= W and Y.shape[0] * 2 <= H:
        Y = up(Y)
        Cb, Cr = _upscale2(Cb), _upscale2(Cr)
    if (Y.shape[1], Y.shape[0]) != (W, H):
        Y, Cb, Cr = (_resize_f(c, W, H) for c in (Y, Cb, Cr))
    ycc2 = np.clip(np.rint(np.stack([Y, Cb, Cr], axis=2)), 0, 255).astype(np.uint8)
    return Image.fromarray(ycc2, "YCbCr").convert("RGB")


def model_to_bytes(model):
    """Yol ağacını dosyaya yazar (detaylı CRW için): [u32 düğüm][u8 katsayı][çocuklar i32][süzgeçler f32]."""
    n = len(model.child)
    return (struct.pack("<IB", n, TAPS) + model.child.astype("<i4").tobytes()
            + model.filters.astype("<f4").tobytes())


def model_from_bytes(d, off):
    """Dosyadaki yol ağacını okur: (FlowModel, yeni_off). Kutular ve derinlikler ağaçtan yeniden kurulur."""
    n, taps = struct.unpack_from("<IB", d, off)
    if taps != TAPS:
        raise ValueError("yol tablosu uyumsuz")
    o = off + 5
    child = np.frombuffer(d, "<i4", n * 2, o).reshape(n, 2).astype(np.int64); o += n * 8
    filters = np.frombuffer(d, "<f4", n * TAPS, o).reshape(n, TAPS).astype(np.float32); o += n * TAPS * 4
    depth = np.zeros(n, dtype=np.int64)
    lo, hi = np.zeros((n, DIMS)), np.ones((n, DIMS))
    for k in range(n):                       # ebeveynler çocuklardan önce gelir
        if child[k, 0] >= 0:
            dd = int(depth[k]) % DIMS
            mid = (lo[k, dd] + hi[k, dd]) / 2
            for side in (0, 1):
                c = child[k, side]
                depth[c] = depth[k] + 1
                lo[c], hi[c] = lo[k], hi[k]
                if side == 0:
                    hi[c, dd] = mid
                else:
                    lo[c, dd] = mid
    return FlowModel(child, lo, hi, depth, filters), o


def apply_ops(img, ops, model):
    """Detay adımlarını sırayla uygular: 'U' = ×2 detaylandır, 'R' = yarı boyuttan motorla yeniden çiz."""
    for op in ops:
        if op == "R":
            img = enhance_strips(img.resize((max(1, img.width // 2), max(1, img.height // 2)),
                                            Image.Resampling.BOX), model)
        elif op == "U":
            img = enhance_strips(img, model)
        else:
            raise ValueError(f"bilinmeyen adim: {op}")
    return img


def enhance_strips(img, model, strip=256, margin=8):
    """
    ×2 detaylandırma, bellek dostu: resim yatay şeritler halinde büyütülür ve sonuca yazılır.
    Her şerit kenarlarından 'margin' satır fazla alınır ve kırpılır; sonuç tek seferde
    işlenmiş haliyle aynıdır, şerit sınırında kayma olmaz.
    """
    W, H = img.size
    ycc = np.asarray(img.convert("YCbCr"))                # uint8, kaynak
    out = np.empty((H * 2, W * 2, 3), dtype=np.uint8)     # sonuç
    for s0 in range(0, H, strip):
        s1 = min(H, s0 + strip)
        a, b = max(0, s0 - margin), min(H, s1 + margin)
        part = ycc[a:b].astype(np.float32)
        Y = model.up2(part[:, :, 0])
        Cb, Cr = _upscale2(part[:, :, 1]), _upscale2(part[:, :, 2])
        top, rows = 2 * (s0 - a), 2 * (s1 - s0)
        sl = np.stack([Y[top:top + rows], Cb[top:top + rows], Cr[top:top + rows]], axis=2)
        rgb = Image.fromarray(np.clip(np.rint(sl), 0, 255).astype(np.uint8), "YCbCr").convert("RGB")
        out[2 * s0: 2 * s0 + rows] = np.asarray(rgb)
    return Image.fromarray(out, "RGB")


# ---------------- Eski CRW7 dosyaları (sabit 384 yol) ----------------
def _legacy_keys(U, y0):
    angle, s1, coh = _structure(U)
    a_bin = np.minimum((angle * _L_ANGLES).astype(np.int32), _L_ANGLES - 1)
    s_bin = np.searchsorted(_L_STRENGTH_EDGES, s1).astype(np.int32)
    c_bin = np.searchsorted(_L_COHERENCE_EDGES, coh).astype(np.int32)
    yy, xx = np.mgrid[y0:y0 + U.shape[0], 0:U.shape[1]]
    phase = (yy % 2) * 2 + (xx % 2)
    return ((a_bin * _L_STRENGTHS + s_bin) * _L_COHERENCES + c_bin) * 4 + phase


def _legacy_up2(Y, filters):
    U = _upscale2(Y)
    H, W = U.shape
    Up = np.pad(U, R, mode="edge")
    out = np.empty_like(U)
    for r0 in range(0, H, TILE_ROWS):
        r1 = min(H, r0 + TILE_ROWS)
        k = _legacy_keys(U[r0:r1], r0).reshape(-1)
        A = _patches(Up, r0, r1, W)
        out[r0:r1] = np.einsum("nt,nt->n", A, filters[k]).reshape(r1 - r0, W)
    return out


def legacy_filters_from_bytes(data):
    return np.frombuffer(data, dtype="<f2", count=LEGACY_KEYS * TAPS).astype(np.float32).reshape(LEGACY_KEYS, TAPS)
