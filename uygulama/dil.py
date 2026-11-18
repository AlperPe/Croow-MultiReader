"""Croow arayüz dili (TR / EN).

Kaynak metinler Türkçe yazılmıştır; İngilizce seçiliyse tkinter'ın etiket, menü, mesaj kutusu ve durum
satırı çağrılarında metin bu sözlükten çevrilir (tam eşleşme önce, sonra parça parça). Sözlükte olmayan metin
olduğu gibi (Türkçe) kalır. Seçim ~/.croow/dil.txt dosyasında saklanır; CROOW_DIL=en|tr ile de verilebilir.
UI language: sources are Turkish; English is applied at display time through this table."""
import locale
import os

from dil_en import EN, PARCA

_VERI = os.environ.get("CROOW_VERI") or os.path.join(os.path.expanduser("~"), ".croow")
_DOSYA = os.path.join(_VERI, "dil.txt")
_H = "A-Za-zçğıöşüÇĞİÖŞÜ"


def _kalip(tr):
    p = ""
    if tr[0].isalpha():
        p += "(?<![%s])" % _H
    p += __import__("re").escape(tr)
    if tr[-1].isalpha():
        p += "(?![%s])" % _H
    return __import__("re").compile(p)


_PARCALAR = [(_kalip(k), v) for k, v in sorted(PARCA.items(), key=lambda kv: -len(kv[0])) if len(k.strip()) >= 5]


def _baslangic():
    v = os.environ.get("CROOW_DIL", "").strip().lower()
    if v in ("tr", "en"):
        return v
    try:
        with open(_DOSYA, encoding="utf-8") as f:
            v = f.read().strip().lower()
        if v in ("tr", "en"):
            return v
    except OSError:
        pass
    try:
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:  # noqa: BLE001
        loc = ""
    return "tr" if loc.startswith("tr") else "en"


DIL = _baslangic()


def ayarla(kod):
    """Dili kalıcı kaydeder (uygulama yeniden başlatılınca etkili olur)."""
    try:
        os.makedirs(_VERI, exist_ok=True)
        with open(_DOSYA, "w", encoding="utf-8") as f:
            f.write(kod)
    except OSError:
        pass


def T(s):
    """Türkçe kaynak metni geçerli dile çevirir."""
    if DIL != "en" or not isinstance(s, str) or not s.strip():
        return s
    if s in EN:
        return EN[s]
    t = s.strip()
    if t in EN:
        return s.replace(t, EN[t])
    out = s
    for kal, en in _PARCALAR:
        out = kal.sub(lambda m, e=en: e, out)
    return out


def _sar_kw(kwargs, adlar=("text", "label", "title", "message")):
    for a in adlar:
        if isinstance(kwargs.get(a), str):
            kwargs[a] = T(kwargs[a])
    return kwargs


def kur():
    """tkinter'ı çeviri yapacak şekilde sarar. Uygulama başında bir kez çağrılır."""
    if DIL != "en":
        return
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    def sar_init(cls, adlar=("text",)):
        eski = cls.__init__

        def yeni(self, *a, **k):
            _sar_kw(k, adlar)
            eski(self, *a, **k)
        cls.__init__ = yeni

    def sar_conf(cls, adlar=("text",)):
        eski = cls.configure

        def yeni(self, cnf=None, **k):
            if isinstance(cnf, dict):
                cnf = _sar_kw(dict(cnf), adlar)
            _sar_kw(k, adlar)
            return eski(self, cnf, **k) if cnf is not None else eski(self, **k)
        cls.configure = yeni
        cls.config = yeni

    for cls in (tk.Label, tk.Button, tk.Checkbutton, tk.Radiobutton, tk.LabelFrame,
                ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton, ttk.LabelFrame, ttk.Labelframe):
        sar_init(cls)
        sar_conf(cls)

    for ad in ("add_command", "add_checkbutton", "add_radiobutton", "add_cascade",
               "insert_command", "insert_checkbutton", "insert_radiobutton", "insert_cascade"):
        eski = getattr(tk.Menu, ad)

        def yeni(self, *a, _e=eski, **k):
            _sar_kw(k, ("label",))
            return _e(self, *a, **k)
        setattr(tk.Menu, ad, yeni)

    eski_add = ttk.Notebook.add

    def nb_add(self, child, **k):
        _sar_kw(k, ("text",))
        return eski_add(self, child, **k)
    ttk.Notebook.add = nb_add

    eski_title = tk.Wm.title

    def title(self, string=None):
        return eski_title(self, T(string) if isinstance(string, str) else string)
    tk.Wm.title = title
    tk.Wm.wm_title = title

    eski_set = tk.StringVar.set

    def svset(self, value):
        return eski_set(self, T(value) if isinstance(value, str) and len(value) >= 8 else value)
    tk.StringVar.set = svset

    for ad in ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel", "askretrycancel", "askquestion"):
        eski = getattr(messagebox, ad)

        def yeni(title=None, message=None, *a, _e=eski, **k):
            return _e(T(title) if isinstance(title, str) else title,
                      T(message) if isinstance(message, str) else message, *a, **k)
        setattr(messagebox, ad, yeni)
    for ad in ("askstring", "askinteger", "askfloat"):
        eski = getattr(simpledialog, ad)

        def yeni(title, prompt, *a, _e=eski, **k):
            return _e(T(title), T(prompt), *a, **k)
        setattr(simpledialog, ad, yeni)

    eski_tv = ttk.Treeview.insert

    def tv_insert(self, parent, index, iid=None, **k):
        _sar_kw(k, ("text",))
        return eski_tv(self, parent, index, iid=iid, **k)
    ttk.Treeview.insert = tv_insert

    eski_li = tk.Listbox.insert

    def li_insert(self, index, *elements):
        return eski_li(self, index, *[T(e) if isinstance(e, str) else e for e in elements])
    tk.Listbox.insert = li_insert

    eski_ct = tk.Canvas.create_text

    def ct(self, *a, **k):
        if isinstance(k.get("text"), str):
            k["text"] = T(k["text"])
        return eski_ct(self, *a, **k)
    tk.Canvas.create_text = ct
