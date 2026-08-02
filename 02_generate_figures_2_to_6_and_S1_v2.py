"""
Generate the reproducible figure set used in the main text and Supplementary Information.

Generated figures
-----------------
Main text:
- Figure 2: aggregate prevalence across rule-boundary settings
- Figure 3: removable-hardware indicators and material disclosure
- Figure 4: retained-barrier indicators and trigger distributions
- Figure 5: presence, conditional mismatch, and leading mismatch pairs
- Figure 6: category-level aggregate comparison and worked reading example

Supplementary Information:
- Figure S1: complete category-by-rule heatmap

Figure 1 is retained as original artwork and is therefore not regenerated.
Figures are exported as editable SVG and publication-ready PDF files. The script
also exports figure-specific source-value files and QA results.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, DrawingArea
from matplotlib.patches import Circle, Polygon, Rectangle

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_PROJECT_DIR = Path(
    r"C:\Users\laptop-kl\OneDrive - Universiteit Leiden\PlasticTradeFlow"
    r"\data_mining_clothing\textile_preprocessing\waste_management\1st_revision"
)
PROJECT_DIR = LOCAL_PROJECT_DIR if LOCAL_PROJECT_DIR.exists() else SCRIPT_DIR

DEFAULT_DATA_DIR = PROJECT_DIR / "outputs_v2"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "figures_2_to_6_and_S1_v2"

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

CATEGORY_DISPLAY_LABELS = {
    "outerwear_coat": "Outerwear coats",
    "outerwear_jacket": "Outerwear jackets",
    "outerwear_gilet": "Outerwear gilets",
    "shirt_blouse": "Shirts/blouses",
    "tshirt_polo": "T-shirts/polos",
    "tank_camisole_vest": "Tanks/camisoles/vests",
    "sweater_cardigan": "Sweaters/cardigans",
    "sweatshirt_hoodie": "Sweatshirts/hoodies",
    "top_generic": "Other tops",
    "jeans": "Jeans",
    "trousers": "Trousers",
    "leggings": "Leggings",
    "joggers": "Joggers",
    "shorts": "Shorts",
    "skirts": "Skirts",
    "underwear_bottoms": "Underwear bottoms",
    "bras_lingerie": "Bras/lingerie",
    "swimwear": "Swimwear",
    "socks_hosiery": "Socks/hosiery",
    "dresses": "Dresses",
    "jumpsuits_overalls": "Jumpsuits/overalls",
    "sleepwear_homewear": "Sleepwear/homewear",
    "set": "Sets",
}

plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.family"] = "Times New Roman"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Folder containing the rule-evaluation CSV outputs.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Folder for PDF, SVG, and audit outputs.")
    return parser.parse_args()


ARGS = parse_args()
DATA_DIR = ARGS.data_dir
OUT_DIR = ARGS.output_dir
OUT_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 1. Load data
# =============================================================================

required_inputs = [
    DATA_DIR / "disruptor_rule_summary.csv",
    DATA_DIR / "disruptor_trigger_diagnostics.csv",
    DATA_DIR / "disruptor_rule_flags_by_variant.csv",
    DATA_DIR / "disruptor_match_evidence.csv",
]
missing_inputs = [str(path) for path in required_inputs if not path.exists()]
if missing_inputs:
    raise FileNotFoundError(
        "Missing figure input files:\n- " + "\n- ".join(missing_inputs)
    )

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
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.svg", bbox_inches="tight")
    print(f"Saved: {OUT_DIR / f'{name}.pdf'}")
    print(f"Saved: {OUT_DIR / f'{name}.svg'}")


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


def format_category_label(value: str) -> str:
    code = str(value).strip()
    if code in CATEGORY_DISPLAY_LABELS:
        return CATEGORY_DISPLAY_LABELS[code]
    fallback = code.replace("_", " ").strip()
    return fallback[:1].upper() + fallback[1:] if fallback else fallback


def _icon_box(kind: str) -> DrawingArea:
    """Return a small vector icon so Figure 2 is fully reproducible."""
    da = DrawingArea(58, 58, clip=False)
    da.add_artist(Circle((29, 29), 25, facecolor="white", edgecolor=ORANGE, linewidth=2.4))

    if kind == "overall":
        da.add_artist(Polygon([[29, 43], [15, 18], [43, 18]], closed=True,
                              facecolor=ORANGE_DARK, edgecolor="none"))
        da.add_artist(plt.Text(29, 26, "!", ha="center", va="center",
                               color="white", fontsize=16, fontweight="bold"))
    elif kind == "retained":
        layers = [
            [[14, 34], [29, 41], [44, 34], [29, 27]],
            [[14, 27], [29, 34], [44, 27], [29, 20]],
            [[14, 20], [29, 27], [44, 20], [29, 13]],
        ]
        for i, pts in enumerate(layers):
            da.add_artist(Polygon(pts, closed=True, facecolor=ORANGE_LIGHT,
                                  edgecolor="white", linewidth=0.8))
    elif kind == "removable":
        # Stylised zipper: two tapes, teeth, and slider.
        da.add_artist(Polygon([[19, 12], [25, 12], [33, 44], [27, 44]], closed=True,
                              facecolor=ORANGE_LIGHT, edgecolor=GREY_DARK, linewidth=0.8))
        da.add_artist(Polygon([[33, 12], [39, 12], [31, 44], [25, 44]], closed=True,
                              facecolor=ORANGE_LIGHT, edgecolor=GREY_DARK, linewidth=0.8))
        for yy in range(16, 40, 5):
            da.add_artist(Rectangle((26.5, yy), 5, 2, facecolor=ORANGE_DARK, edgecolor="none"))
        da.add_artist(Circle((29, 36), 5.0, facecolor="white", edgecolor=GREY_DARK, linewidth=1.0))
        da.add_artist(Circle((29, 36), 2.7, facecolor=LIGHT_GREY, edgecolor="none"))
        da.add_artist(Polygon([[24, 27], [34, 27], [32, 20], [26, 20]], closed=True,
                              facecolor=ORANGE_DARK, edgecolor=GREY_DARK, linewidth=0.7))
    else:
        raise ValueError(f"Unknown Figure 2 icon kind: {kind}")
    return da


def add_icon(ax, x: float, y: float, kind: str) -> None:
    ab = AnnotationBbox(_icon_box(kind), (x, y), frameon=False,
                        box_alignment=(0.5, 0.5), zorder=5)
    ax.add_artist(ab)




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
    Return garment-variant-level material-disclosure split for removable-hardware cues.

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
    Return the distribution of default removable-hardware cue detections across R1–R3.

    This uses evidence-level matches rather than garment-variant flags, so the
    three classes form a proper partition of all detected removable-hardware cues.
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
        name="n_retained_barrier_indicators"
    )
    order = ["0", "1", "2", "3+"]
    out = bins.value_counts().reindex(order, fill_value=0).reset_index()
    out.columns = ["label", "n"]
    out["share"] = out["n"] / out["n"].sum()
    out["plot_label"] = out["label"].map({
        "0": "0 retained-barrier indicators",
        "1": "1 retained-barrier indicator",
        "2": "2 retained-barrier indicators",
        "3+": "3+ retained-barrier indicators",
    })
    return out




# =============================================================================
# Figure 2: Aggregate prevalence across rule-boundary settings
# =============================================================================

agg_df = pd.DataFrame([
    {
        "label": "At least one core\ndisruptor indicator\n(R1–R8)",
        "metric": "any_disruptor_overall",
        "color": GREY_DARK,
        "icon": "overall",
        "icon_x": 36.0,
    },
    {
        "label": "At least one retained-barrier\nindicator\n(R4–R8)",
        "metric": "any_retained_barrier",
        "color": BLUE_DARK,
        "icon": "retained",
        "icon_x": 30.0,
    },
    {
        "label": "At least one removable-hardware\nindicator\n(R1–R3)",
        "metric": "any_removable_disruptor",
        "color": ORANGE_DARK,
        "icon": "removable",
        "icon_x": 14.5,
    },
])
for setting in ["conservative", "default", "expanded"]:
    agg_df[setting] = agg_df["metric"].map(
        lambda metric: scenarios(metric)[setting] * 100
    )

fig, ax = plt.subplots(figsize=(8.6, 5.0))
y_positions = np.array([2, 1, 0], dtype=float)

for y, (_, r) in zip(y_positions, agg_df.iterrows()):
    c, d, e = r["conservative"], r["default"], r["expanded"]
    ax.plot([c, e], [y, y], color=GREY, lw=3.0, solid_capstyle="round", zorder=1)
    ax.scatter([c, e], [y, y], s=58, color="#bfbfbf", edgecolor="none", zorder=2)
    ax.scatter(d, y, s=92, color=r["color"], edgecolor="white", linewidth=0.9, zorder=3)

    if y == 0:
        ax.text(c - 0.8, y + 0.12, f"{c:.1f}", ha="center", va="bottom",
                fontsize=8.0, color="#888888")
        ax.text(e, y + 0.12, f"{e:.1f}", ha="center", va="bottom",
                fontsize=8.0, color="#888888")
        icon_y = y + 0.13
    else:
        ax.text(c - 0.8, y - 0.17, f"{c:.1f}", ha="center", va="top",
                fontsize=8.0, color="#888888")
        ax.text(e, y - 0.17, f"{e:.1f}", ha="center", va="top",
                fontsize=8.0, color="#888888")
        icon_y = y
    ax.text(d, y + 0.15, f"{d:.1f}%", ha="center", va="bottom",
            fontsize=8.7, color=TEXT)
    add_icon(ax, float(r["icon_x"]), icon_y, str(r["icon"]))

ax.set_yticks(y_positions)
ax.set_yticklabels(agg_df["label"], fontsize=9.2)
ax.set_xlim(0, 75)
ax.set_ylim(-0.12, 2.14)
ax.set_xticks(np.arange(0, 71, 10))
ax.set_xlabel("Share of garment variants (%)", fontsize=9.0, color=TEXT)
ax.xaxis.set_label_coords(1.0, -0.12)
ax.xaxis.label.set_horizontalalignment("right")
clean_ax(ax)

# Positional rule-setting key: the left/middle/right position carries the meaning.
key_y = -0.17
key_x = [0.08, 0.20, 0.32]
ax.plot([key_x[0], key_x[2]], [key_y, key_y], transform=ax.transAxes,
        color=GREY, lw=2.4, clip_on=False)
ax.scatter(key_x, [key_y] * 3, transform=ax.transAxes, s=[44, 54, 44],
           color=["#bfbfbf", GREY_DARK, "#bfbfbf"], clip_on=False, zorder=5)
for xk, label in zip(key_x, ["Conservative", "Default", "Expanded"]):
    ax.text(xk, key_y - 0.045, label, transform=ax.transAxes,
            ha="center", va="top", fontsize=7.6, color=TEXT, clip_on=False)

fig.subplots_adjust(left=0.24, right=0.98, top=0.97, bottom=0.25)
save_fig(fig, "Figure_2_aggregate_prevalence")
plt.close(fig)

pd.DataFrame([
    {
        "metric": r["metric"],
        "conservative_percent": r["conservative"],
        "default_percent": r["default"],
        "expanded_percent": r["expanded"],
    }
    for _, r in agg_df.iterrows()
]).to_csv(OUT_DIR / "Figure_2_source_values.csv", index=False)

# =============================================================================
# Figure 3: Removable-hardware indicators
# =============================================================================

rem_df = pd.DataFrame([
    {"label": "Any removable-hardware indicator", **scenarios("any_removable_disruptor")},
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
ax.set_title("Removable-hardware indicator prevalence", fontsize=10, loc="left", color=TEXT)
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

fig.suptitle("Figure 3. Removable-hardware indicators and material disclosure", fontsize=12, y=1.01, color=TEXT)
save_fig(fig, "Figure_3_removable_hardware_indicators")
plt.close(fig)

figure3_panel_a = rem_df.copy()
for setting in ["conservative", "default", "expanded"]:
    figure3_panel_a[f"{setting}_percent"] = figure3_panel_a[setting] * 100
figure3_panel_a[[
    "label", "conservative_percent", "default_percent", "expanded_percent"
]].to_csv(OUT_DIR / "Figure_3_panel_a_source_values.csv", index=False)

figure3_terms = pd.concat([
    r1_top.assign(panel="b", rule="R1"),
    r2_top.assign(panel="c", rule="R2"),
    r3_top.assign(panel="d", rule="R3"),
], ignore_index=True)
figure3_terms.to_csv(OUT_DIR / "Figure_3_panels_b_to_d_top_terms.csv", index=False)
hardware_rule_dist.to_csv(
    OUT_DIR / "Figure_3_panel_e_term_distribution.csv", index=False
)
pd.DataFrame([hardware_disclosure_default]).to_csv(
    OUT_DIR / "Figure_3_panel_f_hardware_disclosure.csv", index=False
)


# =============================================================================
# Figure 4: Retained-barrier indicators
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
ax.set_title("Retained-barrier indicator count per garment", fontsize=9.2, loc="left", color=TEXT, pad=6)
legend_x = [-1.55, -1.55, -1.55, -1.55]
legend_y = [-0.45, -1.05, -1.65, -2.25]
for i, (_, r) in enumerate(dist.iterrows()):
    ax.scatter([legend_x[i]], [legend_y[i]], s=72, marker="s", color=colors[i], edgecolor="white", linewidth=0.5, clip_on=False)
    ax.text(legend_x[i] + 0.36, legend_y[i], f"{r['plot_label']}: {r['share'] * 100:.1f}%", va="center", ha="left", fontsize=6.95, color=TEXT, clip_on=False)
ax.text(-1.55, -2.95, f"Default setting; each tile ≈ 1% of garment variants (n = {N_TOTAL:,}).", fontsize=6.7, color=GREY_DARK, ha="left", va="top", clip_on=False)
panel_label(ax, "(g)")

# Keep panel g as a regular single-panel area; leave the spare grid cell empty.
ax_empty = fig.add_subplot(gs[1, 3])
ax_empty.axis("off")

fig.suptitle("Figure 4. Retained-barrier indicators, dominant terms, and indicator-count distribution", fontsize=12, y=1.01, color=TEXT)
save_fig(fig, "Figure_4_retained_barrier_indicators")
plt.close(fig)

figure4_panel_a = ret_df.copy()
for setting in ["conservative", "default", "expanded"]:
    figure4_panel_a[f"{setting}_percent"] = figure4_panel_a[setting] * 100
figure4_panel_a[[
    "label", "conservative_percent", "default_percent", "expanded_percent"
]].to_csv(OUT_DIR / "Figure_4_panel_a_source_values.csv", index=False)

figure4_terms = pd.concat([
    r4_top.assign(panel="b", rule="R4"),
    r5_top.assign(panel="c", rule="R5"),
    r6_top.assign(panel="d", rule="R6"),
    r7_top.assign(panel="e", rule="R7"),
    r8_top.assign(panel="f", rule="R8"),
], ignore_index=True)
figure4_terms.to_csv(OUT_DIR / "Figure_4_panels_b_to_f_top_terms.csv", index=False)
retained_accumulation.to_csv(
    OUT_DIR / "Figure_4_panel_g_barrier_count.csv", index=False
)

# =============================================================================
# Figure 5: Material mismatch in hidden and secondary components
# =============================================================================

r7 = row["r7_lining_multilayer_default"].astype(bool)
r7b = row["r7b_hidden_layer_mismatch_default"].astype(bool)
r8 = row["r8_secondary_component_presence_default"].astype(bool)
r8b = row["r8b_secondary_material_difference_default"].astype(bool)

presence_mismatch = pd.DataFrame({
    "pair": ["Lining / multilayer", "Secondary component"],
    "presence": [r7.mean(), r8.mean()],
    # Panel (a) retains the full diagnostic prevalence across all variants.
    "mismatch": [r7b.mean(), r8b.mean()],
    # Panel (b) uses only mismatch cases nested within the corresponding presence flag.
    "conditional_mismatch": [
        (r7 & r7b).sum() / r7.sum(),
        (r8 & r8b).sum() / r8.sum(),
    ],
})
outside_r7 = int((~r7 & r7b).sum())
outside_r8 = int((~r8 & r8b).sum())

r7b_top = top_mismatch_df("R7b_hidden_layer_mismatch")
r8b_top = top_mismatch_df("R8b_secondary_material_difference")

fig = plt.figure(figsize=(14.6, 8.4))
gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.0], height_ratios=[0.88, 1.20],
                      hspace=0.64, wspace=0.46)

# Panel (a): prevalence among all colour-specific variants.
ax = fig.add_subplot(gs[0, 0])
x = np.arange(len(presence_mismatch))
width = 0.34
ax.bar(x - width / 2, presence_mismatch["presence"] * 100, width=width,
       color=GREY, edgecolor="none", label="Presence")
ax.bar(x + width / 2, presence_mismatch["mismatch"] * 100, width=width,
       color=ORANGE_LIGHT, edgecolor="none", label="Material mismatch")
for i, r in presence_mismatch.iterrows():
    ax.text(i - width / 2, r["presence"] * 100 + 0.7,
            f"{r['presence'] * 100:.1f}%", ha="center", fontsize=7.5)
    ax.text(i + width / 2, r["mismatch"] * 100 + 0.7,
            f"{r['mismatch'] * 100:.1f}%", ha="center", fontsize=7.5)
ax.set_xticks(x)
ax.set_xticklabels([wrap(v, 16) for v in presence_mismatch["pair"]], fontsize=8)
ax.set_ylabel("Share of garment variants (%)", fontsize=8, color=TEXT)
ax.set_title("Presence versus material mismatch", fontsize=10, loc="left", color=TEXT)
ax.legend(frameon=False, fontsize=7.5, loc="upper right")
ax.set_ylim(0, max(presence_mismatch["presence"] * 100) * 1.35)
clean_ax(ax)
panel_label(ax, "(a)")

# Panel (b): strict conditional mismatch among variants satisfying R7 or R8 presence.
ax = fig.add_subplot(gs[0, 1])
plot_df = presence_mismatch.copy()
plot_df["conditional_mismatch"] = plot_df["conditional_mismatch"].clip(0, 1)
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
    ax.add_patch(Rectangle((x0, mismatch_h), block_w, 1 - mismatch_h,
                           facecolor="white", edgecolor="white", linewidth=1.2))
    ax.add_patch(Rectangle((x0, 0), block_w, mismatch_h,
                           facecolor=ORANGE_LIGHT, edgecolor="white", linewidth=1.2))
    ax.add_patch(Rectangle((x0, 0), block_w, 1.0,
                           facecolor="none", edgecolor="#bdbdbd", linewidth=1.2))
    ax.text(x0 + block_w / 2, 1.055, wrap(r["pair"], 18),
            ha="center", va="bottom", fontsize=8.0, color=TEXT)
    ax.text(x0 + block_w / 2, mismatch_h / 2,
            f"{mismatch_h * 100:.1f}%", ha="center", va="center",
            fontsize=8.0, color=TEXT)
legend_handles = [
    Line2D([0], [0], marker="s", linestyle="none", markerfacecolor="white",
           markeredgecolor="#bdbdbd", markersize=8, label="Material match"),
    Line2D([0], [0], marker="s", linestyle="none", markerfacecolor=ORANGE_LIGHT,
           markeredgecolor="none", markersize=8, label="Material mismatch"),
]
ax.legend(handles=legend_handles, frameon=False, fontsize=7.4, loc="lower center",
          bbox_to_anchor=(0.50, -0.17), ncol=2, handletextpad=0.45, columnspacing=1.2)
ax.text(0.0, -0.22,
        "Each square is conditional on variants where the corresponding presence flag is satisfied.",
        transform=ax.transAxes, fontsize=7.1, color=GREY_DARK, ha="left", va="top")
panel_label(ax, "(b)")

# Panels (c)-(d): the original mismatch-pair rankings remain in the main figure.
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
        ax.set_yticklabels([wrap(v, 30) for v in plot_d["label"]], fontsize=7.5)
        xmax = plot_d["n"].max()
        for i, (_, r) in enumerate(plot_d.iterrows()):
            ax.text(r["n"] + xmax * 0.03, i,
                    f"{int(r['n']):,} ({r['pct'] * 100:.1f}%)",
                    va="center", ha="left", fontsize=7.1, color=TEXT)
        ax.set_xlim(0, xmax * 1.42)
        ax.set_xlabel("Count", fontsize=8, color=TEXT)
        ax.set_title(title, fontsize=9, loc="left", color=TEXT)
        clean_ax(ax)
    panel_label(ax, lab)

fig.suptitle("Figure 5. Material mismatch in hidden and secondary components",
             fontsize=12, y=1.02, color=TEXT)
save_fig(fig, "Figure_5_material_mismatch")
plt.close(fig)

pd.concat([
    r7b_top.assign(panel="c", diagnostic="R7b"),
    r8b_top.assign(panel="d", diagnostic="R8b"),
], ignore_index=True).to_csv(
    OUT_DIR / "Figure_5_panels_c_and_d_top_mismatch_pairs.csv",
    index=False,
)

pd.DataFrame([
    {
        "diagnostic_pair": "R7/R7b",
        "n_presence": int(r7.sum()),
        "n_mismatch_total": int(r7b.sum()),
        "n_mismatch_within_presence": int((r7 & r7b).sum()),
        "n_mismatch_outside_presence": outside_r7,
        "overall_mismatch_percent": r7b.mean() * 100,
        "strict_conditional_mismatch_percent": (r7 & r7b).sum() / r7.sum() * 100,
    },
    {
        "diagnostic_pair": "R8/R8b",
        "n_presence": int(r8.sum()),
        "n_mismatch_total": int(r8b.sum()),
        "n_mismatch_within_presence": int((r8 & r8b).sum()),
        "n_mismatch_outside_presence": outside_r8,
        "overall_mismatch_percent": r8b.mean() * 100,
        "strict_conditional_mismatch_percent": (r8 & r8b).sum() / r8.sum() * 100,
    },
]).to_csv(OUT_DIR / "Figure_5_source_values_and_nesting_audit.csv", index=False)

# =============================================================================
# Figure 6: Category-level comparison and worked reading example
# =============================================================================

agg_cols = {
    "Any removable-hardware indicator": "any_removable_disruptor_default",
    "Any retained-barrier indicator": "any_retained_barrier_default",
}
rule_cols = {
    "R1 metal hardware": "r1_metal_hardware_default",
    "R2 plastic hardware": "r2_plastic_hardware_default",
    "R3 ambiguous hardware": "r3_mixed_hardware_default",
    "R4 attached trim": "r4_fabric_attached_trim_default",
    "R5 decoration": "r5_decorative_nontextile_default",
    "R6 print / coating": "r6_surface_print_coating_default",
    "R7 lining / multilayer": "r7_lining_multilayer_default",
    "R8 secondary component": "r8_secondary_component_presence_default",
}
needed = ["detail_category", *agg_cols.values(), *rule_cols.values()]
missing = sorted(set(needed) - set(row.columns))
if missing:
    raise KeyError(f"Missing category columns: {missing}")

grouped = row.groupby("detail_category")[[*agg_cols.values(), *rule_cols.values()]].mean() * 100
grouped = grouped.rename(columns={
    **{v: k for k, v in agg_cols.items()},
    **{v: k for k, v in rule_cols.items()},
})
grouped["n"] = row.groupby("detail_category").size()
grouped = grouped.sort_values("Any retained-barrier indicator", ascending=True)

example = "outerwear_jacket"
if example not in grouped.index:
    raise KeyError("outerwear_jacket is missing from category results")

fig = plt.figure(figsize=(11.2, 7.6))
gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1.15], wspace=0.42)

# Panel (a): paired category aggregates. The connector is only a visual aid.
ax = fig.add_subplot(gs[0, 0])
y = np.arange(len(grouped))
ax.scatter(grouped["Any removable-hardware indicator"], y, color=ORANGE_DARK, s=38,
           label="Any removable-hardware indicator")
ax.scatter(grouped["Any retained-barrier indicator"], y, color=BLUE_DARK, s=38,
           label="Any retained-barrier indicator")
for i, (a, b) in enumerate(zip(grouped["Any removable-hardware indicator"],
                               grouped["Any retained-barrier indicator"])):
    ax.plot([a, b], [i, i], color=LIGHT_GREY, lw=1.4, zorder=0)
ax.set_yticks(y)
ax.set_yticklabels([wrap(format_category_label(i), 22) for i in grouped.index], fontsize=7.4)
ax.set_xlabel("Share of variants within category (%)")
ax.legend(frameon=False, fontsize=7.5, loc="lower right")
clean_ax(ax)
ax.set_title("(a) Category-level prevalence by indicator group",
             loc="left", fontsize=10, fontweight="bold")
ex_y = list(grouped.index).index(example)
ax.axhspan(ex_y - 0.42, ex_y + 0.42, facecolor="#f4f4f4",
           edgecolor="#888888", lw=0.7, zorder=-1)
ax.text(
    1.0,
    ex_y,
    "Detailed in panel (b)",
    ha="left",
    va="center",
    fontsize=7,
    color=GREY_DARK,
    bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88, "pad": 1.0},
)

# Panel (b): explicit worked example for outerwear jackets.
ax = fig.add_subplot(gs[0, 1])
example_agg = grouped.loc[example, list(agg_cols)]
example_rules = grouped.loc[example, list(rule_cols)]
labels_b = [
    "Any removable-hardware indicator",
    "R1 metal hardware",
    "R2 plastic hardware",
    "R3 ambiguous hardware",
    "Any retained-barrier indicator",
    "R4 attached trim",
    "R5 decoration",
    "R6 print / coating",
    "R7 lining / multilayer",
    "R8 secondary component",
]
values_b = [
    example_agg["Any removable-hardware indicator"],
    example_rules["R1 metal hardware"],
    example_rules["R2 plastic hardware"],
    example_rules["R3 ambiguous hardware"],
    example_agg["Any retained-barrier indicator"],
    example_rules["R4 attached trim"],
    example_rules["R5 decoration"],
    example_rules["R6 print / coating"],
    example_rules["R7 lining / multilayer"],
    example_rules["R8 secondary component"],
]
colors_b = [
    ORANGE_DARK, ORANGE_LIGHT, ORANGE_LIGHT, ORANGE_LIGHT,
    BLUE_DARK, BLUE, BLUE, BLUE, BLUE, BLUE,
]
yy = np.arange(len(labels_b))
ax.barh(yy, values_b, color=colors_b)
ax.set_yticks(yy)
ax.set_yticklabels([wrap(v, 24) for v in labels_b], fontsize=7.4)
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.axhline(3.5, color="#b0b0b0", lw=0.8)
for i, v in enumerate(values_b):
    label_x = max(v + 0.8, 1.8)
    ax.text(label_x, i, f"{v:.1f}%", va="center", fontsize=7.2,
            fontweight="bold" if i in [0, 4] else "normal")
ax.set_xlabel("Share of outerwear jacket variants (%)")
clean_ax(ax)
ax.set_title("(b) Outerwear jackets: aggregate and rule-level prevalence",
             loc="left", fontsize=10, fontweight="bold")
ax.text(0, -0.12,
        "Aggregate indicators represent the union of overlapping rules and therefore "
        "do not equal the sum of the rule-level shares.",
        transform=ax.transAxes, fontsize=7, color=GREY_DARK, va="top")

fig.subplots_adjust(left=0.23, right=0.98, top=0.95, bottom=0.14, wspace=0.52)
save_fig(fig, "Figure_6_category_prevalence_worked_example")
plt.close(fig)

figure6_source = grouped.reset_index().rename(columns={"detail_category": "category_code"})
figure6_source.insert(
    1,
    "category_display",
    figure6_source["category_code"].map(format_category_label),
)
figure6_source.to_csv(OUT_DIR / "Figure_6_source_values.csv", index=False)

# Supplementary Figure S1: complete category-by-rule matrix retained outside the main figure.
heat = grouped.sort_values("Any retained-barrier indicator", ascending=False)
vals = heat[list(rule_cols)].values
fig, ax = plt.subplots(figsize=(10.4, 7.5))
cmap = LinearSegmentedColormap.from_list(
    "category_rule_scale", ["#f4f6fa", BLUE, BLUE_DARK, ORANGE_LIGHT, ORANGE_DARK]
)
im = ax.imshow(vals, aspect="auto", cmap=cmap,
               vmin=0, vmax=max(40, float(np.nanmax(vals))))
ax.set_yticks(np.arange(len(heat)))
ax.set_yticklabels([wrap(format_category_label(v), 24) for v in heat.index], fontsize=7.5)
ax.set_xticks(np.arange(len(rule_cols)))
ax.set_xticklabels([wrap(v, 16) for v in rule_cols], rotation=45,
                   ha="right", fontsize=7.5)
for i in range(vals.shape[0]):
    for j in range(vals.shape[1]):
        if vals[i, j] >= 1:
            ax.text(j, i, f"{vals[i, j]:.0f}", ha="center", va="center",
                    fontsize=6.2, color=TEXT)
cbar = fig.colorbar(im, ax=ax, pad=0.02)
cbar.set_label("Share within category (%)")
ax.tick_params(length=0)
for spine in ax.spines.values():
    spine.set_visible(False)
fig.tight_layout()
save_fig(fig, "Figure_S1_category_rule_heatmap")
plt.close(fig)

figure_s1_source = heat.reset_index().rename(columns={"detail_category": "category_code"})
figure_s1_source.insert(
    1,
    "category_display",
    figure_s1_source["category_code"].map(format_category_label),
)
figure_s1_source.to_csv(
    OUT_DIR / "Figure_S1_source_values.csv",
    index=False,
)

figure_manifest = pd.DataFrame([
    {"figure": "Figure 2", "stem": "Figure_2_aggregate_prevalence", "location": "Main text"},
    {"figure": "Figure 3", "stem": "Figure_3_removable_hardware_indicators", "location": "Main text"},
    {"figure": "Figure 4", "stem": "Figure_4_retained_barrier_indicators", "location": "Main text"},
    {"figure": "Figure 5", "stem": "Figure_5_material_mismatch", "location": "Main text"},
    {"figure": "Figure 6", "stem": "Figure_6_category_prevalence_worked_example", "location": "Main text"},
    {"figure": "Figure S1", "stem": "Figure_S1_category_rule_heatmap", "location": "Supplementary Information"},
])
figure_manifest.to_csv(OUT_DIR / "figure_output_manifest.csv", index=False)

# Final QA checks for the figure-generation stage.
qa = pd.DataFrame([
    {"check": "input_variant_count", "passed": len(row) == 47522,
     "observed": len(row), "expected": 47522},
    {"check": "r7_strict_conditional_rounds_to_34_8", "passed": round((r7 & r7b).sum() / r7.sum() * 100, 1) == 34.8,
     "observed": (r7 & r7b).sum() / r7.sum() * 100, "expected": 34.8},
    {"check": "r7b_outside_r7_equals_82", "passed": outside_r7 == 82,
     "observed": outside_r7, "expected": 82},
    {"check": "r8b_nested_in_r8", "passed": outside_r8 == 0,
     "observed": outside_r8, "expected": 0},
    {"check": "category_display_labels_complete",
     "passed": set(grouped.index).issubset(CATEGORY_DISPLAY_LABELS),
     "observed": sorted(set(grouped.index) - set(CATEGORY_DISPLAY_LABELS)),
     "expected": []},
])
qa.to_csv(OUT_DIR / "Figures_2_to_6_and_S1_QA.csv", index=False)
if not qa["passed"].all():
    raise RuntimeError("One or more figure-generation QA checks failed")

print("\nFigures 2–6 and Supplementary Figure S1 were generated.")
print(f"Output folder: {OUT_DIR.resolve()}")
