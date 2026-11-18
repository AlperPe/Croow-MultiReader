"""Croow dosya seçici (Tk'nin kendi dosya penceresinin yerine).

Neden: Tk'nin yerleşik penceresinde 'Directory' açılır menüsüne ortadan tıklayıp fareyi bırakınca üstteki klasör
seçilip pencere kapanabiliyor. Burada açılır menü yok: klasör listesi, yol satırı, Yukarı/Ev/İndirilenler düğmeleri var;
tıklama yalnızca seçer, çift tık / Enter açar. tkinter.filedialog'un askopenfilename / askopenfilenames /
asksaveasfilename / askdirectory işlevleriyle aynı imzalar ve dönüş değerleri (iptalde '' ya da ())."""
import fnmatch
import os
import tkinter as tk
from tkinter import messagebox, ttk

_son = {"dizin": None}


def _desenler(tipler):
    """filetypes -> [(ad, [desen, ...])]; 'Hepsi' her zaman en sonda."""
    out = []
    for t in tipler or []:
        ad, d = t[0], t[1]
        d = d.split() if isinstance(d, str) else list(d)
        out.append((ad, [x.lower() for x in d]))
    if not any("*" in d or "*.*" in d for _, d in out):
        out.append(("Hepsi", ["*"]))
    return out


def _uyar(ad, desenler):
    a = ad.lower()
    return any(d in ("*", "*.*") or fnmatch.fnmatch(a, d) for d in desenler)


