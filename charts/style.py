"""
Week 7 (rebranded Decision 011, 2026-08-13): Charting standards for
Ireland in Data.

Every chart on the site must call apply_style() and finish_chart() so that
fonts, colours, and the source/methodology footer are consistent everywhere
— per the Design Philosophy's Reproducibility and Transparency principles.
No chart should ever set its own one-off colours or skip the footer.
"""

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# --- Palette ---
# Brand palette per Decision 011: Irish flag green as primary, the existing
# coral kept for the "12+ Months" bucket (verified it still reads well
# against the new primary — see the regenerated PNGs checked in alongside
# that decision), colourblind-safe ordering maintained.
COLOR_PRIMARY = "#169B62"      # Irish flag green — main data series
COLOR_SECONDARY = "#D9541F"    # coral — comparison/second series, kept from the old palette
COLOR_MUTED = "#8A8D93"        # gridlines, annotations
COLOR_BACKGROUND = "#FFFFFF"
COLOR_TEXT = "#1A1A1A"
# PALETTE[2] changed from the old "#2E8B57" (sea green) to avoid sitting
# right next to the new green COLOR_PRIMARY in any future multi-series
# chart — everything else unchanged.
PALETTE = [COLOR_PRIMARY, COLOR_SECONDARY, "#2C6E8C", "#7B4FA0", "#C9A227"]

# Semantic traffic-light scheme (Decision 011) for the three wait-length
# buckets used across every chart that shows Under 6 / 6-12 / 12+ Months
# (see wait_time_buckets.py) — replaces the old arbitrary PALETTE-index
# assignment. Green/amber/red map directly onto "on track / moderate wait /
# long wait worth flagging", which needs no legend-reading to interpret.
# Single source of truth: hospital_band_breakdown.py and
# national_specialty_trend.py import this directly rather than each
# defining their own copy.
BUCKET_COLORS = {
    "Under 6 Months": COLOR_PRIMARY,   # green
    "6-12 Months": "#EF9F27",          # amber
    "12+ Months": COLOR_SECONDARY,     # coral/red
}

FONT_FAMILY = "DejaVu Sans"  # widely available; swap for a licensed brand font later if desired


def apply_style():
    plt.rcParams.update({
        "font.family": FONT_FAMILY,
        "figure.facecolor": COLOR_BACKGROUND,
        "axes.facecolor": COLOR_BACKGROUND,
        "axes.edgecolor": COLOR_MUTED,
        "axes.labelcolor": COLOR_TEXT,
        "axes.grid": True,
        "grid.color": "#E5E5E5",
        "grid.linewidth": 0.6,
        "text.color": COLOR_TEXT,
        "xtick.color": COLOR_TEXT,
        "ytick.color": COLOR_TEXT,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 11,
        "axes.titlesize": 15,
        "axes.titleweight": "bold",
    })


def add_footer(fig, source: str, last_updated: str, methodology_note: str = None):
    """Every chart gets this footer — Source / Last updated / Methodology,
    per the Transparency principle. Not optional."""
    footer_text = f"Source: {source}  |  Last updated: {last_updated}"
    if methodology_note:
        footer_text += f"\n{methodology_note}"
    fig.text(
        0.01, 0.01, footer_text,
        fontsize=8, color=COLOR_MUTED, ha="left", va="bottom",
    )


def finish_chart(fig, output_path: str, source: str, last_updated: str, methodology_note: str = None):
    add_footer(fig, source, last_updated, methodology_note)
    fig.tight_layout(rect=[0, 0.06, 1, 1])  # leave room for footer
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    print(f"Chart saved: {output_path}")
