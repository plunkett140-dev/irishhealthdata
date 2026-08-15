"""
Utility: stitch two already-generated chart PNGs side by side into one
composite image, for articles that compare two hospitals/charts directly.

Deliberately a post-processing composite of two independently-correct,
independently-regenerable PNGs, not a new data visualization in its own
right — each source chart is still produced (and can be fact-checked) on
its own by its own script; this just makes them easy to view together.
Keeps each chart's own scale/axis rather than forcing a shared y-axis,
since forcing one would misrepresent charts being compared precisely
because they're at different scales.

USAGE:
    python charts/side_by_side.py <left.png> <right.png> <output.png>
"""

import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]

GAP_PX = 24
BACKGROUND = (255, 255, 255)


def stitch(left_path: Path, right_path: Path, output_path: Path) -> None:
    left = Image.open(left_path)
    right = Image.open(right_path)

    # Match heights (pad the shorter one, don't stretch) so neither chart's
    # own proportions get distorted.
    height = max(left.height, right.height)
    width = left.width + GAP_PX + right.width

    canvas = Image.new("RGB", (width, height), BACKGROUND)
    canvas.paste(left, (0, (height - left.height) // 2))
    canvas.paste(right, (left.width + GAP_PX, (height - right.height) // 2))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    print(f"Composite saved: {output_path}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python charts/side_by_side.py <left.png> <right.png> <output.png>")
        sys.exit(1)

    left_path, right_path, output_path = (Path(p) for p in sys.argv[1:4])
    stitch(left_path, right_path, output_path)


if __name__ == "__main__":
    main()
