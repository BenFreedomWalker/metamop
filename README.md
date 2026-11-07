# MetaMop

**A lightweight, offline-first metadata cleaner.**

MetaMop inspects image metadata and creates cleaned copies without modifying your originals. It uses Python, Tkinter, and Pillow.

## First milestone

- Add individual images or scan a folder recursively.
- Inspect image properties and available metadata.
- Create metadata-light copies in a separate output folder.
- Keep original files untouched.
- Work offline; no files are uploaded anywhere.

### Supported image formats

JPEG, PNG, WebP, TIFF, and BMP.

Animated and multi-page images are intentionally skipped in this first milestone. JPEG files are re-encoded at high quality when cleaned; other supported formats are rewritten without descriptive metadata. Embedded ICC color profiles are retained when available to avoid unnecessary color shifts.

## Requirements

- Python 3.10 or newer
- Tkinter (included with most Windows Python installations)
- Pillow

## Run on Windows

Double-click `build.bat`. It creates a local virtual environment, installs dependencies, and starts MetaMop.

Or run manually:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux:
source .venv/bin/activate
python -m pip install -r requirements.txt
python metamop.py
```

## Current limitations

This is the first development milestone. Audio, video, PDF, and office-document metadata support is planned for later work. Metadata embedded in unusual format-specific structures may not be covered yet. Always review the output before sharing important files.

## Project

- **Issues:** https://github.com/BenFreedomWalker/metamop/issues
- **License:** GNU General Public License v3.0 or later — see [LICENSE](LICENSE).

MetaMop is provided without warranty.
