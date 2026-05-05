# -*- coding: utf-8 -*-
"""
Generate revised Figures 2–6 for the garment disruptor paper.

Expected input files from scripts/01_evaluate_disruptor_rules.py:
- disruptor_rule_summary.csv
- disruptor_trigger_diagnostics.csv
- disruptor_rule_flags_by_variant.csv
- disruptor_match_evidence.csv
- hardware_material_disclosure_summary.csv (optional; figure script can compute fallback)

Main visual logic:
- Figure 2: aggregate overview only
- Figure 3: removable disruptors + hardware trigger rankings
- Figure 4: retained barriers + trigger rankings
- Figure 5: R7b/R8b mismatch diagnostics with two-block treemap and beautified labels
- Figure 6: category-level concentration

Colour logic:
- Main disruptor figures use orange as the dominant colour family.
- Waffle panels use light-to-dark orange gradients when showing categories within the same concept.
- Grey is used only for neutral context and sensitivity endpoints.
"""

from pathlib import Path
import re
import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt

# =============================================================================
# 0. User settings
# =============================================================================

DATA_DIR = Path("disruptor_eval_outputs")
# Allow direct execution from a folder where the CSV outputs sit next to this script.
if not (DATA_DIR / "disruptor_rule_summary.csv").exists() and Path("disruptor_rule_summary.csv").exists():
    DATA_DIR = Path(".")

OUT_DIR = Path("figures")
OUT_DIR.mkdir(exist_ok=True)

TOP_N = 5
MIN_CATEGORY_N = 100

BLUE = "#b8cff4"
ORANGE = "#f7a263"

BLUE_DARK = "#5f83cf"
ORANGE_DARK = "#d9822b"
ORANGE_MID = "#f7a263"
ORANGE_LIGHT = "#fbd1ad"
ORANGE_PALE = "#fde4cf"

GREY = "#d9d9d9"
GREY_DARK = "#6e6e6e"
LIGHT_GREY = "#f2f2f2"
TEXT = "#333333"
BAR_GREY = "#9a9a9a"

DPI = 400

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# =============================================================================
# 1. Load data
# =============================================================================

summary = pd.read_csv(DATA_DIR / "disruptor_rule_summary.csv")
trigger = pd.read_csv(DATA_DIR / "disruptor_trigger_diagnostics.csv")
row = pd.read_csv(DATA_DIR / "disruptor_rule_flags_by_variant.csv")
evidence = pd.read_csv(DATA_DIR / "disruptor_match_evidence.csv")

N_TOTAL = int(summary["n_total"].dropna().iloc[0])


# =============================================================================
# 2. Necessary small helpers
# =============================================================================

def metric_share(metric):
    return float(summary.loc[summary["metric"] == metric, "share_flagged"].iloc[0])


def scenarios(base_metric):
    return {
        "conservative": metric_share(f"{base_metric}_conservative"),
        "default": metric_share(f"{base_metric}_default"),
        "expanded": metric_share(f"{base_metric}_expanded"),
    }


