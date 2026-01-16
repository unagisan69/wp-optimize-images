#!/usr/bin/env python3
"""
Optimize WordPress uploads for a given year.

Examples:
  ./optimize-images.py 2026
  ./optimize-images.py 2026 --uploads /var/www/site/wp-content/uploads
  ./optimize-images.py 2026 --dry-run
  ./optimize-images.py 2026 --backup
"""

import argparse
import os
import sys
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}  # case-insensitive via .lower()


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTS


def compute_new_size(w: int, h: int, max_w: int, max_h: int):
    """Return (new_w, new_h) maintaining aspect ratio, never upscaling."""
    if w <= max_w and h <= max_h:
        return w, h

    scale = min(max_w / w, max_h / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return new_w, new_h


def atomic_save_preserve_metadata(img: Image.Image, dest_path: Path, fmt: str, save_kwargs: dict):
    """
    Save to a temp file in the same directory, copy dest file metadata to the temp file,
    then atomically replace dest with temp. Preserves perms/owner even when run as root.
    """
    st = os.stat(dest_path)
    mode = st.st_mode & 0o7777
    uid = st.st_uid
    gid = st.st_gid
    atime = st.st_atime
    mtime = st.st_mtime

    dest_dir = dest_path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".imgopt_", dir=str(dest_dir))
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        img.save(tmp_path, format=fmt, **save_kwargs)

        # Restore permissions
        os.chmod(tmp_path, mode)

        # Restore ownership (only works as root)
        try:
            os.chown(tmp_path, uid, gid)
        except PermissionError:
            pass

        # Restore timestamps
        os.utime(tmp_path, (atime, mtime))

        # Atomic replace
        os.replace(tmp_path, dest_path)

    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def process_image(path: Path, max_w: int, max_h: int, dry_run: bool, backup: bool) -> str:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)

        w, h = im.size
        new_w, new_h = compute_new_size(w, h, max_w, max_h)

        if (new_w, new_h) == (w, h):
            return "skip"

        if dry_run:
            print(f"[DRY] resize {path}  {w}x{h} -> {new_w}x{new_h}")
            return "dry"

        if backup:
            bak = path.with_suffix(path.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(path, bak)

        resized = im.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

        ext = path.suffix.lower()
        if ext in {".jpg", ".jpeg"}:
            fmt = "JPEG"
            save_kwargs = {"quality": 85, "optimize": True, "progressive": True}

            if resized.mode in ("RGBA", "LA"):
                resized = resized.convert("RGB")
            elif resized.mode != "RGB":
                resized = resized.convert("RGB")
        else:
            fmt = "PNG"
            save_kwargs = {"optimize": True}

        atomic_save_preserve_metadata(resized, path, fmt, save_kwargs)
        print(f"[OK]  resize {path}  {w}x{h} -> {new_w}x{new_h}")
        return "ok"


def main():
    parser = argparse.ArgumentParser(description="Resize WP uploads images by year.")
    parser.add_argument("year", help="Uploads year folder (e.g., 2026)")
    parser.add_argument("--uploads", default="wp-content/uploads",
                        help="Path to wp-content/uploads (default: wp-content/uploads)")
    parser.add_argument("--max-width", type=int, default=2000, help="Max width (default: 2000)")
    parser.add_argument("--max-height", type=int, default=1000, help="Max height (default: 1000)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing")
    parser.add_argument("--backup", action="store_true", help="Create .bak copies before overwriting")
    args = parser.parse_args()

    base = Path(args.uploads).expanduser().resolve()
    target = (base / str(args.year)).resolve()


    if not base.exists():
        print(f"ERROR: uploads path not found: {base}", file=sys.stderr)
        sys.exit(2)

    if not target.exists() or not target.is_dir():
        print(f"ERROR: year folder not found: {target}", file=sys.stderr)
        sys.exit(2)

    total = changed = skipped = errors = 0

    for root, _, files in os.walk(target):
        for name in files:
            path = Path(root) / name
            if not is_supported_image(path):
                continue

            total += 1
            try:
                result = process_image(path, args.max_width, args.max_height, args.dry_run, args.backup)
                if result in ("ok", "dry"):
                    changed += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"[ERR] {path}: {e}", file=sys.stderr)

    print("\nDone.")
    print(f"Scanned:  {total}")
    print(f"Resized:  {changed}")
    print(f"Skipped:  {skipped}")
    print(f"Errors:   {errors}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
