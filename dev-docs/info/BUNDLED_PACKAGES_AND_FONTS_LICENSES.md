# Bundled packages, fonts, and licenses (inventory)

**Purpose:** Living checklist of **third-party Python packages**, **vendored native binaries**, and **shipped fonts** that may appear in a **PyInstaller** (or source) distribution of DICOM Viewer V3, with pointers to **authoritative license text**.  
**Status:** Maintainer reference — **not** legal advice; product owners remain responsible for compliance, attribution, and source-offer obligations where licenses require them.  
**Last updated:** 2026-04-17

---

## Most restrictive components (built app only)

**Scope:** What typically ships in an **end-user frozen build** (PyInstaller-collected Python deps, **`resources/`** including fonts, and vendored FFmpeg). **Excluded:** test runners (**pytest**), dev-only tools, and **PyInstaller** itself (build host only).

### Summary assessment (commercial vs proprietary closed source)

**Basis:** Application version **`0.2.10`** ([`src/version.py`](../../src/version.py)), **`requirements.txt`** / wheel **`METADATA`**, and bundled fonts as reviewed on **2026-04-17**. Refresh this basis on every release after pin or bundle changes.

**Not legal advice** — distribution strategy needs qualified **IP counsel** for your exact binary layout and markets.

- **Two different axes:** **Commercial** means for-profit use (sales, paid services, internal use at a company). **Proprietary closed source** means you do **not** publish your application’s source under an open license. They are **orthogonal**: many products are **commercial + closed source**; open source can also be commercial (e.g. paid support). Copyleft cares about **redistribution and combination**, not “do you charge money?” alone.
- **Most direct Python dependencies** are **MIT / BSD / Apache-style**. Those generally **allow commercial distribution** and **do not force you to open-source your own code**, subject to **attribution / license-file** requirements.
- **PySide6 / Qt (LGPL path)** — Common pattern for **commercial, closed-source** desktop apps: comply with **LGPL** (notices, delivery/relinking rules as applicable per Qt documentation). That is **not** “must publish all viewer source on GitHub.”
- **FFmpeg (`imageio-ffmpeg`)** — Often shipped in **commercial** products; satisfy **FFmpeg** / wheel obligations (see **`AGENTS.md`**). Again, **not** automatically “entire app must be open source.”
- **`pylibjpeg-libjpeg` (GPL-3.0)** — This is the **main GPL copyleft** piece in the default **`requirements.txt`** stack for **JPEG Baseline / Extended** decoding. It is the usual **reason to call counsel** (or to **remove / replace** that decode path) if the goal is **closed source without GPL-style source-sharing duties** for the combined product. It does **not** mean permissive deps “turned the whole app GPL”; it means **this plugin** needs an explicit decision.
- **Liberation Sans** — **GPL-2.0** font binaries with an **embedding exception** for documents; still handle **font redistribution** compliance (on-disk **`License.txt`** / **`COPYING`**).

**Bottom line:** **Commercial** shipping is compatible with this dependency profile for many models. **Closed-source commercial** is **plausible** for much of the stack but expects **LGPL (Qt, possibly FFmpeg) hygiene** and a **resolved position on `pylibjpeg-libjpeg`** (legal sign-off or architectural alternative).

Rough ordering in the table is by **copyleft strength and common redistribution duties**, not a legal ranking—confirm with counsel for your distribution model.