def save_fig(fig, name):
    fig.savefig(OUT_DIR / f"{name}.png", dpi=DPI, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    print(f"Saved: {OUT_DIR / f'{name}.png'}")
    print(f"Saved: {OUT_DIR / f'{name}.pdf'}")


def clean_ax(ax, grid_axis="x"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#aaaaaa")
    ax.spines["bottom"].set_color("#aaaaaa")
    ax.tick_params(axis="both", colors=TEXT, labelsize=8)
    if grid_axis:
        ax.grid(axis=grid_axis, color="#e9e9e9", linewidth=0.7)
        ax.set_axisbelow(True)


def panel_label(ax, label):
    ax.text(
        -0.08, 1.08, label,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        va="top",
        ha="left",
        color=TEXT
    )


def wrap(s, width=24):
    return "\n".join(textwrap.wrap(str(s), width=width, break_long_words=False))




# -----------------------------------------------------------------------------
# Data preparation helpers retained here because they are reused across figures.
# Plotting code itself is kept inline inside each figure block below.
# -----------------------------------------------------------------------------

def canonical_trigger(match, rule):
    s = str(match).lower().strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)

    if rule == "R1":
        if re.search(r"\bzip|zipper|zipped", s):
            return "zip-related"
        if re.search(r"press[- ]?stud", s):
            return "press-stud(s)"
        if re.search(r"hook[- ]?and[- ]?eye", s):
            return "hook-and-eye"
        if re.search(r"\bbuckle", s):
            return "buckle(s)"
        if re.search(r"\bsnap", s):
            return "snap(s)"
        if re.search(r"\bunderwire", s):
            return "underwire"
        if re.search(r"\beyelet", s):
            return "eyelet(s)"
        if re.search(r"\brivet", s):
            return "rivet(s)"
        if re.fullmatch(r"hook|hooks", s):
            return "hook(s)"
        return s

    if rule == "R2":
        if re.search(r"stopper", s):
            return "stopper(s)"
        if re.search(r"boning", s):
            return "boning"
        if re.search(r"plastic snap", s):
            return "plastic snap(s)"
        if re.search(r"plastic buckle", s):
            return "plastic buckle(s)"
        if re.search(r"toggle", s):
            return "toggle(s)"
        return s

    if rule == "R3":
        if "r1+r2" in s:
            return "R1 + R2 co-occurrence"
        return s

    if rule == "R4":
        if re.search(r"drawstring|drawcord", s):
            return "drawstring / drawcord"
        if re.search(r"\bpatch", s):
            return "patch(es)"
        if re.search(r"\belastic", s):
            return "elastic-related"
        if re.search(r"embroider", s):
            return "embroidery"
        if re.search(r"\blace", s):
            return "lace"
        if re.search(r"binding", s):
            return "binding"
        if re.search(r"\btape", s):
            return "tape"
        if re.search(r"piping", s):
            return "piping"
        return s

    if rule == "R5":
        if re.search(r"sequin", s):
            return "sequin(s)"
        if re.search(r"\bbead", s):
            return "bead(s)"
        if re.search(r"rhinestone", s):
            return "rhinestone(s)"
        if re.search(r"embellish", s):
            return "embellished"
        if re.search(r"pearl", s):
            return "pearl(s)"
        if re.search(r"fringe", s):
            return "fringe"
        if re.search(r"pendant", s):
            return "pendant(s)"
        return s

    if rule == "R6":
        if re.search(r"coated|coating", s):
            return "coating-related"
        if re.search(r"water[- ]?repellent", s):
            return "water-repellent"
        if re.search(r"waterproof", s):
            return "waterproof"
        if re.search(r"bonded", s):
            return "bonded"
        if re.search(r"taped seams?", s):
            return "taped seams"
        if re.search(r"reflective print", s):
            return "reflective print"
        if re.search(r"foil print", s):
            return "foil print"
        return s

    if rule == "R7_presence":
        if s == "lining":
            return "lining"
        if s == "lined":
            return "lined"
        if re.search(r"hood lining", s):
            return "hood lining"
        if re.search(r"cup lining", s):
            return "cup lining"
        if re.search(r"inner layer", s):
            return "inner layer"
        if re.search(r"body lining", s):
            return "body lining"
        if re.search(r"double[- ]?layer", s):
            return "double layer"
        return s

    if rule == "R8_presence":
        if re.search(r"pocket lining", s):
            return "pocket lining"
        if re.search(r"pocket fabric", s):
            return "pocket fabric"
        if re.search(r"top panel", s):
            return "top panel"
        if re.search(r"bottom panel", s):
            return "bottom panel"
        if re.search(r"front panel", s):
            return "front panel"
        if re.search(r"back panel", s):
            return "back panel"
        if s == "mesh":
            return "mesh"
        if s == "wing":
            return "wing"
        return s

    return s


def top_trigger_df(rule, top_n=TOP_N, setting="default"):
    d = trigger[(trigger["rule"] == rule) & (trigger["setting"] == setting)].copy()
    if d.empty:
        return pd.DataFrame(columns=["label", "n", "pct"])

    d["label"] = d["match"].apply(lambda x: canonical_trigger(x, rule))
    d = d.groupby("label", as_index=False)["n"].sum().sort_values("n", ascending=False)
    d["pct"] = d["n"] / d["n"].sum()
    return d.head(top_n).copy()


def beautify_mismatch_label(s, multiline=True):
    """
    Example:
    shell[polyester]__inner_layer[nylon]
    -> Shell: polyester ↔ Inner layer: nylon
    """
    s = str(s).strip()
    parts = s.split("__")

    if len(parts) != 2:
        return s.replace("_", " ")

    def parse_part(part):
        m = re.match(r"(.+?)\[(.+?)\]", part)
        if not m:
            return part.replace("_", " ").strip().title()

        component = m.group(1).replace("_", " ").strip().title()
        material = m.group(2).replace("_", " ").replace("+", " + ").strip()
        return f"{component}: {material}"

    left = parse_part(parts[0])
    right = parse_part(parts[1])

    if multiline:
        return f"{left}\n↔ {right}"
    return f"{left} ↔ {right}"


def top_mismatch_df(rule, top_n=TOP_N, setting="default"):
    d = trigger[(trigger["rule"] == rule) & (trigger["setting"] == setting)].copy()
    if d.empty:
        return pd.DataFrame(columns=["label", "n", "pct"])

    d["label"] = d["match"].apply(lambda x: beautify_mismatch_label(x, multiline=True))
    d = d.groupby("label", as_index=False)["n"].sum().sort_values("n", ascending=False)
    d["pct"] = d["n"] / d["n"].sum()
    return d.head(top_n).copy()


def hardware_material_disclosure(setting="default"):
    """
    Return garment-variant level material-disclosure split for hard-hardware cues.

    Preferred input: hardware_material_disclosure_summary.csv generated by
    the revised rule-evaluation script.

    Fallback: compute from evidence matches. A hardware cue is counted as
    material-specified when the matched text itself contains an explicit material
    word: metal, plastic, polymer, resin, synthetic, moulded, or molded.
    """
    disclosure_file = DATA_DIR / "hardware_material_disclosure_summary.csv"
    if disclosure_file.exists():
        d = pd.read_csv(disclosure_file)
        d = d[(d["setting"] == setting) & (d["level"] == "garment_variant")].copy()
        if not d.empty:
            r = d.iloc[0]
            return {
                "n_hardware": int(r["n_hardware"]),
                "n_specified": int(r["n_material_specified"]),
                "share_specified": float(r["share_material_specified"]),
                "n_unspecified": int(r["n_material_unspecified_or_ambiguous"]),
                "share_unspecified": float(r["share_material_unspecified_or_ambiguous"]),
            }

    hard_ev = evidence[
        (evidence["rule"].isin(["R1", "R2", "R3"])) &
        (evidence["setting"] == setting)
    ].copy()

    material_word_pat = re.compile(r"\b(?:metal|plastic|polymer|resin|synthetic|moulded|molded)\b", flags=re.I)
    hard_ev["material_specified_match"] = hard_ev["match"].fillna("").astype(str).str.contains(material_word_pat)

    all_rows = set(hard_ev["row_id"].dropna().astype(int).unique())
    specified_rows = set(hard_ev.loc[hard_ev["material_specified_match"], "row_id"].dropna().astype(int).unique())
    unspecified_rows = all_rows - specified_rows

    n_hardware = len(all_rows)
    n_specified = len(specified_rows)
    n_unspecified = len(unspecified_rows)

    return {
        "n_hardware": n_hardware,
        "n_specified": n_specified,
        "share_specified": n_specified / n_hardware if n_hardware else 0,
        "n_unspecified": n_unspecified,
        "share_unspecified": n_unspecified / n_hardware if n_hardware else 0,
    }


def hardware_rule_distribution(setting="default"):
    """
    Return the distribution of default hard-hardware cue detections across R1-R3.

    This uses evidence-level matches rather than garment-variant flags, so the
    three classes form a proper partition of all detected hard-hardware cues.
    """
    d = evidence[(evidence["setting"] == setting) & (evidence["rule"].isin(["R1", "R2", "R3"]))].copy()
    if d.empty:
        return pd.DataFrame(columns=["rule", "label", "n", "share"])

    out = d.groupby("rule", as_index=False).size().rename(columns={"size": "n"})
    label_map = {
        "R1": "R1 metal-specified",
        "R2": "R2 plastic-specified",
        "R3": "R3 material-ambiguous",
    }
    out["label"] = out["rule"].map(label_map)
    total = out["n"].sum()
    out["share"] = out["n"] / total if total else 0
    order = ["R1", "R2", "R3"]
    out["order"] = out["rule"].map({k: i for i, k in enumerate(order)})
    out = out.sort_values("order").drop(columns="order")
    return out


def retained_barrier_accumulation(setting="default"):
    """Return garment-variant distribution by number of retained core barriers R4-R8."""
    retained_cols = [
        f"r4_fabric_attached_trim_{setting}",
        f"r5_decorative_nontextile_{setting}",
        f"r6_surface_print_coating_{setting}",
        f"r7_lining_multilayer_{setting}",
        f"r8_secondary_component_presence_{setting}",
    ]
    missing = [c for c in retained_cols if c not in row.columns]
    if missing:
        raise KeyError(f"Missing retained-barrier columns: {missing}")

    n_rules = row[retained_cols].fillna(0).astype(int).sum(axis=1)
    bins = pd.Series(
        np.select(
            [n_rules == 0, n_rules == 1, n_rules == 2, n_rules >= 3],
            ["0", "1", "2", "3+"],
            default="0"
        ),
        name="n_retained_barriers"
    )
    order = ["0", "1", "2", "3+"]
    out = bins.value_counts().reindex(order, fill_value=0).reset_index()
    out.columns = ["label", "n"]
    out["share"] = out["n"] / out["n"].sum()
    out["plot_label"] = out["label"].map({
        "0": "0 retained barriers",
        "1": "1 retained barrier",
        "2": "2 retained barriers",
        "3+": "3+ retained barriers",
    })
    return out




# =============================================================================
# Figure 2: Aggregate overview only
# =============================================================================

agg_df = pd.DataFrame([
    {"label": "Any disruptor overall", **scenarios("any_disruptor_overall"), "color": GREY_DARK},
    {"label": "Any retained barrier", **scenarios("any_retained_barrier"), "color": BLUE_DARK},
    {"label": "Any removable disruptor", **scenarios("any_removable_disruptor"), "color": ORANGE_DARK},
])

fig, ax = plt.subplots(figsize=(7.4, 3.9))

for i, r in agg_df.reset_index(drop=True).iterrows():
    ax.plot(
        [r["conservative"] * 100, r["expanded"] * 100],
        [i, i],
        color=GREY,
        lw=2.6,
        solid_capstyle="round",
        zorder=1,
    )

    ax.scatter(r["conservative"] * 100, i, s=34, color="#bfbfbf", zorder=2)
    ax.scatter(r["expanded"] * 100, i, s=34, color="#bfbfbf", zorder=2)

    ax.scatter(
        r["default"] * 100,
        i,
        s=78,
        color=r["color"],
        edgecolor="white",
        linewidth=0.9,
        zorder=3,
    )

    ax.text(
        r["default"] * 100 + 1.2,
        i,
        f"{r['default'] * 100:.1f}%",
        va="center",
        ha="left",
        fontsize=8.5,
        color=TEXT,
    )

    ax.text(
        r["conservative"] * 100,
        i + 0.18,
        f"{r['conservative'] * 100:.1f}",
        va="center",
        ha="center",
        fontsize=7,
        color="#8a8a8a",
    )
    ax.text(
        r["expanded"] * 100,
        i + 0.18,
        f"{r['expanded'] * 100:.1f}",
        va="center",
        ha="center",
        fontsize=7,
        color="#8a8a8a",
    )

ax.set_yticks(np.arange(len(agg_df)))
ax.set_yticklabels(agg_df["label"], fontsize=8.5)
ax.invert_yaxis()
ax.set_xlim(0, 75)
ax.set_xlabel("Share of garment variants (%)", fontsize=8.5, color=TEXT)
ax.set_title(
    f"Figure 2. Aggregate disruptor prevalence across rule settings (n = {N_TOTAL:,})",
    fontsize=11.5,
    loc="left",
    color=TEXT,
    pad=14,
)

clean_ax(ax)

ax.text(
    0.0,
    -0.30,
    "Grey endpoints indicate conservative and expanded settings; coloured dots indicate the default setting.",
    transform=ax.transAxes,
    fontsize=7.5,
    color=GREY_DARK,
    ha="left",
    va="top",
)

legend_handles = [
    Line2D([0], [0], marker="o", color="none", markerfacecolor="#bfbfbf", markeredgecolor="#bfbfbf", markersize=6, label="Conservative / expanded endpoints"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor=GREY_DARK, markeredgecolor="white", markersize=8, label="Any disruptor overall (default)"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor=BLUE_DARK, markeredgecolor="white", markersize=8, label="Any retained barrier (default)"),
    Line2D([0], [0], marker="o", color="none", markerfacecolor=ORANGE_DARK, markeredgecolor="white", markersize=8, label="Any removable disruptor (default)"),
]
ax.legend(
    handles=legend_handles,
    frameon=False,
    fontsize=7.3,
    loc="upper left",
    bbox_to_anchor=(0.0, -0.14),
    ncol=2,
    columnspacing=1.2,
    handletextpad=0.5,
)

save_fig(fig, "figure2_aggregate_prevalence")
plt.close(fig)


# =============================================================================
# Figure 3: Removable disruptors
# =============================================================================

rem_df = pd.DataFrame([
    {"label": "Any removable disruptor", **scenarios("any_removable_disruptor")},
    {"label": "R1 Metal-specified", **scenarios("r1_metal_hardware")},
    {"label": "R2 Plastic-specified", **scenarios("r2_plastic_hardware")},
    {"label": "R3 Material-ambiguous", **scenarios("r3_mixed_hardware")},
])

r1_top = top_trigger_df("R1")
r2_top = top_trigger_df("R2")
r3_top = top_trigger_df("R3")
hardware_disclosure_default = hardware_material_disclosure(setting="default")
hardware_rule_dist = hardware_rule_distribution(setting="default")

fig = plt.figure(figsize=(14.8, 8.9))
gs = fig.add_gridspec(2, 3, hspace=0.56, wspace=0.56, width_ratios=[1.0, 1.12, 1.18])

# -------------------------
# Panel (a): removable indicator sensitivity
# -------------------------
ax = fig.add_subplot(gs[0, 0])
d = rem_df.copy()
y = np.arange(len(d))
for i, r in d.reset_index(drop=True).iterrows():
    ax.plot([r["conservative"] * 100, r["expanded"] * 100], [i, i], color=GREY, lw=2.2, solid_capstyle="round", zorder=1)
    ax.scatter(r["conservative"] * 100, i, s=28, color="#bfbfbf", zorder=2)
    ax.scatter(r["expanded"] * 100, i, s=28, color="#bfbfbf", zorder=2)
    ax.scatter(r["default"] * 100, i, s=60, color=ORANGE_DARK, edgecolor="white", linewidth=0.8, zorder=3)
    ax.text(r["default"] * 100 + 1.0, i, f"{r['default'] * 100:.1f}%", va="center", ha="left", fontsize=7.6, color=TEXT)
ax.set_yticks(y)
ax.set_yticklabels(d["label"], fontsize=8)
ax.invert_yaxis()
ax.set_xlim(0, 45)
ax.set_xlabel("Share of garment variants (%)", fontsize=8, color=TEXT)
ax.set_title("Prevalence of removable-disruptor indicators", fontsize=10, loc="left", color=TEXT)
clean_ax(ax)
panel_label(ax, "(a)")

# -------------------------
# Panels (b)-(d): ranked top terms, kept inline for easier manual editing
# -------------------------
for ax, d, title in [
    (fig.add_subplot(gs[0, 1]), r1_top, "R1 metal-specified: top 5 terms"),
    (fig.add_subplot(gs[0, 2]), r2_top, "R2 plastic-specified: top 5 terms"),
    (fig.add_subplot(gs[1, 0]), r3_top, "R3 material-ambiguous: top 5 terms"),
]:
    if d.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=9, color=TEXT)
        ax.axis("off")
    else:
        plot_d = d.sort_values("n", ascending=True).copy()
        y = np.arange(len(plot_d))
        colors = [GREY] * len(plot_d)
        colors[-1] = ORANGE_DARK
        ax.barh(y, plot_d["n"], color=colors, edgecolor="none", height=0.72)
        ax.set_yticks(y)
        ax.set_yticklabels([wrap(x, 26) for x in plot_d["label"]], fontsize=7.5)
        xmax = plot_d["n"].max()
        for i, (_, r) in enumerate(plot_d.iterrows()):
            ax.text(r["n"] + xmax * 0.03, i, f"{int(r['n']):,} ({r['pct'] * 100:.1f}%)", va="center", ha="left", fontsize=7.1, color=TEXT)
        ax.set_xlim(0, xmax * 1.42)
        ax.set_xlabel("Count", fontsize=8, color=TEXT)
        ax.set_title(title, fontsize=9, loc="left", color=TEXT)
        clean_ax(ax)
