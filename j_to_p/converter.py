import argparse
import os
import sys
import time
from pathlib import Path

try:
    from PIL import Image
except Exception:
    print("Pillow is required. Install with: pip install -r requirements.txt")
    sys.exit(1)

WATCHDOG_AVAILABLE = True
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except Exception:
    WATCHDOG_AVAILABLE = False


def is_jpeg(path: Path):
    return path.suffix.lower() in (".jpg", ".jpeg")


def wait_for_stable(path: Path, wait_seconds: float = 1.0, attempts: int = 5):
    last_size = -1
    for _ in range(attempts):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last_size:
            return True
        last_size = size
        time.sleep(wait_seconds)
    return True


def convert_to_png(src: Path, dst_dir: Path):
    if not is_jpeg(src):
        return
    if not wait_for_stable(src):
        print(f"Файл недоступен: {src}")
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (src.stem + ".png")
    try:
        with Image.open(src) as im:
            rgb = im.convert("RGB")
            rgb.save(dst, format="PNG")
        print(f"Converted: {src} -> {dst}")
    except Exception as e:
        print(f"Ошибка конвертации {src}: {e}")


class JpegHandler(FileSystemEventHandler):
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        convert_to_png(path, self.out_dir)

    def on_moved(self, event):
        if event.is_directory:
            return
        path = Path(event.dest_path)
        convert_to_png(path, self.out_dir)


def poll_loop(in_dir: Path, out_dir: Path, interval: float = 1.0):
    seen = set()
    while True:
        for p in in_dir.iterdir():
            if p.is_file() and is_jpeg(p) and p not in seen:
                convert_to_png(p, out_dir)
                seen.add(p)
        time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description="Watch folder and convert JPEG->PNG")
    p.add_argument("--input", "-i", required=False, help="Input folder to watch (если не указан — будет диалог выбора)")
    p.add_argument("--output", "-o", required=False, help="Output folder for PNGs (если не указан — будет диалог выбора)")
    p.add_argument("--use-watchdog", action="store_true", help="Use watchdog if installed")
    p.add_argument("--poll-interval", type=float, default=1.0, help="Polling interval seconds (if not using watchdog)")
    args = p.parse_args()

    def choose_directory(prompt: str) -> Path:
        # Попробовать GUI (tkinter), иначе консольный ввод
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            sel = filedialog.askdirectory(title=prompt)
            root.destroy()
            if sel:
                return Path(sel).expanduser().resolve()
        except Exception:
            pass
        # Консольный ввод как fallback
        while True:
            sel = input(f"{prompt} (введите путь или оставьте пустым для отмены): ").strip()
            if not sel:
                print("Отмена выбора папки.")
                sys.exit(1)
            pth = Path(sel).expanduser().resolve()
            if pth.exists() and pth.is_dir():
                return pth
            print("Папка не найдена, попробуйте ещё раз.")

    in_dir = Path(args.input).expanduser().resolve() if args.input else None
    out_dir = Path(args.output).expanduser().resolve() if args.output else None

    if in_dir is None:
        in_dir = choose_directory("Выберите входную папку с JPEG")
    if out_dir is None:
        out_dir = choose_directory("Выберите выходную папку для PNG")

    if not in_dir.exists():
        print(f"Входная папка не найдена: {in_dir}")
        sys.exit(1)

    print(f"Watching {in_dir} -> {out_dir}")

    if args.use_watchdog and WATCHDOG_AVAILABLE:
        handler = JpegHandler(out_dir)
        observer = Observer()
        observer.schedule(handler, str(in_dir), recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        if args.use_watchdog and not WATCHDOG_AVAILABLE:
            print("watchdog не установлена, переключаюсь на polling")
        try:
            poll_loop(in_dir, out_dir, args.poll_interval)
        except KeyboardInterrupt:
            print("Остановлено пользователем")


if __name__ == "__main__":
    main()
