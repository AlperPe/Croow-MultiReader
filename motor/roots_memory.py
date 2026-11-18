#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
CROOW Kök Hafızası - tek dosya: universal_roots.crwm (sınırsız keşif)

- Hiçbir kök atılmaz. Hafıza dolunca kapasite iki katına çıkar (256 -> 512 -> ...), sonu yok.
- Her seviyede "tanıdık renk" mesafesi küçülür: hafıza büyüdükçe daha ince tonları ayırt eder.
  Mesafe en fazla RGB'nin kendi çözünürlüğüne (0.5) kadar iner; orada her tam sayı renk ayrı köktür.
- Resmin BÜTÜN tonları öğrenilir (sabit renk sayısı yok).
- Daha önce öğretilmiş dosya tekrar öğretilmez (parmak izi).

universal_roots.crwm (ikili, little-endian):
    b"CRWM" + [1 bayt sürüm]
    [u32 kök sayısı] [u32 resim sayacı] [u64 kapasite] [u64 toplam yeni] [u32 atlanan]
    [u16 kaynak sayısı] + her biri: [u8 ad uzunluğu][ad][u32 sayı]
    [u32 seviye atlama sayısı] + her biri: [u32 resim no][u64 yeni kapasite]
    kökler: rgb float32 x3 | güç float32 | son görülme int32   (her biri kök sayısı kadar)
    [u32 parmak izi sayısı] + her biri 10 bayt
    piksel yolu bölümü: b"PATH" + ... (paths_memory.py)