panel_label(fig.axes[1], "(b)")
panel_label(fig.axes[2], "(c)")
panel_label(fig.axes[3], "(d)")

# -------------------------
# Panel (e): term-level distribution across R1-R3, revised as a default waffle chart
# -------------------------
ax = fig.add_subplot(gs[1, 1])
labels = list(hardware_rule_dist["label"])
shares = list(hardware_rule_dist["share"])
colors = [ORANGE_DARK, ORANGE_MID, ORANGE_LIGHT]

vals = np.array(shares, dtype=float)
raw = vals / vals.sum() * 100 if vals.sum() else np.zeros(len(vals))
counts = np.floor(raw).astype(int)
remainder = int(100 - counts.sum())
if remainder > 0:
    for i in np.argsort(-(raw - counts))[:remainder]:
        counts[i] += 1
elif remainder < 0:
    for i in np.argsort(raw - counts)[:abs(remainder)]:
        if counts[i] > 0:
            counts[i] -= 1

# Simple 10 x 10 waffle. No hardware silhouette is used because a generic
# waffle is more legible and avoids forcing an unclear hardware shape.
tile_colors = []
for count, color in zip(counts, colors):
    tile_colors.extend([color] * int(count))

# Keep exactly 100 tiles even under edge cases caused by rounding or empty data.
if len(tile_colors) < 100:
    tile_colors.extend([LIGHT_GREY] * (100 - len(tile_colors)))
