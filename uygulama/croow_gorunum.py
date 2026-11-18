#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
croow_gorunum.py - Resim görüntüleyici: yakınlaştırma / uzaklaştırma, kaydırma, bölge seçimi, kutu düzenleme.

Resim her seferinde YALNIZCA GÖRÜNEN KISMI için çizilir (büyük sayfalar 32 kat yakınlaştırılabilir, bellek şişmez).
Bütün koordinatlar RESİM koordinatıdır (ekran koordinatı değil); bindirmeler (çerçeveler) resim koordinatında verilir.

Araçlar:
  tikla  : tık -> tikla_cb(ix, iy, olay). Seçili kutu (duzenle_ata) tutamaklarından sürüklenirse kutu düzenlenir:
           kenar/köşe = boyut, içi = taşı. Shift+sürükle = yeni kutu çiz.
  bolge  : sürükleyerek dikdörtgen bölge seç (bolge_cb)
  esle   : tık -> esle_cb(ix, iy, olay)  (eşleştirme modu)
Fare: tekerlek = kaydır, Shift+tekerlek = yatay, Ctrl+tekerlek = imlecin olduğu yere yakınlaştır, orta/sağ tuş sürükle = kaydır.
"""
import io
import math

from PIL import Image

ZOOM_MIN, ZOOM_MAX = 0.02, 40.0
TUTAMAK = 7            # ekranda tutamak yakalama mesafesi (piksel)


class Gorunum:
    def __init__(self, tk, ttk, cerceve):
        self.tk, self.ttk = tk, ttk
        self.img = None
        self.z = None                          # None = sığdır
        self.x = self.y = 0.0                  # görünümün sol-üst köşesi (resim koordinatı)
        self.foto = None
        self.bindirmeler = {}                  # etiket -> [(x0, y0, x1, y1, renk, kalinlik, kesik)]
        self.bolge = None
        self.duzenle = None                    # (x0, y0, x1, y1) düzenlenen kutu (resim koordinatı)
        self._surukle = None
        # geri çağrılar (uygulama atar)
        self.tikla_cb = self.esle_cb = self.bolge_cb = self.duzenle_cb = self.yeni_kutu_cb = self.sil_cb = None
        self.arac_cb = None
        self.bu_budur_cb = None                # seçili bölgeyi öğret (uygulama atar)
        self.ogret_cb = None                   # Öğret aracı: sürüklenen dikdörtgen (resim koordinatı)

        self.cerceve = cerceve
        ara = ttk.Frame(cerceve)
        ara.pack(side="top", fill="x")
        self.ara = ara                         # araç çubuğu (yan panel bunun önüne yerleşir)
        ttk.Button(ara, text="−", width=3, command=lambda: self.yakinlas(1 / 1.25)).pack(side="left")
        ttk.Button(ara, text="+", width=3, command=lambda: self.yakinlas(1.25)).pack(side="left", padx=(2, 0))
        ttk.Button(ara, text="Sığdır", command=self.sigdir).pack(side="left", padx=(6, 0))
        ttk.Button(ara, text="%100", width=5, command=self.yuzde100).pack(side="left", padx=(2, 0))
        self.zoom_etiket = ttk.Label(ara, text="", width=7)
        self.zoom_etiket.pack(side="left", padx=(6, 12))
        self.arac = tk.StringVar(value="tikla")
        for ad, metin in (("tikla", "Harf / kelime"), ("ogret", "Öğret"), ("bolge", "Bölge seç"), ("esle", "Eşleştir"),
                          ("sil", "Sil"), ("ciz", "Çiz")):
            ttk.Radiobutton(ara, text=metin, value=ad, variable=self.arac, command=self._arac_degisti).pack(side="left", padx=2)
        ttk.Button(ara, text="Bölgeyi temizle", command=lambda: self.bolge_ata(None, bildir=True)).pack(side="left", padx=(10, 0))
        ttk.Button(ara, text="Bu budur…", command=lambda: self.bu_budur_cb and self.bu_budur_cb()).pack(side="left", padx=(6, 0))
        self.bolge_etiket = ttk.Label(ara, text="")
        self.bolge_etiket.pack(side="left", padx=8)

        # fırça ayarları (yalnızca Sil / Çiz araçlarında görünür)
        self.bolge_poly = None                 # esnek bölge: [[x, y], ...] (resim koordinatı; 8 köşeyle başlar, sağ tıkla artar)
        self.bolge_poly_cb = None              # uygulama atar: bolge_poly_cb(poly ya da None)
        self.sekizgen_cb = None                # uygulama atar: seçili bölgeyi mürekkebe yapıştırıp 8 noktalı çerçeve yap
        self.hizli_cb = None                   # uygulama atar: hizli_cb(ix, iy, ekle, olay) — Ctrl+tık hızlı seçim
        self.firca_cb = None                   # uygulama atar: firca_cb(olay 'bas'|'hareket'|'birak', ix, iy)
        self.firca_f = ttk.Frame(cerceve)
        r1 = ttk.Frame(self.firca_f)
        r1.pack(side="top", fill="x")
        r2 = ttk.Frame(self.firca_f)
        r2.pack(side="top", fill="x")
        self.firca_boyut = tk.IntVar(value=14)
        self.firca_sertlik = tk.DoubleVar(value=70)
        self.firca_saydamlik = tk.DoubleVar(value=100)
        self._firca_et = {}
        for ad, degisken, a_, b_, metin in (("boyut", self.firca_boyut, 2, 90, "Boyut"),
                                            ("sertlik", self.firca_sertlik, 0, 100, "Sertlik"),
                                            ("saydamlik", self.firca_saydamlik, 5, 100, "Saydamlık")):
            ttk.Label(r1, text=metin).pack(side="left", padx=(8, 2))
            ttk.Scale(r1, from_=a_, to=b_, variable=degisken, length=110,
                      command=lambda v, ad=ad: self._firca_guncelle()).pack(side="left")
            self._firca_et[ad] = ttk.Label(r1, text="", width=5)
            self._firca_et[ad].pack(side="left")
        self.oneri_var = tk.BooleanVar(value=False)                 # Croow'un önerileri (turuncu) — varsayılan KAPALI: yalnızca izler
        self.oneri_uygula_cb = None
        ttk.Checkbutton(r2, text="Önerileri göster", variable=self.oneri_var).pack(side="left", padx=(12, 2))
        ttk.Button(r2, text="Önerileri uygula", command=lambda: self.oneri_uygula_cb and self.oneri_uygula_cb()).pack(side="left")
        self.izleme_et = ttk.Label(r2, text="", foreground="#2a6a2a")
        self.izleme_et.pack(side="left", padx=8)
        self.firca_ipucu = ttk.Label(r2, text="  Sil: kâğıt rengine boyar · Çiz: mürekkep ekler · Ctrl+Z geri alır",
                                     foreground="#555")
        self.firca_ipucu.pack(side="left", padx=8)
        self._firca_guncelle()

        # bölge işlemleri (yalnızca 'Bölge seç' aracında görünür)
        self.bolge_islem_cb = None             # uygulama atar: bolge_islem_cb(ic: bool)
        self.bolge_f = ttk.Frame(cerceve)
        ttk.Label(self.bolge_f, text="  Seçili bölge:").pack(side="left")
        ttk.Button(self.bolge_f, text="İçini riskli temizle", command=lambda: self.bolge_islem_cb and self.bolge_islem_cb(True)).pack(side="left", padx=4)
        ttk.Button(self.bolge_f, text="Dışını riskli temizle", command=lambda: self.bolge_islem_cb and self.bolge_islem_cb(False)).pack(side="left")
        ttk.Button(self.bolge_f, text="Mürekkebe yapıştır (8 nokta)",
                   command=lambda: self.sekizgen_cb and self.sekizgen_cb()).pack(side="left", padx=(0, 4))
        self.sinif_cb = None                   # uygulama atar: sinif_cb(sinif, sil: bool)
        mb = ttk.Menubutton(self.bolge_f, text="Seçileni öğret ▾")
        mm = tk.Menu(mb, tearoff=0)
        for ad, metin, sil in (("leke", "Leke", False), ("leke", "Leke ve sil", True), ("metin", "Metin (yazı)", False),
                               ("cizgi", "Alt çizgi", False), ("cizgi", "Alt çizgi ve sil", True),
                               ("karartma", "Karartma / sansür", False), ("damga", "Damga / mühür", False),
                               ("imza", "İmza / el yazısı", False), ("diger", "Diğer… (kendi kategorini aç)", False)):
            mm.add_command(label=metin, command=lambda ad=ad, sil=sil: self.sinif_cb and self.sinif_cb(ad, sil))
        mb["menu"] = mm
        mb.pack(side="left", padx=(8, 4))
        ttk.Label(self.bolge_f, text="  Yazı mı leke mi anlar: yazı varsa korur, yoksa hepsini siler · Ctrl+Z geri alır",
                  foreground="#555").pack(side="left", padx=8)

        govde = ttk.Frame(cerceve)
        self.govde = govde
        govde.pack(side="top", fill="both", expand=True)
        self.ysb = ttk.Scrollbar(govde, orient="vertical", command=self._ykaydir)
        self.xsb = ttk.Scrollbar(govde, orient="horizontal", command=self._xkaydir)
        self.ysb.pack(side="right", fill="y")
        self.xsb.pack(side="bottom", fill="x")
        self.tuval = tk.Canvas(govde, background="#2b2b2b", highlightthickness=0, takefocus=1)
        self.tuval.pack(fill="both", expand=True)
        t = self.tuval
        t.bind("<Configure>", lambda e: self.yenile())
        t.bind("<ButtonPress-1>", self._bas)
        t.bind("<B1-Motion>", self._hareket)
        t.bind("<ButtonRelease-1>", self._birak)
        t.bind("<Motion>", self._imlec)
        t.bind("<Leave>", lambda e: t.delete("halka"))
        t.bind("<ButtonPress-2>", self._kaydir_bas)
        t.bind("<B2-Motion>", self._kaydir_hareket)
        t.bind("<ButtonPress-3>", self._sag_bas)                    # sağ: sürükle = kaydır; sürüklemeden tık = çerçevede nokta aç/sil
        t.bind("<B3-Motion>", self._kaydir_hareket)
        t.bind("<ButtonRelease-3>", self._sag_birak)
        t.bind("<MouseWheel>", self._tekerlek)
        t.bind("<Button-4>", lambda e: self._tekerlek(e, 1))
        t.bind("<Button-5>", lambda e: self._tekerlek(e, -1))
        t.bind("<Control-plus>", lambda e: self.yakinlas(1.25))
        t.bind("<Control-equal>", lambda e: self.yakinlas(1.25))
        t.bind("<Control-minus>", lambda e: self.yakinlas(1 / 1.25))
        t.bind("<Control-0>", lambda e: self.sigdir())
        t.bind("<Delete>", lambda e: self.sil_cb and self.sil_cb())
        t.bind("<BackSpace>", lambda e: self.sil_cb and self.sil_cb())
        for tus, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            t.bind(f"<{tus}>", lambda e, dx=dx, dy=dy: self._ok(dx, dy, False))
            t.bind(f"<Shift-{tus}>", lambda e, dx=dx, dy=dy: self._ok(dx, dy, True))

    # ------------------------------------------------------------------ koordinat
    def _boyut(self):
        return max(50, self.tuval.winfo_width()), max(50, self.tuval.winfo_height())

    def zoom(self):
        """Şu anki etkin yakınlaştırma (1.0 = gerçek boyut)."""
        if self.img is None:
            return 1.0
        if self.z is not None:
            return self.z
        W, H = self._boyut()
        return min(W / self.img.width, H / self.img.height, 1.0)

    def c2i(self, cx, cy):
        z = self.zoom()
        return self.x + cx / z, self.y + cy / z

    def i2c(self, ix, iy):
        z = self.zoom()
        return (ix - self.x) * z, (iy - self.y) * z

    # ------------------------------------------------------------------ gösterim
    def goster(self, img, sigdir=True):
        """Yeni resim göster. sigdir: pencereye sığdır (False: gerçek boyut)."""
        yeni = self.img is None or img.size != self.img.size
        self.img = img
        if sigdir:
            self.z = None
        elif sigdir is False:
            self.z = 1.0
        if yeni:
            self.x = self.y = 0.0
        self.yenile()

    def degistir(self, img):
        """Resmi, yakınlaştırmayı ve konumu koruyarak değiştir (işlem sonucu)."""
        self.img = img
        self.yenile()

    def yenile(self):
        if self.img is None:
            return
        t = self.tuval
        W, H = self._boyut()
        iw, ih = self.img.size
        z = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom()))
        if self.z is not None:
            self.z = z
        vw, vh = W / z, H / z
        self.x = min(max(self.x, 0.0), max(0.0, iw - vw))
        self.y = min(max(self.y, 0.0), max(0.0, ih - vh))
        bx0, by0 = int(math.floor(self.x)), int(math.floor(self.y))
        bx1, by1 = min(iw, int(math.ceil(self.x + vw)) + 1), min(ih, int(math.ceil(self.y + vh)) + 1)
        kes = self.img.crop((bx0, by0, bx1, by1)).convert("RGB")
        nw, nh = max(1, int(round((bx1 - bx0) * z))), max(1, int(round((by1 - by0) * z)))
        yontem = Image.Resampling.NEAREST if z >= 2 else (Image.Resampling.BILINEAR if z >= 0.5 else Image.Resampling.BOX)
        kes = kes.resize((nw, nh), yontem)
        tampon = io.BytesIO()
        kes.save(tampon, format="PPM")
        self.foto = self.tk.PhotoImage(data=tampon.getvalue())
        t.delete("resim")
        t.create_image(-(self.x - bx0) * z, -(self.y - by0) * z, anchor="nw", image=self.foto, tags="resim")
        t.tag_lower("resim")
        self.ysb.set(self.y / ih, min(1.0, (self.y + vh) / ih))
        self.xsb.set(self.x / iw, min(1.0, (self.x + vw) / iw))
        self.zoom_etiket.configure(text=f"%{100 * z:.0f}")
        self._bindirme_ciz()

    # ------------------------------------------------------------------ yakınlaştırma
    def yakinlas(self, kat, cx=None, cy=None):
        if self.img is None:
            return
        W, H = self._boyut()
        cx, cy = (W / 2, H / 2) if cx is None else (cx, cy)
        ix, iy = self.c2i(cx, cy)
        z = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom() * kat))
        self.z = z
        self.x, self.y = ix - cx / z, iy - cy / z
        self.yenile()

    def sigdir(self):
        self.z = None
        self.x = self.y = 0.0
        self.yenile()

    def yuzde100(self):
        W, H = self._boyut()
        ix, iy = self.c2i(W / 2, H / 2)
        self.z = 1.0
        self.x, self.y = ix - W / 2, iy - H / 2
        self.yenile()

    def git(self, ix, iy):
        """Görünümü resim noktasına ortala."""
        W, H = self._boyut()
        z = self.zoom()
        self.x, self.y = ix - W / (2 * z), iy - H / (2 * z)
        self.yenile()

    # ------------------------------------------------------------------ kaydırma
    def _ykaydir(self, *a):
        if self.img is None:
            return
        H = self._boyut()[1]
        vh = H / self.zoom()
        if a[0] == "moveto":
            self.y = float(a[1]) * self.img.height
        else:
            self.y += int(a[1]) * (vh * 0.9 if a[2] == "pages" else vh * 0.1)
        self.yenile()

    def _xkaydir(self, *a):
        if self.img is None:
            return
        W = self._boyut()[0]
        vw = W / self.zoom()
        if a[0] == "moveto":
            self.x = float(a[1]) * self.img.width
        else:
            self.x += int(a[1]) * (vw * 0.9 if a[2] == "pages" else vw * 0.1)
        self.yenile()

    def _tekerlek(self, e, yon=None):
        if self.img is None:
            return
        if yon is None:                                           # Windows / macOS
            yon = 1 if e.delta > 0 else -1
        if e.state & 0x4:                                         # Ctrl: yakınlaştır
            self.yakinlas(1.25 if yon > 0 else 1 / 1.25, e.x, e.y)
        elif e.state & 0x1:                                       # Shift: yatay
            self.x -= yon * self._boyut()[0] / self.zoom() * 0.1
            self.yenile()
        else:
            self.y -= yon * self._boyut()[1] / self.zoom() * 0.1
            self.yenile()

    def _kaydir_bas(self, e):
        self._pan = (e.x, e.y, self.x, self.y)

    def _kaydir_hareket(self, e):
        if getattr(self, "_pan", None):
            cx, cy, x, y = self._pan
            z = self.zoom()
            self.x, self.y = x - (e.x - cx) / z, y - (e.y - cy) / z
            self.yenile()

    # ------------------------------------------------------------------ bindirmeler
    def bindir(self, etiket, dikdortgenler):
        """dikdortgenler: [(x0, y0, x1, y1, renk, kalinlik, kesik)] resim koordinatında."""
        self.bindirmeler[etiket] = list(dikdortgenler)
        self._bindirme_ciz()

    def bindir_sil(self, etiket):
        self.bindirmeler.pop(etiket, None)
        self._bindirme_ciz()

    def _bindirme_ciz(self):
        t = self.tuval
        t.delete("bind")
        if self.img is None:
            return
        liste = [r for l in self.bindirmeler.values() for r in l]
        if self.bolge:
            liste.append((*self.bolge, "#ffd23a", 2 if not self.bolge_poly else 1, (6, 4)))
        if self.bolge_poly:                                           # esnek çerçeve: çokgen + tutma noktaları
            zp = []
            for x, y in self.bolge_poly:
                zp += list(self.i2c(x, y))
            t.create_polygon(zp, outline="#ffd23a", fill="", width=2, tags="bind")
            for k in range(0, len(zp), 2):
                t.create_rectangle(zp[k] - 4, zp[k + 1] - 4, zp[k] + 4, zp[k + 1] + 4, fill="#ffffff", outline="#ff7a00",
                                   width=2, tags="bind")
        for r in liste:
            x0, y0, x1, y1, renk, kal, kesik = r[:7]
            a, b = self.i2c(x0, y0)
            c, d = self.i2c(x1, y1)
            t.create_rectangle(a, b, c, d, outline=renk, width=kal, dash=kesik or (), tags="bind")
            if len(r) > 7 and r[7]:                                   # isteğe bağlı etiket (örneğin öğretilen harf)
                t.create_text(a + 1, b - 1, text=r[7], anchor="sw", fill=renk, font=("TkDefaultFont", 9, "bold"), tags="bind")
        if self.duzenle:
            x0, y0, x1, y1 = self.duzenle
            a, b = self.i2c(x0, y0)
            c, d = self.i2c(x1, y1)
            t.create_rectangle(a, b, c, d, outline="#2a6cf0", width=2, tags="bind")
            for hx, hy in self._tutamaklar(a, b, c, d):
                t.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill="#ffffff", outline="#2a6cf0", tags="bind")

    @staticmethod
    def _tutamaklar(a, b, c, d):
        return [(a, b), ((a + c) / 2, b), (c, b), (c, (b + d) / 2), (c, d), ((a + c) / 2, d), (a, d), (a, (b + d) / 2)]

    # ------------------------------------------------------------------ bölge
    def bolge_ata(self, dikdortgen, bildir=False, poly=None):
        """Bölgeyi ata. poly verilirse ESNEK (çok noktalı) çerçeve: işlemler dikdörtgen yerine çokgenin içinde çalışır."""
        self.bolge = tuple(dikdortgen) if dikdortgen else None
        self.bolge_poly = [list(map(float, p)) for p in poly] if (poly and self.bolge) else None
        self.bolge_etiket.configure(text="" if not self.bolge else
                                    f"bölge {int(self.bolge[2] - self.bolge[0])}×{int(self.bolge[3] - self.bolge[1])} px"
                                    + (f" · {len(self.bolge_poly)} nokta" if self.bolge_poly else ""))
        self._bindirme_ciz()
        if bildir and self.bolge_cb:
            self.bolge_cb(self.bolge)
        if bildir and self.bolge_poly_cb:
            self.bolge_poly_cb(self.bolge_poly)

    # ------------------------------------------------------------------ esnek çerçeve (çok noktalı bölge)
    def _poly_bbox(self):
        xs = [p[0] for p in self.bolge_poly]
        ys = [p[1] for p in self.bolge_poly]
        return (min(xs), min(ys), max(xs), max(ys))

    def _poly_yakin(self, cx, cy):
        """Tuval noktasına en yakın: ('nokta', i) | ('kenar', i, ix, iy) | None"""
        import math
        pts = self.bolge_poly
        if not pts:
            return None
        n_ = len(pts)
        kisa = min(math.hypot(*[u - v for u, v in zip(self.i2c(*pts[i]), self.i2c(*pts[(i + 1) % n_]))]) for i in range(n_))
        en, sec = max(4.0, min(12.0, 0.4 * kisa)), None       # küçük çokgende noktalar birbirini yutmasın
        for i, (x, y) in enumerate(pts):
            a, b = self.i2c(x, y)
            d = math.hypot(a - cx, b - cy)
            if d <= en:
                en, sec = d, ("nokta", i)
        if sec:
            return sec
        en = max(3.0, min(9.0, 0.35 * kisa))
        n = len(pts)
        for i in range(n):
            a0, b0 = self.i2c(*pts[i])
            a1, b1 = self.i2c(*pts[(i + 1) % n])
            dx, dy = a1 - a0, b1 - b0
            uz = dx * dx + dy * dy
            if uz < 1e-6:
                continue
            t = max(0.0, min(1.0, ((cx - a0) * dx + (cy - b0) * dy) / uz))
            d = math.hypot(a0 + t * dx - cx, b0 + t * dy - cy)
            if d <= en:
                ix, iy = self.c2i(a0 + t * dx, b0 + t * dy)
                en, sec = d, ("kenar", i, ix, iy)
        return sec

    def _poly_degisti(self):
        """Çokgen değişti: sınır kutusunu güncelle, uygulamaya bildir."""
        x0, y0, x1, y1 = self._poly_bbox()
        self.bolge = (x0, y0, x1, y1)
        self.bolge_etiket.configure(text=f"bölge {int(x1 - x0)}×{int(y1 - y0)} px · {len(self.bolge_poly)} nokta")
        self._bindirme_ciz()
        if self.bolge_cb:
            self.bolge_cb(self.bolge)
        if self.bolge_poly_cb:
            self.bolge_poly_cb(self.bolge_poly)

    def _sag_bas(self, e):
        self._sag = (e.x, e.y)
        self._kaydir_bas(e)

    def _sag_birak(self, e):
        """Sağ tık (sürüklemeden): çerçevenin KENARINDA yeni tutma noktası aç; var olan noktanın üstündeyse sil (en az 3)."""
        bas, self._sag = getattr(self, "_sag", None), None
        if bas is None or abs(e.x - bas[0]) + abs(e.y - bas[1]) > 4 or not self.bolge_poly or self.img is None:
            return
        y = self._poly_yakin(e.x, e.y)
        if not y:
            return
        if y[0] == "kenar":
            W, H = self.img.size
            self.bolge_poly.insert(y[1] + 1, [max(0.0, min(W - 1.0, y[2])), max(0.0, min(H - 1.0, y[3]))])
        elif len(self.bolge_poly) > 3:
            self.bolge_poly.pop(y[1])
        else:
            return
        self._poly_degisti()

    def _arac_degisti(self):
        if self.arac_cb:
            self.arac_cb(self.arac.get())
        a = self.arac.get()
        self.tuval.configure(cursor="crosshair" if a in ("bolge", "ogret", "sil", "ciz") else "")
        self.tuval.delete("halka")
        if a in ("sil", "ciz"):
            if not self.firca_f.winfo_ismapped():
                self.firca_f.pack(side="top", fill="x", before=self.govde)
        else:
            self.firca_f.pack_forget()
        if a == "bolge":
            if not self.bolge_f.winfo_ismapped():
                self.bolge_f.pack(side="top", fill="x", before=self.govde)
        else:
            self.bolge_f.pack_forget()

    def _firca_guncelle(self):
        self._firca_et["boyut"].configure(text=f"{int(self.firca_boyut.get())} px")
        self._firca_et["sertlik"].configure(text=f"%{int(self.firca_sertlik.get())}")
        self._firca_et["saydamlik"].configure(text=f"%{int(self.firca_saydamlik.get())}")

    def firca_ayar(self):
        """Fırça: {'boyut': resim pikseli çapı, 'sertlik': 0..1, 'saydamlik': 0..1}"""
        return {"boyut": max(1, int(self.firca_boyut.get())), "sertlik": float(self.firca_sertlik.get()) / 100.0,
                "saydamlik": float(self.firca_saydamlik.get()) / 100.0}

    def _halka(self, e):
        """Fırça çapını gösteren halka (fare ucunda)."""
        a = self.arac.get()
        t = self.tuval
        t.delete("halka")
        r = max(2.0, self.firca_boyut.get() / 2 * self.zoom())
        renk = "#ff4040" if a == "sil" else "#30b0ff"
        t.create_oval(e.x - r, e.y - r, e.x + r, e.y + r, outline=renk, width=2, tags="halka")
        t.create_oval(e.x - r * self.firca_sertlik.get() / 100, e.y - r * self.firca_sertlik.get() / 100,
                      e.x + r * self.firca_sertlik.get() / 100, e.y + r * self.firca_sertlik.get() / 100,
                      outline=renk, dash=(2, 3), tags="halka")

    # ------------------------------------------------------------------ kutu düzenleme
    def duzenle_ata(self, dikdortgen):
        """Düzenlenebilir kutuyu ata (None: yok). Resim koordinatı."""
        self.duzenle = tuple(dikdortgen) if dikdortgen else None
        self._bindirme_ciz()

    def _tutamak_bul(self, cx, cy):
        """Düzenlenen kutuda tıklanan tutamak: 'tasi' | 'n','s','e','w','ne','nw','se','sw' | None"""
        if not self.duzenle:
            return None
        x0, y0, x1, y1 = self.duzenle
        a, b = self.i2c(x0, y0)
        c, d = self.i2c(x1, y1)
        yak = lambda v, w: abs(v - w) <= TUTAMAK
        icte_x, icte_y = a - TUTAMAK <= cx <= c + TUTAMAK, b - TUTAMAK <= cy <= d + TUTAMAK
        if not (icte_x and icte_y):
            return None
        sol, sag, ust, alt = yak(cx, a), yak(cx, c), yak(cy, b), yak(cy, d)
        yatay = "w" if sol else ("e" if sag else "")
        dikey = "n" if ust else ("s" if alt else "")
        if yatay or dikey:
            return dikey + yatay
        return "tasi" if (a < cx < c and b < cy < d) else None

    def _imlec(self, e):
        if self.arac.get() in ("sil", "ciz"):
            return self._halka(e)
        if self.arac.get() not in ("tikla", "ogret") or self._surukle:
            return
        tut = self._tutamak_bul(e.x, e.y)
        imlec = {"tasi": "fleur", "n": "sb_v_double_arrow", "s": "sb_v_double_arrow", "e": "sb_h_double_arrow",
                 "w": "sb_h_double_arrow", "ne": "top_right_corner", "sw": "bottom_left_corner",
                 "nw": "top_left_corner", "se": "bottom_right_corner"}.get(tut, "")
        self.tuval.configure(cursor=imlec)

    def _ok(self, dx, dy, buyut):
        """Ok tuşu: seçili kutuyu 1 piksel taşı (Shift: sağ/alt kenarı büyüt)."""
        if not self.duzenle or not self.duzenle_cb:
            return
        x0, y0, x1, y1 = self.duzenle
        yeni = (x0, y0, x1 + dx, y1 + dy) if buyut else (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        yeni = self._sinirla(yeni)
        self.duzenle = yeni
        self._bindirme_ciz()
        self.duzenle_cb(yeni, True)

    def _sinirla(self, r):
        """Dikdörtgeni resim sınırlarına çeker, sıralar, en az 2 piksel yapar."""
        iw, ih = self.img.size
        x0, y0, x1, y1 = r
        x0, x1 = (max(0, min(iw, int(round(v)))) for v in (x0, x1))
        y0, y1 = (max(0, min(ih, int(round(v)))) for v in (y0, y1))
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if x1 - x0 < 2:
            x0, x1 = (max(0, x1 - 2), x1) if x1 >= 2 else (0, min(iw, 2))
        if y1 - y0 < 2:
            y0, y1 = (max(0, y1 - 2), y1) if y1 >= 2 else (0, min(ih, 2))
        return (x0, y0, x1, y1)

    # ------------------------------------------------------------------ fare
    def _bas(self, e):
        if self.img is None:
            return
        self.tuval.focus_set()
        ix, iy = self.c2i(e.x, e.y)
        arac = self.arac.get()
        self._surukle = {"cx": e.x, "cy": e.y, "ix": ix, "iy": iy, "kayma": False, "arac": arac, "mod": None}
        if (e.state & 0x4) and arac not in ("sil", "ciz"):          # Ctrl+tık: iz üstünde HIZLI SEÇİM (Shift de varsa seçime ekler)
            self._surukle["mod"] = "hizli"
            self._surukle["ekle"] = bool(e.state & 0x1)
            return
        if arac in ("sil", "ciz"):
            self._surukle["mod"] = "firca"
            if self.firca_cb:
                self.firca_cb("bas", ix, iy)
            return
        if self.bolge_poly:                                         # esnek çerçevenin tutma noktasını sürükle
            y = self._poly_yakin(e.x, e.y)
            if y and y[0] == "nokta":
                self._surukle.update(mod="poly", nokta=y[1])
                return
        if arac == "bolge":
            self._surukle["mod"] = "bolge"
        elif arac == "ogret":
            tut = self._tutamak_bul(e.x, e.y)
            if tut:                                                # seçili (sıkı) kutuyu düzelt
                self._surukle.update(mod="duzenle", tut=tut, ilk=self.duzenle)
            else:                                                  # yeni seçim çiz
                self._surukle["mod"] = "secim"
        elif arac == "tikla":
            if e.state & 0x1:                                      # Shift: yeni kutu çiz
                self._surukle["mod"] = "yeni"
            else:
                tut = self._tutamak_bul(e.x, e.y)
                if tut:
                    self._surukle.update(mod="duzenle", tut=tut, ilk=self.duzenle)

    def _hareket(self, e):
        s = self._surukle
        if not s:
            return
        if s["mod"] == "hizli":
            return
        if s["mod"] == "poly":
            W, H = self.img.size
            ix, iy = self.c2i(e.x, e.y)
            self.bolge_poly[s["nokta"]] = [max(0.0, min(W - 1.0, ix)), max(0.0, min(H - 1.0, iy))]
            s["kayma"] = True
            self.bolge = self._poly_bbox()
            self._bindirme_ciz()
            return
        if s["mod"] == "firca":
            s["kayma"] = True
            self._halka(e)
            if self.firca_cb:
                self.firca_cb("hareket", *self.c2i(e.x, e.y))
            return
        if not s["kayma"] and abs(e.x - s["cx"]) + abs(e.y - s["cy"]) < 4:
            return
        s["kayma"] = True
        ix, iy = self.c2i(e.x, e.y)
        mod = s["mod"]
        if mod == "bolge":
            self.bolge = self._sinirla((s["ix"], s["iy"], ix, iy))
            self._bindirme_ciz()
        elif mod == "yeni":
            self.bindirmeler["yeni_kutu"] = [(*self._sinirla((s["ix"], s["iy"], ix, iy)), "#30c030", 2, (4, 3))]
            self._bindirme_ciz()
        elif mod == "secim":
            self.bindirmeler["secim"] = [(*self._sinirla((s["ix"], s["iy"], ix, iy)), "#2a6cf0", 2, (4, 3))]
            self._bindirme_ciz()
        elif mod == "duzenle":
            x0, y0, x1, y1 = s["ilk"]
            dx, dy = ix - s["ix"], iy - s["iy"]
            t = s["tut"]
            if t == "tasi":
                x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy
            else:
                if "w" in t:
                    x0 += dx
                if "e" in t:
                    x1 += dx
                if "n" in t:
                    y0 += dy
                if "s" in t:
                    y1 += dy
            self.duzenle = self._sinirla((x0, y0, x1, y1))
            self._bindirme_ciz()

    def _birak(self, e):
        s, self._surukle = self._surukle, None
        if not s:
            return
        ix, iy = self.c2i(e.x, e.y)
        mod = s["mod"]
        if mod == "firca":
            if self.firca_cb:
                self.firca_cb("birak", ix, iy)
            return
        if mod == "poly":
            if s["kayma"]:
                self._poly_degisti()
            return
        if mod == "hizli":
            if self.hizli_cb:
                self.hizli_cb(s["ix"], s["iy"], s["ekle"], e)
            return
        if not s["kayma"]:                                         # tıklama
            if s["arac"] == "bolge":
                self.bolge_ata(None, bildir=True)
            elif s["arac"] == "esle" and self.esle_cb:
                self.esle_cb(s["ix"], s["iy"], e)
            elif s["arac"] == "tikla" and self.tikla_cb:
                self.tikla_cb(s["ix"], s["iy"], e)
            return
        if mod == "bolge":
            r = self._sinirla((s["ix"], s["iy"], ix, iy))
            self.bolge_ata(r if (r[2] - r[0] >= 8 and r[3] - r[1] >= 8) else None, bildir=True)
        elif mod == "secim":
            self.bindirmeler.pop("secim", None)
            r = self._sinirla((s["ix"], s["iy"], ix, iy))
            self._bindirme_ciz()
            if self.ogret_cb and r[2] - r[0] >= 4 and r[3] - r[1] >= 4:
                self.ogret_cb(r)
        elif mod == "yeni":
            self.bindirmeler.pop("yeni_kutu", None)
            r = self._sinirla((s["ix"], s["iy"], ix, iy))
            self._bindirme_ciz()
            if self.yeni_kutu_cb and r[2] - r[0] >= 3 and r[3] - r[1] >= 3:
                self.yeni_kutu_cb(r)
        elif mod == "duzenle" and self.duzenle_cb:
            self.duzenle_cb(self.duzenle, True)