| Priority | Component | License (summary) | Why it stands out |
|----------|-----------|-------------------|-------------------|
| **1** | **`pylibjpeg-libjpeg`** (JPEG decode plugin) | **GPL-3.0** (per wheel metadata) | **Strong copyleft** on native decoder code bundled with the app. Review **combined work** / linking interpretation and whether alternatives (e.g. other JPEG paths) are acceptable for a given SKU. |
| **2** | **FFmpeg** binary pulled in by **`imageio-ffmpeg`** | **LGPL** and/or **GPL** (build-dependent) | Native codec stack; obligations often include **notice**, **license text**, and for LGPL/GPL builds **source offer** / attribution. See **`AGENTS.md`** and project **CHANGELOG** cine-export notes. |
| **3** | **Liberation Sans** (`resources/fonts/liberation_sans/`) | **GPL-2.0** + **Red Hat font embedding exceptions** | Font binaries are **GPL-2.0**-licensed with **specific exceptions** for documents using the font—still requires **compliance for redistributing the font files** (read **`License.txt`** / **`COPYING`** in that folder). |
| **4** | **Qt** via **`PySide6`** | **LGPL-3.0-only** *or* **GPL-2.0/3.0** (upstream’s OR choice; commercial Qt license is a separate purchase) | Large GUI/native dependency. **LGPL** is **weaker copyleft than GPL** for many app-distribution patterns but still imposes **ongoing compliance** (notices, object code / relinking rules as applicable—see Qt Company LGPL materials). |

**Everything else** in the direct **`requirements.txt`** surface for this app is generally **permissive** (**MIT**, **BSD**, **Apache-2.0**, **MIT-CMU**, **SIL OFL 1.1** for most bundled fonts)—still requires **attribution** where the license says so.

**Caveat:** PyInstaller may **pull transitive wheels** not named in the tables below. For a **release SBOM**, run **`pip freeze`** (or **`pip-licenses`**) on the **exact** venv used to build the installer and scan for **GPL / LGPL / MPL / (L)GPL** family hits.

### Alternatives to `pylibjpeg-libjpeg` (JPEG Baseline / Extended)

