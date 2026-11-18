#!/usr/bin/env python3
# Croow — Alper Pektas tarafından geliştirilmiştir.
# Copyright (C) 2026  Alper Pektas
# GNU Affero Genel Kamu Lisansı sürüm 3 ile lisanslıdır; ek koşullar için NOTICE dosyasına bakın.
"""
croow_reader.py - CROOW MULTIREADER.
Croow — Alper Pektas tarafından geliştirilmiştir.  Copyright (C) 2026 Alper Pektas.  GNU AGPLv3 (NOTICE).

  * PDF -> metin: PDF'in kendi metin katmanı ya da HARF PALETİ ile piksel analizi (crw_harf.py)
  * Taranmış sayfa / resimdeki yazı -> metin: harf paleti (OCR kullanılmaz)
  * CRW resimleri (CRW5, CRW6, CRW7, detaylı CRW): Croow motoruyla görüntü
      Detaylandır ×2 · Motorla yeniden çiz · Detaylı CRW kaydet · PNG / WebP olarak kaydet
  * Resim (PNG, JPG ...) -> CRW7 (kayıpsız)
  * CRW2 dosyaları: bölümler metin olarak
Büyük metinlerde ilk 500 satır gelir, "Daha fazla" ile devam eder.

Kullanım:
  * Bir kelimeye ÇİFT TIKLA: o kelime aranır.  "← Geri" ile önceki görünüme dönülür.
  * SAĞ TIK: kopyala, satırı kopyala, tümünü seç/kopyala, kelimeyi ara.
  * Ctrl+C kopyala · Ctrl+A tümünü seç · Ctrl+F arama · Ctrl+O dosya aç · Alt+Sol geri
Linux'ta menüye eklemek (bir kez):  python3 croow_reader.py --kur
Gerekenler: Python 3 (tkinter), Pillow, numpy, pypdfium2 (poppler kuruluysa PDF için o kullanılır)
"""
import os
import sys
import time

BURASI = os.path.dirname(os.path.abspath(__file__))
GEREKEN = ("crw.py", "crw_oku.py", "crw_json.py", "crw_harf.py", "crw_pdf.py", "pdf_motor.py")
for _k in (os.path.dirname(BURASI), BURASI):             # kendi klasoru once, sonra bir ust klasor
    if os.path.exists(os.path.join(_k, "crw.py")) and _k not in sys.path:
        sys.path.insert(0, _k)
for _k in (os.path.join(BURASI, "..", "motor"), os.path.join(BURASI, "motor")):   # Croow motoru (depo düzeni)
    if os.path.exists(os.path.join(_k, "crw_motor.py")) and _k not in sys.path:
        sys.path.insert(0, os.path.abspath(_k))
DONMUS = getattr(sys, "frozen", False)                   # kurulumlu uygulama (PyInstaller)
VERI = os.path.join(os.path.expanduser("~"), ".croow")   # kullanıcının veri klasörü (hafıza, harf paleti)
SURUM = "1.0.0"


# ====================================================================== Croow motoru (CRW5/6/7, detaylandırma)
_MOTOR = None


def hafiza_yolu():
    """Croow hafızası: uygulamanın yanında ya da ~/.croow/ içinde universal_roots.crwm (yoksa boş hafıza)."""
    yan = os.path.dirname(sys.executable if DONMUS else os.path.abspath(__file__))
    for aday in (os.path.join(yan, "universal_roots.crwm"), os.path.join(VERI, "universal_roots.crwm")):
        if os.path.exists(aday):
            return aday
    return os.path.join(VERI, "universal_roots.crwm")


def motor():
    global _MOTOR
    if _MOTOR is None:
        os.makedirs(VERI, exist_ok=True)
        os.environ.setdefault("CROOW_ROOTS", hafiza_yolu())
        os.environ["CROOW_SITE_LEARN"] = "0"             # uygulama hiçbir şey öğrenmez
        import crw_motor
        _MOTOR = crw_motor
    return _MOTOR

PARTI = 500                                              # bir seferde gosterilen satir


def _eksikleri_kontrol():
    eksik = [f for f in GEREKEN if not any(os.path.exists(os.path.join(k, f)) for k in sys.path if k)]
    if eksik:
        raise RuntimeError(f"Şu dosyalar bulunamadı: {', '.join(eksik)}\n"
                           f"Hepsini crwreader.py ile AYNI klasöre koy:\n{BURASI}")


# ====================================================================== LOGO: karga + ceviz
# Tek tarif; masaustu simgesi (SVG), pencere simgesi (piksel) ve pencere basligindaki logo (cizim) buradan uretilir.
# (tur, renk, koordinatlar)  -  64x64 alan; sonra gelen ustte cizilir.
LOGO = [
    ("elips", "#16213a", (32, 32, 31, 31)),                          # zemin
    ("cokgen", "#2f4b8a", ((15, 44), (4, 57), (10, 58), (19, 50))),    # kuyruk
    ("elips", "#3e5fa8", (25, 39, 13, 15)),                          # govde
    ("elips", "#2f4b8a", (21, 41, 7, 10)),                           # kanat
    ("elips", "#4f74bd", (28, 22, 10, 10)),                          # bas
    ("cokgen", "#f5b25a", ((36, 18), (48, 23), (36, 27))),             # gaga
    ("elips", "#ffffff", (31, 19, 3.2, 3.2)),                        # goz
    ("elips", "#111111", (32, 19, 1.6, 1.6)),                        # gozbebegi
    ("cokgen", "#f5b25a", ((27, 52), (30, 52), (33, 58), (30, 58))),   # bacak
    ("elips", "#8a5a2b", (43, 47, 12, 10.5)),                        # ceviz
    ("elips", "#a8743f", (39, 43, 4.5, 2.6)),                        # ceviz parlakligi
    ("elips", "#5c3a17", (43, 47, 1.4, 10)),                         # ceviz dikisi
    ("cokgen", "#5c3a17", ((36, 50), (41, 52), (36, 54))),             # kabuk kivrimi
    ("cokgen", "#5c3a17", ((50, 50), (45, 52), (50, 54))),
]


def logo_svg():
    parca = []
    for tur, renk, k in LOGO:
        if tur == "elips":
            parca.append(f'<ellipse cx="{k[0]}" cy="{k[1]}" rx="{k[2]}" ry="{k[3]}" fill="{renk}"/>')
        else:
            parca.append(f'<polygon points="{" ".join(f"{x},{y}" for x, y in k)}" fill="{renk}"/>')
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' + "".join(parca) + "</svg>\n"