tile_colors = tile_colors[:100]

# Mark very small categories with a dark outline so one-tile classes remain visible.
small_category_colors = {color for count, color in zip(counts, colors) if 0 < count <= 2}

n_cols = 10
for i, color in enumerate(tile_colors):
    xx = i % n_cols
    yy = i // n_cols
    ax.add_patch(plt.Rectangle(
        (xx, yy), 0.90, 0.90,
        facecolor=color,
        edgecolor="#555555" if color in small_category_colors else "white",
        linewidth=0.75 if color in small_category_colors else 0.55,
    ))

ax.set_xlim(-0.15, 16.6)
ax.set_ylim(-0.20, 10.10)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)
ax.set_title("Term-level distribution across R1–R3", fontsize=9, loc="left", color=TEXT)

x_text = 11.1
y_top = 8.7
for i, (label, share, color, count) in enumerate(zip(labels, shares, colors, counts)):
    yy = y_top - i * 1.25
    ax.scatter([x_text], [yy], s=60, marker="s", color=color, edgecolor="#555555" if 0 < count <= 2 else "white", linewidth=0.55, clip_on=False)
    ax.text(x_text + 0.40, yy, f"{label}: {share * 100:.1f}%", va="center", ha="left", fontsize=7.4, color=TEXT, clip_on=False)

ax.text(
    0, -0.14,
    f"Default term detections; n = {int(hardware_rule_dist['n'].sum()):,} total R1–R3 cue detections. Each tile ≈ 1% of detections.",
    transform=ax.transAxes,
    ha="left",
    va="top",
    fontsize=7.0,
    color=GREY_DARK,
)
panel_label(ax, "(e)")

# -------------------------
# Panel (f): garment-level hardware material disclosure, revised as a two-value treemap
# -------------------------
ax = fig.add_subplot(gs[1, 2])
labels = ["Material specified", "Material not specified"]
shares = [
    hardware_disclosure_default["share_specified"],
    hardware_disclosure_default["share_unspecified"],
]
colors = [ORANGE, LIGHT_GREY]

vals = np.array(shares, dtype=float)
if vals.sum() > 0:
    vals = vals / vals.sum()
else:
    vals = np.array([0.0, 1.0])

specified_h = float(vals[0])
unspecified_h = float(vals[1])

# One square, vertically split. The larger unspecified share is placed at the
# bottom and the smaller specified share at the top for easy comparison.
block_x = 0.0
block_y = 0.0
block_w = 0.92
block_h = 1.0

