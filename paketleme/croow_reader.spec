# -*- mode: python ; coding: utf-8 -*-
# Croow MultiReader paketleme tarifi (PyInstaller). Croow — Alper Pektas tarafından geliştirilmiştir. AGPLv3.
# Kullanım (depo kökünde):  pyinstaller paketleme/croow_reader.spec
import os
import sys

from PyInstaller.utils.hooks import collect_all

kok = os.path.abspath(os.path.join(SPECPATH, ".."))
datas, binaries, hidden = [], [], []
for paket in ("pypdfium2", "pypdfium2_raw"):
    d, b, h = collect_all(paket)
    datas += d; binaries += b; hidden += h
datas += [(os.path.join(kok, "NOTICE"), ".")]

# Linux: bazı Python dağıtımları Tcl/Tk kütüphanelerini kendi lib klasöründe tutar; PyInstaller onları
# kendiliğinden bulamazsa pencere açılmaz. Bulunanlar pakete elle eklenir.
if sys.platform.startswith("linux"):
    import glob
    for kl in {os.path.join(sys.base_prefix, "lib"), os.path.join(sys.prefix, "lib")}:
        for so in glob.glob(os.path.join(kl, "libtcl*.so*")) + glob.glob(os.path.join(kl, "libtk*.so*")):
            binaries.append((so, "."))
hidden += ["crw", "crw_json", "crw_oku", "crw_harf", "crw_pdf", "pdf_motor", "cricroow", "belge_harf", "croow_gorunum", "croow_dosya", "dil", "dil_en",
           "crw_motor", "roots_memory", "paths_memory"]

a = Analysis([os.path.join(kok, "uygulama", "croow_reader.py")],
             pathex=[os.path.join(kok, "uygulama"), os.path.join(kok, "motor")],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["ngram_crw", "matplotlib", "scipy", "pandas"])
pyz = PYZ(a.pure)
ikon = {"win32": "ikon.ico", "darwin": "ikon.icns"}.get(sys.platform, "ikon.png")
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CroowMultiReader", console=False,
          icon=os.path.join(SPECPATH, ikon))
coll = COLLECT(exe, a.binaries, a.datas, name="CroowMultiReader")

if sys.platform == "darwin":
    surum = os.environ.get("CROOW_SURUM", "1.0.0")
    app = BUNDLE(coll, name="Croow MultiReader.app", icon=os.path.join(SPECPATH, "ikon.icns"),
                 bundle_identifier="com.alperpektas.croow.multireader",
                 info_plist={
                     "CFBundleName": "Croow MultiReader",
                     "CFBundleDisplayName": "Croow MultiReader",
                     "CFBundleShortVersionString": surum,
                     "CFBundleVersion": surum,
                     "NSHighResolutionCapable": True,
                     "NSHumanReadableCopyright": "Croow — Alper Pektas tarafından geliştirilmiştir. © 2026 Alper Pektas. AGPLv3.",
                     "CFBundleDocumentTypes": [
                         {"CFBundleTypeName": "Croow CRW", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Owner",
                          "LSItemContentTypes": ["com.alperpektas.croow.crw"], "CFBundleTypeIconFile": "ikon.icns"},
                         {"CFBundleTypeName": "PDF", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
                          "LSItemContentTypes": ["com.adobe.pdf"]},
                         {"CFBundleTypeName": "Resim", "CFBundleTypeRole": "Viewer", "LSHandlerRank": "Alternate",
                          "LSItemContentTypes": ["public.image"]},
                     ],
                     "UTExportedTypeDeclarations": [
                         {"UTTypeIdentifier": "com.alperpektas.croow.crw", "UTTypeDescription": "Croow CRW",
                          "UTTypeConformsTo": ["public.data"], "UTTypeIconFile": "ikon.icns",
                          "UTTypeTagSpecification": {"public.filename-extension": ["crw"]}},
                     ],
                 })