def _icinde(tur, k, x, y):
    if tur == "elips":
        return ((x - k[0]) / k[2]) ** 2 + ((y - k[1]) / k[3]) ** 2 <= 1
    ic, n = False, len(k)
    for i in range(n):
        (x1, y1), (x2, y2) = k[i], k[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ic = not ic
    return ic


def logo_piksel(tk, boy=32):
    """Pencere simgesi: tarif piksel piksel boyanir (resim dosyasi ya da format gerekmez)."""
    img = tk.PhotoImage(width=boy, height=boy)
    o = 64 / boy
    for py in range(boy):
        satir = []
        for px in range(boy):
            x, y, renk = (px + 0.5) * o, (py + 0.5) * o, None
            for tur, r, k in LOGO:
                if _icinde(tur, k, x, y):
                    renk = r
            satir.append(renk)
        for px, renk in enumerate(satir):
            if renk:
                img.put(renk, to=(px, py, px + 1, py + 1))
    return img


def logo_ciz(canvas, boy):
    o = boy / 64
    for tur, renk, k in LOGO:
        if tur == "elips":
            canvas.create_oval((k[0] - k[2]) * o, (k[1] - k[3]) * o, (k[0] + k[2]) * o, (k[1] + k[3]) * o,
                               fill=renk, outline="")
        else:
            canvas.create_polygon(*[v * o for p in k for v in p], fill=renk, outline="")


# ====================================================================== kurulum (cift tiklama)
MIME = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-croow-crw">
    <comment>Croow CRW dosyası</comment>
    <icon name="crwreader"/>
    <glob pattern="*.crw" weight="90"/>
    <magic priority="90"><match type="string" offset="0" value="CRW2"/><match type="string" offset="0" value="CRW5"/><match type="string" offset="0" value="CRW6"/><match type="string" offset="0" value="CRW7"/></magic>
  </mime-type>
  <mime-type type="application/x-croow-crwl">
    <comment>Croow CRW günlüğü</comment>
    <icon name="crwreader"/>
    <glob pattern="*.crwl" weight="90"/>
    <magic priority="90"><match type="string" offset="0" value="CRWL"/></magic>
  </mime-type>
</mime-info>
"""


def kur():
    import shutil
    import subprocess
    paylas = os.path.join(os.path.expanduser("~"), ".local", "share")
    uyg, mime = os.path.join(paylas, "applications"), os.path.join(paylas, "mime")
    simgeler = os.path.join(paylas, "icons", "hicolor")
    simge = os.path.join(simgeler, "scalable", "apps")
    mime_simge = os.path.join(simgeler, "scalable", "mimetypes")
    for k in (uyg, os.path.join(mime, "packages"), simge, mime_simge):
        os.makedirs(k, exist_ok=True)
    svg = logo_svg()
    for y in (os.path.join(simge, "crwreader.svg"), os.path.join(mime_simge, "application-x-croow-crw.svg"),
              os.path.join(mime_simge, "application-x-croow-crwl.svg")):
        with open(y, "w", encoding="utf-8") as f:
            f.write(svg)
    with open(os.path.join(mime, "packages", "croow-crw.xml"), "w", encoding="utf-8") as f:
        f.write(MIME)
    with open(os.path.join(uyg, "crwreader.desktop"), "w", encoding="utf-8") as f:
        program = os.environ.get("APPIMAGE", sys.executable)   # AppImage: gerçek dosyanın yolu
        calistir_satiri = (f'Exec="{program}" %f\n' if DONMUS
                           else f'Exec={sys.executable} "{os.path.abspath(__file__)}" %f\n')
        f.write("[Desktop Entry]\nType=Application\nName=Croow MultiReader\n"
                "Comment=PDF ve resimlerdeki yazıyı okur · CRW resimlerini açar ve detaylandırır\n"
                + calistir_satiri +
                "Icon=crwreader\nTerminal=false\nCategories=Utility;Viewer;Graphics;\n"
                "MimeType=application/x-croow-crw;application/x-croow-crwl;application/pdf;"
                "image/png;image/jpeg;image/gif;image/bmp;image/webp;image/tiff;\n")
    for komut in (["update-mime-database", mime], ["update-desktop-database", uyg],
                  ["xdg-mime", "default", "crwreader.desktop", "application/x-croow-crw"],
                  ["xdg-mime", "default", "crwreader.desktop", "application/x-croow-crwl"],
                  ["gtk-update-icon-cache", "-f", "-t", simgeler]):
        if shutil.which(komut[0]):
            subprocess.run(komut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Croow MultiReader kuruldu (karga + ceviz simgesiyle).\n"
          "  .crw ve .crwl: çift tıklayınca açılır.\n"
          "  Resim ve PDF: sağ tık → 'Birlikte aç' → Croow MultiReader (varsayılan programların değişmez).\n"
          "Dosya yöneticisi açıksa bir kez kapatıp aç.\n"
          f"Program bu dosyadan çalışır: {os.path.abspath(__file__)} — yerini değiştirirsen --kur'u yeniden çalıştır.")


# ====================================================================== pencere
def tur_bul(yol):
    """-> (tür, okuyucu). resim: CRW5/6/7 (Croow motoru) · eski_resim: CRW1/CRW4 · crw2 · bilinmiyor"""
    import crw_oku as CO
    with open(yol, "rb") as f:
        bas = f.read(4)
    if bas in (b"CRW5", b"CRW6", b"CRW7"):
        return "resim", None
    if bas in (b"CRW1", b"CRW4"):
        return "eski_resim", None
    tur, ok = CO.tur_bul(yol)
    if ok is not None:
        return "crw2", ok                                # dil modeli, dizin, kayıt: bölümleri metin olarak
    return "bilinmiyor", None


def calistir(ilk=None):
    import re
    import tkinter as tk
    import dil
    dil.kur()                                                # arayüz dili (TR/EN): dil.py
    from tkinter import filedialog, messagebox, simpledialog, ttk

    import croow_dosya
    import crw_oku as CO
    croow_dosya.kur(filedialog)                              # Tk'nin yerleşik dosya penceresi yerine Croow'unki

    kok = tk.Tk()
    kok.report_callback_exception = lambda t, e, tb: _hata_goster(e)
    kok.title("Croow MultiReader")
    kok.geometry("1150x720")
    try:
        kok._simge = logo_piksel(tk, 32)
        kok.iconphoto(True, kok._simge)
    except tk.TclError:
        pass

    durum = {"yol": None, "tur": None, "ok": None, "akis": None, "kaynak": None, "satir": 0, "veri": None,
             "baslik": "", "gecmis": [], "ogeler": {}}

    # ---- ust: logo + dosya + arama
    ust = ttk.Frame(kok, padding=(8, 6))
    ust.pack(fill="x")
    tuval = tk.Canvas(ust, width=40, height=40, highlightthickness=0, bd=0)
    logo_ciz(tuval, 40)
    tuval.pack(side="left", padx=(0, 8))
    geri_dugme = ttk.Button(ust, text="← Geri", command=lambda: geri(), state="disabled")
    geri_dugme.pack(side="left")
    ttk.Button(ust, text="Aç…", command=lambda: dosya_sec()).pack(side="left", padx=(6, 0))
    ttk.Button(ust, text="Sekmeyi kapat", command=lambda: sekme_kapat()).pack(side="left", padx=(6, 0))
    yol_etiket = ttk.Label(ust, text="Bir .crw dosyası aç", padding=(10, 0))
    yol_etiket.pack(side="left", fill="x", expand=True)
    arama = ttk.Entry(ust, width=28)
    arama.pack(side="right")
    arama_tur = ttk.Label(ust, text="Ara:", padding=(10, 0, 4, 0))
    arama_tur.pack(side="right")
    arama.bind("<Return>", lambda _: ara())

    # ---- orta: sol liste + sag metin
    bol = ttk.PanedWindow(kok, orient="horizontal")
    bol.pack(fill="both", expand=True, padx=8)
    sekme_cubuk = ttk.Notebook(kok, height=1)                  # yalnızca sekme başlıkları: her sekme bir açık dosya
    sekme_cubuk.pack(fill="x", padx=8, pady=(0, 2), before=bol)
    sekme_cubuk.add(ttk.Frame(sekme_cubuk, height=1), text="Yeni")
    sol = ttk.Treeview(bol, show="tree", selectmode="browse")
    bol.add(sol, weight=1)
    sag = ttk.Frame(bol)
    bol.add(sag, weight=4)
    metin_cerceve = ttk.Frame(sag)
    metin_cerceve.pack(fill="both", expand=True)
    metin = tk.Text(metin_cerceve, wrap="none", font=("DejaVu Sans Mono", 10), undo=False, cursor="xterm")
    ykay = ttk.Scrollbar(metin_cerceve, orient="vertical", command=metin.yview)
    xkay = ttk.Scrollbar(metin_cerceve, orient="horizontal", command=metin.xview)
    metin.configure(yscrollcommand=ykay.set, xscrollcommand=xkay.set)
    ykay.pack(side="right", fill="y")
    xkay.pack(side="bottom", fill="x")
    metin.pack(fill="both", expand=True)

    from croow_gorunum import Gorunum
    resim_cerceve = ttk.Frame(sag)                       # resim gorunumu (gerektiginde metnin yerine gelir)
    gor = Gorunum(tk, ttk, resim_cerceve)                # yakinlastirma, kaydirma, bolge secimi, kutu duzenleme
    resim_tuval = gor.tuval

    def metin_kipi():
        resim_cerceve.pack_forget()
        metin_cerceve.pack(fill="both", expand=True)

    def resim_kipi():
        metin_cerceve.pack_forget()
        resim_cerceve.pack(fill="both", expand=True)
    metin.tag_configure("vurgu", background="#ffe9a8")

    # ---- alt: durum + daha fazla
    alt = ttk.Frame(kok, padding=(8, 4))
    alt.pack(fill="x")
    bilgi = ttk.Label(alt, text="İpucu: bir kelimeye çift tıkla · sağ tık: kopyala")
    bilgi.pack(side="left")
    daha_dugme = ttk.Button(alt, text=f"Daha fazla (+{PARTI})", command=lambda: daha())
    daha_dugme.pack(side="right")
    ttk.Button(alt, text="Hepsini göster", command=lambda: daha(hepsi=True)).pack(side="right", padx=6)

    # ---- metin: salt okunur ama secilebilir/kopyalanabilir (yazma tuslari engellenir)
    def salt_okunur(e):
        if e.state & 0x4 and e.keysym.lower() in ("c", "a", "insert"):      # Ctrl+C / Ctrl+A serbest
            return None
        if e.keysym in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "Shift_L", "Shift_R",
                        "Control_L", "Control_R"):
            return None
        return "break"

    metin.bind("<Key>", salt_okunur)
    for olay in ("<<Paste>>", "<<Cut>>", "<<Clear>>", "<BackSpace>", "<Delete>", "<Return>", "<<PasteSelection>>"):
        metin.bind(olay, lambda _: "break")
    metin.bind("<Button-1>", lambda _: metin.focus_set(), add="+")

    def kopyala(yazi):
        if yazi:
            kok.clipboard_clear()
            kok.clipboard_append(yazi)
            kok.update()                                 # pano hemen dolsun
            bilgi.configure(text=f"Kopyalandı ({len(yazi):,} karakter)")

    def secili():
        try:
            return metin.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def tumunu_sec(_=None):
        metin.tag_add("sel", "1.0", "end-1c")
        return "break"

    for k in ("<Control-c>", "<Control-C>"):
        metin.bind(k, lambda _: (kopyala(secili()), "break")[1])
    for k in ("<Control-a>", "<Control-A>"):
        metin.bind(k, tumunu_sec)

    def kelime_al(indeks):
        """indeks'teki kelime: bosluk/sekme ile ayrilan parca; '→' ve sayilar atlanir."""
        satir = metin.get(f"{indeks} linestart", f"{indeks} lineend")
        kol = int(metin.index(indeks).split(".")[1])
        for m in re.finditer(r"[^\s\t→·:,]+", satir):
            if m.start() <= kol <= m.end():
                w = m.group().strip("()[]'\"")
                return None if not w or w.replace(".", "").isdigit() else w
        return None

    def kelime_ac(w):
        if not w or not durum["yol"]:
            return
        arama.delete(0, "end"); arama.insert(0, w); ara()

    metin.bind("<Double-Button-1>", lambda e: (kelime_ac(kelime_al(f"@{e.x},{e.y}")), "break")[1])

    # ---- sag tik menuleri
    menu = tk.Menu(kok, tearoff=0)

    def sag_tik(e):
        idx = f"@{e.x},{e.y}"
        w = kelime_al(idx)
        menu.delete(0, "end")
        menu.add_command(label="Kopyala", accelerator="Ctrl+C", command=lambda: kopyala(secili()),
                         state="normal" if secili() else "disabled")
        menu.add_command(label="Satırı kopyala",
                         command=lambda: kopyala(metin.get(f"{idx} linestart", f"{idx} lineend")))
        if w:
            menu.add_command(label=f"“{w}” kopyala", command=lambda: kopyala(w))
        menu.add_separator()
        menu.add_command(label="Tümünü seç", accelerator="Ctrl+A", command=tumunu_sec)
        menu.add_command(label="Tümünü kopyala", command=lambda: kopyala(metin.get("1.0", "end-1c")))
        if w:
            menu.add_command(label=f"“{w}” ara", command=lambda: (arama.delete(0, "end"), arama.insert(0, w), ara()))
        menu.tk_popup(e.x_root, e.y_root)

    metin.bind("<Button-3>", sag_tik)

    giris_menu = tk.Menu(kok, tearoff=0)
    giris_menu.add_command(label="Kes", command=lambda: arama.event_generate("<<Cut>>"))
    giris_menu.add_command(label="Kopyala", command=lambda: arama.event_generate("<<Copy>>"))
    giris_menu.add_command(label="Yapıştır", command=lambda: arama.event_generate("<<Paste>>"))
    giris_menu.add_separator()
    giris_menu.add_command(label="Tümünü seç", command=lambda: arama.select_range(0, "end"))
    giris_menu.add_command(label="Temizle", command=lambda: arama.delete(0, "end"))
    arama.bind("<Button-3>", lambda e: (arama.focus_set(), giris_menu.tk_popup(e.x_root, e.y_root)))
    for k in ("<Control-v>", "<Control-V>"):                # bazi klavye duzenlerinde varsayilan baglanti calismiyor
        arama.bind(k, lambda _: (arama.event_generate("<<Paste>>"), "break")[1])
    for k in ("<Control-a>", "<Control-A>"):
        arama.bind(k, lambda _: (arama.select_range(0, "end"), "break")[1])

    sol_menu = tk.Menu(kok, tearoff=0)

    def sol_sag_tik(e):
        iid = sol.identify_row(e.y)
        if not iid:
            return
        sol.selection_set(iid)
        sol_menu.delete(0, "end")
        sol_menu.add_command(label="Adı kopyala", command=lambda: kopyala(sol.item(iid, "text")))
        sol_menu.add_command(label="Gösterileni kopyala", command=lambda: kopyala(metin.get("1.0", "end-1c")))
        sol_menu.tk_popup(e.x_root, e.y_root)

    sol.bind("<Button-3>", sol_sag_tik)

    # ---- akis gosterimi
    def goster(baslik, kaynak, kaydet=False):
        """kaynak: cagrildiginda yeni bir satir ureteci donduren fonksiyon (arama ayni kaynakta suzer)."""
        if kaydet and durum["kaynak"] is not None:
            durum["gecmis"].append((durum["baslik"], durum["kaynak"]))
            geri_dugme.configure(state="normal")
        metin_kipi()
        metin.delete("1.0", "end")
        durum.update(kaynak=kaynak, akis=kaynak(), satir=0, baslik=baslik)
        daha()
        metin.yview_moveto(0)

    def geri(_=None):
        if durum["gecmis"]:
            baslik, kaynak = durum["gecmis"].pop()
            goster(baslik, kaynak)
        geri_dugme.configure(state="normal" if durum["gecmis"] else "disabled")

    def daha(hepsi=False):
        akis = durum["akis"]
        if akis is None:
            return
        n, parca = 0, []
        try:
            for s in akis:
                parca.append(s)
                n += 1
                if not hepsi and n >= PARTI:
                    break
                if len(parca) >= 2000:
                    metin.insert("end", "\n".join(parca) + "\n"); parca = []
            else:
                durum["akis"] = None
        except Exception as e:  # noqa: BLE001
            parca.append(f"\n[okuma hatası: {e!r}]")
            durum["akis"] = None
        if parca:
            metin.insert("end", "\n".join(parca) + "\n")
        durum["satir"] += n
        bitti = durum["akis"] is None
        daha_dugme.configure(state="disabled" if bitti else "normal")
        bilgi.configure(text=f"{durum['baslik']} · {durum['satir']:,} satır" + ("" if bitti else " (devamı var)"))

    # ---- arka plan isi (pencere donmasin): is_(ilerle) baska is parcaciginda, sonuc bitince(sonuc) ile
    def arka_plan(is_, bitince):
        import queue
        import threading
        q = queue.Queue()
        hedef = sekmeler[sekme_durumu["no"]] if 0 <= sekme_durumu["no"] < len(sekmeler) else None

        def ilerle(oran, mesaj=""):
            q.put(("ilerle", oran, mesaj))

        def calis():
            try:
                q.put(("bitti", is_(ilerle)))
            except Exception as e:  # noqa: BLE001
                q.put(("hata", e))
        threading.Thread(target=calis, daemon=True).start()

        def bak():
            try:
                while True:
                    m = q.get_nowait()
                    if m[0] == "ilerle":
                        bilgi.configure(text=f"{m[2] or 'Çalışıyor…'}  %{m[1] * 100:.0f}")
                    elif m[0] == "bitti":
                        if hedef is not None:                      # iş başka sekmeye geçildiyse oraya dön, sonuç doğru sekmeye yazılsın
                            if hedef not in sekmeler:
                                return bilgi.configure(text="")      # sekme kapatıldı
                            if sekmeler[sekme_durumu["no"]] is not hedef:
                                sekme_gec(sekmeler.index(hedef))
                        return bitince(m[1])
                    else:
                        bilgi.configure(text="")
                        return messagebox.showerror("Croow MultiReader", str(m[1]))
            except queue.Empty:
                pass
            kok.after(150, bak)
        bak()

    # ---- sekmeler: her açık dosya kendi durumu, sol listesi ve görünümüyle bir sekmedir
    sekmeler = [{"durum": {}, "sol": sol, "metin": "", "yview": 0.0, "etiket": "", "baslik": "", "geri": "disabled",
                 "arama_tur": "Ara:", "mod": "metin", "gorunum": (None, 0.0, 0.0), "daha": "disabled", "bilgi": ""}]
    sekme_durumu = {"no": 0, "gecis": False}

    def bos_durum():
        return {"yol": None, "tur": None, "ok": None, "akis": None, "kaynak": None, "satir": 0, "veri": None,
                "baslik": "", "gecmis": [], "ogeler": {}}

    def agac_yap():
        a = ttk.Treeview(bol, show="tree", selectmode="browse")
        a.bind("<<TreeviewSelect>>", secildi)
        a.bind("<<TreeviewOpen>>", dal_ac)
        a.bind("<Button-3>", sol_sag_tik)
        return a

    def sekme_kaydet():
        i = sekme_durumu["no"]
        if not 0 <= i < len(sekmeler):
            return
        t = sekmeler[i]
        t.update(durum=dict(durum), metin=metin.get("1.0", "end-1c"), yview=metin.yview()[0],
                 etiket=yol_etiket.cget("text"), baslik=kok.title(), geri=str(geri_dugme.cget("state")),
                 arama_tur=arama_tur.cget("text"), mod="resim" if resim_cerceve.winfo_ismapped() else "metin",
                 gorunum=(gor.z, gor.x, gor.y), daha=str(daha_dugme.cget("state")), bilgi=bilgi.cget("text"))

    def sekme_yukle(i):
        nonlocal sol
        t = sekmeler[i]
        panel_kapat()
        eski = sol
        sol = t["sol"]
        if eski is not sol:
            try:
                bol.forget(eski)
            except tk.TclError:
                pass
            bol.insert(0, sol, weight=1)
        durum.clear()
        durum.update(t["durum"])
        metin.delete("1.0", "end")
        metin.insert("1.0", t["metin"])
        metin.yview_moveto(t["yview"])
        yol_etiket.configure(text=t["etiket"])
        kok.title(t["baslik"])
        geri_dugme.configure(state=t["geri"])
        arama_tur.configure(text=t["arama_tur"])
        daha_dugme.configure(state=t["daha"])
        if t["mod"] == "resim" and durum.get("img") is not None:
            resim_kipi()
            kok.update_idletasks()
            gor.goster(durum["img"], None)
            gor.z, gor.x, gor.y = t["gorunum"]
            gor.yenile()
            gor.bolge_ata(durum.get("bolge"))
            bindirme_yenile()
        else:
            metin_kipi()
        bilgi.configure(text=t.get("bilgi", ""))
        sekme_durumu["no"] = i

    def sekme_sec(i):
        sekme_durumu["gecis"] = True
        try:
            sekme_cubuk.select(i)
        finally:
            sekme_durumu["gecis"] = False

    def sekme_gec(i):
        if i == sekme_durumu["no"] or not 0 <= i < len(sekmeler):
            return
        sekme_kaydet()
        sekme_sec(i)
        sekme_yukle(i)

    def yeni_sekme():
        sekme_kaydet()
        sekmeler.append({"durum": bos_durum(), "sol": agac_yap(), "metin": "", "yview": 0.0, "etiket": "Bir dosya aç",
                         "baslik": "Croow MultiReader", "geri": "disabled", "arama_tur": "Ara:", "mod": "metin",
                         "gorunum": (None, 0.0, 0.0), "daha": "disabled", "bilgi": ""})
        sekme_cubuk.add(ttk.Frame(sekme_cubuk, height=1), text="Yeni")
        sekme_sec(len(sekmeler) - 1)
        sekme_yukle(len(sekmeler) - 1)

    def sekme_adi(ad):
        i = sekme_durumu["no"]
        sekme_cubuk.tab(i, text=(ad if len(ad) <= 26 else ad[:23] + "…"))

    def sekme_kapat(i=None):
        i = sekme_durumu["no"] if i is None else i
        if not 0 <= i < len(sekmeler):
            return
        if len(sekmeler) == 1:                                 # son sekme: boş sekmeye dön
            panel_kapat()
            durum.clear()
            durum.update(bos_durum())
            sol.delete(*sol.get_children())
            metin.delete("1.0", "end")
            metin_kipi()
            yol_etiket.configure(text="Bir dosya aç")
            kok.title("Croow MultiReader")
            sekme_cubuk.tab(0, text="Yeni")
            geri_dugme.configure(state="disabled")
            return
        t = sekmeler.pop(i)
        aktif_mi = i == sekme_durumu["no"]
        sekme_cubuk.forget(i)
        if aktif_mi:
            yeni = min(i, len(sekmeler) - 1)
            sekme_durumu["no"] = -1                            # kapanan sekme kaydedilmez
            sekme_sec(yeni)
            sekme_yukle(yeni)
        elif i < sekme_durumu["no"]:
            sekme_durumu["no"] -= 1
        try:
            t["sol"].destroy()
        except tk.TclError:
            pass

    def sekme_degisti(_):
        if sekme_durumu["gecis"]:
            return
        try:
            i = sekme_cubuk.index("current")
        except tk.TclError:
            return
        if i != sekme_durumu["no"]:
            sekme_kaydet()
            sekme_yukle(i)
    sekme_cubuk.bind("<<NotebookTabChanged>>", sekme_degisti)
    sekme_cubuk.bind("<Button-2>", lambda e: sekme_kapat(sekme_cubuk.index(f"@{e.x},{e.y}")))
    kok.bind("<Control-w>", lambda e: sekme_kapat())

    def yeni_dosya(yol, ad):
        if durum.get("yol") is not None:                       # bu sekmede dosya var: yenisi kendi sekmesinde açılır
            yeni_sekme()
        sekme_adi(os.path.basename(yol))
        durum.update(yol=yol, tur=None, ok=None, veri=None, kaynak=None, gecmis=[], ogeler={}, img=None)
        geri_dugme.configure(state="disabled")
        kok.title(f"Croow MultiReader — {os.path.basename(yol)}")
        yol_etiket.configure(text=f"{yol}  ·  {ad}  ·  {CO._boy(os.path.getsize(yol))}")
        sol.delete(*sol.get_children())
        arama.delete(0, "end")

    def liste(ogeler):
        """ogeler: [(ad, uretec_fonksiyonu)] ya da [(ad, fonksiyon, "eylem")]"""
        for o in ogeler:
            iid = sol.insert("", "end", text=o[0])
            durum["ogeler"][iid] = o
        if sol.get_children():
            sol.selection_set(sol.get_children()[0])

    # ---- RESIM: goster, CRW'ye sikistir
    RESIM_UZ = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff")

    def resim_ciz(sigdir=True):
        """Yeni resmi göster (sigdir: pencereye sığdır, False: gerçek boyut). Bölge ve çerçeveler yeniden çizilir."""
        img = durum.get("img")
        if img is None:
            return
        resim_kipi()
        kok.update_idletasks()
        gor.goster(img, sigdir)
        gor.bolge_ata(durum.get("bolge"))
        bindirme_yenile()
        bilgi.configure(text=f"{img.width}×{img.height} piksel · tekerlek: kaydır · Ctrl+tekerlek: yakınlaştır · "
                             "orta tuş: sürükle")

    def resim_yenile():
        """Resmi yakınlaştırmayı ve konumu bozmadan yenile (işlem sonucu)."""
        img = durum.get("img")
        if img is not None:
            resim_kipi()
            gor.degistir(img)

    def resim_bilgi():
        img, ops = durum.get("img"), durum.get("ops", "")
        satir = [f"tür: {durum.get('resim_tur', 'resim')}", f"boyut: {img.width}×{img.height} piksel",
                 f"dosya: {CO._boy(os.path.getsize(durum['yol']))}",
                 f"ham karşılığı (RGB): {CO._boy(img.width * img.height * 3)}"]
        if ops:
            satir.append("detay adımları: " + " → ".join("×2" if o == "U" else "yeniden çiz" for o in ops))
        if durum.get("taban"):
            satir.append(f"orijinal: {durum['taban'][0]}×{durum['taban'][1]} piksel")
        try:
            m = motor().MEMORY.summary()
            satir.append(f"Croow hafızası: {m['roots']:,} kök, {m.get('paths', 0):,} piksel yolu"
                         + ("" if os.path.exists(hafiza_yolu()) else " (hafıza dosyası yok: Detaylandır düz büyütür)"))
        except Exception:  # noqa: BLE001
            pass
        return iter(satir)

    def resim_ac(yol, crw_mu):
        """CRW5/6/7 ve detaylı CRW: Croow motoru. Diğer resimler: Pillow."""
        def oku(il):
            il(0, "Açılıyor…")
            if crw_mu:
                with open(yol, "rb") as f:
                    veri = f.read()
                sonuc = motor().decode_crw_image(veri)
                if sonuc is None:
                    raise ValueError("geçersiz CRW dosyası")
                img, bilgi_ = sonuc
                return img, bilgi_, veri
            from PIL import Image
            img = Image.open(yol)
            img.load()
            return img.convert("RGB"), {"format": img.format or "resim", "ops": ""}, None

        def bitti(sonuc):
            img, bilgi_, veri = sonuc
            yeni_dosya(yol, f"{bilgi_['format']} resmi")
            durum.pop("cri", None)
            durum.pop("goster", None)
            panel_kapat()
            durum.update(asil_img=img, img=img, crw_veri=veri, ops=bilgi_.get("ops", ""), dosya_ops=bilgi_.get("ops", ""),
                         resim_tur=bilgi_["format"],
                         taban=(bilgi_["base_width"], bilgi_["base_height"]) if bilgi_.get("ops") else None)
            ogeler = [("Görüntü (sığdır)", lambda: resim_ciz(True), "eylem"),
                      ("Görüntü (gerçek boyut)", lambda: resim_ciz(False), "eylem"),
                      ("Bilgi", resim_bilgi),
                      ("Detaylandır ×2", lambda: detaylandir(False), "eylem"),
                      ("Motorla yeniden çiz", lambda: detaylandir(True), "eylem"),
                      ("Seçili bölgeyi yeni sekmede aç", bolge_yeni_sekme, "eylem"),
                      ("PNG olarak kaydet…", lambda: resim_kaydet("PNG"), "eylem"),
                      ("WebP olarak kaydet…", lambda: resim_kaydet("WEBP"), "eylem")]
            if veri is not None and veri[:4] == b"CRW7":
                ogeler.append(("Detaylı CRW kaydet…", detayli_kaydet, "eylem"))
            if not crw_mu:
                ogeler.append(("CRW7'ye sıkıştır…", lambda: resim_sikistir(yol), "eylem"))
            ogeler.append(("Yazıyı çöz (harf paleti)", lambda: yazi_coz(durum["img"]), "eylem"))
            ogeler.append(("CriCroow7 · Anlamlandır (oku + cümle bağlamı; yavaş)", lambda: belge_coz(durum["img"]), "eylem"))
            ogeler.append(("Bu sayfadan harf öğret (doğru metniyle)…", lambda: belge_ogret(durum["img"]), "eylem"))
            ogeler.append(("Harf göster ve öğret (harfe tıkla: \"bu t\")", harf_goster, "eylem"))
            ogeler.append(("CriCroow7 · Leke azalt", lambda: cri_adim("leke"), "eylem"))
            ogeler.append(("CriCroow7 · Leke azalt, riskli (siyah lekeleri sert sil)", lambda: cri_adim("leke_riskli"), "eylem"))
            ogeler.append(("CriCroow7 · Seçili bölgenin İÇİNİ riskli temizle (yazıyı korur)", lambda: cri_adim("bolge_ic"), "eylem"))
            ogeler.append(("CriCroow7 · Seçili bölgenin DIŞINI riskli temizle (yazıyı korur)", lambda: cri_adim("bolge_dis"), "eylem"))
            ogeler.append(("CriCroow7 · Tamamla (kopuk çizgi)", lambda: cri_adim("tamamla"), "eylem"))
            ogeler.append(("CriCroow7 · Tamamla, riskli (uzun boşluk)", lambda: cri_adim("riskli"), "eylem"))
            ogeler.append(("CriCroow7 · Netleştir (incelt)", lambda: cri_adim("netlestir"), "eylem"))
            ogeler.append(("CriCroow7 · Netleştir (genel ×10, sonra harfin yoluyla ×3; uzun sürer)", lambda: cri_adim("netlestir_z"), "eylem"))
            ogeler.append(("CriCroow7 · Netleştir (yalnızca harfin yoluyla; yavaş)", lambda: cri_adim("netlestir_v"), "eylem"))
            ogeler.append(("CriCroow7 · Değişiklik haritasını göster", cri_harita, "eylem"))
            ogeler.append(("CriCroow7 · Kaydet (resim + harita + rapor)…", cri_kaydet, "eylem"))
            ogeler.append(("CriCroow7 · Baştan al (orijinale dön)", cri_sifirla, "eylem"))
            ogeler.append(("CriCroow7 · Tam otomatik (okuyarak; çok yavaş)…", cricroow_calistir, "eylem"))
            liste(ogeler)
            kok.after(30, lambda: resim_ciz(True))
        arka_plan(oku, bitti)

    def detaylandir(yeniden):
        """×2 detaylandırma ya da yarı boyuttan motorla yeniden çizme (öğrenilmiş piksel yolları)."""
        img = durum.get("img")
        if img is None:
            return
        from PIL import Image
        bolgeli = bool(durum.get("bolge"))
        img, _ = bolge_kirp(img)                             # seçili bölge varsa yalnızca o (sonuç yeni sekmede açılır)

        def is_(il):
            il(0, "Motorla yeniden çiziliyor…" if yeniden else f"Detaylandırılıyor: {img.width}×{img.height} → "
                                                              f"{img.width * 2}×{img.height * 2}…")
            kaynak = img.resize((max(1, img.width // 2), max(1, img.height // 2)), Image.Resampling.BOX) if yeniden else img
            return motor().MEMORY.enhance(kaynak)

        def bitti(yeni):
            if bolgeli:
                return resim_sekmede_ac(yeni, f"{os.path.splitext(os.path.basename(durum['yol']))[0]}_bolge_"
                                              f"{'yeniden' if yeniden else 'x2'}")
            durum["img"] = yeni
            durum["ops"] = durum.get("ops", "") + ("R" if yeniden else "U")
            resim_ciz(True)
            bilgi.configure(text=f"{'Motorla yeniden çizildi' if yeniden else 'Detaylandırıldı'}: {yeni.width}×{yeni.height}"
                                 " · orijinalin ötesindeki pikseller öğrenilmiş yollardan tahmin edilir")
        arka_plan(is_, bitti)

    def resim_sekmede_ac(img, ad):
        """Bellekteki bir resmi (kırpılmış bölge, işlem sonucu) PNG olarak kaydedip yeni sekmede açar."""
        import crw_harf as CH
        klasor = os.path.join(CH.VERI, "bolgeler")
        os.makedirs(klasor, exist_ok=True)
        hedef = os.path.join(klasor, f"{ad}_{int(__import__('time').time())}.png")
        img.save(hedef)
        ac(hedef)

    def bolge_yeni_sekme():
        img = durum.get("img")
        b = durum.get("bolge")
        if img is None or not b:
            return messagebox.showinfo("Croow MultiReader", "Önce üstteki araç çubuğundan 'Bölge seç' ile bir bölge çiz.")
        kirp, _ = bolge_kirp(img)
        resim_sekmede_ac(kirp, os.path.splitext(os.path.basename(durum["yol"]))[0] + "_bolge")

    def resim_kaydet(bicim):
        img = durum.get("img")
        if img is None:
            return
        if bicim == "WEBP" and max(img.size) > 16383:
            return messagebox.showwarning("Croow MultiReader", "WebP en fazla 16383 piksel taşıyabilir. PNG olarak kaydet.")
        uz = ".png" if bicim == "PNG" else ".webp"
        ad = os.path.splitext(os.path.basename(durum["yol"]))[0] + f"_{img.width}x{img.height}{uz}"
        hedef = filedialog.asksaveasfilename(title=f"{bicim} olarak kaydet", defaultextension=uz,
                                             initialdir=os.path.dirname(durum["yol"]), initialfile=ad,
                                             filetypes=[(bicim, "*" + uz)])
        if not hedef:
            return
        arka_plan(lambda il: (il(0, "Kaydediliyor…"),
                              img.save(hedef, format=bicim, **({"quality": 95} if bicim == "WEBP" else {"compress_level": 6})))[1],
                  lambda _: bilgi.configure(text=f"Kaydedildi: {hedef} ({CO._boy(os.path.getsize(hedef))})"))

    def detayli_kaydet():
        veri, ops, dosya_ops = durum.get("crw_veri"), durum.get("ops", ""), durum.get("dosya_ops", "")
        yeni = ops[len(dosya_ops):] if ops.startswith(dosya_ops) else ops
        if not yeni:
            return messagebox.showinfo("Croow MultiReader", "Önce Detaylandır ya da Motorla yeniden çiz kullan.")
        img = durum["img"]
        hedef = filedialog.asksaveasfilename(title="Detaylı CRW kaydet", defaultextension=".crw",
                                             initialdir=os.path.dirname(durum["yol"]),
                                             initialfile=os.path.splitext(os.path.basename(durum["yol"]))[0]
                                             + f"_{img.width}x{img.height}_detayli.crw",
                                             filetypes=[("CRW", "*.crw")])
        if not hedef:
            return
        try:
            cs = motor()
            cikti = cs.make_detail_crw(veri, yeni, cs.MEMORY.flow_model())
        except Exception as e:  # noqa: BLE001
            return messagebox.showerror("Croow MultiReader", f"Detaylı CRW yazılamadı:\n{e}")
        with open(hedef, "wb") as f:
            f.write(cikti)
        messagebox.showinfo("Croow MultiReader", f"Kaydedildi: {os.path.basename(hedef)} ({CO._boy(len(cikti))})\n\n"
                            f"Açıldığında aynı adımlarla ({len(ops)} adım) {img.width}×{img.height} olarak üretilir.")

    def yazi_coz(img):
        import crw_harf as CH
        img, _ = bolge_kirp(img)                             # seçili bölge varsa yalnızca o

        def bitti(yazi):
            durum["pdf_metin"] = yazi
            satirlar_ = yazi.splitlines()
            goster("Çözülen yazı" + (" (seçili bölge)" if durum.get("bolge") else ""), lambda: iter(satirlar_), kaydet=True)
        arka_plan(lambda il: (il(0, "Piksel analizi…"), CH.resim_coz(img))[1], bitti)

    def belge_coz(img):
        """Belge deposuyla (belgenin kendi harfleri, sanal silik kopyaları, bağlam) okur; adayları olasılıkla gösterir."""
        import belge_harf as BH
        import crw_harf as CH
        if ortak_depo().bos():
            return messagebox.showinfo("Croow MultiReader",
                                       "Belge deposu boş. Önce 'Bu sayfadan harf öğret' ile bu yazıdan bir parça öğret.")
        img, _ = bolge_kirp(img)                             # seçili bölge varsa yalnızca o

        def is_(il):
            il(0, "Belgenin kendi harfleriyle okunuyor (olasılık · yakından bakma · bağlam)…")
            P = CH.Palet()
            return BH.oku(img, ortak_depo(), P if P.k else None, ayrinti=True)

        def bitti(sonuc):
            yazi, detay = sonuc
            durum["pdf_metin"] = yazi
            satirlar_ = yazi.splitlines() + ["", "—— Kelime adayları (olasılık; kaynak: gerçek / sanal / genel) ——"]
            for d in detay:
                if d["guven"] < 0.6 or d["baglamla_degisti"]:
                    harfler = " ".join("/".join(f"{h}:{p:.2f}" for h, p, _ in hs[:2]) for hs in d["harfler"])
                    satirlar_.append(f"{d['kelime']:<18} güven {d['guven']:.2f}"
                                     f"{'  · bağlamla seçildi' if d['baglamla_degisti'] else ''}   [{harfler}]")
            goster("Çözülen yazı (belge deposu)", lambda: iter(satirlar_), kaydet=True)
        arka_plan(is_, bitti)

    def belge_ogret(img=None):
        """Sayfa resmi + o sayfanın doğru metni -> belge deposu (gerçek harfler, sanal silik kopyalar, bağlam)."""
        import belge_harf as BH
        from PIL import Image
        if img is None:
            yol = filedialog.askopenfilename(title="Öğretilecek sayfa resmi",
                                             filetypes=[("Resimler", " ".join("*" + u for u in RESIM_UZ))])
            if not yol:
                return
            img = Image.open(yol)
            img.load()
        pen = tk.Toplevel(kok)
        pen.title("Bu sayfanın doğru metni")
        tk.Label(pen, justify="left", text="Sayfadaki yazının doğru metnini SATIR SATIR yazın ya da yapıştırın "
                 "(sayfadaki satır düzeniyle).\nOkunamayan ya da üstü çizili satırları atlayabilirsiniz; "
                 "hizalama onları kendisi ayırır.").pack(padx=10, pady=(10, 4), anchor="w")
        kutu = tk.Text(pen, width=90, height=18, wrap="none")
        kutu.pack(padx=10, pady=4, fill="both", expand=True)

        def tamam():
            metin_ = kutu.get("1.0", "end").strip()
            pen.destroy()
            if not metin_:
                return

            def bitti(r):
                messagebox.showinfo("Croow MultiReader",
                                    f"Öğrenildi.\n\nEşleşen satır: {r['eslesen_satir']} / {r['metin_satiri']}"
                                    f" (atlanan {r['atlanan_satir']})\n"
                                    + (f"Daktilo adımı: {r['daktilo_adimi']} piksel\n" if r.get("daktilo_adimi") else "")
                                    + f"Gerçek harf örneği: {r['gercek_harf']:,}\nSanal silik kopya: {r['sanal_harf']:,}\n\n"
                                    f"Depo: {r['harf']} farklı harf · {r['gercek_kok']:,} gerçek kök · "
                                    f"{r['sanal_kok']:,} sanal kök · {r['kelime']:,} kelime")
                bilgi.configure(text="Belge deposu güncellendi")
            arka_plan(lambda il: BH.ogret(img, metin_, ilerleme=il), bitti)
        tk.Button(pen, text="Öğret", command=tamam).pack(pady=(4, 10))

    # ---- Harf göster ve öğret: resimde harfe tıkla, Croow tahminini söylesin; kutuları elle düzenle
    def ortak_depo():
        """Bütün sekmelerin paylaştığı TEK harf deposu (sekmeler birbirinin öğrendiğini görür, birbirini ezmez)."""
        import belge_harf as BH
        if "depo" not in ortak:
            ortak["depo"] = BH.Depo()
        return ortak["depo"]
    ortak = {}

    def harf_goster():
        if durum.get("asil_img") is None:
            return
        import belge_harf as BH

        def is_(il):
            il(0, "Harf kutuları bulunuyor…")
            depo = ortak_depo()
            g, kap, ham, adim = BH.kutular_bul(durum["asil_img"], None if depo.bos() else depo, ayarla=False)
            return g.convert("RGB"), kap, ham, depo, adim

        def bitti(r):
            rgb, kap, ham, depo, adim = r
            ay = depo.kutu_ayari()
            kutular = [BH.kutu_ayarla(k, ay, kap.width, kap.height) for k in ham] if ay else list(ham)
            durum["goster"] = {"rgb": rgb, "kap": kap, "kutular": kutular, "depo": depo, "say": 0, "adim": adim,
                               "kelimeler": BH.kelime_kutulari(kutular, adim) if kutular else [], "okuma": {},
                               "ham": dict(zip(kutular, ham)), "ad": os.path.basename(durum.get("yol") or "sayfa")}
            durum["img"] = rgb
            resim_ciz(True)
            ek = (f" Öğrenilen kutu ayarı uygulandı (sol {ay[0]:+.2f}, sağ {ay[1]:+.2f}, üst {ay[2]:+.2f}, alt {ay[3]:+.2f})."
                  if ay else "")
            bilgi.configure(text=f"Harf göster: {len(kutular):,} harf kutusu.{ek} Bir harfe tıkla: Croow tahminini söyler; "
                                 "mavi kutunun kenarını sürükleyip düzeltebilirsin.")
        arka_plan(is_, bitti)

    def bolge_secildi(r):
        durum["bolge"] = r
        bilgi.configure(text=("Bölge seçildi: CriCroow7 adımları, yazıyı çözme ve detaylandırma yalnızca bu bölgede "
                              f"çalışır ({int(r[2] - r[0])}×{int(r[3] - r[1])} px)") if r else "Bölge temizlendi: işlemler bütün sayfada")

    def bolge_kirp(img):
        """Seçili bölge varsa resmin o parçası, yoksa resmin kendisi. -> (resim, (x0, y0) ya da None)"""
        b = durum.get("bolge")
        if not b:
            return img, None
        x0, y0, x1, y1 = (int(v) for v in b)
        return img.crop((x0, y0, x1, y1)), (x0, y0)

    # ---- Kelime çözücü: yan panel (harf sayısı ____, kilit harfler, aday kelimeler, öğret)
    kp = {}

    def panel_kapat():
        if "cerceve" in kp:
            kp["cerceve"].pack_forget()
        gor.bindir_sil("sec")
        gor.duzenle_ata(None)
        kp.pop("kutular", None)
        kp.pop("kelime_no", None)
        kp.pop("secili_kutu", None)
        kp.pop("tum_kutular", None)

    def bindirme_yenile():
        """Seçili kelime (kırmızı) ve harf (mavi, düzenlenebilir) çerçevelerini yeniden çizer."""
        gs = durum.get("goster")
        gor.bindir_sil("sec")
        gor.duzenle_ata(None)
        if gs and durum.get("img") is gs["rgb"]:              # eşleştirme grubunda bu sayfadan seçilenler (mor)
            gor.bindir("esle", [(k[0] - 1, k[2] - 1, k[1] + 1, k[3] + 1, "#b030d0", 3, None)
                                for it in esl["liste"] if it["kap"] is gs["kap"] for k in (it["kutu"],)])
        else:
            gor.bindir_sil("esle")
        if not gs or durum.get("img") is not gs["rgb"] or "cerceve" not in kp or "secili_kutu" not in kp:
            return
        w, k = kp.get("tum_kutular"), kp.get("secili_kutu")
        if w:
            gor.bindir("sec", [(w[0][0] - 2, min(x[2] for x in w) - 2, w[-1][1] + 2, max(x[3] for x in w) + 2,
                                "#ff3030", 2, None)])
        if k:
            gor.duzenle_ata((k[0], k[2], k[1], k[3]))

    def panel_kur():
        if "cerceve" in kp:
            return
        # Panel sabit genişlikte ve KAYDIRILABİLİR: içeriği ne kadar uzun/geniş olursa olsun görüntü alanını ezmez
        dis = ttk.Frame(resim_cerceve, width=430)
        dis.pack_propagate(False)
        tuv = tk.Canvas(dis, highlightthickness=0, borderwidth=0)
        ky = ttk.Scrollbar(dis, orient="vertical", command=tuv.yview)
        kx = ttk.Scrollbar(dis, orient="horizontal", command=tuv.xview)
        tuv.configure(yscrollcommand=ky.set, xscrollcommand=kx.set)
        kx.pack(side="bottom", fill="x")
        ky.pack(side="right", fill="y")
        tuv.pack(side="left", fill="both", expand=True)
        f = ttk.Frame(tuv, padding=8)
        tuv.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>", lambda e: tuv.configure(scrollregion=tuv.bbox("all")))

        def tekerlek(e):
            tuv.yview_scroll(-1 if (e.num == 4 or getattr(e, "delta", 0) > 0) else 1, "units")
        def tekerlek_ac(e=None):
            def tk_(ev):
                if isinstance(ev.widget, (tk.Text, tk.Listbox)):          # kendi kaydırması olan kutular kendi başına kayar
                    return
                if ev.num == 4 or getattr(ev, "delta", 0) > 0:
                    tuv.yview_scroll(-2, "units")
                else:
                    tuv.yview_scroll(2, "units")
            kp["tekerlek"] = tk_
            for ol in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
                tuv.bind_all(ol, tk_)

        def tekerlek_kapat(e=None):
            for ol in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
                tuv.unbind_all(ol)
        dis.bind("<Enter>", tekerlek_ac)
        dis.bind("<Leave>", lambda e: tekerlek_kapat() if not str(dis.winfo_containing(e.x_root, e.y_root)).startswith(str(dis)) else None)
        kp["cerceve"] = dis
        hf = ttk.LabelFrame(f, text="Seçili harf (mavi çerçeve)", padding=6)
        hf.pack(fill="x", pady=(0, 8))
        kp["harf_tahmin"] = ttk.Label(hf, text="", font=("TkDefaultFont", 12, "bold"), wraplength=300, justify="left")
        kp["harf_tahmin"].pack(anchor="w")
        kp["zoom"] = tk.Label(hf, bd=1, relief="solid", bg="white")
        kp["zoom"].pack(anchor="w", pady=(4, 2))
        kp["zoom"].configure(cursor="fleur")
        kp["zoom"].bind("<ButtonPress-1>", zoom_tut)
        kp["zoom"].bind("<B1-Motion>", zoom_surukle)
        kp["zoom"].bind("<ButtonRelease-1>", zoom_birak)
        kp["esnek"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(hf, text="Esnek kutu (8 noktalı çerçeve)", variable=kp["esnek"],
                        command=lambda: kp.get("secili_kutu") and zoom_yenile(kp["secili_kutu"])).pack(anchor="w")
        ttk.Button(hf, text="Kutuyu mürekkebe sıkıştır", command=lambda: kutu_sikistir()).pack(anchor="w", pady=(0, 2))
        kp["zoom_not"] = ttk.Label(hf, text="", foreground="#555", wraplength=380, justify="left")
        kp["zoom_not"].pack(anchor="w")
        hs = ttk.Frame(hf)
        hs.pack(anchor="w", pady=(4, 0))
        ttk.Button(hs, text="Doğru", command=lambda: harf_cevap(None)).pack(side="left")
        ttk.Label(hs, text="  Değilse doğrusu:").pack(side="left")
        kp["duzelt"] = tk.Entry(hs, width=3, justify="center", font=("DejaVu Sans Mono", 13), relief="solid", bd=1)
        kp["duzelt"].pack(side="left", padx=4)
        kp["duzelt"].bind("<FocusIn>", lambda ev: kp.__setitem__("odak_kip", "harf"))
        kp["duzelt"].bind("<Control-Right>", lambda ev: kelime_gec(1))
        kp["duzelt"].bind("<Control-Left>", lambda ev: kelime_gec(-1))
        kp["duzelt"].bind("<Return>", lambda e: harf_cevap(kp["duzelt"].get().strip() or None))
        ttk.Button(hs, text="Düzelt ve öğret", command=lambda: harf_cevap(kp["duzelt"].get().strip() or "")).pack(side="left")
        kp["ilerle"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(hf, text="Sonraki harfe geç", variable=kp["ilerle"]).pack(anchor="w", pady=(4, 0))
        kp["nizami"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(hf, text="Onaylayınca o harfi nizami (temiz) yap", variable=kp["nizami"]).pack(anchor="w")
        ttk.Button(hf, text="Son nizami dönüşümü geri al (Ctrl+Z)", command=lambda: nizami_geri()).pack(anchor="w", pady=(2, 0))
        vf = ttk.LabelFrame(hf, text="Bu harfin varyasyonları", padding=4)
        vf.pack(fill="x", pady=(6, 0))
        kp["var_resim"] = ttk.Frame(vf)
        kp["var_resim"].pack(anchor="w")
        kp["var_ozet"] = ttk.Label(vf, text="", wraplength=290, justify="left", foreground="#555")
        kp["var_ozet"].pack(anchor="w", pady=(2, 0))
        sf = ttk.Frame(vf)
        sf.pack(anchor="w", pady=(2, 0))
        ttk.Label(sf, text="Bu örnek:").pack(side="left")
        kp["seviye"] = tk.StringVar(value="oto")
        for ad_, m_ in (("oto", "otomatik"), ("nizami", "nizami"), ("orta", "orta kirli"), ("kirli", "kirli")):
            ttk.Radiobutton(sf, text=m_, value=ad_, variable=kp["seviye"]).pack(side="left", padx=2)
        af = ttk.Frame(vf)
        af.pack(anchor="w", pady=(2, 0))
        ttk.Label(af, text="Yazı ailesi:").pack(side="left")
        kp["aile"] = tk.Entry(af, width=14)
        kp["aile"].pack(side="left", padx=4)
        kp["aile"].bind("<Return>", lambda e: aile_ata())
        kp["aile"].bind("<FocusOut>", lambda e: aile_ata())
        kp["harf_durum"] = ttk.Label(hf, text="", wraplength=300, justify="left", foreground="#555")
        kp["harf_durum"].pack(anchor="w")
        kd = ttk.Frame(hf)
        kd.pack(anchor="w", pady=(4, 0))
        ttk.Button(kd, text="Kutuyu sil", command=lambda: kutu_sil()).pack(side="left")
        ttk.Button(kd, text="Sağdakiyle birleştir", command=lambda: kutu_birlestir()).pack(side="left", padx=4)
        ttk.Button(kd, text="İkiye böl", command=lambda: kutu_bol()).pack(side="left")
        ttk.Label(hf, text="Kutuyu düzelt: kenarı/köşesi = boyut, içi = taşı, ok tuşları = 1 px, Shift+sürükle = yeni kutu, "
                           "Delete = sil.", wraplength=300, justify="left", foreground="#777").pack(anchor="w", pady=(4, 0))
        ttk.Label(f, text="Kelime çözücü", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        kp["okundu"] = ttk.Label(f, text="", wraplength=300, justify="left")
        kp["okundu"].pack(anchor="w", pady=(2, 4))
        satir = ttk.Frame(f)
        satir.pack(anchor="w")
        ttk.Label(satir, text="Harf sayısı:").pack(side="left")
        kp["sayi"] = tk.Spinbox(satir, from_=1, to=40, width=4, command=lambda: panel_yuva_kur(False))
        kp["sayi"].pack(side="left", padx=6)
        kp["sayi"].bind("<Return>", lambda e: panel_yuva_kur(False))      # sayıyı değiştirmek yazılan harfleri SİLMEZ
        kp["sayi"].bind("<FocusOut>", lambda e: panel_yuva_kur(False))
        kp["desen"] = ttk.Label(f, text="", font=("DejaVu Sans Mono", 16, "bold"), foreground="#1b5cd6")
        kp["desen"].pack(anchor="w", pady=(8, 0))
        ttk.Label(f, text="Bildiğin harfi yuvasına yaz (dolu yuva = kilit):").pack(anchor="w", pady=(6, 2))
        kp["yuvalar_f"] = ttk.Frame(f)
        kp["yuvalar_f"].pack(anchor="w")
        ttk.Label(f, text="Uygun kelimeler (en olasıdan):").pack(anchor="w", pady=(8, 2))
        lf = ttk.Frame(f)
        lf.pack(fill="both", expand=True)
        kp["liste"] = tk.Listbox(lf, height=12, width=34, font=("DejaVu Sans Mono", 10), exportselection=False)
        ls = ttk.Scrollbar(lf, orient="vertical", command=kp["liste"].yview)
        kp["liste"].configure(yscrollcommand=ls.set)
        ls.pack(side="right", fill="y")
        kp["liste"].pack(side="left", fill="both", expand=True)
        kp["liste"].bind("<Double-Button-1>", lambda e: panel_ogret("secili"))
        bf = ttk.Frame(f)
        bf.pack(fill="x", pady=(6, 2))
        ttk.Button(bf, text="Kelime doğru", command=lambda: panel_ogret("dogru")).pack(side="left", padx=(0, 6))
        ttk.Button(bf, text="Seçili adayı öğret", command=lambda: panel_ogret("secili")).pack(side="left")
        ttk.Button(bf, text="Yazdığımı öğret", command=lambda: panel_ogret("yazilan")).pack(side="left", padx=6)
        ttk.Button(bf, text="Kapat", command=panel_kapat).pack(side="right")
        gf = ttk.Frame(f)
        gf.pack(anchor="w", pady=(2, 0))
        ttk.Button(gf, text="← Önceki kelime (Ctrl+←)", command=lambda: kelime_gec(-1)).pack(side="left")
        ttk.Button(gf, text="Geç → (Ctrl+→)", command=lambda: kelime_gec(1)).pack(side="left", padx=4)
        ttk.Button(f, text="Sayfayı oku (baştan)", command=lambda: panel_sayfa_oku()).pack(anchor="w", pady=(2, 0))
        kp["durum"] = ttk.Label(f, text="", wraplength=300, justify="left", foreground="#555")
        kp["durum"].pack(anchor="w", pady=(2, 4))
        ttk.Label(f, text="Sayfanın yeniden okunması:").pack(anchor="w")
        kp["sayfa"] = tk.Text(f, height=9, width=38, wrap="word", font=("DejaVu Sans Mono", 9))
        kp["sayfa"].pack(fill="both", expand=True)
        kp["yuva_g"], kp["yuva_v"] = [], []

    def panel_yuva_kur(sifirla):
        """Harf sayısı kadar yuva (kutu) kurar; sifirla: önceki yazılanlar silinir."""
        L = max(1, min(40, int(kp["sayi"].get() or 1)))
        eski = [v.get() for v in kp["yuva_v"]] if not sifirla else []
        for g in kp["yuva_g"]:
            g.destroy()
        kp["yuva_g"], kp["yuva_v"] = [], []
        for j in range(L):
            v = tk.StringVar(value=eski[j] if j < len(eski) else "")
            e = tk.Entry(kp["yuvalar_f"], textvariable=v, width=2, justify="center", font=("DejaVu Sans Mono", 14),
                         relief="solid", bd=1)
            e.grid(row=j // 9, column=j % 9, padx=1, pady=1)
            e.bind("<KeyRelease>", lambda ev, j=j: panel_yaz(j))
            e.bind("<BackSpace>", lambda ev, j=j: panel_geri(j))
            e.bind("<Tab>", lambda ev, j=j: panel_tab(j))
            e.bind("<FocusIn>", lambda ev: kp.__setitem__("odak_kip", "yuva"))
            e.bind("<Control-Right>", lambda ev: kelime_gec(1))
            e.bind("<Control-Left>", lambda ev: kelime_gec(-1))
            e.bind("<Return>", lambda ev: panel_enter())
            e.bind("<Left>", lambda ev, j=j: kp["yuva_g"][max(0, j - 1)].focus_set() or "break")
            e.bind("<Right>", lambda ev, j=j: kp["yuva_g"][min(len(kp["yuva_g"]) - 1, j + 1)].focus_set() or "break")
            kp["yuva_g"].append(e)
            kp["yuva_v"].append(v)
        panel_yenile()

    def panel_enter():
        """Enter = öğret. Hepsi yazıldıysa 'Yazdığımı öğret'. Hiç yazılmadıysa Croow'un okuması doğru sayılır AMA yalnızca
        sözlükte bir kelimeyse (çöp okuma yanlışlıkla öğretilmesin). Kısmen yazıldıysa yazılanlar kilit kalır, boşlar
        Croow'un tahminiyle dolar; tahmin sözlükten geldiyse öğretilir, değilse kontrol için bırakılır."""
        gs = durum.get("goster")
        L = len(kp["yuva_v"])
        dolu = sum(1 for v in kp["yuva_v"] if v.get().strip())
        aday = kp.get("sonuc", {}).get("aday", [])
        if dolu == L:
            panel_ogret("yazilan")
        elif dolu == 0:
            okunan = "".join(c[0][0] if c else "?" for c in kp.get("okuma", [])).lower()
            sozlukte = bool(gs and (okunan in gs["depo"].kelime or (aday and aday[0][0].lower().replace("'", "") == okunan)))
            if sozlukte:
                panel_ogret("dogru")
            else:
                kp["durum"].configure(text="Croow'un okuması sözlükte bir kelime değil; hiçbir şey yazmadan Enter'la öğretmem. "
                                           "Yaz (ya da Tab ile tahmini düşür) sonra Enter. Geçmek için Ctrl+→.")
        else:
            adayli = bool(aday and len(aday[0][0].replace("'", "")) == L)
            panel_tab(0)
            if all(v.get().strip() for v in kp["yuva_v"]):
                if adayli:
                    panel_ogret("yazilan")
                else:
                    kp["durum"].configure(text="Boşlar Croow'un okumasıyla dolduruldu (sözlük adayı yok). Kontrol et, "
                                               "doğruysa Enter'a tekrar bas.")
        return "break"

    def panel_tab(j):
        """Tab: Croow'un tahminini BOŞ yuvalara düşürür (dolu/kilitli yuvalara dokunmaz). Tahmin: en olası aday kelime,
        yoksa Croow'un harf harf okuması."""
        import belge_harf as BH
        L = len(kp["yuva_v"])
        aday = kp.get("sonuc", {}).get("aday", [])
        tahmin = None
        if aday and len(aday[0][0].replace("'", "")) == L:
            tahmin = list(aday[0][0].replace("'", ""))
            if kp.get("okuma"):
                tahmin = list(BH.kasa_uyarla("".join(tahmin), kp["okuma"]).replace("'", ""))
        elif kp.get("okuma") and len(kp["okuma"]) == L:
            tahmin = [c[0][0] if c else "" for c in kp["okuma"]]
        if tahmin is None or len(tahmin) != L:
            kp["durum"].configure(text="Tahmin edilecek bir şey yok (aday yok / harf sayısı okumayla uyuşmuyor).")
            return "break"
        dolduruldu = 0
        for q, (v, h) in enumerate(zip(kp["yuva_v"], tahmin)):
            if h and not v.get().strip():
                v.set(h)
                dolduruldu += 1
        panel_yenile()
        kp["durum"].configure(text=f"Tab: Croow'un tahmini {dolduruldu} boş yuvaya yazıldı. Yanlışları ok tuşlarıyla gezip düzelt, "
                                   "Enter = 'Yazdığımı öğret'.")
        for g_, v in zip(kp["yuva_g"], kp["yuva_v"]):               # odak: ilk yanlış olabilecek yer = ilk yuva
            g_.focus_set()
            break
        return "break"

    def kelime_gec(yon=1):
        """Ctrl+→ / Ctrl+←: öğretmeden sıradaki / önceki kelimeye geç (noktalama gibi kelimeleri atlar)."""
        gs = durum.get("goster")
        if not gs or "cerceve" not in kp or kp.get("secili_kutu") is None:
            return "break"
        cur = kp.get("kelime_no")
        if cur is None:
            cur = next((ki for ki, w in enumerate(gs["kelimeler"]) if kp["secili_kutu"] in w), None)
        if cur is None:
            return "break"
        i = cur
        for _ in range(12):
            i += yon
            if not 0 <= i < len(gs["kelimeler"]):
                bilgi.configure(text="Sayfanın sonuna / başına geldin.")
                break
            sec_kutu(gs["kelimeler"][i][0])
            if "kutular" in kp and kp.get("kelime_no") == i:
                break
        kp["odak_kip"] = "yuva"
        odak_ver()
        return "break"

    def panel_geri(j):
        """Geri sil: dolu yuvayı boşaltır; boşsa bir önceki yuvaya geçip onu boşaltır."""
        v = kp["yuva_v"][j]
        if v.get():
            v.set("")
        elif j > 0:
            kp["yuva_v"][j - 1].set("")
            kp["yuva_g"][j - 1].focus_set()
        panel_yenile()
        return "break"

    def panel_yaz(j):
        v = kp["yuva_v"][j]
        t = v.get()
        if len(t) > 1:                                   # tek harf: sonuncuyu tut
            v.set(t[-1])
        panel_yenile()
        # bir sonraki boş yuvaya geç
        if v.get() and j + 1 < len(kp["yuva_g"]) and not kp["yuva_v"][j + 1].get():
            kp["yuva_g"][j + 1].focus_set()

    def panel_kilit():
        return {j: v.get() for j, v in enumerate(kp["yuva_v"]) if v.get().strip()}

    def panel_yenile():
        import belge_harf as BH
        gs = durum.get("goster")
        if not gs or "kutular" not in kp:
            return
        L = len(kp["yuva_v"])
        r = BH.desen_ara(kp["kutular"], kp["okuma"], gs["depo"], gs["adim"], kilit=panel_kilit(), uzunluk=L,
                         onceki=kp.get("onceki"))
        kp["sonuc"] = r
        kp["desen"].configure(text=" ".join((c or "_") for c in r["desen"]))
        kp["liste"].delete(0, "end")
        if gs["depo"].kelime:
            for w, puan, sayi in r["aday"]:
                kp["liste"].insert("end", f"{BH.kasa_uyarla(w, kp['okuma']):<18} {puan:>8.1f}  [{sayi}]")
            if not r["aday"]:
                kp["liste"].insert("end", "(bu kalıba uyan kelime yok: harf sayısını ya da kilitleri değiştir)")
            else:
                kp["liste"].selection_set(0)
        else:
            kp["liste"].insert("end", "(sözlük boş: Araçlar → Cümle bağlamı öğret)")

    def panel_ham(kutular):
        """Bir kelimenin Croow okuması (en olası harfler, küçük harf)."""
        gs = durum["goster"]
        import belge_harf as BH
        import crw_harf as CH
        P = CH.Palet()
        out = []
        for k in kutular:
            if k not in gs["okuma"]:
                gs["okuma"][k] = BH.kutu_okuma(gs["kap"], [k], gs["depo"], P if P.k else None)[0]
            out.append(gs["okuma"][k])
        return out

    def gor_tikla(ix, iy, e):
        """Görüntüde tık (resim koordinatı): tıklanan harf kutusunu seçer."""
        gs = durum.get("goster")
        if not gs or durum.get("img") is not gs["rgb"]:
            return bilgi.configure(text="Önce soldaki listeden 'Harf göster ve öğret'i seç.")
        for w in gs["kelimeler"]:
            if w[0][0] - 3 <= ix <= w[-1][1] + 3 and w[0][4] <= iy <= w[0][5]:
                return sec_kutu(min(w, key=lambda k: abs((k[0] + k[1]) / 2 - ix)))
        bilgi.configure(text="Burada kelime yok. Bir kelimenin ya da harfin üstüne tıkla.")

    def poly_varsayilan(k):
        x0, x1, y0, y1 = k[0], k[1], k[2], k[3]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        return [(x0, y0), (mx, y0), (x1, y0), (x1, my), (x1, y1), (mx, y1), (x0, y1), (x0, my)]

    def poly_al(kutu):
        gs = durum.get("goster")
        return gs.setdefault("poly", {}).get(kutu) or poly_varsayilan(kutu)

    def zoom_yenile(kutu, cizim=None, pencere=None, poly=None):
        """Seçili kutunun içini (ve çevresini) büyütüp panelde gösterir. cizim: sürükleme sırasındaki geçici kutu
        (x0, x1, y0, y1); pencere: sabit kırpma penceresi; poly: geçici 8 nokta (esnek kip)."""
        gs = durum.get("goster")
        if not gs or "zoom" not in kp:
            return
        import io
        from PIL import Image, ImageDraw
        x0, x1, y0, y1, ust, alt = kutu
        if pencere is None:
            pay = max(8, (alt - ust) // 2)
            pencere = (max(0, x0 - pay), max(0, y0 - pay), min(gs["rgb"].width, x1 + pay), min(gs["rgb"].height, y1 + pay))
        a0, b0, a1, b1 = pencere
        parca = gs["rgb"].crop((a0, b0, a1, b1))
        kat = max(1.0, min(5.0, 190 / max(1, parca.height), 400 / max(1, parca.width)))
        z = parca.resize((max(1, int(parca.width * kat)), max(1, int(parca.height * kat))), Image.Resampling.LANCZOS)
        dr = ImageDraw.Draw(z)
        r = cizim or (x0, x1, y0, y1)
        esnek = kp.get("esnek") is not None and kp["esnek"].get()
        if esnek:
            pts = poly or poly_al(kutu)
            zp = [((x - a0) * kat, (y - b0) * kat) for x, y in pts]
            dr.rectangle([(x0 - a0) * kat, (y0 - b0) * kat, (x1 - a0) * kat - 1, (y1 - b0) * kat - 1], outline="#9fbfff", width=1)
            dr.polygon(zp, outline="#ff7a00")
            for px, py in zp:
                dr.rectangle([px - 3, py - 3, px + 3, py + 3], fill="#ff7a00", outline="white")
            not_ = ("ESNEK kutu: turuncu 8 noktadan birini sürükle (her nokta ayrı); 'Kutuyu mürekkebe sıkıştır' noktaları siyah "
                    "kenarlara yapıştırır. Çerçevenin DIŞI (leke, taşma) onaylayınca silinir ve harf yalnızca içinden öğrenilir.")
        else:
            dr.rectangle([(r[0] - a0) * kat, (r[2] - b0) * kat, (r[1] - a0) * kat - 1, (r[3] - b0) * kat - 1],
                         outline="#1060ff", width=2)
            not_ = (f"Mavi çerçeve = Croow'un baktığı kutu ({r[1] - r[0]}×{r[3] - r[2]} px, {kat:.1f}× büyütüldü). "
                    "Kenarını/köşesini BURADA sürükleyerek daralt (harfe oturt), içinden sürükleyerek taşı.")
        tp = io.BytesIO()
        z.convert("RGB").save(tp, "PNG")
        kp["zoom_foto"] = tk.PhotoImage(data=tp.getvalue())
        kp["zoom"].configure(image=kp["zoom_foto"])
        kp["zoom_geo"] = (a0, b0, a1, b1, kat)
        kp["zoom_not"].configure(text=not_)

    def zoom_tut(e):
        k, geo = kp.get("secili_kutu"), kp.get("zoom_geo")
        if not k or not geo:
            return
        a0, b0, a1, b1, kat = geo
        X, Y = e.x / kat + a0, e.y / kat + b0
        if kp["esnek"].get():                                         # esnek kip: en yakın nokta
            pts = list(poly_al(k))
            i = min(range(len(pts)), key=lambda q: (pts[q][0] - X) ** 2 + (pts[q][1] - Y) ** 2)
            if ((pts[i][0] - X) ** 2 + (pts[i][1] - Y) ** 2) ** 0.5 * kat <= 14:
                kp["zoom_surukle"] = {"nokta": i, "pts": pts, "pencere": (a0, b0, a1, b1)}
            return
        t = 6 / kat
        dl, dr, dt, db = abs(X - k[0]), abs(X - k[1]), abs(Y - k[2]), abs(Y - k[3])
        m = {"l": dl <= t and dl <= dr, "r": dr <= t and dr < dl, "t": dt <= t and dt <= db, "b": db <= t and db < dt}
        ic = k[0] - t <= X <= k[1] + t and k[2] - t <= Y <= k[3] + t
        if not any(m.values()):
            if not ic:
                return
            m = {"tasi": True}
        kp["zoom_surukle"] = {"m": m, "x": X, "y": Y, "r0": (k[0], k[1], k[2], k[3]), "pencere": (a0, b0, a1, b1)}

    def zoom_surukle(e):
        d, geo, k = kp.get("zoom_surukle"), kp.get("zoom_geo"), kp.get("secili_kutu")
        if not d or not geo or not k:
            return
        gs = durum.get("goster")
        a0, b0, a1, b1, kat = geo
        X, Y = e.x / kat + a0, e.y / kat + b0
        W, H = gs["rgb"].width, gs["rgb"].height
        if "nokta" in d:
            d["pts"][d["nokta"]] = (max(0.0, min(W - 1.0, X)), max(0.0, min(H - 1.0, Y)))
            d["son_pts"] = list(d["pts"])
            return zoom_yenile(k, None, d["pencere"], d["son_pts"])
        x0, x1, y0, y1 = d["r0"]
        m = d["m"]
        if m.get("tasi"):
            dx, dy = int(round(X - d["x"])), int(round(Y - d["y"]))
            x0, x1, y0, y1 = x0 + dx, x1 + dx, y0 + dy, y1 + dy
        else:
            if m["l"]:
                x0 = int(round(X))
            if m["r"]:
                x1 = int(round(X))
            if m["t"]:
                y0 = int(round(Y))
            if m["b"]:
                y1 = int(round(Y))
        x0, x1 = max(0, min(x0, x1 - 2)), min(W, max(x1, x0 + 2))
        y0, y1 = max(0, min(y0, y1 - 2)), min(H, max(y1, y0 + 2))
        d["son"] = (x0, x1, y0, y1)
        zoom_yenile(k, d["son"], d["pencere"])

    def zoom_birak(e):
        d = kp.pop("zoom_surukle", None)
        if not d:
            return
        k, gs = kp.get("secili_kutu"), durum.get("goster")
        if "nokta" in d:
            if "son_pts" in d and k:
                gs.setdefault("poly", {})[k] = d["son_pts"]
                zoom_yenile(k)
            return
        if "son" not in d:
            return
        x0, x1, y0, y1 = d["son"]
        if (x0, x1, y0, y1) != d["r0"]:
            kutu_duzenlendi((x0, y0, x1, y1), True)

    def poly_sikistir(gs, k):
        """8 noktayı, kutunun dışından içeri (mürekkebin merkezine doğru) yürütüp İLK gerçek mürekkebe yapıştırır."""
        import numpy as np
        a = np.asarray(gs["kap"].crop((k[0], k[2], k[1], k[3])), dtype=np.float32) > 110
        h, w = a.shape
        if a.sum() < 6:
            return None
        ys, xs = np.nonzero(a)
        cx, cy = float(xs.mean()), float(ys.mean())
        yog = np.zeros((h + 2, w + 2), dtype=np.int32)                # 3×3 komşuluk sayımı (tek pikselli leke yoksayılsın)
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                yog[1:h + 1, 1:w + 1] += np.pad(a, 1)[dy:dy + h, dx:dx + w]
        yog = yog[1:h + 1, 1:w + 1]
        out = []
        for px, py in poly_varsayilan(k):
            x, y = px - k[0], py - k[2]
            dx, dy = cx - x, cy - y
            uz = max(1.0, (dx * dx + dy * dy) ** 0.5)
            bulundu = None
            for t in np.arange(0, uz, 0.5):
                xi, yi = int(round(x + dx / uz * t)), int(round(y + dy / uz * t))
                if 0 <= xi < w and 0 <= yi < h and a[yi, xi] and yog[yi, xi] >= 4:
                    bulundu = (x + dx / uz * max(0, t - 0.5), y + dy / uz * max(0, t - 0.5))
                    break
            out.append((k[0] + (bulundu or (x, y))[0], k[2] + (bulundu or (x, y))[1]))
        return out

    def kutu_sikistir():
        """Seçili kutuyu mürekkebe sıkıştırır. Esnek kipte 8 nokta ayrı ayrı siyah kenara yapışır."""
        import belge_harf as BH
        gs, k = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not k:
            return
        if kp["esnek"].get():
            pts = poly_sikistir(gs, k)
            if pts is None:
                return bilgi.configure(text="Kutuda mürekkep yok; sıkıştırılamadı.")
            gs.setdefault("poly", {})[k] = pts
            zoom_yenile(k)
            return bilgi.configure(text="8 nokta siyah kenarlara yapıştı. Noktaları sürükleyerek ince ayar yapabilirsin; "
                                        "onaylayınca çerçevenin dışı temizlenir.")
        sk = BH.sik_kutu(gs["kap"], (k[0], k[2], k[1], k[3]))
        if sk is None:
            return bilgi.configure(text="Kutuda mürekkep yok; sıkıştırılamadı.")
        if sk == (k[0], k[1], k[2], k[3]):
            return bilgi.configure(text="Kutu zaten mürekkebe oturuyor.")
        kutu_duzenlendi((sk[0], sk[2], sk[1], sk[3]), True)

    def poly_uygula(kutu):
        """Esnek çerçevenin DIŞINDAKİ mürekkebi (leke, taşma, komşu kırıntısı) kutuda siler; geri alınabilir."""
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter
        gs = durum.get("goster")
        pts = gs.get("poly", {}).get(kutu) if gs else None
        if not pts:
            return None
        x0, x1, y0, y1 = kutu[0], kutu[1], kutu[2], kutu[3]
        mk = Image.new("L", (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(mk).polygon([(x - x0, y - y0) for x, y in pts], fill=255)
        mk = np.asarray(mk.filter(ImageFilter.MaxFilter(3)), dtype=np.float32) / 255.0
        kap_p = gs["kap"].crop((x0, y0, x1, y1))
        rgb_p = gs["rgb"].crop((x0, y0, x1, y1)).copy()
        nizami_gecmis.append((gs, kutu, kap_p.copy(), rgb_p))
        nizami_zaman[0] = time.time()
        k_yeni = np.asarray(kap_p, dtype=np.float32) * mk
        gs["kap"].paste(Image.fromarray(k_yeni.astype(np.uint8)), (x0, y0))
        g = np.asarray(rgb_p, dtype=np.float32)
        yeni_rgb = g * mk[:, :, None] + 255.0 * (1 - mk[:, :, None])
        gs["rgb"].paste(Image.fromarray(yeni_rgb.astype(np.uint8)), (x0, y0))
        silinen = float((np.asarray(kap_p, dtype=np.float32) * (1 - mk)).sum()) / 255
        return f"çerçeve dışı temizlendi ({silinen:.0f} mürekkep)"

    def odak_ver():
        """İmleç (yanıp sönen I) TIKLAMASIZ yazılacak yerde beklesin: son yazılan yer hatırlanır. Varsayılan: kelime yuvalarının
        ilk BOŞ yuvası; en son 'Değilse doğrusu' kutusuna yazıldıysa orası."""
        try:
            if kp.get("odak_kip", "yuva") == "yuva" and kp.get("yuva_g") and "kutular" in kp:
                bos = next((j for j, v in enumerate(kp["yuva_v"]) if not v.get().strip()), 0)
                kp["yuva_g"][bos].focus_set()
            else:
                kp["duzelt"].focus_set()
        except Exception:  # noqa: BLE001
            pass

    def sec_kutu(kutu):
        """Bir harf kutusunu seçer: Croow tahminini söyler; kelimesi kelime çözücüde açılır; kutu düzenlenebilir."""
        gs = durum.get("goster")
        import belge_harf as BH
        sec = next((ki for ki, w in enumerate(gs["kelimeler"]) if kutu in w), None)
        if sec is None:
            return
        w = gs["kelimeler"][sec]
        okuma = panel_ham(w)
        panel_kur()
        if not kp["cerceve"].winfo_ismapped():
            kp["cerceve"].pack(side="right", fill="y", before=gor.ara)
        yeni_kelime = kp.get("kelime_no") != sec or "kutular" not in kp
        if yeni_kelime:
            a, b = BH.noktalama_kirp(w, okuma)

            def ham(i):
                if not 0 <= i < len(gs["kelimeler"]):
                    return None
                ws = gs["kelimeler"][i]
                if ws[0][4] != w[0][4]:
                    return None                                 # başka satır
                h = "".join(c[0][0] for c in panel_ham(ws) if c and c[0][0].isalnum()).lower()
                return h or None
            kp["kelime_no"] = sec
            kp["tum_kutular"] = w
            def kayma(w=w):                                       # seçilen kelime solda görünsün: oraya kay (gerekirse 100%'e yakınlaş)
                if kp.get("tum_kutular") is not w:
                    return
                cx_, cy_ = (w[0][0] + w[-1][1]) / 2, (min(x_[2] for x_ in w) + max(x_[3] for x_ in w)) / 2
                if gor.zoom() < 0.8:
                    gor.yuzde100()
                gor.git(cx_, cy_)
            kayma()
            kok.after(250, kayma)                                 # panel yeni açıldıysa pencere yeniden boyutlanır: sonra bir kez daha
            if a < b:
                kp["kutular"], kp["okuma"] = w[a:b], okuma[a:b]
                kp["onceki"], kp["sonraki"] = ham(sec - 1), ham(sec + 1)
                kp["okundu"].configure(text="Croow okudu: " + "".join(c[0][0] if c else "?" for c in okuma[a:b]))
                L = BH.tahmin_uzunluk(kp["kutular"], gs["depo"], gs["adim"])
                kp["sayi"].delete(0, "end")
                kp["sayi"].insert(0, str(L))
                panel_yuva_kur(True)
            else:
                kp.pop("kutular", None)
                kp["okundu"].configure(text="Bu kelime noktalama gibi görünüyor.")
        kp["secili_kutu"] = kutu
        bindirme_yenile()
        # --- Croow'un harf tahmini
        ad = okuma[w.index(kutu)]
        if ad:
            ek = f"  ·  ikinci: “{BH.simge_goster(ad[1][0])}” %{100 * ad[1][1]:.0f}" if len(ad) > 1 else ""
            kp["harf_tahmin"].configure(text=f"Bu “{BH.simge_goster(ad[0][0])}”  (%{100 * ad[0][1]:.0f}){ek}")
            kp["tahmin"] = ad[0][0]
        else:
            kp["harf_tahmin"].configure(text="Croow bu şekli tanımıyor.")
            kp["tahmin"] = ""
        zoom_yenile(kutu)
        harf_adi = kp.get("tahmin")
        if not kp["aile"].get():
            kp["aile"].insert(0, gs["depo"].aile)
        varyant_goster(harf_adi)
        n = sum(1 for r in gs["depo"].gercek.k if r[0] == harf_adi) if harf_adi else 0
        kp["harf_durum"].configure(text=f"Doğruysa “Doğru”, değilse doğrusunu yazıp Enter. "
                                        f"(Depoda “{BH.simge_goster(harf_adi)}” için {n} gerçek örnek var.)" if harf_adi else "")
        kp["duzelt"].delete(0, "end")
        odak_ver()
        kp["durum"].configure(text="")

    # ---- kutu düzenleme: Croow konumu tahmin eder, kullanıcı düzeltir, Croow bundan öğrenir
    def aile_ata():
        """Yazı ailesi (yazı tipi / belge türü): varyasyonlar ve nizami şablonlar aile başına tutulur."""
        gs = durum.get("goster")
        if not gs or "aile" not in kp:
            return
        ad = kp["aile"].get().strip() or "genel"
        if gs["depo"].aile != ad:
            gs["depo"].aile = ad
            if kp.get("secili_kutu"):
                varyant_goster(kp.get("tahmin"))

    def varyant_goster(harf):
        """Seçili harfin nizami / orta / kirli şablonlarını yan yana gösterir (dönüşüm yolu: kirli → orta → nizami)."""
        gs = durum.get("goster")
        import io
        import numpy as np
        from PIL import Image
        import belge_harf as BH
        for c in kp["var_resim"].winfo_children():
            c.destroy()
        kp["var_fotolar"] = []
        if not gs or not harf:
            return kp["var_ozet"].configure(text="")
        depo = gs["depo"]
        sira = ("kirli", "orta", "nizami")                       # dönüşüm yönü
        for n_, sv in enumerate(sira):
            t = depo.varyant_sablon(harf, sv)
            f = ttk.Frame(kp["var_resim"])
            f.grid(row=0, column=n_ * 2, padx=2)
            if t is None:
                ttk.Label(f, text="—\n", width=6, justify="center").pack()
            else:
                g = Image.fromarray((255 - t).clip(0, 255).astype(np.uint8)).resize((48, 48), Image.Resampling.BILINEAR).convert("RGB")
                tp = io.BytesIO()
                g.save(tp, format="PPM")
                foto = tk.PhotoImage(data=tp.getvalue())
                kp["var_fotolar"].append(foto)
                ttk.Label(f, image=foto).pack()
            ttk.Label(f, text=f"{sv}\n({depo.varyant_ozet(harf).get(sv, 0)})", font=("TkDefaultFont", 8), justify="center").pack()
            if n_ < 2:
                ttk.Label(kp["var_resim"], text="→").grid(row=0, column=n_ * 2 + 1)
        oz = depo.varyant_ozet(harf)
        kp["var_ozet"].configure(text=("Örnek sayıları: " + ", ".join(f"{sv} {n}" for sv, n in oz.items())) if oz
                                 else "Bu harfin henüz varyasyonu yok (nizami şablon yazı tipinden çizilir).")

    def kutular_yenile(yeni_secili=None):
        gs = durum["goster"]
        import belge_harf as BH
        gs["kutular"].sort(key=lambda k: (k[4], k[0]))
        gs["kelimeler"] = BH.kelime_kutulari(gs["kutular"], gs["adim"]) if gs["kutular"] else []
        gs["okuma"].clear()
        kp.pop("kelime_no", None)
        if yeni_secili is not None and yeni_secili in gs["kutular"]:
            sec_kutu(yeni_secili)
        else:
            panel_kapat()

    def kutu_duzenlendi(rect, son):
        gs, eski = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not eski or not son:
            return
        yeni = (rect[0], rect[2], rect[1], rect[3], eski[4], eski[5])
        if yeni == eski or eski not in gs["kutular"]:
            return
        gs["kutular"][gs["kutular"].index(eski)] = yeni
        gs["ham"][yeni] = gs["ham"].pop(eski, None)
        kutular_yenile(yeni)
        kp["harf_durum"].configure(text="Kutu değişti. Doğru harfi onaylayınca Croow konum düzeltmeni de öğrenir.")

    def kutu_ekle(rect):
        gs = durum.get("goster")
        if not gs or not gs["kutular"]:
            return
        x0, y0, x1, y1 = rect
        cy = (y0 + y1) / 2
        satirlar = sorted({(k[4], k[5]) for k in gs["kutular"]})
        ust, alt = min(satirlar, key=lambda s_: 0 if s_[0] <= cy <= s_[1] else min(abs(cy - s_[0]), abs(cy - s_[1])))
        yeni = (x0, x1, y0, y1, ust, alt)
        gs["kutular"].append(yeni)
        gs["ham"][yeni] = None
        gs["depo"].kutu_olayi("eklendi")
        kutular_yenile(yeni)
        kp["harf_durum"].configure(text="Yeni harf kutusu eklendi (Croow'un kaçırdığı harf). Harfi söyle.")

    def kutu_sil():
        gs, k = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not k or k not in gs["kutular"]:
            return
        i = gs["kutular"].index(k)
        gs["kutular"].remove(k)
        gs["ham"].pop(k, None)
        gs["depo"].kutu_olayi("silindi")
        komsu = gs["kutular"][min(i, len(gs["kutular"]) - 1)] if gs["kutular"] else None
        kutular_yenile(komsu)
        bilgi.configure(text="Kutu silindi (harf değildi). Croow bunu da öğrenir: silinen kutu sayısı kaydedildi.")

    def kutu_birlestir():
        gs, k = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not k:
            return
        i = gs["kutular"].index(k)
        if i + 1 >= len(gs["kutular"]) or gs["kutular"][i + 1][4] != k[4]:
            return bilgi.configure(text="Sağda aynı satırda birleştirilecek kutu yok.")
        n = gs["kutular"][i + 1]
        yeni = (min(k[0], n[0]), max(k[1], n[1]), min(k[2], n[2]), max(k[3], n[3]), k[4], k[5])
        gs["kutular"][i:i + 2] = [yeni]
        gs["ham"].pop(k, None)
        gs["ham"].pop(n, None)
        gs["ham"][yeni] = None
        gs["depo"].kutu_olayi("birlestirildi")
        kutular_yenile(yeni)

    def kutu_bol():
        import numpy as np
        gs, k = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not k or k[1] - k[0] < 6:
            return
        sut = np.asarray(gs["kap"].crop((k[0], k[2], k[1], k[3])), dtype=np.float32).sum(0)
        a, b = max(1, int(len(sut) * 0.3)), max(2, int(len(sut) * 0.7))
        kes = k[0] + a + int(np.argmin(sut[a:b]))                   # ortaya yakın en boş sütun
        sol_k, sag_k = (k[0], kes, k[2], k[3], k[4], k[5]), (kes, k[1], k[2], k[3], k[4], k[5])
        i = gs["kutular"].index(k)
        gs["kutular"][i:i + 1] = [sol_k, sag_k]
        gs["ham"].pop(k, None)
        gs["ham"][sol_k] = gs["ham"][sag_k] = None
        gs["depo"].kutu_olayi("bolundu")
        kutular_yenile(sol_k)

    # ---- Eşleştirme modu: "bu harfler aynı harftir" (sekmeler arası) -> metinden metne aynı harfin görünüşü
    esl = {"liste": [], "pencere": None, "elle": False}

    def esle_kucuk(kap, kutu, yuk=46):
        import io
        from PIL import Image
        g = kap.crop((kutu[0], kutu[2], kutu[1], kutu[3])).point(lambda v: 255 - v).convert("RGB")
        o = yuk / max(1, g.height)
        g = g.resize((max(10, min(90, int(g.width * o))), yuk), Image.Resampling.BILINEAR)
        tampon = io.BytesIO()
        g.save(tampon, format="PPM")
        return tk.PhotoImage(data=tampon.getvalue())

    def esle_arac(ad):
        if ad == "esle":
            esle_penceresi()
            if durum.get("goster") is None and durum.get("asil_img") is not None:
                bilgi.configure(text="Eşleştirme: bu sayfanın harf kutuları bulunuyor…")
                harf_goster()
        bindirme_yenile()

    def esle_tikla(ix, iy, e):
        gs = durum.get("goster")
        if not gs or durum.get("img") is not gs["rgb"]:
            return bilgi.configure(text="Bu sayfanın harf kutuları henüz yok; bulunuyorsa biraz bekle ya da 'Harf göster ve öğret'i seç.")
        import belge_harf as BH
        import crw_harf as CH
        icinde = [k for k in gs["kutular"] if k[0] - 2 <= ix <= k[1] + 2 and k[2] - 2 <= iy <= k[3] + 2]
        if not icinde:
            return bilgi.configure(text="Burada harf kutusu yok.")
        kutu = min(icinde, key=lambda k: abs((k[0] + k[1]) / 2 - ix) + abs((k[2] + k[3]) / 2 - iy))
        for it in esl["liste"]:
            if it["kap"] is gs["kap"] and it["kutu"] == kutu:       # ikinci tık: gruptan çıkar
                esl["liste"].remove(it)
                break
        else:
            P = CH.Palet()
            okuma = BH.kutu_okuma(gs["kap"], [kutu], gs["depo"], P if P.k else None)[0]
            esl["liste"].append({"kap": gs["kap"], "kutu": kutu, "ad": gs.get("ad", "?"), "okuma": okuma,
                                 "foto": esle_kucuk(gs["kap"], kutu)})
        esle_yenile()
        bindirme_yenile()

    def esle_penceresi():
        w = esl.get("pencere")
        if w is not None and w.winfo_exists():
            w.lift()
            return
        w = tk.Toplevel(kok)
        w.title("Eşleştirme — bunlar aynı harf")
        w.geometry("600x430")
        esl["pencere"] = w
        ttk.Label(w, padding=8, wraplength=570, justify="left", text=(
            "Resimde aynı harfe ait kutulara tıkla (farklı sekmelerden de olabilir: her sekmeden tıklamaya devam et). "
            "Küçük resme tıklarsan gruptan çıkar. Sonra aşağıya o harfi yaz ve \"Eşleştir ve öğret\"e bas: hepsi o harfin "
            "örneği olur, Croow aynı harfin metinden metne nasıl göründüğünü öğrenir.")).pack(anchor="w")
        orta = ttk.Frame(w)
        orta.pack(fill="both", expand=True, padx=8)
        tv = tk.Canvas(orta, background="white", highlightthickness=1, highlightbackground="#bbb")
        sb = ttk.Scrollbar(orta, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(fill="both", expand=True)
        ic = ttk.Frame(tv)
        tv.create_window((0, 0), window=ic, anchor="nw")
        ic.bind("<Configure>", lambda e: tv.configure(scrollregion=tv.bbox("all")))
        esl["ic"] = ic
        esl["oy"] = ttk.Label(w, padding=(8, 6, 8, 0), text="")
        esl["oy"].pack(anchor="w")
        alt_ = ttk.Frame(w, padding=8)
        alt_.pack(fill="x")
        ttk.Label(alt_, text="Bu harfler aynı harf:").pack(side="left")
        esl["harf"] = tk.Entry(alt_, width=4, justify="center", font=("DejaVu Sans Mono", 14), relief="solid", bd=1)
        esl["harf"].pack(side="left", padx=6)
        esl["harf"].bind("<KeyRelease>", lambda e: esl.update(elle=True))
        esl["harf"].bind("<Return>", lambda e: esle_ogret())
        ttk.Button(alt_, text="Eşleştir ve öğret", command=lambda: esle_ogret()).pack(side="left", padx=(4, 0))
        ttk.Button(alt_, text="Temizle", command=lambda: esle_temizle()).pack(side="left", padx=4)
        ttk.Button(alt_, text="Kapat", command=lambda: w.destroy()).pack(side="right")
        sv_ = ttk.Frame(w, padding=(8, 0, 8, 0))
        sv_.pack(fill="x")
        ttk.Label(sv_, text="Bu harflerin varyasyonu:").pack(side="left")
        esl["seviye"] = tk.StringVar(value="oto")
        for ad_, m_ in (("oto", "otomatik"), ("nizami", "nizami"), ("orta", "orta kirli"), ("kirli", "kirli")):
            ttk.Radiobutton(sv_, text=m_, value=ad_, variable=esl["seviye"]).pack(side="left", padx=3)
        esl["durum"] = ttk.Label(w, padding=(8, 0, 8, 8), wraplength=570, justify="left", foreground="#555", text=(
            "Harfi bilmiyorsan kutuyu boş bırak: Croow bilinmeyen bir simge atar (‹1›). Sonra o simgeli bir harfe tıklayıp "
            "doğru harfi söylediğinde bütün örnekleri o harf olur (eski yazılar için)."))
        esl["durum"].pack(anchor="w")
        esle_yenile()

    def esle_yenile():
        w = esl.get("pencere")
        if w is None or not w.winfo_exists():
            return
        import collections
        import belge_harf as BH
        for c in esl["ic"].winfo_children():
            c.destroy()
        for n, it in enumerate(esl["liste"]):
            f = ttk.Frame(esl["ic"], padding=3, relief="groove")
            f.grid(row=n // 7, column=n % 7, padx=3, pady=3)
            ad = it["okuma"]
            ttk.Label(f, image=it["foto"]).pack()
            ttk.Label(f, font=("TkDefaultFont", 8), justify="center",
                      text=(f"{BH.simge_goster(ad[0][0])} %{100 * ad[0][1]:.0f}" if ad else "?") + "\n" + it["ad"][:12]).pack()
            for c in (f, *f.winfo_children()):
                c.bind("<Button-1>", lambda e, it=it: (esl["liste"].remove(it), esle_yenile(), bindirme_yenile()))
        oy = collections.Counter()
        for it in esl["liste"]:
            if it["okuma"]:
                oy[it["okuma"][0][0]] += it["okuma"][0][1]
        belge = len({id(it["kap"]) for it in esl["liste"]})
        if oy:
            toplam = sum(oy.values())
            en, ag = oy.most_common(1)[0]
            esl["oy"].configure(text=f"{len(esl['liste'])} harf, {belge} sayfa · Croow'un oyu: " + ", ".join(
                f"{BH.simge_goster(h)} ×{round(a, 1)}" for h, a in oy.most_common(4)))
            if not esl["elle"]:
                esl["harf"].delete(0, "end")
                if ag >= 0.4 * toplam:
                    esl["harf"].insert(0, en)
        else:
            esl["oy"].configure(text="Henüz harf seçilmedi.")

    def esle_temizle():
        esl["liste"].clear()
        esl["elle"] = False
        esle_yenile()
        bindirme_yenile()

    def esle_ogret():
        import belge_harf as BH
        import crw_harf as CH
        if len(esl["liste"]) < 2:
            return esl["durum"].configure(text="En az 2 harf seç (ya da tek harf için doğrudan Harf göster'i kullan).")
        depo = ortak_depo()
        harf = esl["harf"].get().strip()
        yeni_simge = not harf
        if yeni_simge:
            harf = depo.yeni_simge()
        elif not CH.izinli(harf):
            return esl["durum"].configure(text=f"“{harf}” alfabede yok; öğretilemedi.")
        n = 0
        for it in esl["liste"]:
            try:
                sv = esl["seviye"].get()
                BH.elle_ogret(it["kap"], it["kutu"], harf, depo, kaydet=False, seviye=None if sv == "oto" else sv)
                n += 1
            except Exception:  # noqa: BLE001
                pass
        depo.kaydet()
        belge = len({id(it["kap"]) for it in esl["liste"]})
        say = sum(1 for r in depo.gercek.k if r[0] == harf)
        esl["liste"].clear()
        esl["elle"] = False
        gs = durum.get("goster")
        if gs:
            gs["okuma"].clear()
        esle_yenile()
        bindirme_yenile()
        esl["durum"].configure(text=f"Öğrendi: {n} harf, {belge} sayfadan, hepsi “{BH.simge_goster(harf)}” "
                                    f"({'bilinmeyen simge atandı' if yeni_simge else 'adı verilen harf'}). "
                                    f"Depoda “{BH.simge_goster(harf)}” için artık {say} gerçek kök var.")
        bilgi.configure(text=f"Eşleştirme: {n} harf “{BH.simge_goster(harf)}” olarak öğrenildi ({belge} sayfadan)")

    nizami_gecmis = []
    nizami_zaman = [0.0]                                     # nizami yığınına son ekleme zamanı (Ctrl+Z hangisini geri alsın)
    firca = {"yigin": [], "zaman": [], "fs": None}           # fırça (Sil / Çiz) geri alma yığını ve süren darbe

    def firca_oturum():
        """Ekrandaki resim CriCroow7 oturumunun kapsamasıyla AYNI geometrideyse oturum, değilse None."""
        o = durum.get("cri")
        img = durum.get("img")
        if o is None or img is None:
            return None
        try:
            if img.size != (o.kap.shape[1], o.kap.shape[0]):
                return None
            return o if (o.gosterildi or abs(o.aci) < 1e-6) else None
        except Exception:  # noqa: BLE001
            return None

    def firca_cb(olay, ix, iy):
        """Sil / Çiz fırçası. Darbe sürerken görüntü canlı boyanır; bırakınca (1) kapsama haritaları (Harf göster, CriCroow7
        oturumu) eşlenir, (2) silinen/çizilen izin özellikleri öğrenme kaydına eklenir, (3) geri alma yığınına girer."""
        import numpy as np
        from PIL import Image
        import crw_harf as CH
        img = durum.get("img")
        if img is None or img.mode not in ("L", "RGB"):
            if olay == "bas":
                bilgi.configure(text="Bu resim türünde fırça kullanılamıyor (gri ya da RGB resim gerekir).")
            return
        mod = gor.arac.get()
        if olay == "bas":
            gray = img.convert("L")
            mur, kag = CH.seviyeler(gray)
            fark = max(1.0, kag - mur)
            tablo = np.array([0 if (kag - v) * 255 / fark < CH.GURULTU else min(255, int((kag - v) * 255 / fark))
                              for v in range(256)], dtype=np.uint8)
            ref = np.array(img)                                       # darbe başındaki görüntü (kopya)
            if ref.ndim == 2:
                ref = ref[:, :, None]
            kagit = np.percentile(ref[::7, ::7], 85, axis=(0, 1))     # kâğıt rengi (kanal başına)
            murekkep = np.full(ref.shape[2], mur, dtype=np.float32)   # mürekkep tonu
            firca["fs"] = {"img": img, "mod": mod, "ayar": gor.firca_ayar(), "ref": ref, "ref_gri": np.asarray(gray),
                           "tablo": tablo, "A": np.zeros(ref.shape[:2], dtype=np.uint8), "bbox": None, "son": None,
                           "hedef": (kagit if mod == "sil" else murekkep).astype(np.float32), "cur": ref.copy(),
                           "oturum": firca_oturum(), "tur": mod}
        fs = firca.get("fs")
        if fs is None or fs["img"] is not img:
            return
        H, W = fs["ref"].shape[:2]
        r = max(0.5, fs["ayar"]["boyut"] / 2.0)
        sert, saydam = fs["ayar"]["sertlik"], fs["ayar"]["saydamlik"]

        def damga(cx, cy):
            x0, x1 = int(max(0, np.floor(cx - r))), int(min(W, np.ceil(cx + r) + 1))
            y0, y1 = int(max(0, np.floor(cy - r))), int(min(H, np.ceil(cy + r) + 1))
            if x1 <= x0 or y1 <= y0:
                return
            yy, xx = np.mgrid[y0:y1, x0:x1]
            d = np.sqrt((xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2) / r
            al = np.clip((1 - d) / max(1e-3, 1 - sert), 0, 1)
            al[d <= sert] = 1.0
            al[d > 1] = 0.0
            sub = fs["A"][y0:y1, x0:x1]
            np.maximum(sub, (al * 255).astype(np.uint8), out=sub)
            a = (fs["A"][y0:y1, x0:x1].astype(np.float32) / 255.0 * saydam)[:, :, None]
            yeni = fs["ref"][y0:y1, x0:x1].astype(np.float32) * (1 - a) + fs["hedef"] * a
            fs["cur"][y0:y1, x0:x1] = np.clip(yeni.round(), 0, 255).astype(np.uint8)
            parca = fs["cur"][y0:y1, x0:x1]
            img.paste(Image.fromarray(parca[:, :, 0] if parca.shape[2] == 1 else parca), (x0, y0))
            b = fs["bbox"]
            fs["bbox"] = [x0, y0, x1, y1] if b is None else [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]

        if olay in ("bas", "hareket"):
            if fs["son"] is None:
                damga(ix, iy)
            else:
                px, py = fs["son"]
                n = int(max(abs(ix - px), abs(iy - py)) / max(1.0, r / 3)) + 1
                for k in range(1, n + 1):
                    damga(px + (ix - px) * k / n, py + (iy - py) * k / n)
            fs["son"] = (ix, iy)
            resim_yenile()
            return
        # ---- bırakma: eşle, öğren, yığına koy
        firca["fs"] = None
        if fs["bbox"] is None:
            return
        x0, y0, x1, y1 = fs["bbox"]
        maske = fs["A"][y0:y1, x0:x1] > 0
        kap_eski = fs["tablo"][fs["ref_gri"]]
        gri_yeni = np.asarray(img.convert("L"))
        yama_yeni = fs["tablo"][gri_yeni[y0:y1, x0:x1]]
        kap_yeni = kap_eski.copy()
        kap_yeni[y0:y1, x0:x1][maske] = yama_yeni[maske]
        giris = {"img": img, "bbox": (x0, y0, x1, y1), "rgb_eski": Image.fromarray(
            fs["ref"][y0:y1, x0:x1][:, :, 0] if fs["ref"].shape[2] == 1 else fs["ref"][y0:y1, x0:x1]),
            "maske": maske, "kap_eski": kap_eski[y0:y1, x0:x1].copy(), "tur": fs["tur"], "eklenen": 0, "gs": None, "oturum": None}
        gs = durum.get("goster")
        if gs and gs["rgb"] is img:                                    # Harf göster kapsaması
            gp = gs["kap"].crop((x0, y0, x1, y1))
            giris["gs"], giris["gs_eski"] = gs, gp.copy()
            yeni = np.asarray(gp).copy()
            yeni[maske] = yama_yeni[maske]
            gs["kap"].paste(Image.fromarray(yeni), (x0, y0))
            gs["okuma"].clear()
        o = fs["oturum"]
        if o is not None:                                              # CriCroow7 oturumu: sonraki adımlar düzenlemeyi korur
            giris["oturum"], giris["o_eski"] = o, o.kap[y0:y1, x0:x1].copy()
            o.kap[y0:y1, x0:x1][maske] = yama_yeni[maske].astype(np.float32)
            o.kayit["islemler"].append({"islem": "elle düzenleme", "sira": len(o.kayit["islemler"]) + 1, "tur": fs["tur"],
                                        "bolge": [x0, y0, x1 - x0, y1 - y0], "fırça": fs["ayar"]})
            giris["o_kayit"] = len(o.kayit["islemler"]) - 1
        # öğrenme
        import belge_harf as BH
        depo = ortak_depo()
        ol = durum.get("firca_ol")
        if ol is None or ol[0] is not img:
            ol = durum["firca_ol"] = (img,) + BH.satir_olcusu(kap_eski)
        _, bantlar, sb = ol
        ek = ""
        oran = fs["ayar"]["boyut"] / float(sb)
        if fs["tur"] == "sil" and oran >= 2.0:                         # BÜYÜK fırça: bölge temizliği
            kay = BH.bolge_kaydi(kap_eski, kap_yeni, maske, (x0, y0, x1, y1), sb, depo)
            giris["liste"] = "bolge"
            if kay:
                depo.duzenleme["bolge"].append({a_: round(float(b_), 4) for a_, b_ in kay.items()})
                giris["eklenen"] = 1
                ek = (f"BÜYÜK fırça = bölge temizliği öğrenildi (yoğunluk %{100 * kay['yog']:.0f}, büyük izlerin payı "
                      f"%{100 * kay['buyuk']:.0f}, harfe benzeyen %{100 * kay['harf']:.0f}). Toplam {len(depo.duzenleme['bolge'])}/"
                      f"{BH.BOLGE_EN_AZ} örnek.")
            else:
                ek = "Büyük fırça: bu alan yeterince mürekkepli değildi ya da yarısından azı silindi: öğrenme kaydına girmedi."
        elif fs["tur"] == "sil":                                       # KÜÇÜK fırça: yazı içi iz
            kay = BH.leke_kaydi(kap_eski, kap_yeni, (x0, y0, x1, y1), bantlar, sb, depo=depo)
            giris["liste"] = "sil"
            ben = []
            for k_ in kay:
                sab, bo, ho = k_.pop("sab"), k_.pop("benz_once"), k_.pop("harf_once")
                depo.duzenleme["sil"].append({a_: round(float(b_), 4) for a_, b_ in k_.items()})
                depo.duzenleme["leke_sablon"].append(sab)
                if ho:
                    ben.append(f"“{ho}” %{int(100 * bo)}")
            giris["eklenen"] = len(kay)
            giris["sablon"] = len(kay)
            if kay:
                ek = (f"Küçük fırça: {len(kay)} iz leke olarak öğrenildi (harfe yakınsa da). Silmeden önce Croow bunlara "
                      f"{', '.join(ben[:4])} benzetiyordu; artık o şekle benzeyenlerin harf benzerliği düşer. Toplam örnek "
                      f"{len(depo.duzenleme['sil'])}.")
            else:
                ek = "Küçük fırça: bu darbe bütün bir izi silmedi (harf parçası olabilir): öğrenme kaydına girmedi."
        else:
            giris["liste"] = "ciz"
            kay = BH.kopru_kaydi(kap_eski, kap_yeni, (x0, y0, x1, y1), sb)
            if kay:
                depo.duzenleme["ciz"].append({a_: round(float(b_), 4) for a_, b_ in kay.items()})
                giris["eklenen"] = 1
                ek = (f"Köprü öğrenildi (boşluk {kay['bosluk'] * sb:.1f} px). Toplam örnek {len(depo.duzenleme['ciz'])}; "
                      f"{BH.LEKE_EN_AZ}'ten sonra 'Tamamla' bu uzunluktaki boşlukları kapatır.")
            else:
                ek = "Çizim eski mürekkebe bağlanmadı: yeni çizgi sayıldı, öğrenme kaydına girmedi."
        if fs["tur"] == "sil":
            ek += oneri_guncelle(kap_yeni, bantlar, sb)
        izleme_yaz()
        depo.kaydet()
        firca["yigin"].append(giris)
        firca["zaman"].append(time.time())
        gs_ = durum.get("goster")
        bilgi.configure(text=("Silindi. " if fs["tur"] == "sil" else "Çizildi. ") + ek + " (Ctrl+Z geri alır)")

    cri_yigin = []                                           # CriCroow7 adımları öncesi anlık kopyalar (en çok 4)

    def cri_geri():
        o, an, _ = cri_yigin.pop()
        o.anliga_don(an)
        durum["img"] = o.sonuc().convert("RGB")
        resim_yenile()
        bilgi.configure(text="CriCroow7 adımı geri alındı.")

    SINIF_AD = {"leke": "LEKE", "metin": "METİN (yazı)", "cizgi": "ALT ÇİZGİ", "karartma": "KARARTMA / sansür",
                "damga": "DAMGA / mühür", "imza": "İMZA / el yazısı"}

    def izleme_yaz():
        """Croow'un seni izleyerek topladığı örneklerin özeti (araç çubuğunda)."""
        d = ortak_depo().duzenleme
        gor.izleme_et.configure(text=f"Croow izliyor · leke {len(d['sil'])} · bölge {len(d['bolge'])} · köprü {len(d['ciz'])} · "
                                     f"koruma {len(d['korunan_sablon'])} · çizgi {len(d['cizgi'])} · özel {len(d['ozel'])}")

    def oneri_bul(kap, bantlar, sb):
        """SIKI öneriler: öğrenilen leke kuralına uyan ve AYRICA silinmiş izlerin şablonlarından birine en az %60 benzeyen izler
        (en çok 40, benzerliğe göre). Kural için en az 5 silinmiş iz gerekir. -> [(x0, x1, y0, y1, benzerlik)]"""
        import numpy as np
        import belge_harf as BH
        depo = ortak_depo()
        d = depo.duzenleme
        if len(d["sil"]) < 5:
            return []
        kural = BH.leke_kurali(d["sil"][-80:], gevsek=0.0)
        N = BH.leke_sablon_vektorleri(depo)
        if not kural or N is None:
            return []
        bul, et = BH.leke_bul(kap, kural, bantlar, sb, depo=depo)
        out = []
        for x0, x1, y0, y1, i in bul:
            parca = np.where(et[y0:y1, x0:x1] == i, np.asarray(kap)[y0:y1, x0:x1], 0)
            t = np.asarray(BH.iz_sablonu(parca), dtype=np.float32) / 255.0
            t = t - t.mean()
            n = float(np.sqrt((t * t).sum()))
            if n < 1e-6:
                continue
            sim = float((N @ (t / n)).max())
            if sim >= 0.6:
                out.append((x0, x1, y0, y1, sim))
        out.sort(key=lambda r: -r[4])
        return out[:40]

    def oneri_guncelle(kap, bantlar, sb):
        """Öneri kutularını (turuncu) çizer ya da kaldırır. Öneriler varsayılan KAPALI: Croow yalnızca izler."""
        gor.bindir_sil("benzer")
        gor.bindir_sil("ozel")
        durum["oneriler"] = []
        if not gor.oneri_var.get():
            return " (Croow izliyor; öneriler kapalı: araç çubuğundan 'Önerileri göster' ile aç.)"
        on = oneri_bul(kap, bantlar, sb)
        durum["oneriler"] = on
        if on:
            gor.bindir("benzer", [(b[0] - 2, b[2] - 2, b[1] + 2, b[3] + 2, "#ff8800", 2, None, f"%{int(100 * b[4])}") for b in on])
        om = ozel_goster(kap, sb)
        ek = f" Öneri: sildiklerine çok benzeyen {len(on)} iz turuncu (üstünde benzerlik %)." if on else \
            " (öneri yok: en az 5 silinmiş iz ve %60+ benzer iz gerekir)"
        if om:
            ek += f" Mor: açtığın kategorilere benzeyen {om} iz."
        return ek

    def oneri_uygula():
        """Turuncu önerileri siler (tek geri alma adımı). Önerileri sen onaylamış olursun."""
        import numpy as np
        from PIL import Image
        import belge_harf as BH
        import crw_harf as CH
        img = durum.get("img")
        if img is None or img.mode not in ("L", "RGB"):
            return
        gray = img.convert("L")
        mur, kag = CH.seviyeler(gray)
        fark = max(1.0, kag - mur)
        tablo = np.array([0 if (kag - v) * 255 / fark < CH.GURULTU else min(255, int((kag - v) * 255 / fark))
                          for v in range(256)], dtype=np.uint8)
        kap = tablo[np.asarray(gray)]
        ol = durum.get("firca_ol")
        if ol is None or ol[0] is not img:
            ol = durum["firca_ol"] = (img,) + BH.satir_olcusu(kap)
        on = oneri_bul(kap, ol[1], ol[2])
        if not on:
            return bilgi.configure(text="Uygulanacak öneri yok.")
        W, H = img.size
        mask = np.zeros((H, W), dtype=bool)
        for x0, x1, y0, y1, _ in on:
            mask[y0:y1, x0:x1] = kap[y0:y1, x0:x1] > 110
        ys, xs = np.nonzero(mask)
        bx0, bx1, by0, by1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        mk = mask[by0:by1, bx0:bx1]
        arr = np.array(img)
        kagit = np.percentile((arr if arr.ndim == 3 else arr[:, :, None])[::7, ::7], 85, axis=(0, 1))
        eski_rgb = img.crop((bx0, by0, bx1, by1)).copy()
        parca = np.array(img.crop((bx0, by0, bx1, by1)))
        if parca.ndim == 2:
            parca = parca[:, :, None]
        parca[mk] = np.clip(np.round(kagit), 0, 255).astype(np.uint8)
        img.paste(Image.fromarray(parca[:, :, 0] if parca.shape[2] == 1 else parca), (bx0, by0))
        giris = {"img": img, "bbox": (bx0, by0, bx1, by1), "rgb_eski": eski_rgb, "maske": mk, "kap_eski": None, "tur": "etiket",
                 "eklenen": 0, "gs": None, "oturum": None, "listeler": []}
        gs = durum.get("goster")
        if gs and gs["rgb"] is img:
            gp = gs["kap"].crop((bx0, by0, bx1, by1))
            giris["gs"], giris["gs_eski"] = gs, gp.copy()
            yeni = np.asarray(gp).copy()
            yeni[mk] = 0
            gs["kap"].paste(Image.fromarray(yeni), (bx0, by0))
            gs["okuma"].clear()
        o = firca_oturum()
        if o is not None:
            giris["oturum"], giris["o_eski"] = o, o.kap[by0:by1, bx0:bx1].copy()
            o.kap[by0:by1, bx0:bx1][mk] = 0
            o.kayit["islemler"].append({"islem": "elle düzenleme", "sira": len(o.kayit["islemler"]) + 1,
                                        "tur": "önerileri uygula", "bolge": [bx0, by0, bx1 - bx0, by1 - by0]})
            giris["o_kayit"] = len(o.kayit["islemler"]) - 1
        firca["yigin"].append(giris)
        firca["zaman"].append(time.time())
        gor.bindir_sil("benzer")
        durum["oneriler"] = []
        resim_yenile()
        bilgi.configure(text=f"{len(on)} öneri uygulandı (silindi). Ctrl+Z geri alır.")

    def oneri_yanlis(ix, iy):
        """Tıklanan öneri yanlışsa: o izi 'korunan' olarak öğret (bir daha önerilmez). -> True (öneri vardı)"""
        import numpy as np
        import belge_harf as BH
        import crw_harf as CH
        img = durum.get("img")
        for x0, x1, y0, y1, _ in durum.get("oneriler", []):
            if x0 - 3 <= ix <= x1 + 3 and y0 - 3 <= iy <= y1 + 3:
                gray = img.convert("L").crop((x0, y0, x1, y1))
                mur, kag = CH.seviyeler(img.convert("L"))
                fark = max(1.0, kag - mur)
                a = np.clip((kag - np.asarray(gray, dtype=np.float32)) * 255 / fark, 0, 255)
                depo = ortak_depo()
                depo.duzenleme["korunan_sablon"].append(BH.iz_sablonu(a))
                depo.kaydet()
                firca["yigin"].append({"img": img, "bbox": (x0, y0, x1, y1), "rgb_eski": None, "maske": None, "kap_eski": None,
                                       "tur": "etiket", "eklenen": 0, "gs": None, "oturum": None,
                                       "listeler": [("korunan_sablon", 1)]})
                firca["zaman"].append(time.time())
                durum["oneriler"] = [o for o in durum["oneriler"] if o[:4] != (x0, x1, y0, y1)]
                gor.bindir("benzer", [(b[0] - 2, b[2] - 2, b[1] + 2, b[3] + 2, "#ff8800", 2, None, f"%{int(100 * b[4])}")
                                      for b in durum["oneriler"]])
                izleme_yaz()
                bilgi.configure(text="Bu öneri yanlış sayıldı: şekli 'korunan' olarak öğrenildi, bir daha önerilmez. (Ctrl+Z geri alır)")
                return True
        return False

    def ozel_goster(kap, sb):
        """Kullanıcının açtığı kategorilere benzeyen izleri mor çerçeve + 'ad %olasılık' etiketiyle gösterir. -> iz sayısı"""
        import belge_harf as BH
        liste = BH.ozel_bul(kap, ortak_depo(), sb)
        if not liste:
            gor.bindir_sil("ozel")
            return 0
        gor.bindir("ozel", [(r[0] - 2, r[2] - 2, r[1] + 2, r[3] + 2, "#a020f0", 2, None, f"{r[4]} %{int(100 * r[5])}")
                            for r in liste])
        return len(liste)

    def hizli_sec(ix, iy, ekle, ev):
        """Ctrl+tık: tıklanan izi (birleşik mürekkep parçası) seçili bölge yapar, tıkladığın yerde sınıf menüsünü açar.
        Ctrl+Shift+tık: yeni izi mevcut seçime ekler (birleşim)."""
        import numpy as np
        import belge_harf as BH
        import crw_harf as CH
        img = durum.get("img")
        if img is None or img.mode not in ("L", "RGB"):
            return
        gray = img.convert("L")
        mur, kag = CH.seviyeler(gray)
        fark = max(1.0, kag - mur)
        tablo = np.array([0 if (kag - v) * 255 / fark < CH.GURULTU else min(255, int((kag - v) * 255 / fark))
                          for v in range(256)], dtype=np.uint8)
        W, H = img.size
        ol = durum.get("firca_ol")
        sb = ol[2] if (ol is not None and ol[0] is img) else 30
        R = int(max(300, 8 * sb))
        a0, b0, a1, b1 = max(0, int(ix) - R), max(0, int(iy) - R), min(W, int(ix) + R), min(H, int(iy) + R)
        kap = tablo[np.asarray(gray.crop((a0, b0, a1, b1)))]
        et, n, kt, alan = BH.bilesenler(kap > 110)
        cx, cy = int(ix) - a0, int(iy) - b0
        yaricap = max(3, int(0.25 * sb))                                  # ince çizgiyi ıskalamaya karşı tıklama toleransı
        pencere = et[max(0, cy - yaricap):cy + yaricap + 1, max(0, cx - yaricap):cx + yaricap + 1]
        say = np.bincount(pencere[pencere > 0].ravel(), minlength=n + 1) if (pencere > 0).any() else None
        if say is None or say.sum() == 0:
            return bilgi.configure(text="Burada iz yok: Ctrl+tıkı mürekkebin üstüne yap (ince çizgilerde biraz yakınlaştır).")
        i = int(say.argmax())
        comp = (et == i)                                                    # tıklanan izin maskesi (kırpılmış pencerede)
        tam = np.zeros((H, W), dtype=bool)
        tam[b0:b1, a0:a1] = comp
        eski = durum.get("hizli")
        if ekle and eski and eski["img"] is img:                           # Ctrl+Shift+tık: seçime ekle (birleşim)
            tam |= eski["maske"]
        durum["hizli"] = {"img": img, "maske": tam}
        ys, xs = np.nonzero(tam)
        kutu = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        yerel = BH.sekizgen_noktalar(tam[kutu[1]:kutu[3], kutu[0]:kutu[2]])
        poly = [(x + kutu[0], y + kutu[1]) for x, y in yerel] if yerel else None
        if poly:
            poly = [(max(0.0, min(W - 1.0, x)), max(0.0, min(H - 1.0, y))) for x, y in poly]
            yeni = (min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly))
        else:
            yeni = (max(0, kutu[0] - 2), max(0, kutu[1] - 2), min(W, kutu[2] + 2), min(H, kutu[3] + 2))
        gor.bolge_ata(yeni, bildir=True, poly=poly)
        m = tk.Menu(kok, tearoff=0)
        if any(o[0] - 3 <= ix <= o[1] + 3 and o[2] - 3 <= iy <= o[3] + 3 for o in durum.get("oneriler", [])):
            m.add_command(label="✗ Bu öneri YANLIŞ (koru, bir daha önerme)", command=lambda: oneri_yanlis(ix, iy))
            m.add_separator()
        m.add_command(label=f"Seçildi: {yeni[2] - yeni[0]}×{yeni[3] - yeni[1]} px — bu ne?", state="disabled")
        m.add_separator()
        for ad, metin, sil in (("leke", "Leke", False), ("leke", "Leke ve sil", True), ("metin", "Metin (yazı)", False),
                               ("cizgi", "Alt çizgi", False), ("cizgi", "Alt çizgi ve sil", True),
                               ("karartma", "Karartma / sansür", False), ("damga", "Damga / mühür", False),
                               ("imza", "İmza / el yazısı", False), ("diger", "Diğer… (kendi kategorini aç)", False)):
            m.add_command(label=metin, command=lambda ad=ad, sil=sil: gor.sinif_cb(ad, sil))
        m.add_separator()
        m.add_command(label="Yalnızca seç (bir şey öğretme)", command=lambda: None)
        try:
            m.tk_popup(ev.x_root, ev.y_root)
        finally:
            m.grab_release()

    def bolge_sekizgen():
        """'Mürekkebe yapıştır (8 nokta)': seçili bölgedeki (çokgen varsa onun içindeki) mürekkebi saran sıkı sekizgen."""
        import numpy as np
        import belge_harf as BH
        import crw_harf as CH
        img, r = durum.get("img"), durum.get("bolge")
        if img is None or not r:
            return bilgi.configure(text="Önce 'Bölge seç' aracıyla bir yer seç.")
        W, H = img.size
        x0, y0, x1, y1 = (int(max(0, v)) for v in r)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 - x0 < 3 or y1 - y0 < 3:
            return
        gray = img.convert("L")
        mur, kag = CH.seviyeler(gray)
        fark = max(1.0, kag - mur)
        tablo = np.array([0 if (kag - v) * 255 / fark < CH.GURULTU else min(255, int((kag - v) * 255 / fark))
                          for v in range(256)], dtype=np.uint8)
        kap = tablo[np.asarray(gray.crop((x0, y0, x1, y1)))]
        mk = kap > 110
        poly0 = durum.get("bolge_poly")
        if poly0:
            mk &= BH.poligon_maskesi(poly0, x1 - x0, y1 - y0, x0, y0)
        yerel = BH.sekizgen_noktalar(mk)
        if not yerel:
            return bilgi.configure(text="Bölgede mürekkep yok; yapıştırılamadı.")
        poly = [(x + x0, y + y0) for x, y in yerel]
        yeni = (min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly))
        gor.bolge_ata(yeni, bildir=True, poly=poly)
        bilgi.configure(text="8 nokta mürekkebe yapıştı. Noktaları sürükleyebilir, çerçevenin kenarına SAĞ TIKLAYIP yeni nokta "
                             "açabilir, noktaya sağ tıklayıp silebilirsin.")

    def diger_ogret():
        """'Diğer…': kendi kategorini aç. Ad yazılır (ya da var olan seçilir); benzeyenlere ne yapılacağı seçilir."""
        ad_v = tk.StringVar()
        ey_v = tk.StringVar(value="isaretle")
        sonuc = {}
        depo = ortak_depo()
        var = sorted({r["ad"] for r in depo.duzenleme.get("ozel", [])})
        pen = tk.Toplevel(kok)
        pen.title("Yeni kategori")
        pen.transient(kok)
        tk.Label(pen, justify="left", text="Seçtiğin yerin ne olduğunu yaz (Croow bilmiyor, sen adlandırıyorsun):").pack(
            padx=12, pady=(12, 4), anchor="w")
        cb = ttk.Combobox(pen, textvariable=ad_v, values=var, width=36)
        cb.pack(padx=12, anchor="w")
        tk.Label(pen, text="Bu kategoriye benzeyenlere ne yapılsın?").pack(padx=12, pady=(10, 2), anchor="w")
        for v, m in (("isaretle", "Yalnızca işaretle (olasılıkla göster)"), ("sil", "Sil (leke gibi: kuralı da öğrenir)"),
                     ("koru", "Koru (yazı gibi: silme adımları dokunmasın)")):
            tk.Radiobutton(pen, text=m, variable=ey_v, value=v).pack(padx=24, anchor="w")

        def tamam(_e=None):
            if ad_v.get().strip():
                sonuc["ad"], sonuc["ey"] = ad_v.get().strip(), ey_v.get()
                pen.destroy()
        fr = tk.Frame(pen)
        fr.pack(pady=12)
        tk.Button(fr, text="Öğret", command=tamam).pack(side="left", padx=6)
        tk.Button(fr, text="İptal", command=pen.destroy).pack(side="left", padx=6)
        cb.bind("<Return>", tamam)
        cb.focus_set()
        pen.grab_set()
        pen.wait_window()
        if sonuc:
            sinif_ogret("ozel", sonuc["ey"] == "sil", ozel_ad=sonuc["ad"], eylem=sonuc["ey"])

    def sinif_ogret(sinif, sil=False, ozel_ad=None, eylem=None):
        """Seçili bölgedeki izin ne olduğunu öğret: leke / metin / alt çizgi / karartma / damga / imza. Leke ve alt çizgi
        silme kuralına, diğerleri KORUMA şablonlarına girer; 've sil' bölgeyi hemen temizler. Ctrl+Z geri alır."""
        import numpy as np
        from PIL import Image
        import belge_harf as BH
        import crw_harf as CH
        img, r = durum.get("img"), durum.get("bolge")
        if img is None or not r:
            return bilgi.configure(text="Önce 'Bölge seç' aracıyla öğretilecek yeri seç.")
        if img.mode not in ("L", "RGB"):
            return bilgi.configure(text="Bu resim türünde bölge öğretilemiyor.")
        W, H = img.size
        x0, y0, x1, y1 = (int(max(0, v)) for v in r)
        x1, y1 = min(W, x1), min(H, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return bilgi.configure(text="Seçili bölge çok küçük.")
        gray = img.convert("L")
        mur, kag = CH.seviyeler(gray)
        fark = max(1.0, kag - mur)
        tablo = np.array([0 if (kag - v) * 255 / fark < CH.GURULTU else min(255, int((kag - v) * 255 / fark))
                          for v in range(256)], dtype=np.uint8)
        kap = tablo[np.asarray(gray)]
        depo = ortak_depo()
        ol = durum.get("firca_ol")
        if ol is None or ol[0] is not img:
            ol = durum["firca_ol"] = (img,) + BH.satir_olcusu(kap)
        _, bantlar, sb = ol
        pay = int(3 * sb)
        a0, b0, a1, b1 = max(0, x0 - pay), max(0, y0 - pay), min(W, x1 + pay), min(H, y1 + pay)
        crop = kap[b0:b1, a0:a1]
        et, n, kt, alan = BH.bilesenler(crop > 110)
        bolge_m = np.zeros(crop.shape, dtype=bool)
        bolge_m[y0 - b0:y1 - b0, x0 - a0:x1 - a0] = True
        if durum.get("bolge_poly"):                                    # esnek çerçeve: yalnızca çokgenin içi
            bolge_m &= BH.poligon_maskesi(durum["bolge_poly"], crop.shape[1], crop.shape[0], a0, b0)
        mur_ic = np.bincount(et[bolge_m & (crop > 110)].ravel(), minlength=n + 1)
        ids = [i for i in range(1, n + 1) if alan[i] >= 3 and mur_ic[i] >= 0.6 * alan[i]]
        if not ids and sinif != "leke":
            return bilgi.configure(text="Seçili bölgede öğretilecek bir iz yok (bölge boş ya da izler bölge dışına taşıyor).")
        bant_yerel = [(u - b0, a_ - b0) for u, a_ in bantlar]
        oz = BH._ozellikler(et, kt, alan, crop, ids, bant_yerel, sb)
        sabl = []
        for i in ids:
            xx0, xx1, yy0, yy1 = (int(v) for v in kt[i])
            sabl.append(BH.iz_sablonu(np.where(et[yy0:yy1, xx0:xx1] == i, crop[yy0:yy1, xx0:xx1], 0)))
        listeler, ek = [], ""
        d = depo.duzenleme
        if sinif == "leke":
            for f, sb_ in zip(oz, sabl):
                d["sil"].append({a_: round(float(b_), 4) for a_, b_ in f.items()})
                d["leke_sablon"].append(sb_)
            listeler += [("sil", len(oz)), ("leke_sablon", len(sabl))]
            if (x1 - x0) * (y1 - y0) >= (1.5 * sb) ** 2:              # geniş seçim: bölge temizliği örneği de
                sonra = kap.copy()
                sonra[y0:y1, x0:x1] = 0
                kay = BH.bolge_kaydi(kap, sonra, bolge_m[y0 - b0:y1 - b0, x0 - a0:x1 - a0], (x0, y0, x1, y1), sb, depo)
                if kay:
                    d["bolge"].append({a_: round(float(b_), 4) for a_, b_ in kay.items()})
                    listeler.append(("bolge", 1))
                    ek = " Geniş alan olduğu için bölge temizliği örneği de eklendi."
        elif sinif == "cizgi":
            for f in oz:
                d["cizgi"].append({a_: round(float(b_), 4) for a_, b_ in f.items()})
            listeler.append(("cizgi", len(oz)))
        elif sinif == "ozel":                                           # kullanıcının açtığı kategori
            for f, sb_ in zip(oz, sabl):
                d["ozel"].append({"ad": ozel_ad, "eylem": eylem, "alan": round(float(f["alan"]), 4), "sab": sb_})
            listeler.append(("ozel", len(sabl)))
            if eylem == "koru":
                for sb_ in sabl:
                    d["korunan_sablon"].append(sb_)
                listeler.append(("korunan_sablon", len(sabl)))
                ek = " 'Koru' seçildi: bu şekle benzeyenlere silme adımları dokunmaz."
            elif eylem == "sil":
                for f, sb_ in zip(oz, sabl):
                    d["sil"].append({a_: round(float(b_), 4) for a_, b_ in f.items()})
                    d["leke_sablon"].append(sb_)
                listeler += [("sil", len(oz)), ("leke_sablon", len(sabl))]
                ek = " 'Sil' seçildi: leke kuralına da eklendi."
        else:                                                           # metin / karartma / damga / imza: KORUNUR
            for f, sb_ in zip(oz, sabl):
                d["korunan_sablon"].append(sb_)
                d["sinif"].append({"sinif": sinif, **{a_: round(float(b_), 4) for a_, b_ in f.items()}})
            listeler += [("korunan_sablon", len(sabl)), ("sinif", len(oz))]
            ek = " Bu şekle ve benzerlerine artık hiçbir silme adımı dokunmaz."
        giris = {"img": img, "bbox": (x0, y0, x1, y1), "rgb_eski": None, "maske": None, "kap_eski": None, "tur": "etiket",
                 "eklenen": 0, "gs": None, "oturum": None, "listeler": listeler}
        sil_not = ""
        if sil and sinif in ("leke", "cizgi", "ozel"):                  # hemen temizle
            if sinif in ("leke", "ozel"):
                hedef = bolge_m & (crop > 20)                          # seçili alanın bütün mürekkebi
            else:
                hedef = np.isin(et, ids) & bolge_m
            if hedef.any():
                ys, xs = np.nonzero(hedef)
                bx0, bx1, by0, by1 = xs.min() + a0, xs.max() + a0 + 1, ys.min() + b0, ys.max() + b0 + 1
                mk = hedef[by0 - b0:by1 - b0, bx0 - a0:bx1 - a0]
                arr = np.array(img)
                kagit = np.percentile((arr if arr.ndim == 3 else arr[:, :, None])[::7, ::7], 85, axis=(0, 1))
                eski_rgb = img.crop((bx0, by0, bx1, by1)).copy()
                parca = np.array(img.crop((bx0, by0, bx1, by1)))
                if parca.ndim == 2:
                    parca = parca[:, :, None]
                parca[mk] = np.clip(np.round(kagit), 0, 255).astype(np.uint8)
                img.paste(Image.fromarray(parca[:, :, 0] if parca.shape[2] == 1 else parca), (bx0, by0))
                giris.update(bbox=(bx0, by0, bx1, by1), rgb_eski=eski_rgb)
                gs = durum.get("goster")
                if gs and gs["rgb"] is img:
                    gp = gs["kap"].crop((bx0, by0, bx1, by1))
                    giris["gs"], giris["gs_eski"] = gs, gp.copy()
                    yeni = np.asarray(gp).copy()
                    yeni[mk] = 0
                    gs["kap"].paste(Image.fromarray(yeni), (bx0, by0))
                    gs["okuma"].clear()
                o = firca_oturum()
                if o is not None:
                    giris["oturum"], giris["o_eski"] = o, o.kap[by0:by1, bx0:bx1].copy()
                    o.kap[by0:by1, bx0:bx1][mk] = 0
                    o.kayit["islemler"].append({"islem": "elle düzenleme", "sira": len(o.kayit["islemler"]) + 1,
                                                "tur": "sınıf: " + sinif, "bolge": [int(bx0), int(by0), int(bx1 - bx0), int(by1 - by0)]})
                    giris["o_kayit"] = len(o.kayit["islemler"]) - 1
                sil_not = " Bölge temizlendi."
        kap_yeni = kap
        ek += oneri_guncelle(kap_yeni, bantlar, sb)
        izleme_yaz()
        depo.kaydet()
        firca["yigin"].append(giris)
        firca["zaman"].append(time.time())
        if sil_not:                                                     # "… ve sil" sonrası çerçeve kaybolur
            durum["hizli"] = None
            gor.bolge_ata(None, bildir=True)
        resim_yenile()
        bilgi.configure(text=f"Seçilen {len(ids)} iz “{ozel_ad if sinif == 'ozel' else SINIF_AD[sinif]}” olarak öğrenildi.{ek}{sil_not} "
                             "(Ctrl+Z geri alır)")

    def firca_geri():
        """Son fırça darbesini geri alır (görüntü, kapsama haritaları, öğrenme kaydı)."""
        import numpy as np
        from PIL import Image
        g = firca["yigin"].pop()
        firca["zaman"].pop()
        img = g["img"]
        x0, y0, x1, y1 = g["bbox"]
        if g.get("rgb_eski") is not None and durum.get("img") is img:
            img.paste(g["rgb_eski"], (x0, y0))
        if g["gs"] is not None:
            g["gs"]["kap"].paste(g["gs_eski"], (x0, y0))
            g["gs"]["okuma"].clear()
        if g["oturum"] is not None:
            o = g["oturum"]
            o.kap[y0:y1, x0:x1] = g["o_eski"]
            if len(o.kayit["islemler"]) > g.get("o_kayit", 10 ** 9):
                o.kayit["islemler"].pop(g["o_kayit"])
        depo = ortak_depo()
        for ad_, n_ in g.get("listeler", []):                     # etiketle öğretilenler: eklenen kayıtlar silinir
            for _ in range(n_):
                if depo.duzenleme.get(ad_):
                    depo.duzenleme[ad_].pop()
        liste = depo.duzenleme[g.get("liste") or ("sil" if g["tur"] == "sil" else "ciz")]
        for _ in range(g["eklenen"]):
            if liste:
                liste.pop()
        for _ in range(g.get("sablon", 0)):
            if depo.duzenleme["leke_sablon"]:
                depo.duzenleme["leke_sablon"].pop()
        depo.kaydet()
        gor.bindir_sil("benzer")
        resim_yenile()
        bilgi.configure(text="Fırça darbesi geri alındı (öğrenme kaydı da silindi).")


    def nizami_uygula(kutu, harf):
        """Onaylanan harfi o konumda nizami hâle getirir (kapsama + görüntü), geri alınabilir. -> kısa bilgi ya da None"""
        import numpy as np
        import belge_harf as BH
        from PIL import Image
        gs = durum.get("goster")
        if not gs:
            return None
        try:
            r = BH.nizami_yap(gs["kap"], kutu, harf, gs["depo"])
        except Exception:  # noqa: BLE001
            return None
        if r is None:
            return "zaten temiz"
        eski, yeni, bil = r
        if yeni is None:
            return f"dokunulmadı (koruyucu: {bil['neden']})"
        x0, x1, y0, y1 = kutu[0], kutu[1], kutu[2], kutu[3]
        rgb_eski = gs["rgb"].crop((x0, y0, x1, y1)).copy()
        nizami_gecmis.append((gs, kutu, Image.fromarray(eski.astype(np.uint8)), rgb_eski))
        nizami_zaman[0] = time.time()
        gs["kap"].paste(Image.fromarray(yeni.astype(np.uint8)), (x0, y0))
        g = np.asarray(rgb_eski, dtype=np.float32)
        mürek = 255.0 - g.mean(2)
        oran = float(mürek.sum()) / max(1.0, float(eski.sum()))
        yeni_g = np.clip(255.0 - yeni * max(0.3, min(1.5, oran)), 0, 255)
        out = np.stack([yeni_g] * 3, 2).astype(np.uint8)
        gs["rgb"].paste(Image.fromarray(out), (x0, y0))
        resim_yenile()
        bindirme_yenile()
        return f"{bil['yontem']} (oturma %{100 * bil['oturma']:.0f})"

    def nizami_geri(olay=None):
        son = max([firca["zaman"][-1] if firca["yigin"] else 0.0, nizami_zaman[0] if nizami_gecmis else 0.0,
                   cri_yigin[-1][2] if cri_yigin else 0.0])
        if cri_yigin and cri_yigin[-1][2] >= son:                # en son yapılan CriCroow7 adımıysa onu geri al
            return cri_geri()
        if firca["yigin"] and (not nizami_gecmis or firca["zaman"][-1] >= nizami_zaman[0]):
            return firca_geri()
        if not nizami_gecmis:
            return
        gs, kutu, kap_p, rgb_p = nizami_gecmis.pop()
        if durum.get("goster") is not gs:
            return
        gs["kap"].paste(kap_p, (kutu[0], kutu[2]))
        gs["rgb"].paste(rgb_p, (kutu[0], kutu[2]))
        while nizami_gecmis and nizami_gecmis[-1][0] is gs and nizami_gecmis[-1][1] == kutu:   # aynı onayın ikinci adımı
            _, _, kap_p, rgb_p = nizami_gecmis.pop()
            gs["kap"].paste(kap_p, (kutu[0], kutu[2]))
            gs["rgb"].paste(rgb_p, (kutu[0], kutu[2]))
        gs["okuma"].clear()
        resim_yenile()
        bindirme_yenile()
        bilgi.configure(text="Nizami dönüşüm geri alındı.")

    def kutu_ayari_yay(ay):
        """Öğrenilen kutu ayarını, henüz onaylanmamış kutulara hemen uygular (sayfa yeniden taranmadan)."""
        import belge_harf as BH
        gs = durum.get("goster")
        if not gs:
            return
        onayli, yeni_liste, say = gs.get("onayli", set()), [], 0
        for k in gs["kutular"]:
            h = gs["ham"].get(k)
            if k in onayli or not h:
                yeni_liste.append(k)
                continue
            n = BH.kutu_ayarla(h, ay, gs["kap"].width, gs["kap"].height)
            if n != k:
                gs["ham"][n] = gs["ham"].pop(k)
                say += 1
            yeni_liste.append(n)
        sec = kp.get("secili_kutu")
        gs["kutular"][:] = yeni_liste
        if say:
            gs["okuma"].clear()
            gs["kelimeler"] = BH.kelime_kutulari(gs["kutular"], gs["adim"]) if gs["kutular"] else []
            bilgi.configure(text=f"Kutu ayarı öğrenildi: sol {ay[0]:+.2f}, sağ {ay[1]:+.2f}, üst {ay[2]:+.2f}, alt {ay[3]:+.2f} "
                                 f"→ onaylanmamış {say} kutuya hemen uygulandı.")
            bindirme_yenile()

    kok.bind("<Control-z>", nizami_geri)
    kok.bind("<Control-Right>", lambda e: kelime_gec(1))
    kok.bind("<Control-Left>", lambda e: kelime_gec(-1))

    SERI_HEDEF = 10

    def seri_tamam():
        """Üst üste SERI_HEDEF doğru: Croow sayfayı okumayı dener; yanlışsa kullanıcı doğru cümleleri yazar, öğrenir."""
        import belge_harf as BH
        import crw_harf as CH
        if not messagebox.askyesno("Croow MultiReader",
                                   f"Croow harfleri ve kelimeleri üst üste {SERI_HEDEF} kez doğru bildi.\n\nŞimdi bütün sayfayı (ya da seçili bölgeyi) "
                                   "okumayı denesin mi?\nYanlışları sen düzeltirsin, o da cümlelerden öğrenir."):
            return
        img, _ = bolge_kirp(durum["asil_img"])

        def is_(il):
            il(0, "Sayfa şimdiye kadar öğrendiğiyle okunuyor…")
            P = CH.Palet()
            return BH.oku(img, ortak_depo(), P if P.k else None)

        def bitti(yazi):
            pen = tk.Toplevel(kok)
            pen.title("Croow'un okuması — yanlışları düzelt")
            tk.Label(pen, justify="left", text="Croow sayfayı böyle okudu. YANLIŞ yerleri doğrusuyla değiştir (satır sayısını "
                     "ve sırasını bozma;\nokunamayan satırı silebilirsin). 'Doğrusunu öğret' düzeltilmiş metinden bütün sayfayı öğrenir.").pack(
                padx=10, pady=(10, 4), anchor="w")
            kutu_ = tk.Text(pen, width=100, height=26, wrap="none", font=("DejaVu Sans Mono", 10))
            kutu_.pack(padx=10, pady=4, fill="both", expand=True)
            kutu_.insert("1.0", yazi)
            alt_ = ttk.Frame(pen)
            alt_.pack(pady=(4, 10))

            def ogret_():
                metin_ = kutu_.get("1.0", "end").strip()
                pen.destroy()
                if not metin_:
                    return

                def b2(r):
                    bilgi.configure(text=f"Doğru metinden öğrenildi: {r['eslesen_satir']}/{r['metin_satiri']} satır eşleşti, "
                                         f"{r['gercek_harf']:,} gerçek harf örneği eklendi. 'Harf göster' ile devam edebilirsin.")
                arka_plan(lambda il: BH.ogret(img, metin_, ortak_depo(), ilerleme=il), b2)
            ttk.Button(alt_, text="Doğrusunu öğret", command=ogret_).pack(side="left", padx=6)
            ttk.Button(alt_, text="Doğruymuş, kapat", command=pen.destroy).pack(side="left", padx=6)
        arka_plan(is_, bitti)

    def coklu_ogret(metin, kutu):
        """Genişletilmiş kutu birden çok harf içeriyor: yazılan metin kadar kutuya böler, her harfi öğretir."""
        import belge_harf as BH
        gs = durum.get("goster")
        harfler = [c for c in metin if not c.isspace()]
        n = len(harfler)
        parcalar = BH.bolgeyi_kutulara(gs["kap"], (kutu[0], kutu[2], kutu[1], kutu[3]), n)
        if len(parcalar) != n:
            msg = f"Kutu {n} harfe bölünemedi (bulunan parça: {len(parcalar)}). Kutuyu harflere göre ayarlayıp tekrar dene."
            kp["harf_durum"].configure(text=msg)
            return bilgi.configure(text=msg)
        yeni = [(a_[0], a_[1], a_[2], a_[3], kutu[4], kutu[5]) for a_ in parcalar]
        sv = kp["seviye"].get()
        say = 0
        for k_, h_ in zip(yeni, harfler):
            if not CH_izinli(h_):
                continue
            BH.elle_ogret(gs["kap"], k_, h_, gs["depo"], kaydet=False, seviye=None if sv == "oto" else sv)
            say += 1
        i = gs["kutular"].index(kutu)
        gs["kutular"][i:i + 1] = yeni
        gs["ham"].pop(kutu, None)
        for k_ in yeni:
            gs["ham"][k_] = None
            gs.setdefault("onayli", set()).add(k_)
        gs["depo"].kutu_olayi("bolundu")
        gs["depo"].kaydet()
        nz = sum(1 for k_, h_ in zip(yeni, harfler) if kp["nizami"].get() and nizami_uygula(k_, h_) not in (None, "zaten temiz"))
        gs["say"] += say
        kutular_yenile(yeni[0])
        msg = (f"“{metin}” {n} harfe bölündü ve öğretildi (nizami yapılan: {nz}). Yanlış bölündüyse kutuları tek tek "
               "ayarla.")
        bilgi.configure(text=msg)
        kp["harf_durum"].configure(text=msg)

    def CH_izinli(c):
        import crw_harf as CH
        return CH.izinli(c)

    def harf_cevap(harf):
        """None: Croow doğru söyledi. Metin: doğru harf (düzeltme). Her ikisi de bir GERÇEK örnek olarak öğrenilir."""
        gs, kutu = durum.get("goster"), kp.get("secili_kutu")
        if not gs or not kutu:
            return
        import belge_harf as BH
        import crw_harf as CH
        dogru = kp.get("tahmin") if harf is None else harf
        if not dogru:
            return kp["harf_durum"].configure(text="Doğru harfi yuvaya yaz.")
        if not CH.izinli(dogru):
            return kp["harf_durum"].configure(text=f"“{dogru}” alfabede yok; öğretilemedi.")
        if len(dogru) > 1 and dogru not in CH.DEGEN and dogru not in CH.LIGATUR.values() and not CH.simge_mi(dogru):
            return coklu_ogret(dogru, kutu)
        tahmin = kp.get("tahmin")
        if CH.simge_mi(tahmin) and dogru != tahmin:              # bilinmeyen simgeye ad verildi: bütün örnekleri o harfe katılır
            ta = gs["depo"].etiket_birlestir(tahmin, dogru)
            if ta:
                kp["harf_durum"].configure(text=f"“{BH.simge_goster(tahmin)}” simgesinin {ta} örneği “{dogru}” oldu.")
        pt = poly_uygula(kutu) if kp["esnek"].get() else None    # esnek çerçeve varsa dışı temizlenir, harf yalnızca içinden öğrenilir
        try:
            sv = kp["seviye"].get()
            n = BH.elle_ogret(gs["kap"], kutu, dogru, gs["depo"], kaydet=False, seviye=None if sv == "oto" else sv)
        except Exception as ex:  # noqa: BLE001
            return kp["harf_durum"].configure(text=f"Öğretilemedi: {ex}")
        ham_k = gs["ham"].get(kutu)
        ay0 = gs["depo"].kutu_ayari()
        if ham_k:                                                # Croow'un kutusu ile onaylanan kutu: konum öğrenilir
            gs["depo"].kutu_duzelt_kaydet(ham_k, kutu)
        gs["depo"].kaydet()
        ay1 = gs["depo"].kutu_ayari()
        if ay1 and ay1 != ay0:
            bilgi.configure(text="Kutu ayarı öğrenildi: sol %+.2f, sağ %+.2f, üst %+.2f, alt %+.2f (satır boyuna oranla). "
                                 "Yeni sayfalarda otomatik uygulanır." % tuple(ay1))
        gs["okuma"].clear()
        gs["say"] += 1
        nz = nizami_uygula(kutu, dogru) if kp["nizami"].get() else None
        if pt:
            nz = (nz + " · " if nz else "") + pt
        gs.setdefault("onayli", set()).add(kutu)
        if ay1 and ay1 != ay0:
            kutu_ayari_yay(ay1)
        if ortak.get("asama", "harf") == "harf":                 # aşama 1: harfler
            ortak["seri"] = ortak.get("seri", 0) + 1 if dogru == tahmin else 0
        sonuc = "doğruydu" if dogru == tahmin else f"düzeltildi (Croow “{tahmin or '?'}” demişti)"
        if ortak.get("asama", "harf") == "harf" and ortak["seri"] >= SERI_HEDEF:
            ortak["asama"], ortak["seri"] = "kelime", 0
            kok.after(50, lambda: messagebox.showinfo(
                "Croow MultiReader", f"Harfleri üst üste {SERI_HEDEF} kez doğru bildi: HARF aşaması tamam.\n\n"
                "Şimdi KELİME aşaması: bir harfe tıkla, yan paneldeki kelime çözücüde Croow'un okuduğu kelimeye bak.\n"
                "Doğruysa 'Kelime doğru', yanlışsa doğru kelimeyi yuvalara yazıp 'Yazdığımı öğret'.\n"
                f"Kelimeleri de {SERI_HEDEF} kez üst üste doğru bilince bütün metni okumayı deneyecek."))
        if not (ay1 and ay1 != ay0):
            nk = len(gs["depo"].kutu_duz)
            bilgi.configure(text=f"“{BH.simge_goster(dogru)}” öğrenildi ({sonuc}) · depoda “{BH.simge_goster(dogru)}” için {n} gerçek örnek · "
                                 f"bu oturumda {gs['say']} harf öğretildi · kutu konumu örneği: {nk}"
                                 + (" (kutu ayarı için en az 3 gerek)" if nk < 3 else "")
                                 + (f" · nizami: {nz}" if nz else "")
                                 + (f" · harf aşaması: üst üste doğru {ortak['seri']}/{SERI_HEDEF}"
                                    if ortak.get("asama", "harf") == "harf" else ""))
        if "kutular" in kp and "tum_kutular" in kp:              # kelime çözücünün okuması yenilensin (yuvalar korunur)
            w = kp["tum_kutular"]
            okuma = panel_ham(w)
            a, b = BH.noktalama_kirp(w, okuma)
            if a < b:
                kp["kutular"], kp["okuma"] = w[a:b], okuma[a:b]
                kp["okundu"].configure(text="Croow okudu: " + "".join(c[0][0] if c else "?" for c in okuma[a:b]))
                panel_yenile()
        if kp["ilerle"].get():                                   # aynı satırdaki sonraki harf kutusu
            ks = gs["kutular"]
            i = ks.index(kutu)
            if i + 1 < len(ks) and ks[i + 1][4] == kutu[4]:
                return sec_kutu(ks[i + 1])
        sec_kutu(kutu)                                           # kalındığı yerde yeni tahmini göster
        kp["harf_durum"].configure(text=f"“{dogru}” öğrenildi ({sonuc}). Şimdi Croow bu harfe “{kp.get('tahmin') or '?'}” diyor.")

    def panel_ogret(tur):
        import belge_harf as BH
        import crw_harf as CH
        gs = durum.get("goster")
        if not gs or "kutular" not in kp:
            return
        if kp.get("mesgul"):
            return kp["durum"].configure(text="Sayfa yeniden okunuyor; bitince tekrar dene.")
        okunan = "".join(c[0][0] if c else "?" for c in kp.get("okuma", []))
        if tur == "dogru":                                        # Croow'un okuması doğru
            if "?" in okunan or not okunan:
                return kp["durum"].configure(text="Okumada bilinmeyen harf var; doğrusunu yuvalara yazıp 'Yazdığımı öğret'.")
            tur, harfler = "yazilan", list(okunan)
            for v_, h_ in zip(kp["yuva_v"], harfler):
                v_.set(h_)
        if tur == "yazilan":
            harfler = [v.get().strip() for v in kp["yuva_v"]]
            if not all(harfler):
                return kp["durum"].configure(text="Yazdığımı öğretmek için bütün yuvalar dolu olmalı.")
            kelime = "".join(harfler)
        else:
            sec = kp["liste"].curselection()
            adaylar = kp.get("sonuc", {}).get("aday", [])
            if not sec or sec[0] >= len(adaylar):
                return kp["durum"].configure(text="Önce listeden bir aday seç.")
            kelime = BH.kasa_uyarla(adaylar[sec[0]][0], kp["okuma"])   # sayfanın büyük/küçük harf düzenine
        if not CH.izinli(kelime.replace("'", "")):
            return kp["durum"].configure(text=f"“{kelime}” alfabede olmayan harf içeriyor.")
        kelime_dogru = kelime.lower().replace("'", "") == okunan.lower()
        n = BH.kelime_ogret(gs["kap"], kp["kutular"], kelime, gs["depo"], gs["adim"], kp.get("onceki"), kp.get("sonraki"))
        gs["okuma"].clear()                                   # öğrenilenlerle okumalar eskidi
        seri_not = ""
        if ortak.get("asama", "harf") == "kelime":            # aşama 2: kelimeler
            ortak["seri"] = ortak.get("seri", 0) + 1 if kelime_dogru else 0
            seri_not = f" Kelime aşaması: üst üste doğru {ortak['seri']}/{SERI_HEDEF}."
            if ortak["seri"] >= SERI_HEDEF:
                ortak["asama"], ortak["seri"] = "metin", 0
                kok.after(50, seri_tamam)                     # aşama 3: bütün metin
        sec_no = kp.get("kelime_no")
        kp.pop("kelime_no", None)
        gs["say"] += 1
        for k_ in kp["kutular"]:
            gs.setdefault("onayli", set()).add(k_)
        gs["depo"].kaydet()
        gec = (gs["kelimeler"][sec_no + 1][0] if sec_no is not None and sec_no + 1 < len(gs["kelimeler"]) else None)
        bilgi.configure(text=f"“{kelime}” öğrenildi ({n} harf kutusundan, sözlüğe eklendi).{seri_not} "
                             "Sayfa yeniden okunmadı; istediğinde 'Sayfayı oku'ya bas.")
        if gec is not None:                                    # sonraki kelimeye geç (sayfayı yeniden okumadan)
            sec_kutu(gec)
            kp["durum"].configure(text=f"“{kelime}” öğrenildi.{seri_not} Şimdi sıradaki kelime.")
        else:
            kp["durum"].configure(text=f"“{kelime}” öğrenildi.{seri_not}")

    def panel_sayfa_oku():
        """Sayfayı BAŞTAN, şimdiye kadar öğrenilenlerle okur (kelime öğretirken otomatik okunmaz)."""
        import belge_harf as BH
        import crw_harf as CH
        gs = durum.get("goster")
        if not gs or "cerceve" not in kp:
            return
        if kp.get("mesgul"):
            return kp["durum"].configure(text="Sayfa zaten okunuyor; bitince tekrar dene.")
        kp["mesgul"] = True
        P = CH.Palet()
        img, _ = bolge_kirp(durum["asil_img"])

        def is_(il):
            il(0.1, "Sayfa baştan okunuyor (öğrendiklerinle)…")
            return BH.oku(img, gs["depo"], P if P.k else None)

        def bitti(metin_):
            kp["mesgul"] = False
            if "cerceve" not in kp:
                return
            kp["sayfa"].delete("1.0", "end")
            kp["sayfa"].insert("end", metin_)
            durum["pdf_metin"] = metin_
            kp["durum"].configure(text="Sayfa baştan okundu (aşağıdaki kutuda).")
        arka_plan(is_, bitti)
    gor.tikla_cb = gor_tikla
    gor.firca_cb = firca_cb
    gor.hizli_cb = hizli_sec
    gor.oneri_uygula_cb = oneri_uygula
    kok.after(300, izleme_yaz)
    gor.sekizgen_cb = bolge_sekizgen
    gor.bolge_poly_cb = lambda p: durum.__setitem__("bolge_poly", p)
    gor.sinif_cb = lambda ad, sil: diger_ogret() if ad == "diger" else sinif_ogret(ad, sil)
    gor.bolge_islem_cb = lambda ic: cri_adim("bolge_ic" if ic else "bolge_dis")
    gor.esle_cb = esle_tikla
    gor.arac_cb = esle_arac
    gor.bolge_cb = bolge_secildi
    gor.duzenle_cb = kutu_duzenlendi
    gor.yeni_kutu_cb = kutu_ekle
    gor.sil_cb = kutu_sil

    # ---- "Bu budur": bölge seç, tek harf ya da kelime olarak öğret (nizami / orta / kirli örnek olarak)
    def bu_budur():
        b = durum.get("bolge")
        if durum.get("img") is None or not b:
            return messagebox.showinfo("Bu budur", "Önce üstteki araç çubuğundan 'Bölge seç'i seç ve bir harfin ya da kelimenin "
                                                   "etrafına dikdörtgen çiz; sonra 'Bu budur…'a bas.")
        import numpy as np
        from PIL import Image
        import belge_harf as BH
        import crw_harf as CH
        x0, y0, x1, y1 = (int(v) for v in b)
        kes = durum["img"].crop((x0, y0, x1, y1)).convert("RGB")
        o = min(1.0, 260 / kes.width, 110 / kes.height)
        onizle = kes.resize((max(1, int(kes.width * o)), max(1, int(kes.height * o))))
        pen = tk.Toplevel(kok)
        pen.title("Bu budur")
        pen.transient(kok)
        import io
        tp = io.BytesIO()
        onizle.save(tp, format="PPM")
        pen._foto = tk.PhotoImage(data=tp.getvalue())
        ttk.Label(pen, image=pen._foto).pack(padx=10, pady=(10, 4))
        ttk.Label(pen, wraplength=300, justify="left", text="Seçtiğin parça nedir? Tek harf ya da bir kelime yaz. "
                  "Kelimede her harf kendi kutusundan öğrenilir (önce 'Harf göster ve öğret' çalışmış olmalı).").pack(padx=10)
        giris = tk.Entry(pen, width=24, font=("DejaVu Sans Mono", 14), relief="solid", bd=1)
        giris.pack(padx=10, pady=6)
        giris.focus_set()
        sv = tk.StringVar(value="oto")
        sf = ttk.Frame(pen)
        sf.pack(padx=10)
        ttk.Label(sf, text="Bu örnek:").pack(side="left")
        for ad_, m_ in (("oto", "otomatik"), ("nizami", "nizami (temiz)"), ("orta", "orta kirli"), ("kirli", "kirli")):
            ttk.Radiobutton(sf, text=m_, value=ad_, variable=sv).pack(side="left", padx=2)
        durum_et = ttk.Label(pen, text="", wraplength=300, foreground="#555", justify="left")
        durum_et.pack(padx=10, pady=(6, 0))

        def tamam():
            metin_ = giris.get().strip()
            if not metin_:
                return durum_et.configure(text="Bir harf ya da kelime yaz.")
            for c in metin_:
                if not CH.izinli(c):
                    return durum_et.configure(text=f"“{c}” alfabede yok; öğretilemedi.")
            depo = ortak_depo()
            gs = durum.get("goster")
            gst = bool(gs and durum.get("img") is gs["rgb"])
            seviye = None if sv.get() == "oto" else sv.get()
            try:
                if len(metin_) == 1:                                  # tek harf: seçim sıkı kutuya çevrilir
                    kap = gs["kap"] if gst else CH.kapsama(durum["img"].convert("L"))
                    a = np.asarray(kap.crop((x0, y0, x1, y1)), dtype=np.float32) > 80
                    if a.sum() < 4:
                        return durum_et.configure(text="Seçilen bölgede mürekkep yok.")
                    ys, xs = np.nonzero(a)
                    tx0, tx1, ty0, ty1 = x0 + int(xs.min()), x0 + int(xs.max()) + 1, y0 + int(ys.min()), y0 + int(ys.max()) + 1
                    ust, alt = ty0, ty1
                    if gst and gs["kutular"]:                        # satır bandı: en yakın satır
                        cy = (ty0 + ty1) / 2
                        ust, alt = min(sorted({(k[4], k[5]) for k in gs["kutular"]}),
                                       key=lambda s_: 0 if s_[0] <= cy <= s_[1] else min(abs(cy - s_[0]), abs(cy - s_[1])))
                    BH.elle_ogret(kap, (tx0, tx1, ty0, ty1, ust, alt), metin_, depo, seviye=seviye)
                    n = 1
                else:                                                # kelime: seçimdeki harf kutuları sırayla
                    if not gst:
                        return durum_et.configure(text="Kelime için önce 'Harf göster ve öğret'i çalıştır; harf kutuları gerek.")
                    ks = sorted((k for k in gs["kutular"]
                                 if x0 <= (k[0] + k[1]) / 2 <= x1 and y0 <= (k[2] + k[3]) / 2 <= y1), key=lambda k: k[0])
                    if not ks:
                        return durum_et.configure(text="Seçimde harf kutusu yok.")
                    n = BH.kelime_ogret(gs["kap"], ks, metin_, depo, gs["adim"], seviye=seviye)
                    gs["okuma"].clear()
            except Exception as ex:  # noqa: BLE001
                return durum_et.configure(text=f"Öğretilemedi: {ex}")
            depo.kaydet()
            ozet = {c: depo.varyant_ozet(c) for c in dict.fromkeys(metin_)}
            bilgi.configure(text=f"“{metin_}” öğrenildi ({n} harf, seviye: {sv.get()}). "
                                 + " · ".join(f"{c}: {o_}" for c, o_ in list(ozet.items())[:3]))
            pen.destroy()
        ttk.Button(pen, text="Öğret", command=tamam).pack(side="left", padx=(10, 4), pady=10)
        ttk.Button(pen, text="İptal", command=pen.destroy).pack(side="left", pady=10)
        giris.bind("<Return>", lambda e: tamam())
    gor.bu_budur_cb = bu_budur

    def pdf_sayfa_resim(pdf):
        """PDF sayfasını 300 DPI resim olarak açar: harf göstermek ve CriCroow7 için."""
        import pdf_motor
        try:
            n = pdf_motor.sayfa_sayisi(pdf)
        except Exception as ex:  # noqa: BLE001
            return messagebox.showerror("Croow MultiReader", f"PDF açılamadı:\n{ex}")
        k = 1 if n == 1 else simpledialog.askinteger("Sayfa", f"Hangi sayfa? (1–{n})", parent=kok, minvalue=1, maxvalue=n)
        if not k:
            return
        import crw_harf as CH
        klasor = os.path.join(CH.VERI, "sayfalar")
        os.makedirs(klasor, exist_ok=True)
        hedef = os.path.join(klasor, f"{os.path.splitext(os.path.basename(pdf))[0]}_s{k}.png")

        def is_(il):
            il(0, f"Sayfa {k} resme çevriliyor (300 DPI)…")
            img = pdf_motor.ciz(pdf, k, 300)
            if img is None:
                raise RuntimeError("sayfa çizilemedi")
            img.save(hedef)
            return hedef
        arka_plan(is_, lambda y: ac(y))

    def pdf_resim_ac(yol):
        """PDF'i sayfa RESMİ olarak açar (her sayfa kendi sekmesinde, 300 DPI): resimlerdeki bütün araçlar (Harf göster,
        CriCroow7, bölge seçimi) çalışır. PDF'in metne çevrilmesi Araçlar → 'PDF'i metne çevir…' altındadır."""
        import re as re_
        import crw_harf as CH
        import pdf_motor
        try:
            n = pdf_motor.sayfa_sayisi(yol)
        except Exception as ex:  # noqa: BLE001
            return messagebox.showerror("Croow MultiReader", f"PDF açılamadı:\n{ex}")
        if n <= 3:
            sayfalar = list(range(1, n + 1))
        else:
            s_ = simpledialog.askstring("Sayfalar", f"PDF {n} sayfa. Hangi sayfalar açılsın?\n(örn: 1-3, 5; en çok 12 sayfa)",
                                        initialvalue="1", parent=kok)
            if not s_:
                return
            sayfalar = []
            for parca in re_.split(r"[,\s]+", s_.strip()):
                m_ = re_.fullmatch(r"(\d+)(?:-(\d+))?", parca)
                if m_:
                    a_, b_ = int(m_.group(1)), int(m_.group(2) or m_.group(1))
                    sayfalar += [k for k in range(a_, b_ + 1) if 1 <= k <= n and k not in sayfalar]
            sayfalar = sayfalar[:12]
            if not sayfalar:
                return messagebox.showinfo("Croow MultiReader", "Geçerli sayfa numarası yok.")
        klasor = os.path.join(CH.VERI, "sayfalar")
        os.makedirs(klasor, exist_ok=True)
        ad = os.path.splitext(os.path.basename(yol))[0]

        def is_(il):
            yollar = []
            for i, k in enumerate(sayfalar):
                il(i / len(sayfalar), f"PDF sayfa {k}/{n} resme çevriliyor (300 DPI)…")
                img = pdf_motor.ciz(yol, k, 300)
                if img is None:
                    raise RuntimeError(f"sayfa {k} çizilemedi")
                hedef = os.path.join(klasor, f"{ad}_s{k}.png")
                img.save(hedef)
                yollar.append(hedef)
            return yollar
        arka_plan(is_, lambda yollar: [ac(y) for y in yollar])

    # ---- CriCroow7 adım adım: her basış tek geçiş (okuma yok, hızlı)
    def cri_oturum():
        """Açık resim için CriCroow7 oturumu (ilk basışta kurulur). Orijinal dosyaya dokunulmaz."""
        o = durum.get("cri")
        if o is None:
            import belge_harf as BH
            import cricroow
            yol, kaynak = durum.get("yol"), None
            if yol and os.path.isfile(yol):
                with open(yol, "rb") as f:
                    kaynak = f.read()
            depo = ortak_depo()
            o = durum["cri"] = cricroow.Oturum(durum["asil_img"], None if depo.bos() else depo, kaynak_bayt=kaynak)
            o.duzenleme = depo.duzenleme                         # elle silinen / çizilenlerden öğrenilen kurallar
            o.harf_depo = depo                                   # harf hafızası (öğrenilmiş harf kalıpları)
        return o

    def cri_adim(tur):
        if durum.get("img") is None:
            return

        def is_(il):
            il(0, {"leke": "Leke azaltılıyor…", "leke_riskli": "Leke azaltılıyor (riskli: siyah lekeler sert)…",
                   "bolge_ic": "Seçili bölgenin içi riskli temizleniyor…", "bolge_dis": "Seçili bölgenin dışı riskli temizleniyor…", "tamamla": "Kopuk çizgiler tamamlanıyor…",
                   "riskli": "Kopuk çizgiler tamamlanıyor (riskli)…", "netlestir": "Netleştiriliyor (inceltme)…",
                   "netlestir_v": "Harfler tanınıyor ve yollarına göre inceltiliyor (yavaş)…",
                   "netlestir_z": "Önce genel inceltme ×10, sonra harfin yoluna göre ×3 (uzun sürer)…"}[tur])
            o = cri_oturum()
            cri_yigin.append((o, o.anlik(), time.time()))    # Ctrl+Z bu adımı geri alabilsin
            del cri_yigin[:-4]
            o.bolge_ayarla(durum.get("bolge"), durum.get("bolge_poly"))   # işlem yalnızca seçili bölgede / çokgenin içinde
            r = {"leke": o.leke_azalt, "leke_riskli": lambda: o.leke_azalt(risk=1.0), "bolge_ic": lambda: o.riskli_temizle(True),
                 "bolge_dis": lambda: o.riskli_temizle(False), "tamamla": lambda: o.tamamla(0.3), "riskli": lambda: o.tamamla(0.9),
                 "netlestir": o.netlestir, "netlestir_v": lambda: o.netlestir(varyant=True),
                 "netlestir_z": lambda: o.netlestir_zincir(10, 3)}[tur]()
            return o.sonuc().convert("RGB"), r, o.rapor()["toplam"]

        def bitti(sonuc):
            img, r, t = sonuc
            durum["img"] = img
            resim_yenile()                                   # yakınlaştırma ve konum korunur
            ayrinti = " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in r.items() if k not in ("islem", "sira"))
            bilgi.configure(text=f"CriCroow7 {r['sira']}. işlem ({r['islem']}): {ayrinti}  |  toplam: eklenen "
                                 f"{t['eklenen_piksel']:,} px, soldurulan {t['soldurulan_piksel']:,} px · delil değildir")
        arka_plan(is_, bitti)

    def cri_harita():
        o = durum.get("cri")
        if o is None:
            return messagebox.showinfo("CriCroow7", "Henüz bir CriCroow7 işlemi yapılmadı.")
        resim_kipi()
        gor.degistir(o.harita())                             # haritayı göster; asıl sonuç durum["img"]'de kalır
        bilgi.configure(text="Değişiklik haritası: mavi = eklenen, kırmızı = soldurulan/inceltilen, koyu gri = karartma (dokunulmadı)")

    def cri_sifirla():
        durum.pop("cri", None)
        if durum.get("asil_img") is not None:
            durum["img"] = durum["asil_img"]
            resim_yenile()
            bilgi.configure(text="CriCroow7: orijinale dönüldü")

    def cri_kaydet():
        o, yol = durum.get("cri"), durum.get("yol")
        if o is None:
            return messagebox.showinfo("CriCroow7", "Henüz bir CriCroow7 işlemi yapılmadı.")
        klasor = filedialog.askdirectory(title="CriCroow7 çıktılarının kaydedileceği klasör",
                                         initialdir=os.path.dirname(yol) if yol else None)
        if not klasor:
            return
        import cricroow
        on = os.path.join(klasor, os.path.splitext(os.path.basename(yol or "sayfa"))[0] + "_cricroow")
        rapor = o.rapor()
        rapor["orijinal_dosya"] = os.path.basename(yol) if yol else None
        o.sonuc().save(on + ".png"); o.harita().save(on + "_harita.png"); cricroow.rapor_yaz(rapor, on + "_rapor.json")
        t = rapor["toplam"]
        messagebox.showinfo("CriCroow7", f"{t['islem_sayisi']} işlem · eklenen {t['eklenen_piksel']:,} piksel · soldurulan "
                            f"{t['soldurulan_piksel']:,} piksel · korunan karartma kutusu {t['karartma']}\n\nKaydedildi:\n"
                            f"{os.path.basename(on)}.png\n{os.path.basename(on)}_harita.png\n"
                            f"{os.path.basename(on)}_rapor.json\n\nBu görüntü bir okuma yardımıdır, delil değildir. "
                            "Orijinal dosya değiştirilmedi.")

    def cricroow_calistir():
        """CriCroow7: sayfayı netleştirir, harf deposundan hafifçe tamamlar, lekeleri soldurur.
        Orijinal dosyaya dokunulmaz; sonuç, değişiklik haritası ve SHA-256'lı rapor ayrı dosyalara yazılır."""
        img, yol = durum.get("img"), durum.get("yol")
        if img is None:
            return
        import crw_harf as CH
        import belge_harf as BH
        belge_kipi = not ortak_depo().bos()
        if not belge_kipi and not CH.Palet().k:
            return messagebox.showwarning("Croow MultiReader",
                                          "Harf deposu boş. Önce 'Bu sayfadan harf öğret' (önerilen) ya da "
                                          "Araçlar → 'Harf paletini alfabeden öğret'.")
        if not messagebox.askokcancel(
                "CriCroow7",
                "CriCroow7 sayfayı netleştirir, tanıdığı harflerin eksik çizgilerini çok hafif tamamlar ve harf "
                "olmayan izleri (leke) adım adım soldurur.\n\nTamamlanan kısımlar motorun TAHMİNİDİR: sonuç bir okuma "
                "yardımıdır, delil değildir. Orijinal dosya değiştirilmez; her eklenen ve soldurulan piksel bir "
                "değişiklik haritasında, orijinalin SHA-256 parmak iziyle birlikte raporlanır.\n\nDevam edilsin mi?"):
            return
        klasor = filedialog.askdirectory(title="CriCroow7 çıktılarının kaydedileceği klasör",
                                         initialdir=os.path.dirname(yol) if yol else None)
        if not klasor:
            return
        on = os.path.join(klasor, os.path.splitext(os.path.basename(yol or "sayfa"))[0] + "_cricroow")

        def is_(il):
            import cricroow
            kaynak = None
            if yol and os.path.isfile(yol):
                with open(yol, "rb") as f:
                    kaynak = f.read()
            if belge_kipi:                 # belgenin kendi harfleriyle: olasılık, bağlam, karşılaştırma, karartma koruması
                P = CH.Palet()
                sonuc, harita, rapor = cricroow.onar_belge(img, ortak_depo(), P if P.k else None, kaynak_bayt=kaynak,
                                                           ilerleme=il)
            else:
                sonuc, harita, rapor = cricroow.onar(img, kaynak_bayt=kaynak, ilerleme=il)
            rapor["orijinal_dosya"] = os.path.basename(yol) if yol else None
            il(0.97, "Kaydediliyor…")
            sonuc.save(on + ".png"); harita.save(on + "_harita.png"); cricroow.rapor_yaz(rapor, on + "_rapor.json")
            return sonuc, rapor

        def bitti(r):
            sonuc, rapor = r
            durum["img"] = sonuc.convert("RGB")
            resim_ciz(True)
            t = rapor["toplam"]
            son = rapor["adimlar"][-1] if rapor["adimlar"] else {}
            bilgi.configure(text=f"CriCroow7: {len(rapor['adimlar'])} adım · eklenen {t['eklenen_piksel']:,} px · "
                                 f"soldurulan {t['soldurulan_piksel']:,} px · tahmin içerir, delil değildir")
            messagebox.showinfo("CriCroow7",
                                (f"Kip: belgenin kendi harfleri\nAdım: {len(rapor['adimlar'])}\n"
                                 f"Yerine konan harf (son adım): {son.get('yerine_konan', 0):,} / {son.get('harf_kutusu', 0):,}\n"
                                 f"Karşılaştırmada geri alınan: {t.get('celiski', 0):,}\n"
                                 f"Korunan karartma (sansür) kutusu: {t.get('karartma', 0)}\n"
                                 if "yerine_konan" in son else
                                 f"Netleştirme: {rapor.get('netlestirme')}\nAdım: {len(rapor['adimlar'])}\n"
                                 f"Tanınan harf: {son.get('taninan', 0):,} / {son.get('harf_kutusu', 0):,}\n"
                                 f"Leke sayılan iz: {son.get('leke_izi', 0):,}\n")
                                + f"Eklenen mürekkep: {t['eklenen_piksel']:,} piksel (haritada mavi)\n"
                                f"Soldurulan leke: {t['soldurulan_piksel']:,} piksel (haritada kırmızı)\n"
                                + (f"\n⚠ {rapor['fren']}\n" if rapor.get("fren") else "")
                                + f"\nKaydedildi:\n{os.path.basename(on)}.png\n{os.path.basename(on)}_harita.png\n"
                                f"{os.path.basename(on)}_rapor.json\n\nOrijinal dosya değiştirilmedi.")
        arka_plan(is_, bitti)

    def resim_sikistir(girdi=None):
        """Herhangi bir resim -> CRW7 (kayıpsız; palet Croow hafızasından)."""
        import base64
        girdi = girdi or filedialog.askopenfilename(
            title="Sıkıştırılacak resim", filetypes=[("Resimler", " ".join("*" + u for u in RESIM_UZ)), ("Tüm dosyalar", "*")])
        if not girdi:
            return
        hedef = filedialog.asksaveasfilename(title="CRW olarak kaydet", defaultextension=".crw",
                                             initialdir=os.path.dirname(girdi),
                                             initialfile=os.path.splitext(os.path.basename(girdi))[0] + ".crw",
                                             filetypes=[("CRW resmi", "*.crw")])
        if not hedef:
            return

        def is_(il):
            il(0, "CRW7'ye sıkıştırılıyor…")
            with open(girdi, "rb") as f:
                r = motor().encode_image_to_crw5(f.read())
            veri = base64.b64decode(r["crw_base64"])
            with open(hedef, "wb") as f:
                f.write(veri)
            return r

        def bitti(r):
            asil = os.path.getsize(girdi)
            ham = r["width"] * r["height"] * 3
            messagebox.showinfo("Croow MultiReader",
                                f"Kaydedildi: {os.path.basename(hedef)}\n\n"
                                f"Ham (RGB): {CO._boy(ham)}\nAsıl dosya: {CO._boy(asil)}\nCRW7: {CO._boy(r['crw_size'])}\n"
                                f"Palet: {r['palette_size']:,} ton\n\nCRW7 kayıpsızdır: açıldığında orijinalin aynısıdır.")
            ac(hedef)
        arka_plan(is_, bitti)

    # ---- PDF -> metin
    def pdf_ac(yol):
        """PDF HER ZAMAN Croow'un yontemiyle okunur: her sayfanin goruntusu harf paletiyle (piksel analizi).
        PDF'in icindeki hazir metin (varsa) yalnizca karsilastirma icin ayri bir secenek olarak durur."""
        import crw_harf as CH
        import crw_pdf as CP
        yeni_dosya(yol, "PDF")
        metin_kipi()
        metin.delete("1.0", "end")

        def oku(il):
            import tempfile
            try:
                katman = CP.metin_katmani(yol)
            except RuntimeError:
                katman = ""
            P = CH.Palet()
            if not P.k:
                return None, katman
            n = CH.sayfa_sayisi(yol)
            sayfalar = []
            with tempfile.TemporaryDirectory(prefix="croow_multi_") as gecici:
                for k in range(1, n + 1):
                    il((k - 1) / max(1, n), f"Croow okuyor: sayfa {k}/{n} (piksel analizi)…")
                    sayfalar.append(CH.sayfa_coz(yol, k, gecici, P))
            return "\f".join(sayfalar), katman

        def bitti(sonuc):
            croow, katman = sonuc
            if croow is None:
                messagebox.showinfo("Croow MultiReader", "Harf paleti boş; PDF'in kendi metni gösteriliyor.\n"
                                    "Araçlar → 'Harf paletini alfabeden öğret' ile öğretebilirsin.")
            durum["pdf_metin"] = croow if croow is not None else katman
            durum["pdf_kitap"] = katman if katman.strip() else durum["pdf_metin"]   # Croow ogrenecekse dogrusu
            ay = lambda s: s.replace("\f", "\n\n— sayfa —\n\n").splitlines()
            ogeler = []
            if croow is not None:
                ogeler.append(("Croow okuması (piksel)", lambda: iter(ay(croow))))
            if katman.strip():
                ogeler.append(("PDF'in kendi metni (karşılaştırma)", lambda: iter(ay(katman))))
            ogeler += [("Bilgi", lambda: iter([
                           "Croow okuması: sayfa görüntüsü harf paletiyle (kapsama, tepeler, profiller, zoom)"
                           if croow is not None else "Croow okuması yok (harf paleti boş)",
                           f"PDF'in kendi metni: {'var' if katman.strip() else 'yok (taranmış PDF)'}",
                           f"{len(durum['pdf_metin']):,} karakter"])),
                       (".txt olarak kaydet…", lambda: metni_kaydet(yol, False), "eylem"),
                       ("Sayfayı resim olarak aç (harf göster · CriCroow7)…", lambda: pdf_sayfa_resim(yol), "eylem")]
            liste(ogeler)
            bilgi.configure(text="PDF · Croow'un piksel okuması" if croow is not None else "PDF · kendi metni")
        arka_plan(oku, bitti)

    def metni_kaydet(pdf, _kitaplara=False):
        ad = os.path.splitext(os.path.basename(pdf))[0] + ".txt"
        hedef = filedialog.asksaveasfilename(title="Metni kaydet", defaultextension=".txt",
                                             initialdir=os.path.dirname(pdf), initialfile=ad,
                                             filetypes=[("Metin", "*.txt")])
        if not hedef:
            return
        with open(hedef, "w", encoding="utf-8") as f:
            f.write(durum.get("pdf_metin", ""))
        messagebox.showinfo("Croow MultiReader", f"Kaydedildi:\n{hedef}")

    # ---- menu cubugu
    cubuk = tk.Menu(kok)
    m_dosya = tk.Menu(cubuk, tearoff=0)
    m_dosya.add_command(label="Aç…", accelerator="Ctrl+O", command=lambda: dosya_sec())
    m_dosya.add_separator()
    m_dosya.add_command(label="Çıkış", command=kok.destroy)
    m_arac = tk.Menu(cubuk, tearoff=0)
    m_arac.add_command(label="Resmi CRW7'ye sıkıştır…", command=lambda: resim_sikistir())
    m_arac.add_command(label="PDF'i metne çevir…", command=lambda: (lambda y: y and pdf_ac(y))(
        filedialog.askopenfilename(title="PDF seç", filetypes=[("PDF", "*.pdf")])))
    def harf_ogret():
        import crw_harf as CH
        pdfler = filedialog.askopenfilenames(title="Metin katmanlı PDF'ler seç (öğretmek için)",
                                             filetypes=[("PDF", "*.pdf")])
        if not pdfler:
            return

        def bitti(sonuc):
            n, atla = sonuc
            P = CH.Palet()
            messagebox.showinfo("Croow MultiReader",
                                f"{n:,} harf örneği öğrenildi ({atla:,} bitişik kelime güvenli değil diye atlandı).\n\n"
                                f"Harf paleti: {P.harf_sayisi()} farklı harf, {len(P.k):,} kök ızgara.\n"
                                "Artık taranmış PDF'ler ve resimlerdeki yazılar bu paletle çözülür.")
            bilgi.configure(text="Harf paleti güncellendi")
        arka_plan(lambda il: CH.ogren(list(pdfler), ilerleme=il), bitti)

    def harf_sina(kirli):
        import crw_harf as CH
        pdf = filedialog.askopenfilename(title="Sınamak için GÖRÜLMEMİŞ, metinli bir PDF seç",
                                         filetypes=[("PDF", "*.pdf")])
        if pdf:
            arka_plan(lambda il: CH.sina(pdf, 5, kirli, il),
                      lambda rapor: goster("Harf paleti sınaması", lambda: iter(rapor), kaydet=True))

    def alfabe_ogret():
        import crw_harf as CH
        fontlar = CH.yazi_tipleri()
        if not messagebox.askyesno("Croow MultiReader",
                                   f"Bilgisayarda {len(fontlar)} yazı tipi var. Her birinde alfabe sıra sıra çizilip "
                                   "harf paletine öğretilsin mi?"):
            return
        arka_plan(lambda il: CH.alfabe_ogren(fontlar, ilerleme=il),
                  lambda s: messagebox.showinfo("Croow MultiReader",
                                                f"{s[0]:,} harf örneği, {s[1]} yazı tipinden öğrenildi."))

    m_arac.add_separator()
    m_arac.add_command(label="Harf paletini alfabeden öğret (yazı tipleri)…", command=alfabe_ogret)
    m_arac.add_command(label="Harf paletini öğret (metinli PDF'lerden)…", command=harf_ogret)
    def yol_ogret():
        import crw_harf as CH
        pdfler = filedialog.askopenfilenames(title="Metinli PDF'ler seç (yazı yollarını öğretmek için)",
                                             filetypes=[("PDF", "*.pdf")])
        if not pdfler:
            return
        arka_plan(lambda il: CH.yazi_yollari_ogren(list(pdfler), ilerleme=il),
                  lambda s: messagebox.showinfo("Croow MultiReader",
                                                f"{s[0]:,} sayfadan yazı yolları öğrenildi: {s[1]['paths']:,} yol.\n\n"
                                                "Resimlerde ve taramalarda emin olunmayan satırlar artık CRW7 ile "
                                                "detaylandırılıp yeniden okunur."))

    m_arac.add_command(label="Yazı yollarını öğret (CRW7, metinli PDF'lerden)…", command=yol_ogret)
    m_arac.add_command(label="Belgeden harf öğret (sayfa resmi + doğru metni)…", command=lambda: belge_ogret())

    def baglam_ogret():
        import belge_harf as BH
        yollar = filedialog.askopenfilenames(title="Bağlam için düz metin dosyaları (.txt) — belgelerin dilinde",
                                             filetypes=[("Metin", "*.txt"), ("Tüm dosyalar", "*")])
        if yollar:
            arka_plan(lambda il: BH.baglam_ogret(list(yollar), ilerleme=il),
                      lambda r: messagebox.showinfo("Croow MultiReader",
                                                    f"{r[0]} dosyadan cümle bağlamı öğrenildi.\nDepoda {r[1]:,} kelime var."))
    m_arac.add_command(label="Cümle bağlamı öğret (metin dosyalarından)…", command=baglam_ogret)
    m_arac.add_command(label="Harf paletini sına (temiz sayfa)…", command=lambda: harf_sina(False))
    m_arac.add_command(label="Harf paletini sına (tarama benzeri, kirli)…", command=lambda: harf_sina(True))
    def hakkinda():
        import pdf_motor
        try:
            m = motor().MEMORY.summary()
            hafiza = f"{m['roots']:,} kök, {m.get('paths', 0):,} piksel yolu" + ("" if os.path.exists(hafiza_yolu()) else " (dosya yok)")
        except Exception as e:  # noqa: BLE001
            hafiza = f"yüklenemedi ({e})"
        messagebox.showinfo("Croow MultiReader hakkında",
                            f"Croow MultiReader {SURUM}\n\n"
                            "Croow — Alper Pektas tarafından geliştirilmiştir.\n"
                            "Copyright (C) 2026 Alper Pektas\n\n"
                            "Bu program özgür yazılımdır: GNU Affero Genel Kamu Lisansı sürüm 3 (AGPLv3) ile "
                            "lisanslıdır. Ek koşullar için NOTICE dosyasına bakın.\n"
                            "Kaynak kodu: https://github.com/AlperPe/Croow-MultiReader\n\n"
                            f"PDF motoru: {pdf_motor.motor() or 'yok'}\n"
                            f"Croow hafızası: {hafiza}\n"
                            f"Veri klasörü: {VERI}")

    m_yardim = tk.Menu(cubuk, tearoff=0)
    m_yardim.add_command(label="Hakkında", command=hakkinda)

    def dil_sec(kod):
        dil.ayarla(kod)
        messagebox.showinfo("Dil / Language", "Dil değişti; uygulamayı yeniden başlat.\nLanguage changed; restart the application.")
    m_dil = tk.Menu(m_yardim, tearoff=0)
    m_dil.add_command(label="Türkçe" + ("  ✓" if dil.DIL == "tr" else ""), command=lambda: dil_sec("tr"))
    m_dil.add_command(label="English" + ("  ✓" if dil.DIL == "en" else ""), command=lambda: dil_sec("en"))
    m_yardim.add_cascade(label="Dil / Language", menu=m_dil)
    cubuk.add_cascade(label="Dosya", menu=m_dosya)
    cubuk.add_cascade(label="Araçlar", menu=m_arac)
    cubuk.add_cascade(label="Yardım", menu=m_yardim)
    kok.configure(menu=cubuk)

    # ---- dosya acma
    def dosya_sec():
        yollar = filedialog.askopenfilenames(title="Dosya aç (birden çok seçebilirsin: her biri kendi sekmesinde açılır)",
                                             filetypes=[
            ("Hepsi (PDF, CRW, resim)", "*.pdf *.crw " + " ".join("*" + u for u in RESIM_UZ)),
            ("CRW dosyaları", "*.crw"), ("Resimler", " ".join("*" + u for u in RESIM_UZ)),
            ("PDF", "*.pdf"), ("Tüm dosyalar", "*")])
        for y in yollar:
            ac(y)

    def ac(yol):
        uz = os.path.splitext(yol)[1].lower()
        if uz == ".pdf":
            return pdf_resim_ac(yol)                         # sayfalar RESİM olarak açılır (Harf göster, CriCroow7 çalışır)
        if uz in RESIM_UZ:
            return resim_ac(yol, False)
        try:
            tur, ok = tur_bul(yol)
        except Exception as e:  # noqa: BLE001
            return messagebox.showerror("Croow MultiReader", f"Dosya açılamadı:\n{e}")
        if tur == "resim":
            return resim_ac(yol, True)
        if tur == "eski_resim":
            return messagebox.showinfo("Croow MultiReader", "Bu eski bir CRW1/CRW4 resmi; bu sürüm açmıyor.\n"
                                       "Asıl resmi 'CRW7'ye sıkıştır' ile yeniden çevirebilirsin.")
        yeni_dosya(yol, "CRW2" if tur == "crw2" else "tanınmadı")
        durum.update(tur=tur, ok=ok, img=None)
        if tur == "crw2":
            arama_tur.configure(text="Süz:")
            ogeler = [("Bölümler", lambda: CO.ozet_genel(ok))] + [
                (f"bölüm: {b}", (lambda b=b: CO.bolum_metin(ok, b))) for b in ok.bolumler]
            for ad_, f in ogeler:
                iid = sol.insert("", "end", text=ad_)
                durum["ogeler"][iid] = (ad_, f)
            sol.selection_set(sol.get_children()[0])
            return
        goster("Bilgi", lambda: iter(["Bu dosya tanınmadı. Açılabilenler: PDF, CRW5/6/7 resimleri, CRW2 dosyaları, "
                                      "PNG/JPG/WebP/BMP/TIFF resimler."]))

    # ---- kayit agaci (tembel: dal acilinca doldurulur)
    def dal_ekle(ust_iid, v, yol_):
        ogeler = list(v.items()) if isinstance(v, dict) else list(enumerate(v)) if isinstance(v, list) else []
        for k, x in ogeler[:5000]:
            etiket = f"{k}" if isinstance(x, (dict, list)) else f"{k}: {str(x)[:80]}"
            if isinstance(x, (dict, list)):
                etiket += f"  ({len(x)})"
            iid = sol.insert(ust_iid, "end", text=etiket, values=(repr(yol_ + (k,)),))
            if isinstance(x, (dict, list)) and x:
                sol.insert(iid, "end", text="…")         # acilinca doldurulacak
        if len(ogeler) > 5000:
            sol.insert(ust_iid, "end", text=f"… ve {len(ogeler) - 5000:,} öğe daha (sağdaki metinde tamamı)")

    def dal_degeri(iid):
        import ast
        d = durum["veri"]
        degerler = sol.item(iid, "values")
        if not degerler:
            return None, ()
        yol_ = ast.literal_eval(degerler[0])
        for k in yol_:
            d = d[k]
        return d, yol_

    def dal_ac(_):
        iid = sol.focus()
        if durum["tur"] != "kayit":
            return
        cocuk = sol.get_children(iid)
        if len(cocuk) == 1 and sol.item(cocuk[0], "text") == "…":
            sol.delete(cocuk[0])
            v, yol_ = dal_degeri(iid)
            dal_ekle(iid, v, yol_)

    def secildi(_):
        sec = sol.selection()
        if not sec:
            return
        iid = sec[0]
        if durum["tur"] == "kayit":
            v, yol_ = dal_degeri(iid)
            if yol_:
                goster(" / ".join(map(str, yol_)), lambda: CO._agac_metin(v), kaydet=True)
            return
        oge = durum["ogeler"].get(iid)
        if oge and len(oge) > 2 and oge[2] == "eylem":
            kok.after(10, lambda: sol.selection_remove(iid))   # ayni eyleme tekrar tiklanabilsin
            oge[1]()
        elif oge:
            goster(oge[0], oge[1], kaydet=True)

    sol.bind("<<TreeviewSelect>>", secildi)
    sol.bind("<<TreeviewOpen>>", dal_ac)

    # ---- arama
    def ara():
        q = arama.get().strip()
        if not q or not durum["yol"]:
            return
        kaynak = durum["kaynak"]
        if kaynak:
            ql = q.lower()
            goster(f"'{q}' içerenler", lambda: (s for s in kaynak() if ql in s.lower()), kaydet=True)

    if sys.platform == "darwin":
        # macOS dosyaları (çift tıklama, "Birlikte aç", simgeye sürükleme) Apple olayıyla gönderir
        kok.createcommand("::tk::mac::OpenDocument", lambda *yollar: [ac(y_) for y_ in yollar])
    kok.bind("<Control-o>", lambda _: dosya_sec())
    kok.bind("<Control-f>", lambda _: arama.focus_set())
    kok.bind("<Alt-Left>", geri)
    if ilk:
        kok.after(50, lambda: ac(ilk))
    # iç durum erişimi (otomatik sınama için; arayüzde görünmez)
    kok.croow_ic = {"durum": durum, "gor": gor, "kp": kp, "bilgi": bilgi, "nizami_gecmis": nizami_gecmis, "seri_tamam": seri_tamam, "cri_adim": cri_adim, "sinif_ogret": sinif_ogret, "cri_oturum": cri_oturum, "sekmeler": sekmeler, "sekme_durumu": sekme_durumu,
                    "ortak_depo": ortak_depo, "ac": ac, "kutular_yenile": kutular_yenile, "sec_kutu": sec_kutu,
                    "esle": esl, "esle_ogret": esle_ogret, "esle_tikla": esle_tikla}
    kok.mainloop()


# ====================================================================== hata gosterme
def _hata_goster(e):
    """Cift tiklamada terminal olmadigi icin hata gorunmez: dosyaya yazilir ve pencerede gosterilir."""
    import traceback
    iz = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    gunluk = os.path.expanduser("~/crwreader_hata.txt")
    try:
        with open(gunluk, "w", encoding="utf-8") as f:
            f.write(f"argumanlar: {sys.argv}\npython: {sys.executable}\n\n{iz}")
    except OSError:
        pass
    print(iz, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        if tk._default_root is None:
            tk.Tk().withdraw()
        messagebox.showerror("CRW Reader", f"{e}\n\nAyrıntı: {gunluk}")
    except Exception:  # noqa: BLE001 - tkinter de yoksa
        pass


if __name__ == "__main__":
    try:
        if "--kur" in sys.argv:
            kur()
        else:
            if not DONMUS:                               # kurulumlu uygulamada modüller paketin içinde
                _eksikleri_kontrol()
            calistir(next((a for a in sys.argv[1:] if not a.startswith("-")), None))
    except Exception as _e:  # noqa: BLE001
        _hata_goster(_e)
