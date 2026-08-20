"""Remove white backdrop and trim mockup PNGs for landing page."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "public" / "assets" / "images"
FILES = [
    "landing-mockup-hero.png",
    "landing-mockup-chat.png",
    "landing-mockup-phone.png",
    "landing-mockup-card.png",
]


def is_background_pixel(r: int, g: int, b: int, tolerance: int) -> bool:
    return r >= 255 - tolerance and g >= 255 - tolerance and b >= 255 - tolerance


def flood_remove_background(image: Image.Image, tolerance: int = 22) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visited = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            if is_background_pixel(*pixels[x, y][:3], tolerance):
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_background_pixel(*pixels[x, y][:3], tolerance):
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or visited[y][x]:
            continue
        if not is_background_pixel(*pixels[x, y][:3], tolerance):
            continue
        visited[y][x] = True
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    return rgba


def trim_transparent(image: Image.Image, padding: int = 8) -> Image.Image:
    bbox = image.getbbox()
    if not bbox:
        return image
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def main() -> None:
    for name in FILES:
        path = ASSETS / name
        if not path.exists():
            print(f"skip missing: {name}")
            continue
        original = Image.open(path)
        processed = trim_transparent(flood_remove_background(original))
        processed.save(path, format="PNG", optimize=True)
        print(f"{name}: {original.size} -> {processed.size} (RGBA)")


if __name__ == "__main__":
    main()
