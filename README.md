# WordPress Uploads Image Optimizer

A production-safe Python script for resizing large images in a WordPress
`wp-content/uploads` directory — without breaking file permissions, even when run as `root`.

It can process a single year (e.g. `uploads/2026/**`) or automatically process
all year folders found under `wp-content/uploads`.

---

## Features

- Recursively processes WordPress uploads folders
- Supports JPG / JPEG / PNG (case-insensitive extensions)
- Preserves ownership, permissions, and timestamps
- Safe to run as root or site user
- Skips images already within limits
- Correctly handles EXIF orientation
- Optional dry-run mode
- Optional .bak backups
- Atomic file replacement (no partial writes)

---

## Default Resize Rules

- Max width: 2000px
- Max height: 1000px
- Aspect ratio preserved
- Images are never upscaled

---

## Requirements

- Python 3.9+ (tested with Python 3.12)
- Pillow (PIL fork)

```bash
python3 -m pip install --user pillow
```

---

## Usage

### Single year

```bash
python optimize-images.py 2026 --uploads /home/USER/public_html/wp-content/uploads
```

### All uploads years

```bash
python optimize-images.py --all-uploads /home/USER/public_html/wp-content/uploads
```

---

## Command-Line Options

| Option | Description |
|------|-------------|
| YEAR | Process a single year |
| --uploads PATH | Path to wp-content/uploads |
| --all-uploads PATH | Process all year folders |
| --max-width | Max width (default: 2000) |
| --max-height | Max height (default: 1000) |
| --dry-run | No changes |
| --backup | Create .bak files |

---

## Permissions & Safety

The script preserves file ownership, permissions, and timestamps even when run as root.

---

## License

MIT License

---

## Author

Chris White