ax.add_patch(plt.Rectangle(
    (block_x, block_y), block_w, unspecified_h,
    facecolor=colors[1],
    edgecolor="white",
    linewidth=1.2,
))
ax.add_patch(plt.Rectangle(
    (block_x, block_y + unspecified_h), block_w, specified_h,
    facecolor=colors[0],
    edgecolor="white",
    linewidth=1.2,
))
ax.add_patch(plt.Rectangle(
    (block_x, block_y), block_w, block_h,
    facecolor="none",
    edgecolor="#bdbdbd",
    linewidth=0.8,
))

# Label both values. When the specified part is too thin, place its label outside.
if specified_h >= 0.12:
    ax.text(block_x + block_w / 2, block_y + unspecified_h + specified_h / 2,
            f"Specified\n{specified_h * 100:.1f}%", ha="center", va="center", fontsize=7.8, color=TEXT)
else:
    ax.text(block_x + block_w + 0.05, block_y + unspecified_h + specified_h / 2,
            f"Specified {specified_h * 100:.1f}%", ha="left", va="center", fontsize=7.4, color=TEXT)

if unspecified_h >= 0.12:
    ax.text(block_x + block_w / 2, block_y + unspecified_h / 2,
            f"Not specified\n{unspecified_h * 100:.1f}%", ha="center", va="center", fontsize=7.8, color=TEXT)
else:
    ax.text(block_x + block_w + 0.05, block_y + unspecified_h / 2,
            f"Not specified {unspecified_h * 100:.1f}%", ha="left", va="center", fontsize=7.4, color=TEXT)

ax.set_xlim(-0.05, 1.98)
ax.set_ylim(-0.02, 1.12)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Garment-level hardware material disclosure", fontsize=9, loc="left", color=TEXT)

x_text = 1.17
y_top = 0.88
for i, (label, share, color) in enumerate(zip(labels, shares, colors)):
    yy = y_top - i * 0.13
    ax.scatter([x_text], [yy], s=60, marker="s", color=color, edgecolor="white", linewidth=0.5, clip_on=False)
    ax.text(x_text + 0.07, yy, f"{label}: {share * 100:.1f}%", va="center", ha="left", fontsize=7.4, color=TEXT, clip_on=False)

ax.text(
    0, -0.14,
    f"Garment-variant level; n = {hardware_disclosure_default['n_hardware']:,} variants with at least one R1–R3 cue.",
    transform=ax.transAxes,
    ha="left",
    va="top",
    fontsize=7.0,
    color=GREY_DARK,
)
panel_label(ax, "(f)")

fig.suptitle("Figure 3. Removable hard-hardware disruptors and material disclosure", fontsize=12, y=1.01, color=TEXT)
save_fig(fig, "figure3_removable_disruptors")
plt.close(fig)


# =============================================================================
# Figure 4: Retained barriers
# =============================================================================

ret_df = pd.DataFrame([
    {"label": "R7 Lining / multilayer", **scenarios("r7_lining_multilayer")},
    {"label": "R4 Fabric attached trim", **scenarios("r4_fabric_attached_trim")},
    {"label": "R8 Secondary component", **scenarios("r8_secondary_component_presence")},
    {"label": "R6 Surface print / coating", **scenarios("r6_surface_print_coating")},
    {"label": "R5 Decorative / non-textile", **scenarios("r5_decorative_nontextile")},
]).sort_values("default", ascending=False)

r4_top = top_trigger_df("R4")
r5_top = top_trigger_df("R5")
r6_top = top_trigger_df("R6")
r7_top = top_trigger_df("R7_presence")
r8_top = top_trigger_df("R8_presence")
retained_accumulation = retained_barrier_accumulation(setting="default")

fig = plt.figure(figsize=(15.8, 8.9))
gs = fig.add_gridspec(2, 4, width_ratios=[1.12, 1.16, 1.16, 1.16], height_ratios=[1.0, 1.05], hspace=0.68, wspace=0.60)

# Panel (a): retained indicator sensitivity
ax = fig.add_subplot(gs[0, 0])
d = ret_df.copy()
y = np.arange(len(d))
for i, r in d.reset_index(drop=True).iterrows():
    ax.plot([r["conservative"] * 100, r["expanded"] * 100], [i, i], color=GREY, lw=2.2, solid_capstyle="round", zorder=1)
    ax.scatter(r["conservative"] * 100, i, s=28, color="#bfbfbf", zorder=2)
    ax.scatter(r["expanded"] * 100, i, s=28, color="#bfbfbf", zorder=2)
    ax.scatter(r["default"] * 100, i, s=60, color=BLUE_DARK, edgecolor="white", linewidth=0.8, zorder=3)
    ax.text(r["default"] * 100 + 1.0, i, f"{r['default'] * 100:.1f}%", va="center", ha="left", fontsize=7.6, color=TEXT)
ax.set_yticks(y)
ax.set_yticklabels(d["label"], fontsize=8)
ax.invert_yaxis()
ax.set_xlim(0, 35)
ax.set_xlabel("Share of garment variants (%)", fontsize=8, color=TEXT)
ax.set_title("Prevalence of retained-barrier indicators", fontsize=10, loc="left", color=TEXT)
clean_ax(ax)
panel_label(ax, "(a)")

# Panels (b)-(f): retained-barrier ranked terms, inline
rank_panels = [
    (fig.add_subplot(gs[0, 1]), r4_top, "R4 fabric attached trim: top 5 terms", "(b)"),
    (fig.add_subplot(gs[0, 2]), r5_top, "R5 decorative / non-textile: top 5 terms", "(c)"),
    (fig.add_subplot(gs[0, 3]), r6_top, "R6 surface print / coating: top 5 terms", "(d)"),
    (fig.add_subplot(gs[1, 0]), r7_top, "R7 lining / multilayer: top 5 terms", "(e)"),
    (fig.add_subplot(gs[1, 1]), r8_top, "R8 secondary component: top 5 terms", "(f)"),
]
for ax, d, title, lab in rank_panels:
    if d.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=9, color=TEXT)
        ax.axis("off")
    else:
        plot_d = d.sort_values("n", ascending=True).copy()
        y = np.arange(len(plot_d))
        colors = [GREY] * len(plot_d)
        colors[-1] = BLUE_DARK
        ax.barh(y, plot_d["n"], color=colors, edgecolor="none", height=0.72)
        ax.set_yticks(y)
        ax.set_yticklabels([wrap(x, 26) for x in plot_d["label"]], fontsize=7.5)
        xmax = plot_d["n"].max()
        for i, (_, r) in enumerate(plot_d.iterrows()):
            ax.text(r["n"] + xmax * 0.03, i, f"{int(r['n']):,} ({r['pct'] * 100:.1f}%)", va="center", ha="left", fontsize=7.1, color=TEXT)
        ax.set_xlim(0, xmax * 1.42)
        ax.set_xlabel("Count", fontsize=8, color=TEXT)
        ax.set_title(title, fontsize=9, loc="left", color=TEXT)
        clean_ax(ax)
    panel_label(ax, lab)

