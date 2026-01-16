#!/usr/bin/env python3
"""
WordPress Uploads Image Optimizer

Resize images under wp-content/uploads by year or across all years.

Examples:
  # Single year (default uploads path relative to current dir)
  ./optimize-images.py 2026

  # Single year with explicit uploads base
  ./optimize-images.py 2026 --uploads /var/www/site/wp-content/uploads

  # All years by pointing at wp-content (or uploads)
  ./optimize-images.py --all-uploads /home/user/public_html/wp-content/

  # Dry run
  ./optimize-images.py 2026 --uploads /var/www/site/wp-content/uploads --dry-run

Notes:
- Preserves ownership, permissions, and timestamps even when run as root.
- Supports: JPG/JPEG/PNG (case-insensitive).
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


def resolve_uploads_base(path_str: str) -> Path:
    """
    Accepts any of:
      - /path/to/wp-content/uploads
      - /path/to/wp-content
      - /path/to/site-root (containing wp-content/uploads)
    Returns the resolved uploads base directory path.

    Raises ValueError if not found.
    """
    p = Path(path_str).expanduser().resolve()

    # If user already pointed to uploads
    cand1 = p
    # If user pointed to wp-content
    cand2 = p / "uploads"
    # If user pointed to site root
    cand3 = p / "wp-content" / "uploads"

    for cand in (cand1, cand2, cand3):
        if cand.exists() and cand.is_dir() and cand.name == "uploads":
            return cand

    # Also accept cand2/cand3 even if the folder name isn't exactly uploads
    # but path ends with wp-content or site-root (common in real usage).
    if cand2.exists() and cand2.is_dir():
        return cand2
    if cand3.exists() and cand3.is_dir():
        return cand3

    raise ValueError(
        f"Could not find an uploads directory under: {p}\n"
        f"Tried: {cand1}, {cand2}, {cand3}"
    )


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

        # Restore ownership (works as root; otherwise ignore PermissionError)
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

            # Ensure mode compatible with JPEG
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


def iter_year_dirs(uploads_base: Path):
    """
    Yield year directories (YYYY) under uploads_base, sorted ascending.
    Only directories matching 4 digits are considered.
    """
    years = []
    for child in uploads_base.iterdir():
        if child.is_dir() and child.name.isdigit() and len(child.name) == 4:
            years.append(child)
    for yd in sorted(years, key=lambda p: p.name):
        yield yd


def process_tree(root_dir: Path, max_w: int, max_h: int, dry_run: bool, backup: bool):
    total = changed = skipped = errors = 0

    for r, _, files in os.walk(root_dir):
        for name in files:
            p = Path(r) / name
            if not is_supported_image(p):
                continue

            total += 1
            try:
                result = process_image(p, max_w, max_h, dry_run, backup)
                if result in ("ok", "dry"):
                    changed += 1
                else:
                    skipped += 1
            except Exception as e:
                errors += 1
                print(f"[ERR] {p}: {e}", file=sys.stderr)

    return total, changed, skipped, errors


def main():
    parser = argparse.ArgumentParser(description="Resize WordPress uploads images safely.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("year", nargs="?", help="Uploads year folder (e.g., 2026)")
    group.add_argument(
        "--all-uploads",
        metavar="PATH",
        help="Process every year folder found under uploads. "
             "PATH may point to wp-content/uploads, wp-content, or site root."
    )

    parser.add_argument(
        "--uploads",
        default="wp-content/uploads",
        help="Path to wp-content/uploads (default: wp-content/uploads). "
             "Used only when processing a single year."
    )
    parser.add_argument("--max-width", type=int, default=2000, help="Max width (default: 2000)")
    parser.add_argument("--max-height", type=int, default=1000, help="Max height (default: 1000)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change; write nothing")
    parser.add_argument("--backup", action="store_true", help="Create .bak copies before overwriting")

    args = parser.parse_args()

    grand_total = grand_changed = grand_skipped = grand_errors = 0

    if args.all_uploads:
        try:
            uploads_base = resolve_uploads_base(args.all_uploads)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)

        year_dirs = list(iter_year_dirs(uploads_base))
        if not year_dirs:
            print(f"ERROR: No year folders (YYYY) found in {uploads_base}", file=sys.stderr)
            sys.exit(2)

        print(f"Uploads base: {uploads_base}")
        print(f"Year folders: {', '.join([p.name for p in year_dirs])}\n")

        for yd in year_dirs:
            print(f"=== Processing year {yd.name} ===")
            total, changed, skipped, errors = process_tree(
                yd, args.max_width, args.max_height, args.dry_run, args.backup
            )
            print(f"Year {yd.name} done: scanned={total} resized={changed} skipped={skipped} errors={errors}\n")

            grand_total += total
            grand_changed += changed
            grand_skipped += skipped
            grand_errors += errors

    else:
        # Single year mode
        base = Path(args.uploads).expanduser().resolve()
        target = (base / str(args.year)).resolve()

        if not base.exists():
            print(f"ERROR: uploads path not found: {base}", file=sys.stderr)
            sys.exit(2)

        if not target.exists() or not target.is_dir():
            print(f"ERROR: year folder not found: {target}", file=sys.stderr)
            sys.exit(2)

        print(f"Uploads base: {base}")
        print(f"Target year:  {args.year}\n")

        total, changed, skipped, errors = process_tree(
            target, args.max_width, args.max_height, args.dry_run, args.backup
        )

        grand_total += total
        grand_changed += changed
        grand_skipped += skipped
        grand_errors += errors

    print("Done.")
    print(f"Scanned:  {grand_total}")
    print(f"Resized:  {grand_changed}")
    print(f"Skipped:  {grand_skipped}")
    print(f"Errors:   {grand_errors}")

    if grand_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