def _dialog(parent, baslik, tipler, coklu, dizin, kip, uz="", dosya=""):
    """kip: 'ac' | 'kaydet' | 'klasor'. -> liste (seçilen yollar) ya da []"""
    kok = parent or tk._default_root
    pen = tk.Toplevel(kok)
    pen.title(baslik or "Dosya")
    pen.geometry("720x520")
    try:
        pen.transient(kok.winfo_toplevel())
    except Exception:  # noqa: BLE001
        pass
    sonuc = []
    bas = dizin or _son["dizin"] or os.getcwd()
    if not os.path.isdir(bas):
        bas = os.path.expanduser("~")
    simdi = {"dizin": os.path.abspath(bas)}
    filt = _desenler(tipler)

    ust = ttk.Frame(pen, padding=(8, 8, 8, 2))
    ust.pack(fill="x")
    yol_v = tk.StringVar()
    liste_ogeleri = []

    def git(yol):
        yol = os.path.abspath(os.path.expanduser(yol))
        if os.path.isfile(yol):                                     # yol satırına dosya yazıldı
            return sec_ve_kapat([yol])
        if not os.path.isdir(yol):
            return durum.configure(text=f"Klasör yok: {yol}")
        simdi["dizin"] = yol
        yenile()

    def yukari():
        git(os.path.dirname(simdi["dizin"]) or simdi["dizin"])

    ttk.Button(ust, text="↑ Yukarı", width=9, command=yukari).pack(side="left")
    ev = os.path.expanduser("~")
    ttk.Button(ust, text="Ev", width=5, command=lambda: git(ev)).pack(side="left", padx=(4, 0))
    for ad in ("İndirilenler", "Downloads", "Masaüstü", "Desktop", "Belgeler", "Documents"):
        p = os.path.join(ev, ad)
        if os.path.isdir(p):
            ttk.Button(ust, text=ad, command=lambda p=p: git(p)).pack(side="left", padx=(4, 0))
    yol_e = ttk.Entry(pen, textvariable=yol_v)
    yol_e.pack(fill="x", padx=8, pady=(4, 4))
    yol_e.bind("<Return>", lambda e: git(yol_v.get()))

    orta = ttk.Frame(pen)
    orta.pack(fill="both", expand=True, padx=8)
    lb = tk.Listbox(orta, selectmode="extended" if (coklu and kip == "ac") else "browse", exportselection=False,
                    font=("DejaVu Sans Mono", 10), activestyle="dotbox")
    sb = ttk.Scrollbar(orta, orient="vertical", command=lb.yview)
    lb.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    lb.pack(side="left", fill="both", expand=True)

    alt = ttk.Frame(pen, padding=(8, 4, 8, 8))
    alt.pack(fill="x")
    ad_v = tk.StringVar(value=dosya)
    if kip == "kaydet":
        ttk.Label(alt, text="Dosya adı:").grid(row=0, column=0, sticky="w")
        ad_e = ttk.Entry(alt, textvariable=ad_v)
        ad_e.grid(row=0, column=1, sticky="ew", padx=4)
    else:
        ad_e = None
    alt.columnconfigure(1, weight=1)
    filt_v = tk.StringVar(value=filt[0][0])
    fc = None
    if kip != "klasor":
        ttk.Label(alt, text="Tür:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        fc = ttk.Combobox(alt, textvariable=filt_v, values=[a for a, _ in filt], state="readonly")
        fc.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 0))
    durum = ttk.Label(alt, text="", foreground="#555")
    durum.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
    dg = ttk.Frame(alt)
    dg.grid(row=0, column=2, rowspan=3, padx=(8, 0))

    def aktif_desen():
        return next((d for a, d in filt if a == filt_v.get()), ["*"])

    def yenile(*_):
        yol_v.set(simdi["dizin"])
        lb.delete(0, "end")
        liste_ogeleri.clear()
        try:
            adlar = sorted(os.listdir(simdi["dizin"]), key=str.lower)
        except OSError as ex:
            durum.configure(text=f"Okunamadı: {ex}")
            return
        klas = [a for a in adlar if not a.startswith(".") and os.path.isdir(os.path.join(simdi["dizin"], a))]
        dos = [] if kip == "klasor" else [a for a in adlar if not a.startswith(".") and
                                            os.path.isfile(os.path.join(simdi["dizin"], a)) and _uyar(a, aktif_desen())]
        for a in klas:
            lb.insert("end", "›  " + a + "/")
            liste_ogeleri.append((a, True))
        for a in dos:
            lb.insert("end", "    " + a)
            liste_ogeleri.append((a, False))
        durum.configure(text=f"{len(klas)} klasör" + ("" if kip == "klasor" else f", {len(dos)} dosya"))

    def sec_ve_kapat(yollar):
        if yollar:
            _son["dizin"] = simdi["dizin"]
        sonuc.extend(yollar)
        pen.destroy()

    def tamam(*_):
        if kip == "klasor":
            sel = lb.curselection()
            yol = (os.path.join(simdi["dizin"], liste_ogeleri[sel[0]][0]) if sel and liste_ogeleri[sel[0]][1]
                   else simdi["dizin"])
            return sec_ve_kapat([yol])
        if kip == "kaydet":
            ad = ad_v.get().strip()
            if not ad:
                return durum.configure(text="Bir dosya adı yaz.")
            if uz and not os.path.splitext(ad)[1]:
                ad += uz
            yol = os.path.join(simdi["dizin"], ad)
            if os.path.exists(yol) and not messagebox.askyesno("Üzerine yaz?", f"{ad} zaten var. Üzerine yazılsın mı?",
                                                                parent=pen):
                return
            return sec_ve_kapat([yol])
        sel = [liste_ogeleri[i] for i in lb.curselection()]
        dosyalar = [os.path.join(simdi["dizin"], a) for a, k in sel if not k]
        klasor = [a for a, k in sel if k]
        if not dosyalar and klasor:                                 # yalnız klasör seçili: içine gir
            return git(os.path.join(simdi["dizin"], klasor[0]))
        if not dosyalar:
            return durum.configure(text="Bir dosya seç.")
        sec_ve_kapat(dosyalar if coklu else dosyalar[:1])

    def cift(e):
        i = lb.nearest(e.y)
        if i < 0 or i >= len(liste_ogeleri):
            return
        a, k = liste_ogeleri[i]
        if k:
            git(os.path.join(simdi["dizin"], a))
        elif kip == "ac":
            sec_ve_kapat([os.path.join(simdi["dizin"], a)])
        elif kip == "kaydet":
            ad_v.set(a)

    def tek(e):
        if kip == "kaydet":
            sel = lb.curselection()
            if sel and not liste_ogeleri[sel[0]][1]:
                ad_v.set(liste_ogeleri[sel[0]][0])

    lb.bind("<Double-Button-1>", cift)
    lb.bind("<ButtonRelease-1>", tek)
    lb.bind("<Return>", tamam)
    pen.bind("<Escape>", lambda e: pen.destroy())
    pen.bind("<Alt-Up>", lambda e: yukari())
    lb.bind("<BackSpace>", lambda e: yukari())
    if fc is not None:
        fc.bind("<<ComboboxSelected>>", yenile)
    ttk.Button(dg, text={"ac": "Aç", "kaydet": "Kaydet", "klasor": "Bu klasörü seç"}[kip], command=tamam).pack(fill="x")
    ttk.Button(dg, text="İptal", command=pen.destroy).pack(fill="x", pady=(4, 0))
    yenile()
    (ad_e or lb).focus_set()
    pen.grab_set()
    pen.wait_window()
    return sonuc


def askopenfilename(**k):
    r = _dialog(k.get("parent"), k.get("title"), k.get("filetypes"), False, k.get("initialdir"), "ac")
    return r[0] if r else ""


def askopenfilenames(**k):
    r = _dialog(k.get("parent"), k.get("title"), k.get("filetypes"), True, k.get("initialdir"), "ac")
    return tuple(r)


def asksaveasfilename(**k):
    r = _dialog(k.get("parent"), k.get("title"), k.get("filetypes"), False, k.get("initialdir"), "kaydet",
                uz=k.get("defaultextension") or "", dosya=k.get("initialfile") or "")
    return r[0] if r else ""


def askdirectory(**k):
    r = _dialog(k.get("parent"), k.get("title"), None, False, k.get("initialdir"), "klasor")
    return r[0] if r else ""


def kur(filedialog_modulu):
    """tkinter.filedialog açma/kaydetme işlevlerini bu seçiciyle değiştirir (başkası zaten değiştirdiyse dokunmaz)."""
    for ad, yeni in (("askopenfilename", askopenfilename), ("askopenfilenames", askopenfilenames),
                     ("asksaveasfilename", asksaveasfilename), ("askdirectory", askdirectory)):
        eski = getattr(filedialog_modulu, ad, None)
        if getattr(eski, "__module__", "").startswith("tkinter"):
            setattr(filedialog_modulu, ad, yeni)