# Panel (g): retained-barrier count as garment-shaped waffle, inline
ax = fig.add_subplot(gs[1, 2])
dist = retained_accumulation.copy()
mask = [
    "001111111100",
    "011111111110",
    "111111111111",
    "111111111111",
    "011111111110",
    "001111111100",
    "001111111100",
    "001111111100",
    "001111111100",
    "001111111100",
    "001111111100",
]
coords = []
nrows_mask = len(mask)
for rr, line in enumerate(mask):
    for cc, ch in enumerate(line):
        if ch == "1":
            coords.append((cc, nrows_mask - 1 - rr))
if len(coords) != 100:
    raise ValueError(f"Garment silhouette mask should contain 100 tiles, found {len(coords)}")
vals = dist["share"].values.astype(float)
raw = vals / vals.sum() * len(coords) if vals.sum() else np.zeros(len(vals))
counts = np.floor(raw).astype(int)
remainder = int(len(coords) - counts.sum())
if remainder > 0:
    for i in np.argsort(-(raw - counts))[:remainder]:
        counts[i] += 1
elif remainder < 0:
    for i in np.argsort(raw - counts)[:abs(remainder)]:
        if counts[i] > 0:
            counts[i] -= 1
colors = [LIGHT_GREY, "#d6e2f3", BLUE, BLUE_DARK]
tile_colors = []
for count, color in zip(counts, colors):
    tile_colors.extend([color] * int(count))
for i, (xx, yy) in enumerate(coords):
    ax.add_patch(plt.Rectangle((xx, yy), 0.90, 0.90, facecolor=tile_colors[i], edgecolor="white", linewidth=0.55))
ax.add_patch(plt.Circle((5.95, 10.45), 1.05, facecolor="white", edgecolor="white", zorder=4))
ax.set_xlim(-0.25, 12.05)
ax.set_ylim(-3.35, 11.35)
ax.set_aspect("equal")
ax.set_xticks([])
ax.set_yticks([])
for spine in ax.spines.values():
    spine.set_visible(False)
ax.set_title("Retained-barrier count per garment", fontsize=9.2, loc="left", color=TEXT, pad=6)
legend_x = [-1.55, 7.05, -1.55, 7.05]
legend_y = [-0.80, -0.80, -1.65, -1.65]
for i, (_, r) in enumerate(dist.iterrows()):
    ax.scatter([legend_x[i]], [legend_y[i]], s=72, marker="s", color=colors[i], edgecolor="white", linewidth=0.5, clip_on=False)
    ax.text(legend_x[i] + 0.36, legend_y[i], f"{r['plot_label']}: {r['share'] * 100:.1f}%", va="center", ha="left", fontsize=6.95, color=TEXT, clip_on=False)
ax.text(-1.55, -2.65, f"Default setting; each tile ≈ 1% of garment variants (n = {N_TOTAL:,}).", fontsize=6.7, color=GREY_DARK, ha="left", va="top", clip_on=False)
panel_label(ax, "(g)")

# Keep panel g as a regular single-panel area; leave the spare grid cell empty.
ax_empty = fig.add_subplot(gs[1, 3])
ax_empty.axis("off")

fig.suptitle("Figure 4. Retained barriers, dominant terms, and barrier-count distribution", fontsize=12, y=1.01, color=TEXT)
save_fig(fig, "figure4_retained_barriers")
plt.close(fig)

# =============================================================================
# Figure 5: Mismatch diagnostics
# =============================================================================

presence_mismatch = pd.DataFrame({
    "pair": ["Lining / multilayer", "Secondary component"],
    "presence": [metric_share("r7_lining_multilayer_default"), metric_share("r8_secondary_component_presence_default")],
    "mismatch": [metric_share("r7b_hidden_layer_mismatch_default"), metric_share("r8b_secondary_material_difference_default")],
})
presence_mismatch["conditional_mismatch"] = presence_mismatch["mismatch"] / presence_mismatch["presence"]

r7b_top = top_mismatch_df("R7b_hidden_layer_mismatch")
r8b_top = top_mismatch_df("R8b_secondary_material_difference")

fig = plt.figure(figsize=(14.6, 8.4))
gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.0], height_ratios=[0.88, 1.20], hspace=0.64, wspace=0.46)

# Panel (a): absolute prevalence
ax = fig.add_subplot(gs[0, 0])
x = np.arange(len(presence_mismatch))
width = 0.34
ax.bar(x - width / 2, presence_mismatch["presence"] * 100, width=width, color=BLUE, edgecolor="none", label="Presence")
ax.bar(x + width / 2, presence_mismatch["mismatch"] * 100, width=width, color=ORANGE, edgecolor="none", label="Mismatch")
for i, r in presence_mismatch.iterrows():
    ax.text(i - width / 2, r["presence"] * 100 + 0.7, f"{r['presence'] * 100:.1f}%", ha="center", fontsize=7.5)
    ax.text(i + width / 2, r["mismatch"] * 100 + 0.7, f"{r['mismatch'] * 100:.1f}%", ha="center", fontsize=7.5)
ax.set_xticks(x)
ax.set_xticklabels([wrap(v, 16) for v in presence_mismatch["pair"]], fontsize=8)
ax.set_ylabel("Share of garment variants (%)", fontsize=8, color=TEXT)
ax.set_title("Presence versus material mismatch", fontsize=10, loc="left", color=TEXT)
ax.legend(frameon=False, fontsize=7.5, loc="upper right")
ax.set_ylim(0, max(presence_mismatch["presence"] * 100) * 1.35)
clean_ax(ax)
panel_label(ax, "(a)")

