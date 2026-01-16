# WordPress Uploads Image Optimizer

A production-safe Python script for resizing large images in a WordPress
`wp-content/uploads` directory by year — without breaking file permissions,
even when run as `root`.

The script recursively scans a year folder (e.g. `uploads/2026/**`) and ensures
images do not exceed a maximum width or height while preserving aspect ratio.

---

## Features

- Recursively processes a single WordPress uploads year
- Supports JPEG / JPG / PNG (case-insensitive extensions)
- Preserves ownership, permissions, and timestamps
- Safe to run as root or site user
- Skips images already within limits
- Correctly handles EXIF orientation
- Optional dry-run mode
- Optional backups before overwrite
- Atomic file replacement (no partial writes)

---

## Default Resize Rules

- Max width: **2000px**
- Max height: **1000px**
- Aspect ratio is always preserved
- Images are never upscaled

Limits can be overridden via command-line flags.

---

## Requirements

- Python **3.9+** (tested on 3.12)
- Pillow (PIL fork)

Install dependency:

```bash
python3 -m pip install --user pillow
```

---

## Usage

### Basic usage

```bash
./optimize-images.py 2026
```

### Specify uploads path explicitly

```bash
./optimize-images.py 2026 --uploads /home/USERNAME/public_html/wp-content/uploads
```

### Dry run (no files modified)

```bash
./optimize-images.py 2026 --dry-run
```

### Create backups

```bash
./optimize-images.py 2026 --backup
```

---

## Command-Line Options

| Option | Description |
|------|-------------|
| `year` | Uploads year folder (e.g. `2023`) |
| `--uploads` | Path to `wp-content/uploads` |
| `--max-width` | Max image width (default: 2000) |
| `--max-height` | Max image height (default: 1000) |
| `--dry-run` | Show changes without writing |
| `--backup` | Create `.bak` copies before overwrite |

---

## Permissions & Safety

The script preserves original file ownership, permissions, and timestamps even
when executed as `root`.

---

## License

MIT License

---

## Author

Chris White
