# -*- coding: utf-8 -*-
"""
Evaluate garment-level disruptor indicators from component-normalized JSONL data.

The script applies the transparent R1–R8 rule framework and the R7b/R8b
material-mismatch diagnostics under conservative, default, and expanded rule
boundaries. It exports row-level flags, aggregate summaries, matched evidence,
trigger/category diagnostics, the regex inventory, and hardware-material
disclosure diagnostics.

Default inputs and outputs
--------------------------
When the configured local project folder exists, it is used as the project
root. Otherwise, the folder containing this script is used. Paths can always
be overridden with --input-jsonl and --output-dir.

Primary output directory:
- outputs_v2
"""

import argparse
import json
import re
import time
from pathlib import Path
from collections import Counter, defaultdict
import pandas as pd


# =========================================================
# Input / output
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_PROJECT_DIR = Path(
    r"C:\Users\laptop-kl\OneDrive - Universiteit Leiden\PlasticTradeFlow"
    r"\data_mining_clothing\textile_preprocessing\waste_management\1st_revision"
)
PROJECT_DIR = LOCAL_PROJECT_DIR if LOCAL_PROJECT_DIR.exists() else SCRIPT_DIR

DEFAULT_INPUT = PROJECT_DIR / "6_JSONL_component_normalized.jsonl"
if not DEFAULT_INPUT.exists():
    DEFAULT_INPUT = SCRIPT_DIR / "6_JSONL_component_normalized.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs_v2"

_parser = argparse.ArgumentParser(description=__doc__)
_parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT,
                     help="Component-normalized JSONL input.")
_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                     help="Folder for row-level flags, summaries, evidence, and diagnostics.")
_parser.add_argument(
    "--progress-every",
    type=int,
    default=1000,
    help="Print progress after this many processed records; use 0 to disable.",
)
_args = _parser.parse_args()

input_file = _args.input_jsonl
output_dir = _args.output_dir

if not input_file.exists():
    raise FileNotFoundError(
        f"Input JSONL not found: {input_file}\n"
        "Place 6_JSONL_component_normalized.jsonl in the project folder "
        "or pass --input-jsonl with the full path."
    )

output_dir.mkdir(parents=True, exist_ok=True)
run_started = time.perf_counter()
print("Starting disruptor-rule evaluation.", flush=True)
print(f"Input:  {input_file}", flush=True)
print(f"Output: {output_dir}", flush=True)
print(
    "Output files are written after all input records have been evaluated.",
    flush=True,
)

row_csv_out = output_dir / "disruptor_rule_flags_by_variant.csv"
summary_csv_out = output_dir / "disruptor_rule_summary.csv"
aggregate_csv_out = output_dir / "disruptor_aggregate_summary.csv"
evidence_csv_out = output_dir / "disruptor_match_evidence.csv"
regex_table_file = output_dir / "disruptor_regex_inventory.csv"
summary_txt_out = output_dir / "disruptor_summary_readable.txt"
trigger_diag_csv_out = output_dir / "disruptor_trigger_diagnostics.csv"
category_diag_csv_out = output_dir / "disruptor_category_diagnostics.csv"
hardware_disclosure_csv_out = output_dir / "hardware_material_disclosure_summary.csv"


# =========================================================
# Tiny shared helpers only
# =========================================================

def norm_text(x):
    if x is None:
        return ""
    if isinstance(x, list):
        x = " ".join(str(i) for i in x if i is not None)
    x = str(x).lower().strip()
    x = x.replace("\u2019", "'").replace("\u2018", "'")
    x = x.replace("\u2013", "-").replace("\u2014", "-")
    x = re.sub(r"\s+", " ", x)
    return x


def canon_material(x):
    m = norm_text(x)
    if not m:
        return None

    if m in {"polyamide", "pa", "pa6", "pa66"}:
        return "nylon"
    if m in {"spandex", "lycra"}:
        return "elastane"
    if m in {"merino", "merino wool", "cashmere", "alpaca", "mohair"}:
        return "wool"
    if m == "rayon":
        return "viscose"
    if m == "flax":
        return "linen"
    if m in {"tencel", "tencel lyocell"}:
        return "lyocell"
    if m == "tencel modal":
        return "modal"
    if m == "naia":
        return "acetate"
    if m == "supima":
        return "cotton"
    if m in {"pet", "pes", "repreve"}:
        return "polyester"
    if m == "pp":
        return "polypropylene"

    return m


def hit(patterns, text):
    if not text:
        return False
    return any(re.search(p, text, flags=re.I) for p in patterns)


def hit_first(patterns, text):
    if not text:
        return None
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(0)
    return None