The GPL-3.0 label applies to this **JPEG plugin**, not to the whole viewer. If you need a **closed-source-friendly** or **simpler-compliance** path for **lossy / lossless JPEG DICOM** (not JPEG 2000 / JPEG-LS), consider **engineering tradeoffs** below and verify against [pydicom compressed pixel data / decoder plugins](https://pydicom.github.io/pydicom/stable/guides/decoding/decoder_plugins.html) for your modality mix.

| Direction | License (typical) | Notes |
|-----------|-------------------|--------|
| **Pillow only** (already required) | **MIT-CMU** | **pydicom** may decode **some** JPEG transfer syntaxes via Pillow-related handlers. Coverage and **numerical / reversibility** behavior differ from **pylibjpeg**; pydicom documents when **pylibjpeg** is preferred. Often the first step in a “no `pylibjpeg-libjpeg`” experiment. |
| **Omit `pylibjpeg-libjpeg` from a build profile** | Removes that GPL wheel | Ship a variant **without** the plugin only if QA proves **acceptable decode coverage** for your customers (Pillow / other handlers). UX must set expectations if some JPEG instances fail. |
| **`PyTurboJPEG`** against **`libjpeg-turbo`** | **libjpeg-turbo** is commonly **BSD-style** (verify wheel/sdist) | **Not** wired in this repo today; would need **custom integration** with pydicom’s decoding pipeline and PyInstaller packaging validation. |
| **`python-gdcm` (GDCM)** | **LGPL / GPL** family (verify upstream) | Broad DICOM decompression support but **does not automatically remove copyleft** from the stack—compare obligations to staying on **pylibjpeg-libjpeg**. |
| **`pylibjpeg-openjpeg`**, **`pyjpegls`** (already in stack) | **MIT** | Cover **JPEG 2000** and **JPEG-LS**; they **do not** replace **Baseline / Extended JPEG** handled by **`pylibjpeg-libjpeg`**. |

---

## How to maintain this document

1. **Primary dependency list:** [`requirements.txt`](../../requirements.txt) (and [`requirements-build.txt`](../../requirements-build.txt) for frozen builds only).  
2. **Authoritative text:** Inspect each wheel’s **`*.dist-info/METADATA`** (`License`, `License-Expression`) and any **`LICENSE*`** files inside the installed package or its sdist — PyPI classifiers can be wrong or incomplete.  
3. **Quick audit (optional):** In an activated venv, tools such as **`pip-licenses`** (if installed) can dump a table; always **spot-check** GPL/LGPL/MPL families against primary sources.  
4. **Fonts:** Shipped files live under **`resources/fonts/`**; the registry in **`src/utils/bundled_fonts.py`** lists which TTFs the app registers. Each font subtree should retain its upstream **`OFL.txt`**, **`LICENSE`**, **`COPYING`**, or **`License.txt`** (do not strip these from releases).  
5. **When to update:** After any **`requirements.txt`** pin change, PyInstaller **`datas` / `binaries`** change, or font add/remove — update the tables below and bump **Last updated**.

---

## Python application dependencies

Direct pins from **`requirements.txt`** (versions are minimums or exact pins as in that file). **Transitive** dependencies (not listed) are still bundled when PyInstaller collects the import graph — use **`pip freeze`** on a release venv for a complete bill of materials.

| Package | Typical SPDX / summary (verify in wheel) | Notes |
|---------|------------------------------------------|--------|
| **PySide6** | **LGPL-3.0-only** OR **GPL-2.0-only** OR **GPL-3.0-only** (Qt Company choice); Qt Commercial also offered upstream | GUI stack; large shared libs. Frozen app includes Qt **plugins** and **translations** as collected by PyInstaller. |
| **pydicom** | **MIT** | DICOM I/O. |
| **numpy** | **BSD-3-Clause** (and other permissive components per metadata) | Core numerics. |
| **Pillow** | **MIT-CMU** (HPND-style) | Imaging / export pipeline. |
| **imageio** | **BSD-2-Clause** | Cine / video helpers. |
| **imageio-ffmpeg** | **BSD-2-Clause** (Python wrapper) | **Also vendors an FFmpeg binary** — see [Vendored native binaries](#vendored-native-binaries). |
| **matplotlib** | Project license (BSD-style components + **Matplotlib** license text in wheel) | Histogram and plotting backends (`backend_qtagg`). |
| **openpyxl** | **MIT** | Tag export **.xlsx**. |
| **sqlcipher3** | **MIT** (binding; **SQLCipher** itself is **BSD-style** upstream — confirm combined notice) | Local encrypted study index. |
| **keyring** | **MIT** | OS credential store for DB passphrase. |
| **SimpleITK** | **Apache-2.0** | Fusion resampling. |
| **pylinac** | **MIT** (`License-Expression` in current pin) | Phantom QA; pin verified per **`PYLINAC_INTEGRATION_OVERVIEW.md`**. |
| **scipy** | **BSD-3-Clause** (legacy header in metadata) | pylinac / numerics. |
| **scikit-image** | **BSD-3-Clause** | pylinac imaging. |
| **pypdf** | **BSD-3-Clause** | PDF merge for QA reports. |
| **pylibjpeg** | (verify wheel) | JPEG plugin host. |
| **pylibjpeg-libjpeg** | **GPL-3.0** (stated in wheel metadata) | **Copyleft** — distribution implications for combined works; confirm policy with legal review before shipping in restricted environments. |
| **pylibjpeg-openjpeg** | **MIT** | JPEG 2000 plugin. |
| **pylibjpeg-rle** | (verify wheel) | RLE plugin. |
| **pyjpegls** | **MIT** | JPEG-LS. |

**Test-only** packages in the same file (**pytest**, **Pygments**) are usually **not** shipped in end-user executables unless accidentally collected — keep PyInstaller **`excludes`** aligned with **`tests/test_pyinstaller_exclude_audit.py`**.

---

## Vendored native binaries

| Component | Source | License (summary) | Notes |
|-----------|--------|-------------------|--------|
| **FFmpeg** (via **imageio-ffmpeg**) | Binary extracted at runtime from the **imageio-ffmpeg** wheel | **LGPL / GPL** family (build configuration–dependent) | **`IMAGEIO_FFMPEG_EXE`** may redirect to a system FFmpeg; frozen builds must still satisfy **FFmpeg license obligations** (attribution, license texts, source offers where required). See **`AGENTS.md`** (cine export) and **`CHANGELOG`** cine/video entries. |

---

## Bundled fonts (`resources/fonts/`)

Registered in **`src/utils/bundled_fonts.py`**. **Authoritative** license text is in each directory next to the TTFs.

| Family (app name) | Upstream / style | License file(s) in repo | SPDX / summary |
|-------------------|------------------|-------------------------|----------------|
| **IBM Plex Sans** | IBM Plex | `resources/fonts/IBM_Plex_Sans/OFL.txt` | **SIL OFL 1.1** |
| **Noto Sans** | Google Noto | `resources/fonts/Noto_Sans/OFL.txt` | **SIL OFL 1.1** |
| **Noto Serif** | Google Noto | `resources/fonts/Noto_Serif/OFL.txt` | **SIL OFL 1.1** |
| **Open Sans** | Google Fonts | `resources/fonts/Open_Sans/OFL.txt` | **SIL OFL 1.1** |
| **Liberation Sans** | Red Hat Liberation | `resources/fonts/liberation_sans/License.txt`, `COPYING` | **GPL-2.0** + **font embedding exceptions** (read full text) |
| **Raleway** | Impallari / collaborators | `resources/fonts/Raleway/OFL.txt` | **SIL OFL 1.1** |
| **Red Hat Text** | Red Hat | `resources/fonts/Red_Hat_Text/OFL.txt` | **SIL OFL 1.1** |
| **Spectral** | Production Type | `resources/fonts/Spectral/OFL.txt` | **SIL OFL 1.1** |
| **DejaVu Sans** | DejaVu project | *(if `DejaVuSans.ttf` / `DejaVuSans-Bold.ttf` are shipped under `resources/fonts/`)* | **Bitstream Vera / DejaVu fonts license** (permissive; confirm **`LICENSE`** next to files when added) |

If **DejaVu** files are absent from the repo but referenced in **`bundled_fonts.py`**, treat them as **optional payload**: either ship with license or remove registry entries until files exist.

---

## Build-only tooling (usually not in app bundle)

| Package | Role | License (typical) |
|---------|------|-------------------|
| **PyInstaller** | Frozen executable | **GPL-2.0-or-later** with bootloader exception — see PyInstaller docs |
| **UPX** (optional) | Compress binaries | **GPL-2.0+** |

See **`dev-docs/info/BUILDING_EXECUTABLES.md`** and **`DICOMViewerV3.spec`**.

---

## Related project notes

- **Executable size / trims:** [`PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`](PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md)  
- **Code signing / notarization (macOS):** [`CODE_SIGNING_AND_NOTARIZATION.md`](CODE_SIGNING_AND_NOTARIZATION.md)  
- **Release process:** [`../RELEASING.md`](../RELEASING.md), [`SEMANTIC_VERSIONING_GUIDE.md`](SEMANTIC_VERSIONING_GUIDE.md)

---

## Revision history (this file)

| Date | Notes |
|------|--------|
| 2026-04-17 | Top **Summary assessment** (commercial vs closed source); **`pylibjpeg-libjpeg` alternatives** table (Pillow, omit plugin, TurboJPEG, GDCM, MIT plugins); removed duplicate “Does this block…” prose. |
| 2026-04-17 | After restrictive summary: **Commercial vs proprietary** note with **assessment basis** (`__version__` **0.2.10**, date **2026-04-17**). |
| 2026-04-17 | Added **Most restrictive components (built app only)** summary (GPL/LGPL stack + Liberation fonts + caveat on transitive deps). |
| 2026-04-17 | Initial inventory: Python deps from `requirements.txt`, FFmpeg note, fonts from `bundled_fonts.py` + `resources/fonts/` license files. |
