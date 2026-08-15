"""
Convert an article's markdown into clean, standalone HTML for pasting into
Substack's editor.

Not a general-purpose markdown parser — a small, targeted converter for
this project's article format specifically (headings, paragraphs, images,
bold/italic, links, horizontal rules). No pandoc or Python markdown
library was available in this environment, so this exists as the fallback
the task asked for rather than an external dependency.

WORKFLOW: Substack's editor turns pasted RICH TEXT into formatted content,
not pasted raw HTML source — pasting this file's text directly would just
show literal tags. Open the generated .html file in a browser, select all,
copy, and paste into Substack; the browser's rendered copy carries the
formatting across. Minimal inline CSS here is for a legible local preview
before copying, not meant to survive into Substack (which restyles
everything with its own theme once pasted).

USAGE:
    python articles/convert_to_substack_html.py articles/2026-08-hospital-waiting-lists/article.md
"""

import re
import sys
from pathlib import Path


def convert_inline(text: str) -> str:
    """Bold, italic, links — applied to a single block of prose text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


def convert_block(block: str) -> str:
    stripped = block.strip()

    if stripped == "---":
        return "<hr>"

    heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
    if heading_match:
        level = len(heading_match.group(1))
        return f"<h{level}>{convert_inline(heading_match.group(2))}</h{level}>"

    image_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", stripped)
    if image_match:
        alt, src = image_match.group(1), image_match.group(2)
        return f'<img src="{src}" alt="{alt}" style="max-width:100%;height:auto;">'

    # A block that's just "*Italic Text*" (e.g. the byline) — treat as its
    # own paragraph rather than requiring a separate blockquote syntax.
    return f"<p>{convert_inline(stripped)}</p>"


def convert(markdown_text: str) -> str:
    blocks = re.split(r"\n\s*\n", markdown_text.strip())
    html_blocks = [convert_block(b) for b in blocks if b.strip()]
    return "\n\n".join(html_blocks)


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: Georgia, 'Times New Roman', serif; max-width: 700px; margin: 40px auto; padding: 0 20px; color: #1A1A1A; line-height: 1.6; }}
  h1 {{ font-size: 2em; line-height: 1.2; }}
  h2 {{ font-size: 1.4em; margin-top: 2em; }}
  img {{ display: block; margin: 1.5em 0; border: 1px solid #E5E5E5; }}
  a {{ color: #169B62; }}
  hr {{ border: none; border-top: 1px solid #E5E5E5; margin: 2em 0; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def main():
    if len(sys.argv) != 2:
        print("Usage: python articles/convert_to_substack_html.py <article.md>")
        sys.exit(1)

    md_path = Path(sys.argv[1])
    markdown_text = md_path.read_text()

    title_match = re.search(r"^#\s+(.*)$", markdown_text, re.MULTILINE)
    title = title_match.group(1) if title_match else md_path.stem

    body_html = convert(markdown_text)
    full_html = HTML_TEMPLATE.format(title=title, body=body_html)

    output_path = md_path.parent / "for-substack.html"
    output_path.write_text(full_html)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