# Panel (b): conditional match / mismatch composition, inline treemap
ax = fig.add_subplot(gs[0, 1])
plot_df = presence_mismatch.copy()
plot_df["conditional_mismatch"] = plot_df["conditional_mismatch"].clip(lower=0, upper=1)
plot_df["conditional_match"] = 1 - plot_df["conditional_mismatch"]
ax.set_xlim(0, 2.18)
ax.set_ylim(0, 1.18)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Conditional match / mismatch composition", fontsize=10, loc="left", color=TEXT)
block_w = 0.92
gap = 0.28
x0s = [0.00, block_w + gap]
for i, (_, r) in enumerate(plot_df.iterrows()):
    x0 = x0s[i]
    mismatch_h = float(r["conditional_mismatch"])
    match_h = float(r["conditional_match"])
    ax.add_patch(plt.Rectangle((x0, mismatch_h), block_w, match_h, facecolor=BLUE, edgecolor="white", linewidth=1.2))
    ax.add_patch(plt.Rectangle((x0, 0), block_w, mismatch_h, facecolor=ORANGE, edgecolor="white", linewidth=1.2))
    ax.add_patch(plt.Rectangle((x0, 0), block_w, 1.0, facecolor="none", edgecolor="#bdbdbd", linewidth=0.8))
    ax.text(x0 + block_w / 2, 1.055, wrap(r["pair"], 18), ha="center", va="bottom", fontsize=8.0, color=TEXT)
    mismatch_pct = mismatch_h * 100
    if mismatch_h >= 0.16:
        ax.text(x0 + block_w / 2, mismatch_h / 2, f"mismatch\n{mismatch_pct:.1f}%", ha="center", va="center", fontsize=7.8, color=TEXT)
    else:
        ax.text(x0 + block_w + 0.03, mismatch_h / 2, f"mismatch {mismatch_pct:.1f}%", ha="left", va="center", fontsize=7.2, color=TEXT)
legend_handles = [
    Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=BLUE, markeredgecolor="none", markersize=8, label="Material match"),
    Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=ORANGE, markeredgecolor="none", markersize=8, label="Material mismatch"),
]
ax.legend(handles=legend_handles, frameon=False, fontsize=7.4, loc="lower center", bbox_to_anchor=(0.50, -0.17), ncol=2, handletextpad=0.45, columnspacing=1.2)
ax.text(0.0, -0.22, "Each square is conditional on garments where the corresponding component type is present.", transform=ax.transAxes, fontsize=7.1, color=GREY_DARK, ha="left", va="top")
panel_label(ax, "(b)")

# Panels (c)-(d): mismatch pair rankings, inline
for ax, d, title, lab in [
    (fig.add_subplot(gs[1, 0]), r7b_top, "R7b hidden-layer mismatch pairs", "(c)"),
    (fig.add_subplot(gs[1, 1]), r8b_top, "R8b secondary-component mismatch pairs", "(d)"),
]:
    if d.empty:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=9, color=TEXT)
        ax.axis("off")
    else:
        plot_d = d.sort_values("n", ascending=True).copy()
        y = np.arange(len(plot_d))
        colors = [GREY] * len(plot_d)
        colors[-1] = ORANGE_DARK
        ax.barh(y, plot_d["n"], color=colors, edgecolor="none", height=0.72)
        ax.set_yticks(y)
        ax.set_yticklabels([wrap(x, 30) for x in plot_d["label"]], fontsize=7.5)
        xmax = plot_d["n"].max()
        for i, (_, r) in enumerate(plot_d.iterrows()):
            ax.text(r["n"] + xmax * 0.03, i, f"{int(r['n']):,} ({r['pct'] * 100:.1f}%)", va="center", ha="left", fontsize=7.1, color=TEXT)
        ax.set_xlim(0, xmax * 1.42)
        ax.set_xlabel("Count", fontsize=8, color=TEXT)
        ax.set_title(title, fontsize=9, loc="left", color=TEXT)
        clean_ax(ax)
    panel_label(ax, lab)

fig.suptitle("Figure 5. Presence and mismatch risk of hidden and secondary components", fontsize=12, y=1.02, color=TEXT)
save_fig(fig, "figure5_mismatch_diagnostics")
plt.close(fig)


# =============================================================================
# Figure 6: Category-level concentration
# =============================================================================

# Main heatmap data: aggregates separated from core rules
category_cols_agg = {
    "Any removable": "any_removable_disruptor_default",
    "Any retained": "any_retained_barrier_default",
}

category_cols_rules = {
    "R1 metal-specified": "r1_metal_hardware_default",
    "R2 plastic-specified": "r2_plastic_hardware_default",
    "R3 material-ambiguous": "r3_mixed_hardware_default",
    "R4 trim": "r4_fabric_attached_trim_default",
    "R5 decorative": "r5_decorative_nontextile_default",
    "R6 coating": "r6_surface_print_coating_default",
    "R7 lining": "r7_lining_multilayer_default",
    "R8 secondary": "r8_secondary_component_presence_default",
}

needed = ["detail_category"] + list(category_cols_agg.values()) + list(category_cols_rules.values())
missing = [c for c in needed if c not in row.columns]
if missing:
    raise KeyError(f"Missing columns in row-level file: {missing}")

cat = row[needed].copy()
cat_n = cat.groupby("detail_category").size().rename("n_category")

cat_prev = cat.groupby("detail_category")[list(category_cols_agg.values()) + list(category_cols_rules.values())].mean()
cat_prev = cat_prev.rename(columns={
    **{v: k for k, v in category_cols_agg.items()},
    **{v: k for k, v in category_cols_rules.items()},
})
cat_prev = cat_prev.join(cat_n).reset_index()

agg_cols = list(category_cols_agg.keys())
rule_cols = list(category_cols_rules.keys())

cat_prev["sort_key_1"] = cat_prev["Any retained"]
cat_prev["sort_key_2"] = cat_prev["Any removable"]
cat_prev["sort_key_3"] = cat_prev[rule_cols].max(axis=1)
cat_prev = cat_prev.sort_values(["sort_key_1", "sort_key_2", "sort_key_3"], ascending=False).reset_index(drop=True)

heat = cat_prev.copy()
heat_agg = heat[agg_cols].values * 100
heat_rules = heat[rule_cols].values * 100

top_rem = cat_prev[["detail_category", "Any removable"]].sort_values("Any removable", ascending=False).head(TOP_N)
top_ret = cat_prev[["detail_category", "Any retained"]].sort_values("Any retained", ascending=False).head(TOP_N)