def pretty_pattern_compact(raw_pat):
    text = str(raw_pat)
    text = text.replace(r"\b", "")
    text = text.replace(r"\s+", " ")
    text = text.replace(r"\s*", " ")
    text = text.replace("[- ]", "-")
    text = text.replace("|", " / ")
    text = re.sub(r"\(\?:", "(", text)
    text = re.sub(r"\(\?<![^)]*\)", "", text)
    text = re.sub(r"\(\?![^)]*\)", "", text)
    text = text.replace("\\", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def r3_combo_label(r1_match, r2_match):
    """Return a stable evidence label for derived R3 co-occurrence cases."""
    r1 = norm_text(r1_match) or "missing_r1"
    r2 = norm_text(r2_match) or "missing_r2"
    return f"R1:{r1} + R2:{r2}"


def build_component_material_dict(comp):
    tmp = defaultdict(float)
    for m in comp.get("materials") or []:
        mat = canon_material(m.get("material"))
        pct = m.get("pct")
        if mat is None:
            continue
        try:
            pct_val = float(pct)
        except Exception:
            continue
        tmp[mat] += pct_val
    return dict(tmp)


# =========================================================
# Pattern inventories
# =========================================================
# Each pattern group is stored as (regex, plain-English label). The regex lists
# used for matching are then derived from these tuples. This keeps the matching
# logic transparent and also gives the exported regex table readable wording.

PATTERN_LABELS = {}


def patterns_only(pattern_rows):
    for pattern, label in pattern_rows:
        PATTERN_LABELS[pattern] = label
    return [pattern for pattern, _ in pattern_rows]


# ---------------------------------------------------------
# R1 Metal-specified or metal-conventional removable-hardware cues
# ---------------------------------------------------------
# R1 is intentionally restricted to explicit metal wording or hardware terms
# that are strongly metal-conventional in garment construction. Generic terms
# such as zip, buckle and snap are handled by R3 because their material is often
# not disclosed in retailer text.
R1_METAL_CONSERVATIVE_RULES = [
    # Explicit metal wording: "metal X"
    (r"\bmetal[- ]zip\b", "metal zip"),
    (r"\bmetal[- ]zipper(?:s)?\b", "metal zipper"),
    (r"\bmetal[- ]buckle(?:s)?\b", "metal buckle"),
    (r"\bmetal[- ]button(?:s)?\b", "metal button"),
    (r"\bmetal[- ]snap(?:s)?\b", "metal snap"),
    (r"\bmetal[- ]press[- ]stud(?:s)?\b", "metal press stud"),
    (r"\bmetal[- ]hook(?:s)?\b", "metal hook"),
    (r"\bmetal[- ]clasp(?:s)?\b", "metal clasp"),
    (r"\bmetal[- ]ring(?:s)?\b", "metal ring"),
    (r"\bmetal[- ]trim\b", "metal trim"),
    (r"\bmetal[- ]hardware\b", "metal hardware"),
    (r"\bmetal[- ]fastener(?:s)?\b", "metal fastener"),

    # Explicit metal wording: "X in metal" or "X metal"
    (r"\bzip\s+(?:in\s+)?metal\b", "zip in metal"),
    (r"\bzipper(?:s)?\s+(?:in\s+)?metal\b", "zipper in metal"),
    (r"\bbuckle(?:s)?\s+(?:in\s+)?metal\b", "buckle in metal"),
    (r"\bbutton(?:s)?\s+(?:in\s+)?metal\b", "button in metal"),
    (r"\bsnap(?:s)?\s+(?:in\s+)?metal\b", "snap in metal"),
    (r"\bpress[- ]stud(?:s)?\s+(?:in\s+)?metal\b", "press stud in metal"),
    (r"\bhook(?:s)?\s+(?:in\s+)?metal\b", "hook in metal"),
    (r"\bclasp(?:s)?\s+(?:in\s+)?metal\b", "clasp in metal"),
    (r"\bring(?:s)?\s+(?:in\s+)?metal\b", "ring in metal"),
    (r"\bfastener(?:s)?\s+(?:in\s+)?metal\b", "fastener in metal"),

    # Strongly metal-conventional garment hardware
    (r"\brivet(?:s)?\b", "rivet"),
    (r"\beyelet(?:s)?\b", "eyelet"),
    (r"\bgrommet(?:s)?\b", "grommet"),
    (r"\bunderwire\b", "underwire"),
    (r"\bhook[- ]and[- ]eye\b", "hook-and-eye fastener"),
    (r"\bbutton[- ]and[- ]hook\b", "button-and-hook closure"),
]
R1_METAL_DEFAULT_EXTRA_RULES = [
    # Metal-associated but less explicit than conservative terms
    (r"\bpress[- ]stud(?:s)?\b", "press stud"),
    (r"\bstud(?:s|ded)?\b", "stud or studded detail"),
    (r"\bclasp(?:s)?\b", "clasp"),
    (r"\bcharm(?:s)?\b", "charm"),
    (r"\bhook(?:s)?\b", "hook"),
]
R1_METAL_EXPANDED_EXTRA_RULES = [
    # Weakly metal-associated accessories; sensitivity only
    (r"\bcarabiner(?:s)?\b", "carabiner"),
    (r"\bring(?:s)?\b", "ring"),
]
R1_METAL_EXCLUDE_RULES = [
    (r"\bbutton[- ]down\b", "button-down phrase"),
    (r"\bhooks?\s*:\s*no\b", "negative hook mention"),
    (r"\bhooks?\s+no\b", "negative hook mention"),
]
PAT_R1_METAL_CONSERVATIVE = patterns_only(R1_METAL_CONSERVATIVE_RULES)
PAT_R1_METAL_DEFAULT_EXTRA = patterns_only(R1_METAL_DEFAULT_EXTRA_RULES)
PAT_R1_METAL_EXPANDED_EXTRA = patterns_only(R1_METAL_EXPANDED_EXTRA_RULES)
PAT_R1_METAL_EXCLUDE = patterns_only(R1_METAL_EXCLUDE_RULES)


# ---------------------------------------------------------
# R2 Plastic-specified removable-hardware cues
# ---------------------------------------------------------
# R2 is restricted to explicit plastic / polymer / resin wording. Generic
# hardware terms such as stopper, cord lock, toggle and boning are handled by R3
# unless the retailer text explicitly identifies them as plastic.
R2_PLASTIC_CONSERVATIVE_RULES = [
    # Explicit plastic wording: "plastic X"
    (r"\bplastic[- ]zip\b", "plastic zip"),
    (r"\bplastic[- ]zipper(?:s)?\b", "plastic zipper"),
    (r"\bplastic[- ]buckle(?:s)?\b", "plastic buckle"),
    (r"\bplastic[- ]snap(?:s)?\b", "plastic snap"),
    (r"\bplastic[- ]button(?:s)?\b", "plastic button"),
    (r"\bplastic[- ]fastener(?:s)?\b", "plastic fastener"),
    (r"\bplastic[- ]toggle(?:s)?\b", "plastic toggle"),
    (r"\bplastic[- ]stopper(?:s)?\b", "plastic stopper"),
    (r"\bplastic[- ]hardware\b", "plastic hardware"),
    (r"\bplastic[- ]trim\b", "plastic trim"),

    # Explicit plastic wording: "X in plastic" or "X plastic"
    (r"\bzip\s+(?:in\s+)?plastic\b", "zip in plastic"),
    (r"\bzipper(?:s)?\s+(?:in\s+)?plastic\b", "zipper in plastic"),
    (r"\bbuckle(?:s)?\s+(?:in\s+)?plastic\b", "buckle in plastic"),
    (r"\bsnap(?:s)?\s+(?:in\s+)?plastic\b", "snap in plastic"),
    (r"\bbutton(?:s)?\s+(?:in\s+)?plastic\b", "button in plastic"),
    (r"\bfastener(?:s)?\s+(?:in\s+)?plastic\b", "fastener in plastic"),
    (r"\btoggle(?:s)?\s+(?:in\s+)?plastic\b", "toggle in plastic"),
    (r"\bstopper(?:s)?\s+(?:in\s+)?plastic\b", "stopper in plastic"),

    # Brand-specific explicit phrase observed in retailer text
    (r"\bhypoallergenic[- ]plastic[- ]snap[- ]button(?:s)?\b", "hypoallergenic plastic snap button"),

    # Moulded plastic wording
    (r"\bmoulded[- ]plastic[- ]zip\b", "moulded plastic zip"),
    (r"\bmoulded[- ]plastic[- ]zipper(?:s)?\b", "moulded plastic zipper"),
    (r"\bmolded[- ]plastic[- ]zip\b", "molded plastic zip"),
    (r"\bmolded[- ]plastic[- ]zipper(?:s)?\b", "molded plastic zipper"),
    (r"\bmoulded[- ]plastic[- ]buckle(?:s)?\b", "moulded plastic buckle"),
    (r"\bmolded[- ]plastic[- ]buckle(?:s)?\b", "molded plastic buckle"),
    (r"\bmoulded[- ]plastic[- ]button(?:s)?\b", "moulded plastic button"),
    (r"\bmolded[- ]plastic[- ]button(?:s)?\b", "molded plastic button"),
    (r"\bmoulded[- ]plastic[- ]snap(?:s)?\b", "moulded plastic snap"),
    (r"\bmolded[- ]plastic[- ]snap(?:s)?\b", "molded plastic snap"),
    (r"\bmoulded[- ]plastic[- ]fastener(?:s)?\b", "moulded plastic fastener"),
    (r"\bmolded[- ]plastic[- ]fastener(?:s)?\b", "molded plastic fastener"),
    (r"\bmoulded[- ]plastic[- ]trim\b", "moulded plastic trim"),
    (r"\bmolded[- ]plastic[- ]trim\b", "molded plastic trim"),
]
R2_PLASTIC_DEFAULT_EXTRA_RULES = [
    # Additional explicit plastic / polymer / resin wording
    (r"\bpolymer[- ]zip(?:per)?(?:s)?\b", "polymer zip or zipper"),
    (r"\bpolymer[- ]buckle(?:s)?\b", "polymer buckle"),
    (r"\bpolymer[- ]snap(?:s)?\b", "polymer snap"),
    (r"\bpolymer[- ]button(?:s)?\b", "polymer button"),
    (r"\bpolymer[- ]fastener(?:s)?\b", "polymer fastener"),
    (r"\bresin[- ]button(?:s)?\b", "resin button"),
    (r"\bresin[- ]buckle(?:s)?\b", "resin buckle"),
    (r"\bresin[- ]fastener(?:s)?\b", "resin fastener"),
]
R2_PLASTIC_EXPANDED_EXTRA_RULES = [
    # Weak explicit synthetic wording; sensitivity only
    (r"\bsynthetic[- ]button(?:s)?\b", "synthetic button"),
    (r"\bsynthetic[- ]buckle(?:s)?\b", "synthetic buckle"),
    (r"\bsynthetic[- ]fastener(?:s)?\b", "synthetic fastener"),
]
R2_PLASTIC_EXCLUDE_RULES = [
    (r"\bbutton[- ]down\b", "button-down phrase"),
]
PAT_R2_PLASTIC_CONSERVATIVE = patterns_only(R2_PLASTIC_CONSERVATIVE_RULES)
PAT_R2_PLASTIC_DEFAULT_EXTRA = patterns_only(R2_PLASTIC_DEFAULT_EXTRA_RULES)
PAT_R2_PLASTIC_EXPANDED_EXTRA = patterns_only(R2_PLASTIC_EXPANDED_EXTRA_RULES)
PAT_R2_PLASTIC_EXCLUDE = patterns_only(R2_PLASTIC_EXCLUDE_RULES)


# ---------------------------------------------------------
# R3 Material-ambiguous removable-hardware cues
# ---------------------------------------------------------
# R3 includes generic hard-hardware terms whose material cannot be inferred
# reliably from retailer text. Explicit mixed-material wording is retained here
# as a non-mono removable-hardware cue, but R3 is no longer derived from R1 + R2
# co-occurrence.
R3_MIXED_CONSERVATIVE_RULES = [
    # Explicit mixed-material wording
    (r"\bmetal[- ]and[- ]plastic\b", "metal and plastic"),
    (r"\bmixed[- ]hardware\b", "mixed hardware"),
    (r"\bmixed[- ]material[- ]zip\b", "mixed-material zip"),
    (r"\bmixed[- ]buckle\b", "mixed buckle"),

    # Common but material-ambiguous hard-hardware terms
    (r"\bzip\b", "zip"),
    (r"\bzipper(?:s)?\b", "zipper"),
    (r"\bzip[- ]up\b", "zip-up"),
    (r"\bfull[- ]zip\b", "full-zip"),
    (r"\bhalf[- ]zip\b", "half-zip"),
    (r"\bzip[- ]fly\b", "zip fly"),
    (r"\bconcealed[- ]zip\b", "concealed zip"),
    (r"\bside[- ]zip\b", "side zip"),
    (r"\bzipped\b", "zipped"),
    (r"\bbuckle(?:s)?\b", "buckle"),
    (r"\bsnap(?:[- ]button)?(?:s)?\b", "snap or snap button"),
    (r"\btoggle(?:s)?\b", "toggle"),
    (r"\bboning\b", "boning"),
    (r"\bcord[- ]lock(?:s)?\b", "cord lock"),
    (r"\bstopper(?:s)?\b", "stopper"),
    (r"\bcollar[- ]stay(?:s)?\b", "collar stay"),
    (r"\bcollar[- ]support(?:s)?\b", "collar support"),
]
R3_MIXED_DEFAULT_EXTRA_RULES = [
    (r"\bfastener(?:s)?\b", "fastener"),
]
R3_MIXED_EXPANDED_EXTRA_RULES = [
    (r"\bhardware[- ]combination\b", "hardware combination"),
    (r"\bmultiple[- ]hardware[- ]types\b", "multiple hardware types"),
    (r"\bhardware\b", "hardware"),
    (r"\bbutton(?:s)?\b", "button"),
]
R3_MIXED_EXCLUDE_RULES = [
    (r"\bbutton[- ]down\b", "button-down phrase"),
    (r"\bhooks?\s*:\s*no\b", "negative hook mention"),
    (r"\bhooks?\s+no\b", "negative hook mention"),
]
PAT_R3_MIXED_CONSERVATIVE = patterns_only(R3_MIXED_CONSERVATIVE_RULES)
PAT_R3_MIXED_DEFAULT_EXTRA = patterns_only(R3_MIXED_DEFAULT_EXTRA_RULES)
PAT_R3_MIXED_EXPANDED_EXTRA = patterns_only(R3_MIXED_EXPANDED_EXTRA_RULES)
PAT_R3_MIXED_EXCLUDE = patterns_only(R3_MIXED_EXCLUDE_RULES)


# ---------------------------------------------------------
# R4 Fabric attached trim
# ---------------------------------------------------------
R4_COMPONENT_RULES = [
    (r"\belastic_part\b", "component name: elastic part"),
    (r"\belastic\b", "component name: elastic"),
    (r"\bbinder_part\b", "component name: binder part"),
    (r"\bbinding\b", "component name: binding"),
    (r"\bpiping\b", "component name: piping"),
    (r"\btape\b", "component name: tape"),
    (r"\blace\b", "component name: lace"),
    (r"\bstrap\b", "component name: strap"),
    (r"\bcuff\b", "component name: cuff"),
]
R4_TRIM_CONSERVATIVE_RULES = [
    (r"\bdrawstring(?:s)?\b", "drawstring"),
    (r"\bdrawcord(?:s)?\b", "drawcord"),
    (r"\bpatch(?:es)?\b", "patch"),
    (r"\bembroidery\b", "embroidery"),
    (r"\bembroidered\b", "embroidered detail"),
    (r"\bapplique\b", "applique"),
    (r"\bappliqué\b", "appliqué"),
    (r"\bbadge(?:s)?\b", "badge"),
    (r"\blace[- ]trim\b", "lace trim"),
]
R4_TRIM_DEFAULT_EXTRA_RULES = [
    (r"\bbinding\b", "binding"),
    (r"\bpiping\b", "piping"),
    (r"\belastic\b", "elastic"),
    (r"\btape(?:s)?\b", "tape"),
    (r"\bribbon(?:s)?\b", "ribbon"),
]
R4_TRIM_EXPANDED_EXTRA_RULES = [
    (r"\belasticated\b", "elasticated"),
    (r"\bstrap(?:s)?\b", "strap"),
    (r"\bfabric[- ]trim\b", "fabric trim"),
    (r"\bdecorative[- ]tape\b", "decorative tape"),
    (r"\bcontrast[- ]trim\b", "contrast trim"),
]
R4_TRIM_EXCLUDE_RULES = [
    (r"\bribbed\b", "ribbed"),
    (r"\bstretch\b", "stretch"),
]
PAT_R4_COMPONENT = patterns_only(R4_COMPONENT_RULES)
PAT_R4_TRIM_CONSERVATIVE = patterns_only(R4_TRIM_CONSERVATIVE_RULES)
PAT_R4_TRIM_DEFAULT_EXTRA = patterns_only(R4_TRIM_DEFAULT_EXTRA_RULES)
PAT_R4_TRIM_EXPANDED_EXTRA = patterns_only(R4_TRIM_EXPANDED_EXTRA_RULES)
PAT_R4_TRIM_EXCLUDE = patterns_only(R4_TRIM_EXCLUDE_RULES)


# ---------------------------------------------------------
# R5 Decorative / non-textile attachments
# ---------------------------------------------------------
R5_DECOR_CONSERVATIVE_RULES = [
    (r"\bleather[- ]trim\b", "leather trim"),
    (r"\bsuede[- ]patch\b", "suede patch"),
    (r"\bfur[- ]trim\b", "fur trim"),
    (r"\bfaux[- ]fur\b", "faux fur"),
    (r"\bfaux_fur\b", "faux fur component"),
    (r"\bpendant(?:s)?\b", "pendant"),
    (r"\bsequin(?:s|ed)?\b", "sequin or sequined detail"),
    (r"\blurex\b", "lurex"),
    (r"\bmetallic[- ]yarn\b", "metallic yarn"),
    (r"\brhinestone(?:s)?\b", "rhinestone"),
]
R5_DECOR_DEFAULT_EXTRA_RULES = [
    (r"\bbead(?:ed|s)?\b", "bead or beaded detail"),
    (r"\bglitter\b", "glitter"),
    (r"\bembellished\b", "embellished detail"),
    (r"\bpearl(?:s)?\b", "pearl"),
    (r"\bfringe\b", "fringe"),
]
R5_DECOR_EXPANDED_EXTRA_RULES = [
    (r"\bsparkle[- ]trim\b", "sparkle trim"),
    (r"\bornamental[- ]trim\b", "ornamental trim"),
    (r"\bdecorative[- ]embellishment\b", "decorative embellishment"),
]
PAT_R5_DECOR_CONSERVATIVE = patterns_only(R5_DECOR_CONSERVATIVE_RULES)
PAT_R5_DECOR_DEFAULT_EXTRA = patterns_only(R5_DECOR_DEFAULT_EXTRA_RULES)
PAT_R5_DECOR_EXPANDED_EXTRA = patterns_only(R5_DECOR_EXPANDED_EXTRA_RULES)


# ---------------------------------------------------------
# R6 Surface print / coating / laminated barrier
# ---------------------------------------------------------
R6_COMPONENT_RULES = [
    (r"\bcoating\b", "component name: coating"),
]
R6_SURFACE_CONSERVATIVE_RULES = [
    (r"\bcoated\b", "coated"),
    (r"\bcoating\b", "coating"),
    (r"\blaminated\b", "laminated"),
    (r"\bbonded\b", "bonded"),
    (r"\breflective[- ]print\b", "reflective print"),
    (r"\bfoil[- ]print\b", "foil print"),
    (r"\bflock[- ]print\b", "flock print"),
    (r"\bpu[- ]coating\b", "PU coating"),
    (r"\bpvc\b", "PVC"),
    (r"\bseam[- ]tape\b", "seam tape"),
]
R6_SURFACE_DEFAULT_EXTRA_RULES = [
    (r"\bgraphic[- ]print\b", "graphic print"),
    (r"\blogo[- ]print\b", "logo print"),
    (r"\breflective[- ]print\b", "reflective print"),
    (r"\bfoil[- ]print\b", "foil print"),
    (r"\bflock[- ]print\b", "flock print"),
    (r"\bwater[- ]repellent\b", "water-repellent finish"),
    (r"\bwaterproof\b", "waterproof finish"),
    (r"\bwater[- ]resistant\b", "water-resistant finish"),
    (r"\blaminated[- ]film\b", "laminated film"),
    (r"\btaped[- ]seams?\b", "taped seams"),
]
R6_SURFACE_EXPANDED_EXTRA_RULES = [
    (r"\ball[- ]over[- ]print\b", "all-over print"),
    (r"\bwaterproof[- ]finish\b", "waterproof finish"),
    (r"\btreated[- ]surface\b", "treated surface"),
    (r"\bprotective[- ]coating\b", "protective coating"),
    (r"\breflective[- ]details?\b", "reflective details"),
]
PAT_R6_COMPONENT = patterns_only(R6_COMPONENT_RULES)
PAT_R6_SURFACE_CONSERVATIVE = patterns_only(R6_SURFACE_CONSERVATIVE_RULES)
PAT_R6_SURFACE_DEFAULT_EXTRA = patterns_only(R6_SURFACE_DEFAULT_EXTRA_RULES)
PAT_R6_SURFACE_EXPANDED_EXTRA = patterns_only(R6_SURFACE_EXPANDED_EXTRA_RULES)


# ---------------------------------------------------------
# R7 Lining / multilayer
# ---------------------------------------------------------
R7_COMPONENT_RULES = [
    (r"\blining\b", "component name: lining"),
    (r"\bfront_body_lining\b", "component name: front body lining"),
    (r"\bbody_lining\b", "component name: body lining"),
    (r"\bskirt_lining\b", "component name: skirt lining"),
    (r"\bcup_lining\b", "component name: cup lining"),
    (r"\bhood_lining\b", "component name: hood lining"),
    (r"\bsleeve_lining\b", "component name: sleeve lining"),
    (r"\binner_layer\b", "component name: inner layer"),
    (r"\binner_pants\b", "component name: inner pants"),
    (r"\binterlining\b", "component name: interlining"),
    (r"\bpetticoat\b", "component name: petticoat"),
    (r"\bdown_proof_fabric\b", "component name: down-proof fabric"),
]
R7_LINING_DEFAULT_RULES = [
    (r"\blined\b", "lined"),
    (r"\bfully[- ]lined\b", "fully lined"),
    (r"\bdouble[- ]layer\b", "double layer"),
    (r"\bdouble layer\b", "double layer"),
    (r"\binner[- ]layer\b", "inner layer"),
    (r"\bmesh[- ]lined\b", "mesh-lined"),
    (r"\bfleece[- ]lined\b", "fleece-lined"),
    (r"\bjersey[- ]lined\b", "jersey-lined"),
]
R7_LINING_EXPANDED_EXTRA_RULES = [
    (r"\blayered\b", "layered"),
    (r"\bmultilayer\b", "multilayer"),
    (r"\btwo[- ]layer\b", "two-layer"),
    (r"\binsulated[- ]lining\b", "insulated lining"),
]
R7_LINING_EXCLUDE_RULES = [
    (r"\bneckline\b", "neckline"),
    (r"\bhemline\b", "hemline"),
    (r"\ba-line\b", "A-line"),
    (r"\blinen\b", "linen"),
]
PAT_R7_COMPONENT = patterns_only(R7_COMPONENT_RULES)
PAT_R7_LINING_DEFAULT = patterns_only(R7_LINING_DEFAULT_RULES)
PAT_R7_LINING_EXPANDED_EXTRA = patterns_only(R7_LINING_EXPANDED_EXTRA_RULES)
PAT_R7_LINING_EXCLUDE = patterns_only(R7_LINING_EXCLUDE_RULES)


# ---------------------------------------------------------
# R8 Secondary component presence
# ---------------------------------------------------------
R8_COMPONENT_RULES = [
    (r"\bpocket_lining\b", "component name: pocket lining"),
    (r"\bpocket_fabric\b", "component name: pocket fabric"),
    (r"\bchest_pocket_fabric\b", "component name: chest pocket fabric"),
    (r"\binner_pocket_fabric\b", "component name: inner pocket fabric"),
    (r"\bside_pocket_fabric\b", "component name: side pocket fabric"),
    (r"\bmesh\b", "component name: mesh"),
    (r"\btop_panel\b", "component name: top panel"),
    (r"\bbottom_panel\b", "component name: bottom panel"),
    (r"\bfront_panel\b", "component name: front panel"),
    (r"\bback_panel\b", "component name: back panel"),
    (r"\bside_panel\b", "component name: side panel"),
    (r"\binside_panel\b", "component name: inside panel"),
    (r"\bwing\b", "component name: wing"),
    (r"\bwoven_part\b", "component name: woven part"),
    (r"\bknit_part\b", "component name: knit part"),
]
R8_SECONDARY_CONSERVATIVE_RULES = [
    (r"\bcontrast[- ]panel\b", "contrast panel"),
    (r"\bcontrast[- ]insert\b", "contrast insert"),
    (r"\bcontrast[- ]fabric\b", "contrast fabric"),
    (r"\bmesh[- ]insert\b", "mesh insert"),
    (r"\bpocket[- ]lining\b", "pocket lining"),
    (r"\bpocket[- ]bag\b", "pocket bag"),
    (r"\bpocket[- ]fabric\b", "pocket fabric"),
]
R8_SECONDARY_DEFAULT_EXTRA_RULES = []
R8_SECONDARY_EXPANDED_EXTRA_RULES = [
    (r"\byoke\b", "yoke"),
    (r"\binset\b", "inset"),
    (r"\binsert\b", "insert"),
    (r"\bpanel[- ]detail\b", "panel detail"),
    (r"\binsert[- ]detail\b", "insert detail"),
]
R8_SECONDARY_EXCLUDE_RULES = [
    (r"\bpocket\b", "generic pocket mention"),
    (r"\bpanel\b", "generic panel mention"),
]
PAT_R8_COMPONENT = patterns_only(R8_COMPONENT_RULES)
PAT_R8_SECONDARY_CONSERVATIVE = patterns_only(R8_SECONDARY_CONSERVATIVE_RULES)
PAT_R8_SECONDARY_DEFAULT_EXTRA = patterns_only(R8_SECONDARY_DEFAULT_EXTRA_RULES)
PAT_R8_SECONDARY_EXPANDED_EXTRA = patterns_only(R8_SECONDARY_EXPANDED_EXTRA_RULES)
PAT_R8_SECONDARY_EXCLUDE = patterns_only(R8_SECONDARY_EXCLUDE_RULES)


# Plain-English pattern export helper

def pattern_to_plain_english(pattern):
    return PATTERN_LABELS.get(pattern, pretty_pattern_compact(pattern))


# =========================================================
# Hidden / secondary logic inventories borrowed from v6
# =========================================================
HIDDEN_COMPONENT_CLASSES = {"lining_component", "filling_component"}

HIDDEN_COMPONENT_NAMES = {
    "lining", "body_lining", "hood_lining", "sleeve_lining", "skirt_lining",
    "cup_lining", "inner_layer", "interlining", "inner_pants", "petticoat",
    "filling", "padding", "body_filling", "upper_body_filling", "under_body_filling",
    "down_proof_fabric",
}

SECONDARY_COMPONENT_CLASSES = {"pocket_component", "panel_component", "trim_component"}
SECONDARY_COMPONENT_NAMES = {
    "pocket_lining", "pocket_fabric", "chest_pocket_fabric",
    "inner_pocket_fabric", "side_pocket_fabric", "mesh", "top_panel",
    "bottom_panel", "front_panel", "back_panel", "side_panel",
    "inside_panel", "wing", "woven_part", "knit_part",
}

R8B_ALLOWED_COMPONENT_NAMES = {
    "pocket_lining", "pocket_fabric", "chest_pocket_fabric",
    "inner_pocket_fabric", "side_pocket_fabric", "mesh", "top_panel",
    "bottom_panel", "front_panel", "back_panel", "side_panel",
    "inside_panel", "wing", "woven_part", "knit_part"
}


# =========================================================
# Main
# =========================================================

rows = []
summary_rows = []
aggregate_rows = []
evidence_rows = []

brand_counter = Counter()
parent_counter = Counter()

with open(input_file, "r", encoding="utf-8") as fin:
    for line_no, line in enumerate(fin, start=1):
        line = line.strip()
        if not line:
            continue

        rec = json.loads(line)

        brand_counter[str(rec.get("brand"))] += 1
        parent_counter[str(rec.get("parent_category"))] += 1

        comps = rec.get("components_structured") or []
        if not isinstance(comps, list):
            comps = []

        # -------------------------------------------------
        # Build searchable fields
        # -------------------------------------------------
        product_name = norm_text(rec.get("product_name"))
        raw_description_text = norm_text(rec.get("raw_description_text"))
        raw_function_text = norm_text(rec.get("raw_function_text"))
        raw_material_text_norm = norm_text(rec.get("raw_material_text_norm"))
        raw_material_text_full = norm_text(rec.get("raw_material_text_full"))
        variant_colour = norm_text(rec.get("variant_colour"))
        parent_category = norm_text(rec.get("parent_category"))
        detail_category = norm_text(rec.get("detail_category"))

        component_name_list = []
        component_class_list = []
        component_path_list = []
        component_raw_list = []

        shell_material_pairs = []
        all_material_pairs = []

        for comp in comps:
            cname = norm_text(comp.get("component_name_norm"))
            cclass = norm_text(comp.get("component_class"))
            cpath = norm_text(comp.get("component_path_raw"))
            craw = norm_text(comp.get("raw_text"))

            if cname:
                component_name_list.append(cname)
            if cclass:
                component_class_list.append(cclass)
            if cpath:
                component_path_list.append(cpath)
            if craw:
                component_raw_list.append(craw)

            mats = comp.get("materials") or []
            tmp_pairs = []
            for m in mats:
                mat = canon_material(m.get("material"))
                pct = m.get("pct")
                if mat is None:
                    continue
                try:
                    pct_val = float(pct) if pct is not None else None
                except Exception:
                    pct_val = None

                tmp_pairs.append((mat, pct_val))
                all_material_pairs.append((mat, pct_val))

            if cname in {"shell", "body", "main"} or cclass == "surface_component":
                shell_material_pairs.extend(tmp_pairs)

        component_names_text = " ".join(component_name_list)
        component_classes_text = " ".join(component_class_list)
        component_paths_text = " ".join(component_path_list)
        component_raw_text = " ".join(component_raw_list)

        # -------------------------------------------------
        # Borrowed surface-reference logic from sorting v6
        # -------------------------------------------------
        surface_ref_name = ""
        surface_ref_dict = {}
        surface_ref_sorted = []
        surface_ref_source = ""

        # first: coating as outermost readable surface
        for comp in comps:
            cclass = norm_text(comp.get("component_class"))
            cname = norm_text(comp.get("component_name_norm"))
            if cclass == "surface_component" and cname == "coating":
                tmp = build_component_material_dict(comp)
                if tmp:
                    surface_ref_name = "coating"
                    surface_ref_dict = tmp
                    surface_ref_sorted = sorted(tmp.items(), key=lambda x: (-x[1], x[0]))
                    surface_ref_source = "coating_surface_component"
                    break

        # second: first surface_component in original order
        if not surface_ref_dict:
            for comp in comps:
                cclass = norm_text(comp.get("component_class"))
                cname = norm_text(comp.get("component_name_norm"))
                if cclass == "surface_component":
                    tmp = build_component_material_dict(comp)
                    if tmp:
                        surface_ref_name = cname
                        surface_ref_dict = tmp
                        surface_ref_sorted = sorted(tmp.items(), key=lambda x: (-x[1], x[0]))
                        surface_ref_source = "first_surface_component"
                        break

        # third: first component overall as fallback
        if not surface_ref_dict and comps:
            comp = comps[0]
            cname = norm_text(comp.get("component_name_norm"))
            tmp = build_component_material_dict(comp)
            if tmp:
                surface_ref_name = cname
                surface_ref_dict = tmp
                surface_ref_sorted = sorted(tmp.items(), key=lambda x: (-x[1], x[0]))
                surface_ref_source = "first_component_fallback"

        surface_dom = surface_ref_sorted[0][0] if surface_ref_sorted else None

        hidden_components = []
        secondary_components = []

        for comp in comps:
            cclass = norm_text(comp.get("component_class"))
            cname = norm_text(comp.get("component_name_norm"))
            if cclass in HIDDEN_COMPONENT_CLASSES or cname in HIDDEN_COMPONENT_NAMES:
                hidden_components.append(comp)
            if cclass in SECONDARY_COMPONENT_CLASSES or cname in SECONDARY_COMPONENT_NAMES:
                secondary_components.append(comp)

        out = {
            "row_id": line_no,
            "brand": rec.get("brand"),
            "region": rec.get("region"),
            "parent_product_id": rec.get("parent_product_id"),
            "variant_colour": rec.get("variant_colour"),
            "parent_category": rec.get("parent_category"),
            "detail_category": rec.get("detail_category"),
            "product_name": rec.get("product_name"),
            "surface_ref_component_name": surface_ref_name,
            "surface_ref_source": surface_ref_source,
            "surface_ref_dominant_material": surface_dom,
        }

        # =================================================
        # Scenario loop
        # =================================================
        for setting in ["conservative", "default", "expanded"]:

            # -------------------------------------------------
            # R1 Metal-specified or metal-conventional removable-hardware cues
            # -------------------------------------------------
            r1_patterns = list(PAT_R1_METAL_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r1_patterns += PAT_R1_METAL_DEFAULT_EXTRA
            if setting == "expanded":
                r1_patterns += PAT_R1_METAL_EXPANDED_EXTRA

            r1_hit = False
            r1_field = ""
            r1_match = ""

            for fld, txt in [
                ("product_name", product_name),
                ("raw_description_text", raw_description_text),
                ("raw_function_text", raw_function_text),
            ]:
                if hit(PAT_R1_METAL_EXCLUDE, txt):
                    txt = re.sub("|".join(PAT_R1_METAL_EXCLUDE), " ", txt, flags=re.I)

                m = hit_first(r1_patterns, txt)
                if m:
                    if m in {"button", "buttons", "hook", "hooks", "snap", "snaps", "stud", "studs", "clasp", "clasps", "ring", "rings"}:
                        if not re.search(r"zip|zipper|closure|fasten|hardware|button|snap|hook|buckle|eyelet|grommet|underwire", txt, flags=re.I):
                            continue
                    r1_hit = True
                    r1_field = fld
                    r1_match = m
                    break

            out[f"r1_metal_hardware_{setting}"] = int(r1_hit)
            if r1_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R1", "setting": setting, "field": r1_field, "match": r1_match})

            # -------------------------------------------------
            # R2 Plastic-specified removable-hardware cues
            # -------------------------------------------------
            r2_patterns = list(PAT_R2_PLASTIC_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r2_patterns += PAT_R2_PLASTIC_DEFAULT_EXTRA
            if setting == "expanded":
                r2_patterns += PAT_R2_PLASTIC_EXPANDED_EXTRA

            r2_hit = False
            r2_field = ""
            r2_match = ""

            for fld, txt in [
                ("product_name", product_name),
                ("raw_description_text", raw_description_text),
                ("raw_function_text", raw_function_text),
            ]:
                if hit(PAT_R2_PLASTIC_EXCLUDE, txt):
                    txt = re.sub("|".join(PAT_R2_PLASTIC_EXCLUDE), " ", txt, flags=re.I)

                m = hit_first(r2_patterns, txt)
                if m:
                    if m in {"buckle", "buckles", "zipper", "zippers", "button", "buttons"}:
                        if not re.search(r"plastic|polymer|resin|synthetic", txt, flags=re.I):
                            continue
                    r2_hit = True
                    r2_field = fld
                    r2_match = m
                    break

            out[f"r2_plastic_hardware_{setting}"] = int(r2_hit)
            if r2_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R2", "setting": setting, "field": r2_field, "match": r2_match})

            # -------------------------------------------------
            # R3 Material-ambiguous removable-hardware cues
            # -------------------------------------------------
            r3_patterns = list(PAT_R3_MIXED_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r3_patterns += PAT_R3_MIXED_DEFAULT_EXTRA
            if setting == "expanded":
                r3_patterns += PAT_R3_MIXED_EXPANDED_EXTRA

            r3_hit = False
            r3_field = ""
            r3_match = ""

            for fld, txt in [
                ("product_name", product_name),
                ("raw_description_text", raw_description_text),
                ("raw_function_text", raw_function_text),
            ]:
                if hit(PAT_R3_MIXED_EXCLUDE, txt):
                    txt = re.sub("|".join(PAT_R3_MIXED_EXCLUDE), " ", txt, flags=re.I)

                m = hit_first(r3_patterns, txt)
                if m:
                    if m in {"button", "buttons", "hardware", "fastener", "fasteners"}:
                        if not re.search(r"zip|zipper|closure|fasten|hardware|button|snap|hook|buckle|eyelet|grommet|underwire|drawstring|cord", txt, flags=re.I):
                            continue
                    r3_hit = True
                    r3_field = fld
                    r3_match = m
                    break

            out[f"r3_mixed_hardware_{setting}"] = int(r3_hit)
            if r3_hit:
                evidence_rows.append({
                    "row_id": line_no,
                    "rule": "R3",
                    "setting": setting,
                    "field": r3_field,
                    "match": r3_match,
                    "r3_evidence_type": "explicit_text",
                })

            # -------------------------------------------------
            # R4 Fabric attached trim
            # -------------------------------------------------
            r4_patterns = list(PAT_R4_TRIM_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r4_patterns += PAT_R4_TRIM_DEFAULT_EXTRA
            if setting == "expanded":
                r4_patterns += PAT_R4_TRIM_EXPANDED_EXTRA

            r4_hit = False
            r4_field = ""
            r4_match = ""

            m = hit_first(PAT_R4_COMPONENT, component_names_text)
            if m:
                r4_hit = True
                r4_field = "component_names_text"
                r4_match = m
            else:
                for fld, txt in [
                    ("raw_description_text", raw_description_text),
                    ("product_name", product_name),
                ]:
                    if hit(PAT_R4_TRIM_EXCLUDE, txt):
                        txt = re.sub("|".join(PAT_R4_TRIM_EXCLUDE), " ", txt, flags=re.I)
                    m = hit_first(r4_patterns, txt)
                    if m:
                        r4_hit = True
                        r4_field = fld
                        r4_match = m
                        break

            out[f"r4_fabric_attached_trim_{setting}"] = int(r4_hit)
            if r4_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R4", "setting": setting, "field": r4_field, "match": r4_match})

            # -------------------------------------------------
            # R5 Decorative / non-textile attachments
            # -------------------------------------------------
            r5_patterns = list(PAT_R5_DECOR_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r5_patterns += PAT_R5_DECOR_DEFAULT_EXTRA
            if setting == "expanded":
                r5_patterns += PAT_R5_DECOR_EXPANDED_EXTRA

            r5_hit = False
            r5_field = ""
            r5_match = ""

            for fld, txt in [
                ("product_name", product_name),
                ("raw_description_text", raw_description_text),
                ("component_names_text", component_names_text),
            ]:
                m = hit_first(r5_patterns, txt)
                if m:
                    r5_hit = True
                    r5_field = fld
                    r5_match = m
                    break

            out[f"r5_decorative_nontextile_{setting}"] = int(r5_hit)
            if r5_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R5", "setting": setting, "field": r5_field, "match": r5_match})

            # -------------------------------------------------
            # R6 Surface print / coating
            # -------------------------------------------------
            r6_patterns = list(PAT_R6_SURFACE_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r6_patterns += PAT_R6_SURFACE_DEFAULT_EXTRA
            if setting == "expanded":
                r6_patterns += PAT_R6_SURFACE_EXPANDED_EXTRA

            r6_hit = False
            r6_field = ""
            r6_match = ""

            m = hit_first(PAT_R6_COMPONENT, component_names_text)
            if m:
                r6_hit = True
                r6_field = "component_names_text"
                r6_match = m
            else:
                for fld, txt in [
                    ("raw_description_text", raw_description_text),
                    ("product_name", product_name),
                    ("raw_function_text", raw_function_text),
                ]:
                    m = hit_first(r6_patterns, txt)
                    if m:
                        r6_hit = True
                        r6_field = fld
                        r6_match = m
                        break

            out[f"r6_surface_print_coating_{setting}"] = int(r6_hit)
            if r6_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R6", "setting": setting, "field": r6_field, "match": r6_match})

            # -------------------------------------------------
            # R7 Lining / multilayer presence
            # -------------------------------------------------
            r7_patterns = []
            if setting in {"default", "expanded"}:
                r7_patterns += PAT_R7_LINING_DEFAULT
            if setting == "expanded":
                r7_patterns += PAT_R7_LINING_EXPANDED_EXTRA

            r7_hit = False
            r7_field = ""
            r7_match = ""

            m = hit_first(PAT_R7_COMPONENT, component_names_text)
            if m:
                r7_hit = True
                r7_field = "component_names_text"
                r7_match = m
            else:
                for fld, txt in [
                    ("raw_description_text", raw_description_text),
                    ("product_name", product_name),
                    ("raw_function_text", raw_function_text),
                ]:
                    if hit(PAT_R7_LINING_EXCLUDE, txt):
                        txt = re.sub("|".join(PAT_R7_LINING_EXCLUDE), " ", txt, flags=re.I)
                    m = hit_first(r7_patterns, txt)
                    if m:
                        r7_hit = True
                        r7_field = fld
                        r7_match = m
                        break

            out[f"r7_lining_multilayer_{setting}"] = int(r7_hit)
            if r7_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R7_presence", "setting": setting, "field": r7_field, "match": r7_match})

            # -------------------------------------------------
            # R7b Hidden-layer material mismatch (NEW)
            # -------------------------------------------------
            r7b_hit = False
            r7b_sig = ""

            if setting == "conservative":
                # dominant hidden material differs from dominant surface material
                for comp in hidden_components:
                    hidden_name = norm_text(comp.get("component_name_norm"))
                    hidden_dict = build_component_material_dict(comp)
                    if hidden_dict:
                        hidden_sorted = sorted(hidden_dict.items(), key=lambda x: (-x[1], x[0]))
                        hidden_dom = hidden_sorted[0][0]
                        if surface_dom is not None and hidden_dom != surface_dom:
                            r7b_hit = True
                            r7b_sig = f"{surface_ref_name}[{surface_dom}]__{hidden_name}[{hidden_dom}]"
                            break

            elif setting == "default":
                # hidden layer contains >5% material absent from surface reference
                for comp in hidden_components:
                    hidden_name = norm_text(comp.get("component_name_norm"))
                    hidden_dict = build_component_material_dict(comp)
                    for mat, pct in hidden_dict.items():
                        if pct > 5 and mat not in surface_ref_dict:
                            r7b_hit = True
                            r7b_sig = f"{surface_ref_name}[{'+'.join(sorted(surface_ref_dict.keys()))}]__{hidden_name}[{mat}]"
                            break
                    if r7b_hit:
                        break

            else:
                # expanded kept equal to default to avoid conflating mismatch with mere hidden-layer presence
                for comp in hidden_components:
                    hidden_name = norm_text(comp.get("component_name_norm"))
                    hidden_dict = build_component_material_dict(comp)
                    for mat, pct in hidden_dict.items():
                        if pct > 5 and mat not in surface_ref_dict:
                            r7b_hit = True
                            r7b_sig = f"{surface_ref_name}[{'+'.join(sorted(surface_ref_dict.keys()))}]__{hidden_name}[{mat}]"
                            break
                    if r7b_hit:
                        break

            out[f"r7b_hidden_layer_mismatch_{setting}"] = int(r7b_hit)
            if r7b_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R7b_hidden_layer_mismatch", "setting": setting, "field": "surface_hidden_logic", "match": r7b_sig})

            # -------------------------------------------------
            # R8 Secondary component presence
            # -------------------------------------------------
            r8_patterns = list(PAT_R8_SECONDARY_CONSERVATIVE)
            if setting in {"default", "expanded"}:
                r8_patterns += PAT_R8_SECONDARY_DEFAULT_EXTRA
            if setting == "expanded":
                r8_patterns += PAT_R8_SECONDARY_EXPANDED_EXTRA

            r8_hit = False
            r8_field = ""
            r8_match = ""

            m = hit_first(PAT_R8_COMPONENT, component_names_text)
            if m:
                r8_hit = True
                r8_field = "component_names_text"
                r8_match = m
            else:
                for fld, txt in [
                    ("raw_description_text", raw_description_text),
                    ("product_name", product_name),
                ]:
                    m = hit_first(r8_patterns, txt)
                    if m:
                        if m in {"yoke", "inset", "insert"}:
                            if not re.search(r"contrast|mesh|fabric|lining|panel|insert", txt, flags=re.I):
                                continue
                        if m in {"panel detail", "insert detail"} and setting != "expanded":
                            continue
                        r8_hit = True
                        r8_field = fld
                        r8_match = m
                        break

            out[f"r8_secondary_component_presence_{setting}"] = int(r8_hit)
            if r8_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R8_presence", "setting": setting, "field": r8_field, "match": r8_match})

            # -------------------------------------------------
            # R8b Secondary component material difference (diagnostic only)
            # -------------------------------------------------
            # R8b is nested under R8 and is used only as a stricter diagnostic
            # in the results, not as a standalone core disruptor rule.
            r8b_hit = False
            r8b_sig = ""

            if r8_hit:
                if setting == "conservative":
                    # require at least one explicit secondary component whose dominant material differs
                    for comp in secondary_components:
                        sname = norm_text(comp.get("component_name_norm"))
                        if not sname or sname == surface_ref_name or sname == "pocket" or sname not in R8B_ALLOWED_COMPONENT_NAMES:
                            continue
                        sdict = build_component_material_dict(comp)
                        if sdict:
                            ssorted = sorted(sdict.items(), key=lambda x: (-x[1], x[0]))
                            sdom = ssorted[0][0]
                            if surface_dom is not None and sdom != surface_dom:
                                r8b_hit = True
                                r8b_sig = f"{surface_ref_name}[{surface_dom}]__{sname}[{sdom}]"
                                break

                elif setting == "default":
                    # any secondary component with >5% material absent from surface reference
                    for comp in secondary_components:
                        sname = norm_text(comp.get("component_name_norm"))
                        if not sname or sname == surface_ref_name or sname == "pocket" or sname not in R8B_ALLOWED_COMPONENT_NAMES:
                            continue
                        sdict = build_component_material_dict(comp)
                        for mat, pct in sdict.items():
                            if pct > 5 and mat not in surface_ref_dict:
                                r8b_hit = True
                                r8b_sig = f"{surface_ref_name}[{'+'.join(sorted(surface_ref_dict.keys()))}]__{sname}[{mat}]"
                                break
                        if r8b_hit:
                            break
                        
                else:
                    # expanded kept equal to default to avoid conflating material mismatch
                    # with mere secondary-component presence
                    for comp in secondary_components:
                        sname = norm_text(comp.get("component_name_norm"))
                        if (
                            not sname
                            or sname == surface_ref_name
                            or sname == "pocket"
                            or sname not in R8B_ALLOWED_COMPONENT_NAMES
                        ):
                            continue

                        sdict = build_component_material_dict(comp)
                        for mat, pct in sdict.items():
                            if pct > 5 and mat not in surface_ref_dict:
                                r8b_hit = True
                                r8b_sig = (
                                    f"{surface_ref_name}[{'+'.join(sorted(surface_ref_dict.keys()))}]"
                                    f"__{sname}[{mat}]"
                                )
                                break

                        if r8b_hit:
                            break

            out[f"r8b_secondary_material_difference_{setting}"] = int(r8b_hit)
            if r8b_hit:
                evidence_rows.append({"row_id": line_no, "rule": "R8b_secondary_material_difference", "setting": setting, "field": "surface_secondary_logic", "match": r8b_sig})
                
            # -------------------------------------------------
            # Aggregates
            # -------------------------------------------------
            removable_hit = any([
                r1_hit, r2_hit, r3_hit
            ])
            # The retained-barrier aggregate follows the core rule framework
            # reported in the manuscript tables (R4-R8). R7b and R8b are kept as
            # diagnostics and are therefore not included here.
            retained_hit = any([
                r4_hit, r5_hit, r6_hit, r7_hit, r8_hit
            ])
            any_disruptor_hit = removable_hit or retained_hit

            out[f"any_removable_disruptor_{setting}"] = int(removable_hit)
            out[f"any_retained_barrier_{setting}"] = int(retained_hit)
            out[f"any_disruptor_overall_{setting}"] = int(any_disruptor_hit)

        rows.append(out)
        if _args.progress_every > 0 and len(rows) % _args.progress_every == 0:
            elapsed = time.perf_counter() - run_started
            rate = len(rows) / elapsed if elapsed > 0 else 0.0
            print(
                f"Processed {len(rows):,} records | "
                f"elapsed {elapsed / 60:.1f} min | {rate:.1f} records/s",
                flush=True,
            )


# =========================================================
# Row-level CSV
# =========================================================

df = pd.DataFrame(rows)
df.to_csv(row_csv_out, index=False, encoding="utf-8-sig")

n_total = len(df)

# =========================================================
# Summary outputs
# =========================================================
flag_cols = [
    col for col in df.columns
    if (re.match(r"^r\d", col) or col.startswith("any_"))
    and pd.api.types.is_numeric_dtype(df[col])
]

for col in flag_cols:
    n_flag = int(df[col].sum())
    summary_rows.append({
        "metric": col,
        "n_total": n_total,
        "n_flagged": n_flag,
        "share_flagged": n_flag / n_total if n_total else None,
        "n_not_flagged": n_total - n_flag,
        "share_not_flagged": (n_total - n_flag) / n_total if n_total else None,
    })

summary_df = pd.DataFrame(summary_rows).sort_values("metric")
summary_df.to_csv(summary_csv_out, index=False, encoding="utf-8-sig")

aggregate_metrics = [x for x in summary_df["metric"] if x.startswith("any_")]
aggregate_df = summary_df[summary_df["metric"].isin(aggregate_metrics)].copy()
aggregate_df.to_csv(aggregate_csv_out, index=False, encoding="utf-8-sig")

evidence_df = pd.DataFrame(evidence_rows)
if not evidence_df.empty:
    evidence_df = evidence_df.merge(
        df[["row_id", "parent_category", "detail_category"]],
        on="row_id",
        how="left"
    )
evidence_df.to_csv(evidence_csv_out, index=False, encoding="utf-8-sig")

trigger_diag_df = pd.DataFrame()
category_diag_df = pd.DataFrame()
if not evidence_df.empty:
    trigger_diag_df = (
        evidence_df
        .groupby(["rule", "setting", "match"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values(["rule", "setting", "n", "match"], ascending=[True, True, False, True])
    )
    category_diag_df = (
        evidence_df
        .groupby(["rule", "setting", "parent_category", "detail_category"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values(["rule", "setting", "n", "parent_category", "detail_category"], ascending=[True, True, False, True, True])
    )

trigger_diag_df.to_csv(trigger_diag_csv_out, index=False, encoding="utf-8-sig")
category_diag_df.to_csv(category_diag_csv_out, index=False, encoding="utf-8-sig")

# =========================================================
# Hardware material-disclosure diagnostic
# =========================================================
# This diagnostic asks: among garment variants with detected removable-hardware cues,
# how often does retailer text explicitly specify hardware material?
# It is computed separately from R1-R3 flags because R1 still includes a small
# set of strongly metal-conventional cues (e.g. rivet, eyelet, underwire), while
# the disclosure question is stricter: does the matched text itself contain a
# material word such as metal, plastic, polymer, resin, synthetic, moulded, or
# molded?

material_word_pat = re.compile(
    r"\b(?:metal|plastic|polymer|resin|synthetic|moulded|molded)\b",
    flags=re.I
)

hardware_disclosure_rows = []
if not evidence_df.empty:
    hard_ev = evidence_df[evidence_df["rule"].isin(["R1", "R2", "R3"])].copy()
    hard_ev["material_specified_match"] = hard_ev["match"].fillna("").astype(str).str.contains(material_word_pat)

    for setting in ["conservative", "default", "expanded"]:
        hset = hard_ev[hard_ev["setting"] == setting].copy()
        all_rows = set(hset["row_id"].dropna().astype(int).unique())
        specified_rows = set(hset.loc[hset["material_specified_match"], "row_id"].dropna().astype(int).unique())
        ambiguous_rows = all_rows - specified_rows

        n_all = len(all_rows)
        n_spec = len(specified_rows)
        n_amb = len(ambiguous_rows)

        hardware_disclosure_rows.append({
            "setting": setting,
            "level": "garment_variant",
            "n_hardware": n_all,
            "n_material_specified": n_spec,
            "share_material_specified": n_spec / n_all if n_all else None,
            "n_material_unspecified_or_ambiguous": n_amb,
            "share_material_unspecified_or_ambiguous": n_amb / n_all if n_all else None,
        })

        n_ev = len(hset)
        n_ev_spec = int(hset["material_specified_match"].sum())
        n_ev_amb = n_ev - n_ev_spec
        hardware_disclosure_rows.append({
            "setting": setting,
            "level": "evidence_match",
            "n_hardware": n_ev,
            "n_material_specified": n_ev_spec,
            "share_material_specified": n_ev_spec / n_ev if n_ev else None,
            "n_material_unspecified_or_ambiguous": n_ev_amb,
            "share_material_unspecified_or_ambiguous": n_ev_amb / n_ev if n_ev else None,
        })

hardware_disclosure_df = pd.DataFrame(hardware_disclosure_rows)
hardware_disclosure_df.to_csv(hardware_disclosure_csv_out, index=False, encoding="utf-8-sig")

# =========================================================
# Regex table export
# =========================================================
regex_lists = {
    "PAT_R1_METAL_CONSERVATIVE": PAT_R1_METAL_CONSERVATIVE,
    "PAT_R1_METAL_DEFAULT_EXTRA": PAT_R1_METAL_DEFAULT_EXTRA,
    "PAT_R1_METAL_EXPANDED_EXTRA": PAT_R1_METAL_EXPANDED_EXTRA,
    "PAT_R1_METAL_EXCLUDE": PAT_R1_METAL_EXCLUDE,

    "PAT_R2_PLASTIC_CONSERVATIVE": PAT_R2_PLASTIC_CONSERVATIVE,
    "PAT_R2_PLASTIC_DEFAULT_EXTRA": PAT_R2_PLASTIC_DEFAULT_EXTRA,
    "PAT_R2_PLASTIC_EXPANDED_EXTRA": PAT_R2_PLASTIC_EXPANDED_EXTRA,
    "PAT_R2_PLASTIC_EXCLUDE": PAT_R2_PLASTIC_EXCLUDE,

    "PAT_R3_MIXED_CONSERVATIVE": PAT_R3_MIXED_CONSERVATIVE,
    "PAT_R3_MIXED_DEFAULT_EXTRA": PAT_R3_MIXED_DEFAULT_EXTRA,
    "PAT_R3_MIXED_EXPANDED_EXTRA": PAT_R3_MIXED_EXPANDED_EXTRA,
    "PAT_R3_MIXED_EXCLUDE": PAT_R3_MIXED_EXCLUDE,

    "PAT_R4_COMPONENT": PAT_R4_COMPONENT,
    "PAT_R4_TRIM_CONSERVATIVE": PAT_R4_TRIM_CONSERVATIVE,
    "PAT_R4_TRIM_DEFAULT_EXTRA": PAT_R4_TRIM_DEFAULT_EXTRA,
    "PAT_R4_TRIM_EXPANDED_EXTRA": PAT_R4_TRIM_EXPANDED_EXTRA,
    "PAT_R4_TRIM_EXCLUDE": PAT_R4_TRIM_EXCLUDE,

    "PAT_R5_DECOR_CONSERVATIVE": PAT_R5_DECOR_CONSERVATIVE,
    "PAT_R5_DECOR_DEFAULT_EXTRA": PAT_R5_DECOR_DEFAULT_EXTRA,
    "PAT_R5_DECOR_EXPANDED_EXTRA": PAT_R5_DECOR_EXPANDED_EXTRA,

    "PAT_R6_COMPONENT": PAT_R6_COMPONENT,
    "PAT_R6_SURFACE_CONSERVATIVE": PAT_R6_SURFACE_CONSERVATIVE,
    "PAT_R6_SURFACE_DEFAULT_EXTRA": PAT_R6_SURFACE_DEFAULT_EXTRA,
    "PAT_R6_SURFACE_EXPANDED_EXTRA": PAT_R6_SURFACE_EXPANDED_EXTRA,

    "PAT_R7_COMPONENT": PAT_R7_COMPONENT,
    "PAT_R7_LINING_DEFAULT": PAT_R7_LINING_DEFAULT,
    "PAT_R7_LINING_EXPANDED_EXTRA": PAT_R7_LINING_EXPANDED_EXTRA,
    "PAT_R7_LINING_EXCLUDE": PAT_R7_LINING_EXCLUDE,

    "PAT_R8_COMPONENT": PAT_R8_COMPONENT,
    "PAT_R8_SECONDARY_CONSERVATIVE": PAT_R8_SECONDARY_CONSERVATIVE,
    "PAT_R8_SECONDARY_DEFAULT_EXTRA": PAT_R8_SECONDARY_DEFAULT_EXTRA,
    "PAT_R8_SECONDARY_EXPANDED_EXTRA": PAT_R8_SECONDARY_EXPANDED_EXTRA,
    "PAT_R8_SECONDARY_EXCLUDE": PAT_R8_SECONDARY_EXCLUDE,
}

regex_rows = []
for group_name, patterns in regex_lists.items():
    rule_type = "exclude" if group_name.endswith("_EXCLUDE") else "include"
    regex_rows.append({
        "group_name": group_name,
        "rule_type": rule_type,
        "n_patterns": len(patterns),
        "pretty_patterns_joined": " ; ".join(pattern_to_plain_english(p) for p in patterns),
        "raw_patterns_joined": " ; ".join(patterns),
    })

df_regex = pd.DataFrame(regex_rows)
df_regex.to_csv(regex_table_file, index=False, encoding="utf-8")

# =========================================================
# Summary text
# =========================================================
with open(summary_txt_out, "w", encoding="utf-8") as fsum:
    fsum.write("Disruptor rule evaluation summary (surface/hidden logic and cue-based R1-R3 hardware boundaries)\n\n")
    fsum.write(f"Input file: {input_file}\n")
    fsum.write(f"Processed rows: {n_total}\n\n")
    fsum.write("R1–R3 removable-hardware indicator note\n")
    fsum.write("=" * 60 + "\n")
    fsum.write("R1–R3 are cue-based removable-hardware indicators, not verified material-composition classes.\n")
    fsum.write("R1 = metal-specified / strongly metal-conventional hardware cues; R2 = plastic-specified hardware cues; R3 = material-ambiguous hardware cues. R3 is not derived from R1 + R2 co-occurrence.\n\n")

    if not hardware_disclosure_df.empty:
        fsum.write("Hardware material-disclosure diagnostic\n")
        fsum.write("=" * 60 + "\n")
        for _, hrow in hardware_disclosure_df.iterrows():
            fsum.write(
                f"{hrow['setting']} | {hrow['level']} | n_hardware={int(hrow['n_hardware'])} | "
                f"material_specified={int(hrow['n_material_specified'])} "
                f"({hrow['share_material_specified']:.6f}) | "
                f"unspecified_or_ambiguous={int(hrow['n_material_unspecified_or_ambiguous'])} "
                f"({hrow['share_material_unspecified_or_ambiguous']:.6f})\n"
            )
        fsum.write("\n")

    fsum.write("Brand counts\n")
    fsum.write("=" * 60 + "\n")
    for k in sorted(brand_counter):
        fsum.write(f"{k}: {brand_counter[k]}\n")

    fsum.write("\nParent category counts\n")
    fsum.write("=" * 60 + "\n")
    for k in sorted(parent_counter):
        fsum.write(f"{k}: {parent_counter[k]}\n")

    fsum.write("\nRule / aggregate shares\n")
    fsum.write("=" * 60 + "\n")
    for _, row in summary_df.iterrows():
        fsum.write(
            f"{row['metric']} | n_flagged={int(row['n_flagged'])} | share_flagged={row['share_flagged']:.6f}\n"
        )

output_manifest = pd.DataFrame([
    {"file": row_csv_out.name, "description": "Row-level indicator and aggregate flags"},
    {"file": summary_csv_out.name, "description": "Rule-level prevalence summary"},
    {"file": aggregate_csv_out.name, "description": "Removable-hardware, retained-barrier, and overall core-disruptor aggregate prevalence"},
    {"file": evidence_csv_out.name, "description": "Matched evidence supporting rule assignments"},
    {"file": trigger_diag_csv_out.name, "description": "Trigger-term diagnostics"},
    {"file": category_diag_csv_out.name, "description": "Category-level diagnostics"},
    {"file": regex_table_file.name, "description": "Executed regex inventory"},
    {"file": hardware_disclosure_csv_out.name, "description": "Hardware material-disclosure diagnostic"},
    {"file": summary_txt_out.name, "description": "Human-readable calculation summary"},
    {"file": "rule_evaluation_QA.csv", "description": "Core rule-evaluation QA checks"},
])
output_manifest.to_csv(output_dir / "rule_evaluation_output_manifest.csv", index=False)

required_flag_columns = {
    "any_removable_disruptor_default",
    "any_retained_barrier_default",
    "any_disruptor_overall_default",
    "r7b_hidden_layer_mismatch_default",
    "r8b_secondary_material_difference_default",
}
qa = pd.DataFrame([
    {
        "check": "nonempty_input",
        "passed": n_total > 0,
        "observed": n_total,
        "expected": "> 0",
    },
    {
        "check": "required_default_output_columns",
        "passed": required_flag_columns.issubset(df.columns),
        "observed": sorted(required_flag_columns.intersection(df.columns)),
        "expected": sorted(required_flag_columns),
    },
    {
        "check": "row_ids_unique",
        "passed": bool(df["row_id"].is_unique),
        "observed": int(df["row_id"].nunique()),
        "expected": n_total,
    },
])
qa.to_csv(output_dir / "rule_evaluation_QA.csv", index=False)
if not qa["passed"].all():
    raise RuntimeError("One or more rule-evaluation QA checks failed")

elapsed_total = time.perf_counter() - run_started
print(f"Done. Processed {n_total:,} records in {elapsed_total / 60:.1f} minutes.")
print(f"Row CSV:            {row_csv_out}")
print(f"Summary CSV:        {summary_csv_out}")
print(f"Aggregate CSV:      {aggregate_csv_out}")
print(f"Evidence CSV:       {evidence_csv_out}")
print(f"Trigger diag CSV:   {trigger_diag_csv_out}")
print(f"Category diag CSV:  {category_diag_csv_out}")
print(f"Regex table:        {regex_table_file}")
print(f"Hardware disclosure:{hardware_disclosure_csv_out}")
print(f"Summary txt:        {summary_txt_out}")
