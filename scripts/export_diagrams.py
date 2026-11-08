"""Export the report's figures as standalone SVG files for the README.

The report in docs/report/ is the single source of the diagrams. Its inline
SVGs take their colours from the page's CSS, so on their own they would show
up black on black in GitHub's dark mode. This script copies each figure into
its own file and adds the styles it needs: a light palette, a dark palette
for readers whose system is set to dark, and a solid background.

Run it again after changing a figure in the report:

    make diagrams
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "report" / "open-weight-llm-risk-review.html"
OUT_DIR = ROOT / "docs" / "diagrams"

# One file name per figure, in the order the figures appear in the report.
NAMES = (
    "01-bare-vs-harnessed.svg",
    "02-governed-loop.svg",
    "03-context-provenance.svg",
    "04-hosted-vs-local.svg",
)

LIGHT = {
    "bg": "#ffffff", "sunk": "#eceff3", "surface": "#ffffff", "ink": "#17212c",
    "muted": "#586473", "line": "#9aa6b4", "accent": "#1f4e8c", "accent-soft": "#e5ecf6",
    "risk": "#b42318", "risk-soft": "#fbe9e7", "ok": "#2f6b3a", "ok-soft": "#e6f2e8",
}
DARK = {
    "bg": "#0f151c", "sunk": "#151d26", "surface": "#18222d", "ink": "#e5eaf0",
    "muted": "#9ba7b5", "line": "#4f5e6e", "accent": "#86ade3", "accent-soft": "#1c2a3c",
    "risk": "#f08a7f", "risk-soft": "#3a1f1d", "ok": "#82c891", "ok-soft": "#1b3022",
}

RULES = """
text { fill: var(--ink); font-family: "IBM Plex Sans", "Segoe UI", system-ui, -apple-system, sans-serif;
       font-size: 13px; }
.t-lbl { fill: var(--muted); font-size: 11px; }
.t-ttl { font-weight: 600; font-size: 14px; }
.t-risk { fill: var(--risk); }
.bg { fill: var(--bg); }
.panel { fill: var(--sunk); stroke: none; }
.box { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
.box-accent { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 1.2; }
.box-risk { fill: var(--risk-soft); stroke: var(--risk); stroke-width: 1.2; }
.box-ok { fill: var(--ok-soft); stroke: var(--ok); stroke-width: 1.2; }
.boundary { fill: none; stroke: var(--line); stroke-width: 1.2; stroke-dasharray: 6 4; }
.edge { stroke: var(--ink); stroke-width: 1.4; fill: none; }
.edge-risk { stroke: var(--risk); stroke-width: 1.4; fill: none; }
.edge-dash { stroke: var(--line); stroke-width: 1.2; stroke-dasharray: 4 4; fill: none; }
.ah { fill: var(--ink); }
.ah-risk { fill: var(--risk); }
.ah-muted { fill: var(--line); }
"""


def _variables(palette: dict[str, str]) -> str:
    """Write a palette as CSS custom properties.

    Args:
        palette: Token names mapped to colours.

    Returns:
        The declarations, for example ``--ink: #17212c;``.
    """
    return " ".join(f"--{name}: {value};" for name, value in palette.items())


def _style() -> str:
    """Build the style block shared by every exported figure.

    Returns:
        A ``<style>`` element with both palettes and the diagram rules.
    """
    return (
        "<style>\n"
        f"svg {{ {_variables(LIGHT)} }}\n"
        f"@media (prefers-color-scheme: dark) {{ svg {{ {_variables(DARK)} }} }}\n"
        f"{RULES}</style>"
    )


def standalone(figure: str, markers: str) -> str:
    """Turn one inline figure from the report into a self-contained SVG file.

    Args:
        figure: The ``<svg class="dg" ...>...</svg>`` markup from the report.
        markers: The ``<defs>`` block with the arrowhead markers.

    Returns:
        The SVG document as text.

    Raises:
        ValueError: If the figure has no viewBox.
    """
    view_box = re.search(r'viewBox="0 0 (\d+) (\d+)"', figure)
    if view_box is None:
        raise ValueError("figure has no viewBox")
    width, height = view_box.groups()
    opening, body = figure.split(">", 1)
    opening = opening.replace('class="dg" ', "")
    background = f'<rect class="bg" x="0" y="0" width="{width}" height="{height}"/>'
    return (
        f'{opening} xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n'
        f"{_style()}\n{markers}\n{background}\n{body}\n"
    )


def main() -> int:
    """Export every figure and report what was written.

    Returns:
        0 on success, 1 if the report does not hold the expected figures.
    """
    html = REPORT.read_text(encoding="utf-8")
    markers = re.search(r"<defs>.*?</defs>", html, re.S)
    figures = re.findall(r'<svg class="dg".*?</svg>', html, re.S)
    if markers is None or len(figures) != len(NAMES):
        sys.stderr.write(f"Expected {len(NAMES)} figures and arrow markers in {REPORT}, "
                         f"found {len(figures)} figures.\n")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, figure in zip(NAMES, figures):
        (OUT_DIR / name).write_text(standalone(figure, markers.group(0)), encoding="utf-8")
        sys.stdout.write(f"wrote docs/diagrams/{name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