Önceki sürümlerin dosyaları (.bin, .stats.json, .state, .seen) .crwm yoksa bir kez içeri
alınır ve silinir.
"""
import array
import sys
import hashlib
import heapq
import json
import os
import struct
import tempfile
import threading
import time

from paths_memory import PathMemory, flow_expand, enhance_strips

BASE_CAPACITY = 256     # ilk seviye kapasite; sonrası sınırsız katlanır
BASE_SNAP = 12.0        # ilk seviyede "tanıdık" sayılan renk mesafesi (RGB öklid)
SNAP_SHRINK = 0.75      # her seviye atlamada mesafe bu oranla küçülür (daha detaylı)
RGB_RESOLUTION = 0.5    # tam sayı RGB'de iki farklı renk en az 1 uzaktadır
MIN_RATE = 0.05         # kökün yeni renge doğru en az kayma oranı
SAVE_INTERVAL = 5.0     # sunucuda hafıza en geç bu kadar saniyede bir diske yazılır
EXT_MAGIC = b"XR"       # yalnızca eski .bin dosyalarını okumak için
MEM_MAGIC = b"CRWM"
MEM_VERSION = 1
CHUNK = 65535


def fingerprint(data):
    """Dosyanın parmak izi (aynı bayt = aynı iz)."""
    return hashlib.sha1(data).hexdigest()[:20]


def extract_tones(img):
    """
    Resimdeki BÜTÜN farklı tonlar ve piksel sayıları, sıkıştırılmış olarak:
    (tonlar: uint32 r<<16|g<<8|b, sayılar). learn() bunu doğrudan kabul eder.
    """
    import numpy as np
    a = np.asarray(img.convert("RGB"), dtype=np.uint32).reshape(-1, 3)
    packed = (a[:, 0] << 16) | (a[:, 1] << 8) | a[:, 2]
    del a
    tones, counts = np.unique(packed, return_counts=True)
    return tones, counts



def _clamp(c):
    return max(0, min(255, round(c)))


if sys.byteorder != "little":
    raise RuntimeError("CRWM hafıza dosyası little-endian sistem gerektirir")


class RootsMemory:
    def __init__(self, path):
        self.path = path
        base = os.path.splitext(path)[0]
        self.mem_path = base + ".crwm"
        # önceki sürümlerin dosyaları: .crwm yoksa bir kez okunur, .crwm'ye taşınıp silinir
        self.bin_path = base + ".bin"
        self.stats_path = base + ".stats.json"
        self.state_path = base + ".state"
        self.seen_path = base + ".seen"
        self.lock = threading.RLock()
        # Kökler sıkışık dizilerde tutulur (kök başına 24 bayt): 16.7 milyon kök ~ 470 MB
        self.n = 0
        self.rgb = array.array("f")      # r, g, b, r, g, b, ...
        self.hits = array.array("f")     # kök gücü
        self.last = array.array("i")     # en son görüldüğü resim no
        self.nxt = array.array("i")      # aynı hücredeki bir sonraki kök (ızgara zinciri)
        self.head = array.array("i")     # hücre -> ilk kök (-1: boş)
        self.cell = 1.0
        self.dim = 1
        self.clock = 0
        self.capacity = BASE_CAPACITY
        self.total_new = 0
        self.level_ups = []
        self.sources = {}
        self.skipped = 0
        self.seen = set()
        self.dirty = False
        self.last_save = 0.0
        self.paths = PathMemory()   # piksel yolu hafızası (.crwm içinde)
        self._load()

    # ---------------- Seviye ----------------
    @property
    def level(self):
        lvl, cap = 0, BASE_CAPACITY
        while cap < self.capacity:
            cap *= 2
            lvl += 1
        return lvl

    @property
    def snap_dist(self):
        return max(RGB_RESOLUTION, BASE_SNAP * (SNAP_SHRINK ** self.level))

    # ---------------- Hızlı arama ızgarası ----------------
    # Hücre boyu tanıdık mesafeden küçük olmaz, bu yüzden komşu 27 hücreye bakmak yeterlidir.
    def _cell_of(self, r, g, b):
        cs, d = self.cell, self.dim
        return ((int(r // cs) * d) + int(g // cs)) * d + int(b // cs)

    def _rebuild_grid(self):
        self.cell = max(1.0, self.snap_dist)
        self.dim = int(256 // self.cell) + 2
        self.head = array.array("i", [-1]) * (self.dim ** 3)
        self.nxt = array.array("i", [-1]) * self.n
        rgb, head, nxt = self.rgb, self.head, self.nxt
        for i in range(self.n):
            c = self._cell_of(rgb[3 * i], rgb[3 * i + 1], rgb[3 * i + 2])
            nxt[i] = head[c]
            head[c] = i

    def _find(self, r, g, b):
        """Tanıdık mesafe içindeki en yakın kök numarası ya da -1."""
        cs, d = self.cell, self.dim
        x, y, z = int(r // cs), int(g // cs), int(b // cs)
        rgb, head, nxt = self.rgb, self.head, self.nxt
        best, best_d = -1, self.snap_dist ** 2
        for xx in (x - 1, x, x + 1):
            if xx < 0 or xx >= d:
                continue
            for yy in (y - 1, y, y + 1):
                if yy < 0 or yy >= d:
                    continue
                row = (xx * d + yy) * d
                for zz in (z - 1, z, z + 1):
                    if zz < 0 or zz >= d:
                        continue
                    i = head[row + zz]
                    while i >= 0:
                        j = 3 * i
                        dd = (rgb[j] - r) ** 2 + (rgb[j + 1] - g) ** 2 + (rgb[j + 2] - b) ** 2
                        if dd <= best_d:
                            best, best_d = i, dd
                        i = nxt[i]
        return best

    def _nearest_any(self, r, g, b):
        """Mesafe sınırı olmadan en yakın kök (halka halka genişleyen arama). Boşsa -1."""
        if self.n == 0:
            return -1
        cs, d = self.cell, self.dim
        x, y, z = int(r // cs), int(g // cs), int(b // cs)
        rgb, head, nxt = self.rgb, self.head, self.nxt
        best, best_d = -1, float("inf")
        R = 0
        while R <= d:
            for xx in range(x - R, x + R + 1):
                if xx < 0 or xx >= d:
                    continue
                ex = abs(xx - x) == R
                for yy in range(y - R, y + R + 1):
                    if yy < 0 or yy >= d:
                        continue
                    ey = ex or abs(yy - y) == R
                    row = (xx * d + yy) * d
                    zs = range(z - R, z + R + 1) if ey else (z - R, z + R)
                    for zz in zs:
                        if zz < 0 or zz >= d:
                            continue
                        i = head[row + zz]
                        while i >= 0:
                            j = 3 * i
                            dd = (rgb[j] - r) ** 2 + (rgb[j + 1] - g) ** 2 + (rgb[j + 2] - b) ** 2
                            if dd < best_d:
                                best, best_d = i, dd
                            i = nxt[i]
            # daha dıştaki halkalar en az R*cs uzakta: daha yakını olamaz
            if best >= 0 and best_d <= (R * cs) ** 2:
                break
            R += 1
        return best

    def nearest_roots(self, colors):
        """Her renk için hafızadaki en yakın kökün numarası (mesafe sınırı yok)."""
        with self.lock:
            return [self._nearest_any(float(c[0]), float(c[1]), float(c[2])) for c in colors]

    def _unlink(self, i, c):
        """Kökü hücre zincirinden çıkarır. Bulamazsa False (sonsuz döngü yok)."""
        head, nxt = self.head, self.nxt
        if head[c] == i:
            head[c] = nxt[i]
            return True
        p = head[c]
        while p >= 0 and nxt[p] != i:
            p = nxt[p]
        if p < 0:
            return False
        nxt[p] = nxt[i]
        return True

    def _move(self, i, r, g, b):
        # Hücreler her zaman SAKLANMIŞ (float32'ye yuvarlanmış) değerden hesaplanır;
        # yoksa sınırdaki bir renk yanlış hücrede aranır.
        j = 3 * i
        rgb = self.rgb
        old_c = self._cell_of(rgb[j], rgb[j + 1], rgb[j + 2])
        rgb[j], rgb[j + 1], rgb[j + 2] = r, g, b
        new_c = self._cell_of(rgb[j], rgb[j + 1], rgb[j + 2])
        if old_c != new_c:
            if not self._unlink(i, old_c):
                self._rebuild_grid()        # tutarsızlık olursa ızgarayı baştan kur
                return
            self.nxt[i] = self.head[new_c]
            self.head[new_c] = i

    def _add(self, r, g, b, weight):
        i = self.n
        self.rgb.extend((r, g, b))
        self.hits.append(weight)
        self.last.append(self.clock)
        j = 3 * i
        c = self._cell_of(self.rgb[j], self.rgb[j + 1], self.rgb[j + 2])
        self.nxt.append(self.head[c])
        self.head[c] = i
        self.n += 1

    def root(self, i):
        j = 3 * i
        return (self.rgb[j], self.rgb[j + 1], self.rgb[j + 2])

    # ---------------- Dosya ----------------
    def _read_bin(self):
        if not os.path.exists(self.bin_path):
            return b""
        try:
            with open(self.bin_path, "rb") as f:
                data = f.read()
            n = data[0]
            out = bytearray(data[1:1 + n * 3])
            off = 1 + n * 3
            while data[off:off + 2] == EXT_MAGIC:
                extra = struct.unpack(">H", data[off + 2:off + 4])[0]
                out += data[off + 4: off + 4 + extra * 3]
                off += 4 + extra * 3
            return bytes(out[: len(out) // 3 * 3])
        except Exception:
            return b""

    def _load_crwm(self):
        """universal_roots.crwm okunur (asıl kaynak). Kök sayısını dosyanın kendisi belirler."""
        if not os.path.exists(self.mem_path):
            return False
        try:
            with open(self.mem_path, "rb") as f:
                d = f.read()
            if d[:4] != MEM_MAGIC:
                return False
            off = 5
            count, clock, capacity, total_new, skipped = struct.unpack_from("<IIQQI", d, off)
            off += 28
            n = count
            sources = {}
            (ns,) = struct.unpack_from("<H", d, off); off += 2
            for _ in range(ns):
                ln = d[off]; off += 1
                name = d[off:off + ln].decode(); off += ln
                (cnt,) = struct.unpack_from("<I", d, off); off += 4
                sources[name] = cnt
            (nl,) = struct.unpack_from("<I", d, off); off += 4
            level_ups = []
            for _ in range(nl):
                level_ups.append(list(struct.unpack_from("<IQ", d, off))); off += 12
            rgb, hits, last = array.array("f"), array.array("f"), array.array("i")
            rgb.frombytes(d[off: off + n * 12]); off += n * 12
            hits.frombytes(d[off: off + n * 4]); off += n * 4
            last.frombytes(d[off: off + n * 4]); off += n * 4
            (nseen,) = struct.unpack_from("<I", d, off); off += 4
            seen = {d[off + i * 10: off + i * 10 + 10].hex() for i in range(nseen)}
            off += nseen * 10
            self.paths, off = PathMemory.from_bytes(d, off)
        except Exception:
            return False
        if len(rgb) != n * 3 or len(hits) != n or len(last) != n:
            return False
        self.rgb, self.hits, self.last = rgb, hits, last
        self.n = n
        self.clock, self.capacity, self.total_new, self.skipped = clock, capacity, total_new, skipped
        self.sources, self.level_ups, self.seen = sources, level_ups, seen
        return True

    def _load_legacy(self, n):
        """Önceki sürümlerin .stats.json / .state / .seen dosyaları."""
        stats = {}
        if os.path.exists(self.stats_path):
            try:
                with open(self.stats_path) as f:
                    stats = json.load(f)
            except Exception:
                stats = {}
        loaded = False
        if os.path.exists(self.state_path) and stats.get("count") == n and stats.get("state") == 2:
            with open(self.state_path, "rb") as f:
                raw = f.read()
            if len(raw) == n * 20:
                self.rgb.frombytes(raw[: n * 12])
                self.hits.frombytes(raw[n * 12: n * 16])
                self.last.frombytes(raw[n * 16:])
                loaded = True
        elif len(stats.get("roots", [])) == n and n:
            for r in stats["roots"]:
                self.rgb.extend(float(c) for c in r["rgb"])
                self.hits.append(float(r["hits"]))
                self.last.append(int(r["last"]))
            loaded = True
        if loaded:
            self.clock = stats.get("clock", 0)
            self.total_new = stats.get("total_new", 0)
            self.level_ups = stats.get("level_ups", [])
            self.sources = stats.get("sources", {})
            self.skipped = stats.get("skipped", 0)
            self.capacity = stats.get("capacity", BASE_CAPACITY)
        if os.path.exists(self.seen_path):
            with open(self.seen_path) as f:
                self.seen = {line.strip() for line in f if line.strip()}
        return loaded

    def _load(self):
        migrated = False
        if self._load_crwm():
            n = self.n
        else:
            bin_rgb = self._read_bin()
            n = len(bin_rgb) // 3
            self.rgb, self.hits, self.last = array.array("f"), array.array("f"), array.array("i")
            if not self._load_legacy(n):
                # eski .bin tek başına (v4 / swarm): istatistikler sıfırdan
                self.rgb = array.array("f", list(bin_rgb))
                self.hits = array.array("f", [1.0]) * n
                self.last = array.array("i", [0]) * n
            migrated = any(os.path.exists(p) for p in (self.bin_path, self.stats_path, self.state_path, self.seen_path))
        self.n = n
        while self.n >= self.capacity:
            self.capacity *= 2
        self._rebuild_grid()
        if migrated:
            self._save()
            for p in (self.bin_path, self.stats_path, self.state_path, self.seen_path):
                if os.path.exists(p):
                    os.remove(p)

    def _atomic_write(self, path, data, mode):
        d = os.path.dirname(os.path.abspath(path))
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_roots_")
        with os.fdopen(fd, mode) as f:
            f.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)

    def _save(self):
        n = self.n
        mem = bytearray(MEM_MAGIC) + bytes([MEM_VERSION])
        mem += struct.pack("<IIQQI", n, self.clock, self.capacity, self.total_new, self.skipped)
        mem += struct.pack("<H", len(self.sources))
        for name, cnt in self.sources.items():
            nb = name.encode()[:255]
            mem += bytes([len(nb)]) + nb + struct.pack("<I", cnt)
        mem += struct.pack("<I", len(self.level_ups))
        for clk, cap in self.level_ups:
            mem += struct.pack("<IQ", clk, cap)
        mem += self.rgb.tobytes() + self.hits.tobytes() + self.last.tobytes()
        mem += struct.pack("<I", len(self.seen))
        mem += b"".join(bytes.fromhex(k) for k in self.seen)
        mem += self.paths.to_bytes()
        self._atomic_write(self.mem_path, bytes(mem), "wb")
        self.dirty = False
        self.last_save = time.time()

    def save(self):
        """Hafızayı hemen diske yazar."""
        with self.lock:
            self._save()

    def flush(self):
        """Değişiklik varsa diske yazar."""
        with self.lock:
            if self.dirty:
                self._save()

    def start_autosave(self):
        """Sunucu için: değişiklikleri birkaç saniyede bir arka planda diske yazar."""
        def loop():
            while True:
                time.sleep(SAVE_INTERVAL)
                try:
                    self.flush()
                except Exception:
                    pass
        threading.Thread(target=loop, daemon=True).start()

    # ---------------- Parmak izleri ----------------
    def _mark(self, keys):
        fresh = [k for k in keys if k and k not in self.seen]
        if fresh:
            self.seen.update(fresh)
            self.dirty = True

    def mark_seen(self, *keys):
        with self.lock:
            self._mark(keys)

    def is_seen(self, key):
        with self.lock:
            return key in self.seen

    # ---------------- Öğrenme ----------------
    def learn(self, palette, counts=None, source="encode", key=None, save=True):
        """
        palette: resmin tonları [(r,g,b), ...] - sayı sınırı yok
        counts : her tonun piksel sayısı (yoksa hepsi eşit sayılır)
        key    : dosyanın parmak izi; daha önce öğretildiyse hafıza değişmez
        save   : True ise en geç SAVE_INTERVAL saniyede bir diske yazılır
        Dönüş : (köklere oturtulmuş palet, rapor)
        """
        packed = hasattr(palette, "dtype") and getattr(palette, "ndim", 0) == 1
        if counts is None:
            counts = [1] * len(palette)
        total_px = max(1, int(sum(counts)) if not hasattr(counts, "sum") else int(counts.sum()))
        n_tones = len(palette)
        if packed:                                    # sıkıştırılmış tonlar (extract_tones)
            pk = palette.tolist()
            palette = ((v >> 16, (v >> 8) & 255, v & 255) for v in pk)
            counts = counts.tolist()

        with self.lock:
            if key is not None and key in self.seen:
                self.skipped += 1
                self.dirty = True
                mapped = None if packed else self._map_only(palette)
                return mapped, self._report(tones=n_tones, skipped="tekrar")
            self.clock += 1
            self.sources[source] = self.sources.get(source, 0) + 1
            out = None if packed else []      # sıkıştırılmış girdide çıktı listesi tutulmaz
            add_out = (lambda t: None) if packed else out.append
            familiar = new = 0
            level_up = None
            hits, rgb = self.hits, self.rgb

            for c, cnt in zip(palette, counts):
                r, g, b = float(c[0]), float(c[1]), float(c[2])
                if cnt <= 0:
                    add_out((_clamp(r), _clamp(g), _clamp(b)))
                    continue
                weight = cnt / total_px * n_tones          # baskın tonlar daha çok öğretir
                i = self._find(r, g, b)
                if i >= 0:
                    # TANIDIK: köke otur, kök bu tona doğru kayar (gelişir)
                    hits[i] += weight
                    rate = max(MIN_RATE, weight / hits[i])
                    j = 3 * i
                    self._move(i, rgb[j] + (r - rgb[j]) * rate,
                               rgb[j + 1] + (g - rgb[j + 1]) * rate,
                               rgb[j + 2] + (b - rgb[j + 2]) * rate)
                    self.last[i] = self.clock
                    familiar += 1
                    add_out((_clamp(rgb[j]), _clamp(rgb[j + 1]), _clamp(rgb[j + 2])))
                else:
                    # YENİ TON: yer yoksa kapasite katlanır (sınır yok), ızgara incelir
                    if self.n >= self.capacity:
                        self.capacity *= 2
                        level_up = self.capacity
                        self.level_ups.append([self.clock, self.capacity])
                        self._rebuild_grid()
                    self._add(r, g, b, weight)
                    new += 1
                    add_out((_clamp(r), _clamp(g), _clamp(b)))

            self.total_new += new
            self.dirty = True
            if key is not None:
                self._mark([key])
            if save and time.time() - self.last_save >= SAVE_INTERVAL:
                self._save()
            return out, self._report(tones=n_tones, familiar=familiar, new=new, level_up=level_up)

    def learn_paths(self, img):
        """Piksel yollarını öğrenir: bulanıklaştır, aç, gerçekle karşılaştır; yollar ikiye bölünerek büyür."""
        with self.lock:
            self.paths.learn(img)
            self.dirty = True

    def flow_model(self):
        with self.lock:
            return self.paths.model()

    def enhance(self, img):
        """Resmi öğrenilmiş piksel yollarıyla ×2 detaylandırır."""
        return enhance_strips(img, self.flow_model())

    def _map_only(self, palette):
        out = []
        for c in palette:
            i = self._find(float(c[0]), float(c[1]), float(c[2]))
            src = self.root(i) if i >= 0 else c
            out.append(tuple(_clamp(x) for x in src))
        return out

    def map_palette(self, palette):
        """Hafızayı değiştirmeden renkleri en yakın tanıdık köke oturtur."""
        with self.lock:
            return self._map_only(palette)

    def _report(self, tones=0, familiar=0, new=0, level_up=None, skipped=None):
        return {
            "roots": self.n,
            "capacity": self.capacity,
            "level": self.level,
            "snap_dist": round(self.snap_dist, 3),
            "tones": tones,
            "familiar": familiar,
            "new": new,
            "level_up": level_up,
            "images_seen": self.clock,
            "skipped": skipped,
        }

    def summary(self):
        with self.lock:
            top = heapq.nlargest(16, range(self.n), key=self.hits.__getitem__)
            return {
                "roots": self.n,
                "capacity": self.capacity,
                "level": self.level,
                "snap_dist": round(self.snap_dist, 3),
                "images_seen": self.clock,
                "learned_from": dict(self.sources),
                "skipped_repeats": self.skipped,
                "known_files": len(self.seen),
                "total_new": self.total_new,
                "level_ups": self.level_ups,
                **self.paths.summary(),
                "strongest": [[_clamp(x) for x in self.root(i)] for i in top],
            }