mismatch_prev = (
    row.groupby("detail_category")[["r7b_hidden_layer_mismatch_default", "r8b_secondary_material_difference_default"]]
    .mean()
    .reset_index()
    .rename(columns={
        "r7b_hidden_layer_mismatch_default": "R7b mismatch",
        "r8b_secondary_material_difference_default": "R8b mismatch",
    })
)

cat_prev = cat_prev.merge(mismatch_prev, on="detail_category", how="left")
cat_prev["R7b mismatch"] = cat_prev["R7b mismatch"].fillna(0)
cat_prev["R8b mismatch"] = cat_prev["R8b mismatch"].fillna(0)
cat_prev["Max mismatch"] = cat_prev[["R7b mismatch", "R8b mismatch"]].max(axis=1)
top_mis = cat_prev[["detail_category", "Max mismatch"]].sort_values("Max mismatch", ascending=False).head(TOP_N)

fig = plt.figure(figsize=(15.5, 10.8))
gs = fig.add_gridspec(3, 4, width_ratios=[0.95, 2.25, 2.25, 1.15], height_ratios=[1.0, 1.0, 1.0], hspace=0.62, wspace=0.58)

# Panel (a): Aggregate heatmap
ax = fig.add_subplot(gs[:, 0])
cmap_agg = LinearSegmentedColormap.from_list("agg_seq_blue_orange", ["#eef4fb", "#bfd2f0", "#7fa6de", "#f2c79f", "#f7a263"])
im_agg = ax.imshow(heat_agg, aspect="auto", cmap=cmap_agg, vmin=0, vmax=100)
ax.set_yticks(np.arange(len(heat)))
ax.set_yticklabels([wrap(x.replace("_", " "), 24) for x in heat["detail_category"]], fontsize=7.4)
ax.set_xticks(np.arange(len(agg_cols)))
ax.set_xticklabels([wrap(x, 11) for x in agg_cols], fontsize=7.2, rotation=45, ha="right")
ax.set_title("Aggregate indicators", fontsize=9.5, loc="left", color=TEXT)
for i in range(heat_agg.shape[0]):
    for j in range(heat_agg.shape[1]):
        val = heat_agg[i, j]
        if val > 0:
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=6.3, color=TEXT)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(length=0)
divider = make_axes_locatable(ax)
cax = divider.append_axes("right", size=0.12, pad=0.08)
cbar = fig.colorbar(im_agg, cax=cax)
cbar.set_label("Aggregate share (%)", fontsize=8, color=TEXT)
cbar.ax.tick_params(labelsize=7)
panel_label(ax, "(a)")

# Panel (b): Core-rule heatmap
ax = fig.add_subplot(gs[:, 1:3])
cmap_rules = LinearSegmentedColormap.from_list("rules_seq_blue_orange", ["#f1f6fc", "#c9daf2", "#8fb0e3", "#5d86cf", "#f1c69d", "#f7a263"])
im_rules = ax.imshow(heat_rules, aspect="auto", cmap=cmap_rules, vmin=0, vmax=40)
ax.set_yticks(np.arange(len(heat)))
ax.set_yticklabels([])
ax.set_xticks(np.arange(len(rule_cols)))
ax.set_xticklabels([wrap(x, 11) for x in rule_cols], fontsize=7.2, rotation=45, ha="right")
ax.set_title("Core rule indicators (R1–R8)", fontsize=9.5, loc="left", color=TEXT)
for i in range(heat_rules.shape[0]):
    for j in range(heat_rules.shape[1]):
        val = heat_rules[i, j]
        if val > 0:
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=6.0, color=TEXT)
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(length=0)
divider = make_axes_locatable(ax)
cax = divider.append_axes("right", size=0.12, pad=0.08)
cbar = fig.colorbar(im_rules, cax=cax)
cbar.set_label("Rule share (%)", fontsize=8, color=TEXT)
cbar.ax.tick_params(labelsize=7)
panel_label(ax, "(b)")
ax.text(0.0, -0.12, "All nonzero cells are annotated. Aggregate indicators and core rules are shown in separate panels to avoid compressing the rule-level colour scale.", transform=ax.transAxes, fontsize=7.1, color=GREY_DARK, ha="left", va="top")

# Panels (c)-(e): category bars, inline
# Style matches the ranked bars in Figures 3–5:
# - the longest / top category is highlighted;
# - all remaining categories are shown in light grey.
for ax, d, value_col, title, highlight_color, lab in [
    (fig.add_subplot(gs[0, 3]), top_rem, "Any removable", "Top categories: removable disruptors", ORANGE_DARK, "(c)"),
    (fig.add_subplot(gs[1, 3]), top_ret, "Any retained", "Top categories: retained barriers", ORANGE_DARK, "(d)"),
    (fig.add_subplot(gs[2, 3]), top_mis, "Max mismatch", "Top categories: mismatch diagnostics", ORANGE_DARK, "(e)"),
]:
    plot_d = d.sort_values(value_col, ascending=True).copy()
    y = np.arange(len(plot_d))

    bar_colors = [LIGHT_GREY] * len(plot_d)
    if len(bar_colors) > 0:
        bar_colors[-1] = highlight_color

    ax.barh(y, plot_d[value_col] * 100, color=bar_colors, edgecolor="none", height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels([wrap(x.replace("_", " "), 18) for x in plot_d["detail_category"]], fontsize=7.2)
    xmax = plot_d[value_col].max() * 100 if len(plot_d) else 1
    for i, (_, r) in enumerate(plot_d.iterrows()):
        ax.text(r[value_col] * 100 + xmax * 0.03, i, f"{r[value_col] * 100:.1f}%", va="center", fontsize=7)
    ax.set_xlim(0, xmax * 1.35)
    ax.set_xlabel("Share within category (%)", fontsize=7.5, color=TEXT)
    ax.set_title(title, fontsize=9, loc="left", color=TEXT)
    clean_ax(ax)
    panel_label(ax, lab)

fig.suptitle("Figure 6. Category-level concentration of disruptor barriers", fontsize=12, y=0.98, color=TEXT)
save_fig(fig, "figure6_category_concentration")
plt.close(fig)

print("\nAll revised figures generated.")
print(f"Output folder: {OUT_DIR.resolve()}")
