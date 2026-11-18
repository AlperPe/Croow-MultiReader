# Croow MultiReader

🇬🇧 English · 🇹🇷 [Türkçe](README.tr.md)

**Croow — Alper Pektas tarafından geliştirilmiştir.** *(Developed by Alper Pektas.)*

Croow MultiReader is a desktop application (Windows · macOS · Linux) for **reading, cleaning and making sense of** old, faded, dirty, scanned documents: typewritten pages, correspondence, declassified archive pages, pages under forensic examination. It uses no ready-made OCR library: it **learns the letters from the document itself**, and you steer that learning.

> **Important:** Croow is a reading aid, not evidence. Its output is an estimate; for critical use, compare it with the original document. Your original files are never modified.

---

## Contents
1. [What it is for](#what-it-is-for) · 2. [How it works](#how-it-works) · 3. [Why learning matters](#why-learning-matters) · 4. [Download and install](#download-and-install) · 5. [Quick start](#quick-start) · 6. [Feature guide](#feature-guide) · 7. [Language](#language) · 8. [Shortcuts](#shortcuts) · 9. [Where data is stored](#where-data-is-stored) · 10. [What Croow learns](#what-croow-learns) · 11. [Reading test](#reading-test) · 12. [Run from source](#run-from-source) · 13. [Ideas and contact](#open-to-ideas--contact) · 14. [License](#license)

> **About button names.** The application interface is available in Turkish and English (see [Language](#language)). This guide writes buttons and menu items in English; the Turkish original is given in *italics* where it helps, e.g. **Show letters and teach** (*Harf göster ve öğret*).

---

## What it is for

| Goal | How |
|---|---|
| Read text in images and PDFs | Letter palette + the document's own letters, with probabilities; correction by sentence context |
| Clean dirty / thickened / faded letters | **CriCroow7**: stain reduction, completing broken strokes, thinning (sharpening) |
| Solve an unreadable word | **Word solver**: candidate words from the letter count, the letters you know, and a dictionary |
| Adapt the program to your own document | Teach letters, words, boxes, stains, lines, bridges; every correction you make is saved |
| Store images losslessly | **CRW7** format, enhancement ×2/×4/…, detailed CRW |

## How it works

1. **Line and letter boxes:** The page skew is corrected, text lines and the letter pitch (typewriter grid) are found, and each letter is cut into a *box*. Struck-through lines and the scan edge are handled separately.
2. **Letter store:** For each letter Croow keeps real samples from your document (*real roots*), faded *virtual* copies, its main path (skeleton), width, templates per dirtiness level (*regular / medium dirty / dirty*) and a common path.
3. **Probability:** A box is compared with the letters in the store and each letter gets a probability (the panel shows the most likely letter and the runner-up, with percentages).
4. **Context:** The word dictionary and neighboring words correct the probabilities ("does this letter fit in this word?").
5. **You:** If it is right, press "Correct"; if not, type the right letter. Croow saves it as a sample. Every function below serves this loop.

## Why learning matters

Croow is not a giant pre-trained model; it is a system that **learns from you and your document**. On a document it has never been taught, it is weak. Every *Correct*, every correction, every brush stroke and every label becomes an example and is **carried over to the next pages**. The more — and the cleaner — you teach, the better it reads.

- First teach a few pages / a few paragraphs; then try new pages in the same typeface.
- Teaching something wrong also teaches: skipping what you are unsure about (`Ctrl+→`) is better than teaching it wrongly. Every teaching step can be **undone with Ctrl+Z**.
- Accuracy depends on the document you teach and on how much you teach, so we do not publish ready-made figures. To measure it on your own document there is `okuma_testi.py` (see [Reading test](#reading-test)).

## Download and install

Download from the [Releases](https://github.com/AlperPe/Croow-MultiReader/releases/latest) page:

| System | File |
|---|---|
| Windows (x64) | `CroowMultiReader-Setup-x64.exe` — setup wizard, Start menu, `.crw` file association |
| macOS (Apple Silicon) | `CroowMultiReader-macos-arm64.dmg` |
| macOS (Intel) | `CroowMultiReader-macos-intel.dmg` |
| Linux (x86_64) | `CroowMultiReader-x86_64.AppImage` |
| Linux (ARM64) | `CroowMultiReader-aarch64.AppImage` |

- **Windows:** Because it is unsigned, SmartScreen may warn: "More info" → "Run anyway".
- **macOS:** Open the DMG and drag the app to Applications; on first launch **right-click → Open** (or `xattr -dr com.apple.quarantine "/Applications/Croow MultiReader.app"`).
- **Linux:** `chmod +x CroowMultiReader-*.AppImage && ./CroowMultiReader-x86_64.AppImage`. To add it to the menu, run it once with `--kur` (*install*).
- **Arch Linux (from source):** `sudo pacman -S tk python-pillow python-numpy poppler` (poppler for PDF), then see [Run from source](#run-from-source).

## Quick start

1. Open an image or PDF with **Open…** (*Aç…*; you can select several files, each opens in its own tab). PDFs open as page **images**.
2. (First use) **Tools → Teach letter palette from alphabet** — a general starter palette.
3. In the list on the left choose **Show letters and teach** (*Harf göster ve öğret*); Croow draws the letter boxes.
4. **Click** a letter. Croow tells you its guess. If right press **Correct** (or Enter); if not, type the right letter and press **Fix and teach**.
5. In the **Word solver** in the side panel, type the word correctly (`Tab` drops Croow's guess, `Enter` teaches).
6. If cleaning is needed, run the **CriCroow7** steps in order (Reduce stains → Complete → Sharpen); undo anything you don't like with **Ctrl+Z**.
7. To re-read the page from scratch, use **Read page (from scratch)** in the panel or **CriCroow7 · Make sense**.

## Feature guide

### Files and view
- **Tabs:** Each file opens in its own tab with its own view; all tabs share **the same letter store** (when one learns, all learn). `Ctrl+W` closes.
- **Zoom:** `Ctrl+wheel`, `+`/`−`, *Fit*, *100%*; pan by dragging with the middle or right button. On large pages only the visible part is drawn.
- **PDF:** Pages open as 300 DPI images (all pages up to 3; beyond that you are asked for a page range). To convert to plain text use **Tools → Convert PDF to text…**.
- **File dialog:** Croow's own file picker (Up / Home / Downloads buttons, path line, type filter; a click only selects, double-click / Enter opens).
- **Save:** PNG, WebP, CRW7, **detailed CRW**; text as `.txt`.

### Show letters and teach
Croow finds the letter boxes; clicking a letter opens the panel.
- **Blue frame = the box Croow is looking at**; its magnified view is in the panel. **Shrink** it by dragging its edge/corner in the panel or in the image, move it by dragging inside. *Snap box to ink* fits the box to the letter. The **Flexible box (8-point frame)** option uses a polygon around the letter instead of a rectangle; stains outside the frame are erased on confirm.
- **Correct / Fix and teach:** The letter is learned together with its box position and dirtiness level. If you type the contents (e.g. `19`) into an enlarged box that holds several letters, the box is split into that many letters and each is taught.
- **On confirm, make that letter regular (clean):** The confirmed letter is rebuilt in its clean form at that position (by flexing the letter's common path / typeface reference). If the letter would be damaged, the *guard* leaves it alone and says why. `Ctrl+Z` undoes.
- **Box correction:** `Shift+drag` new box, `Delete` remove, *Merge with right*, *Split in two*, arrow keys move 1 pixel (`Shift+arrow` grows the right/bottom edge). If your corrections are consistent, the box shift is **learned** and applied automatically to following pages.
- **Variations:** A letter's dirty → medium → regular templates are shown side by side; you can pick the level while teaching. The *Writing family* field keeps different typefaces apart.

### Word solver (side panel)
It finds the word's letter count, shows the letters it is sure of in their positions (`O O M _ I _ _ I _ _`), and as you type into the slots it filters the dictionary and ranks candidates.
- `Tab`: writes Croow's guess into empty slots · `Enter`: teaches · `←/→`: move between slots · `Backspace`: delete backward.
- `Ctrl+→` / `Ctrl+←`: go to the next / previous word **without teaching** (skip a word you don't understand). The view scrolls to the selected word.
- **Word correct**, **Teach selected candidate**, **Teach what I typed**. The correct-typing mode stays on: the caret waits in the slot without clicking.
- **Read page (from scratch):** re-reads the page with what has been learned (it is not re-read automatically while you teach words).

### Three-stage learning
When it gets letters right **10 times in a row**, the turn goes to **words**, and when it gets words right 10 times in a row, to the **whole text**: Croow reads the page, you correct the wrong lines, and the page is learned from the corrected text. This raises its confidence in a measured way.

### Other ways to teach
| Function | What it does |
|---|---|
| **Teach letters from this page (with its correct text)** | Page image + that page's correct text → store (alignment matches lines itself) |
| **This is…** | Select a region → type the letter or word → learned from that region (level selectable) |
| **Match** | Select boxes of the same letter (also from different tabs), type the letter; if you don't know it, Croow assigns an "unknown symbol" that you name later |
| **Teach sentence context** | Word dictionary and neighbors from plain-text (.txt) files; gap-filling strength depends on the dictionary |
| **Teach letter palette from alphabet / from text PDFs** | General starter palette |

### CriCroow7 — cleaning and sense-making steps
Each step is a separate button; the original file does not change, and **Start over (back to original)** is always there.

| Step | Purpose |
|---|---|
| **Reduce stains** | Reduces marks outside letter boxes, dust and underlines; the **stain rule learned from your manual erasing** and black-stain softening (similarity to a reference letter) work here. Strict and safe. |
| **Reduce stains, risky** | The same step with the rule loosened: also erases slightly large marks close to neighboring writing. |
| **Risky-clean inside / outside the selected region** | Tells writing from stain; erases everything if there is no writing, keeps the writing if there is. With the flexible frame it works inside the polygon. |
| **Complete (broken lines)** | Bridges broken strokes when the line comes in straight and there is ink on the other side. Learns the gap length from the bridges you draw. The *risky* version closes longer gaps. |
| **Sharpen (thin)** | Thins thickened letters with general thinning. |
| **Sharpen (to the letter's regular form)** | Recognizes the letter, measures its dirtiness level, thins it along its common path; if the letter would break, that box's step is undone. |
| **Sharpening chain** | First general thinning ×10, then along the letter's path ×3 (takes long). |
| **Make sense (read + sentence context)** | Reads with letter probabilities + dictionary context. |
| **Change map / Save** | Shows what changed; saves image + map + report. "Manual editing" steps go into the report too. |

`Ctrl+Z` undoes the last CriCroow7 step (last 4 steps), the last brush stroke and the last regular-form conversion, whichever came last.

### Manual editing: Erase / Draw brush
In the toolbar: **Erase** (paints ink with paper color) and **Draw** (adds ink). **Size, Hardness, Opacity** are adjustable; a brush ring shows at the pointer.
- **Small brush** (inside writing): the shape, size, fill and position of erased marks become a **stain sample**. Before erasing, Croow says what it took the mark for; as you erase, the letter similarity of things resembling that shape drops.
- **Large brush** (diameter ≥ 2× line height): **region cleaning** is learned (dense areas that don't look like letters).
- **Draw**: lines that connect to old ink become **bridge** samples.

### Region selection and teaching by label
- **Select region:** drag a rectangle; CriCroow7 steps work only there. **Snap to ink (8 points)** turns the region into an 8-point frame hugging the mark. Drag the points; **right-click the frame's edge** → new handle; **right-click a point** → delete it.
- **`Ctrl+left click`: quick selection.** The mark (connected part) you click is selected with an 8-point frame and a "what is this?" menu opens. `Ctrl+Shift+click` adds to the selection.
- **Teach selection ▾:** Stain · Stain and erase · Text (writing) · Underline · Underline and erase · Redaction / censorship · Stamp / seal · Signature / handwriting · **Other…** (create your own category: type a name; things resembling it show in a purple frame with probability; mark / erase / protect).
  - *Stain* and *Underline* go into the erase rule; *Text, Redaction, Stamp, Signature* go into the **protection** list (no erase step touches things that resemble them).
  - After "… and erase" the frame disappears.

### Learning by watching, and suggestions
By default Croow **only watches**: every erase, draw, label and correction you make is recorded; a summary shows in the toolbar ("Croow is watching · stain 6 · region 2 · bridge 3 · protection 7 …"). If you like, turn on **Show suggestions**: marks very similar to a shape you taught are marked orange (similarity % on top). **Apply suggestions** erases them; on a wrong suggestion `Ctrl+click` → **✗ This suggestion is WRONG** (that shape is protected and never suggested again). Suggestions are strict: at least 5 erased marks and 60%+ similarity are required.

### CRW format
**CRW7** stores the image losslessly (the palette is built from the engine's color memory). **Enhance** ×2, ×4, ×8… upscales (pixels beyond the original are the engine's estimate); **Redraw with engine** regenerates from half size; **Detailed CRW** carries the original, the steps applied and the pixel paths in one file.

## Language

The interface language is chosen in **Help → Dil / Language** (takes effect after restart). On first launch the system language is used: Turkish if the system is Turkish, otherwise English. You can force it with the `CROOW_DIL=tr` or `CROOW_DIL=en` environment variable. The choice is stored in `~/.croow/dil.txt`.

All texts live in `uygulama/dil_en.py` (Turkish source → English). Corrections and new languages are welcome (see [Ideas and contact](#open-to-ideas--contact)).

## Shortcuts

| Shortcut | Function |
|---|---|
| `Ctrl+O` / `Ctrl+W` | Open file / close tab |
| `Ctrl+Z` | Undo the last operation (brush stroke, regular-form conversion, CriCroow7 step, label) |
| `Ctrl+wheel`, `Ctrl++`, `Ctrl+−`, `Ctrl+0` | Zoom in / out / fit |
| Drag with middle or right button | Pan the image |
| **Right click** (on frame edge / point) | Add / delete a point on the flexible frame |
| **`Ctrl+left click`** | Quick selection + "what is this?" menu; `Ctrl+Shift+click` adds to the selection |
| `Shift+drag` (Show letters) | Draw a new letter box |
| `Delete` / `Backspace` | Delete the selected letter box |
| Arrow keys / `Shift+arrow` | Move the box 1 pixel / grow the bottom-right edge |
| `Enter` (on a letter box) | Correct or Fix and teach |
| `Tab` (in word slots) | Write Croow's guess into empty slots |
| `Enter` (in word slots) | Teach what you typed (if nothing was typed: Croow's reading counts as correct only if it is a dictionary word) |
| `←` `→` (in slots), `Backspace` | Move between slots / delete backward |
| `Ctrl+→` / `Ctrl+←` | Go to the next / previous word **without teaching** |
| File dialog: `Alt+↑`, `Backspace`, `Esc` | Parent folder / parent folder / close |
| In text: `Ctrl+C`, `Ctrl+A` | Copy / select all |

## Where data is stored

Croow keeps everything **on your own computer**; no data is sent anywhere. The default folder is **`~/.croow/`** (Windows: `C:\Users\<name>\.croow\`). It can be moved with the `CROOW_VERI` environment variable (e.g. a separate store for each project).

| File | Content |
|---|---|
| `harf_koklari_v6.crw` | **General letter palette** (from typefaces / text PDFs) |
| `belge_harf.crw` | **Real letter roots**: letter samples learned from your documents |
| `belge_harf_sanal.crw` | **Virtual (faded) copies**: faded versions generated from real letters |
| `belge_kelime.crw` | Word dictionary and neighbor counts, letter patterns, main paths, widths, **variation templates**, **letter paths**, box corrections, **manual editing samples** (stain, region, bridge, line, protection, custom categories) |
| `yazi_yollari.crwm` | Pixel paths learned from writing (optional) |
| `sayfalar/` | Page images drawn from PDFs (PNG) |
| `universal_roots.crwm` | Croow color memory (optional; empty if absent) — can also be placed next to the app |
| `dil.txt` | Interface language (`tr` / `en`) |

- **Backup:** copy the `~/.croow/` folder. **Start from scratch:** rename/delete the folder. Trained memory and palette files do not go into the repository (`.gitignore`).
- Original images/PDFs are **not modified**. Brush and cleaning work on the on-screen working copy; nothing is written to disk unless you save (what was learned *is* saved).

## What Croow learns

| What you do | What Croow records | Where it helps |
|---|---|---|
| Confirm / correct a letter | Letter sample, virtual copy, pattern, main path, width, dirtiness level, common path | Reading probabilities, regular-form conversion |
| Correct a box | Box shift (relative to line height) | Boxes fit automatically on following pages |
| Teach a word | Word and neighbor counts, each letter's box | Gap filling, context correction |
| **Erase** with the brush | Shape, size, fill and position of the mark (+ 24×24 template) | **Reduce stains** (learned rule), suggestions, lowering letter similarity |
| Clean with the **large brush** | Region density, share of large marks, share resembling letters | **Risky** stain reduction / region cleaning |
| **Draw** | Length of the bridged gap | **Complete** |
| **Label a selection** | Stain / line → erase rule; text, redaction, stamp, signature → protection template; custom category → template + action | Erase steps leave protected things alone; purple probability marks |
| Call a suggestion **wrong** | That shape is added to the protection list | Never suggested again |

Learning is designed to be safe: a minimum sample count is required to derive a rule (stain ≥3, region ≥2, suggestion ≥5), and everything can be undone with `Ctrl+Z`.

## Reading test

`uygulama/okuma_testi.py` measures fairly by **separating the lines it was taught from the lines it is tested on**:

```bash
python uygulama/okuma_testi.py page.png correct_text.txt              # teach from the first half, read the rest
python uygulama/okuma_testi.py page.png correct_text.txt --egit 0.3   # teach from the first 30%
python uygulama/okuma_testi.py page.png correct_text.txt --egit 0     # teach nothing (needs the general palette)
python uygulama/okuma_testi.py page.png correct_text.txt --capraz     # cross-check with even/odd lines
python uygulama/okuma_testi.py page.png correct_text.txt --metin folder/   # .txt folder for context
python uygulama/okuma_testi.py page.png correct_text.txt --goster     # line by line: correct / read
```

`correct_text.txt`: the lines on the page, one per line, in page order. Output: character and word accuracy (edit distance), without and with context. It uses a temporary store and does not touch your data.

## Run from source

```bash
pip install pillow numpy pypdfium2
python uygulama/croow_reader.py          # Croow MultiReader (needs tkinter)
python egitim/croow_egit.py <photo_folder> --hafiza universal_roots.crwm   # color-memory training (optional)
```

| Folder | Content |
|---|---|
| `uygulama/` | MultiReader: interface (`croow_reader.py`, `croow_gorunum.py`, `croow_dosya.py`, `dil.py`/`dil_en.py` for language), letter store and reading (`belge_harf.py`, `crw_harf.py`), CriCroow7 (`cricroow.py`), PDF (`crw_pdf.py`, `pdf_motor.py`), reading test |
| `motor/` | CRW encoder/decoder (`crw_motor.py`), color memory (`roots_memory.py`), pixel paths (`paths_memory.py`) |
| `egitim/` | Color-memory training script |
| `paketleme/` | Icons, PyInstaller recipe, Windows installer wizard, Linux AppImage files |
| `.github/workflows/` | On every `v*` tag, builds the Windows, macOS and Linux installers |

> Source code, identifiers and file names are in Turkish (the project's original language); the interface and this guide are available in English.

## Open to ideas · Contact

Croow is a young project that **improves by learning**, and we learn most from **the people who use it**. Ideas that would improve reading accuracy, misread examples, difficult documents, usability suggestions, bug reports and contributions are all very welcome. Write as you like:

**📧 pektalper@croowsearch.com**

You can also open *Issues* on GitHub for bugs and suggestions. In a bug report, a small crop of the page (if you can share it), what you did, and the message in the bottom bar help a lot.

## License

Copyright (C) 2026 Alper Pektas

This program is licensed under the **GNU Affero General Public License v3 (AGPLv3)** (`LICENSE`). Additional terms are in the `NOTICE` file:

- The author notice ("Croow — Alper Pektas tarafından geliştirilmiştir.", i.e. "Developed by Alper Pektas") must be kept in the source, in every copy, in documentation and in the user interface.
- Modified versions must not be presented as the original Croow.
- Anyone who offers this program or a modified version as a network service must make the complete source code available to its users (AGPLv3 Section 13).
