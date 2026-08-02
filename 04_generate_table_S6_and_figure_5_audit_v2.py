"""
Generate Supplementary Table S6 and the Figure 5 conditional-mismatch audit.

Outputs
-------
Supplementary Information:
- Table S6: R6 rule-boundary sensitivity for technical outerwear categories

Main-text figure audit:
- Figure 5: nesting of the R7b and R8b material-mismatch diagnostics within
  the corresponding R7 and R8 retained-barrier indicators, including the strict
  conditional mismatch percentages used in panel (b)

The jacket row in Table S6 represents all variants assigned to the
outerwear_jacket category; it is not an individual garment case study.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_PROJECT_DIR = Path(
    r"C:\Users\laptop-kl\OneDrive - Universiteit Leiden\PlasticTradeFlow"
    r"\data_mining_clothing\textile_preprocessing\waste_management\1st_revision"
)
PROJECT_DIR = LOCAL_PROJECT_DIR if LOCAL_PROJECT_DIR.exists() else SCRIPT_DIR

DEFAULT_FLAGS = PROJECT_DIR / "outputs_v2" / "disruptor_rule_flags_by_variant.csv"
DEFAULT_OUT = PROJECT_DIR / "table_S6_and_figure_5_audit_v2"

OUTERWEAR = ["outerwear_coat", "outerwear_jacket", "outerwear_gilet"]
OUTERWEAR_DISPLAY = {
    "outerwear_coat": "Outerwear coats",
    "outerwear_jacket": "Outerwear jackets",
    "outerwear_gilet": "Outerwear gilets",
}
SETTINGS = ["conservative", "default", "expanded"]


def pct(x: pd.Series) -> float:
    return float(x.mean() * 100.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flags-csv", type=Path, default=DEFAULT_FLAGS)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    if not args.flags_csv.exists():
        raise FileNotFoundError(
            f"Row-level flag file not found: {args.flags_csv}\n"
            "Run 01_evaluate_disruptor_rules_v2.py first or pass --flags-csv."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.flags_csv)
    required = {"detail_category"}
    for setting in SETTINGS:
        required.add(f"r6_surface_print_coating_{setting}")
    required |= {
        "r7_lining_multilayer_default",
        "r7b_hidden_layer_mismatch_default",
        "r8_secondary_component_presence_default",
        "r8b_secondary_material_difference_default",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    # Table S6: category-specific R6 rule-boundary sensitivity.
    rows = []
    groups = [("Technical outerwear combined", df["detail_category"].isin(OUTERWEAR))]
    groups += [(OUTERWEAR_DISPLAY[c], df["detail_category"].eq(c)) for c in OUTERWEAR]
    for label, mask in groups:
        sub = df.loc[mask]
        row = {"Category": label, "Variants (n)": int(len(sub))}
        for setting in SETTINGS:
            row[setting.title()] = pct(sub[f"r6_surface_print_coating_{setting}"])
        rows.append(row)
    r6 = pd.DataFrame(rows)
    r6.to_csv(args.output_dir / "Table_S6_technical_outerwear_R6_sensitivity.csv", index=False)

    # Strict conditional mismatch shares require numerator nesting.
    audits = []
    for label, presence_col, mismatch_col in [
        ("R7/R7b", "r7_lining_multilayer_default", "r7b_hidden_layer_mismatch_default"),
        ("R8/R8b", "r8_secondary_component_presence_default", "r8b_secondary_material_difference_default"),
    ]:
        presence = df[presence_col].astype(bool)
        mismatch = df[mismatch_col].astype(bool)
        n_presence = int(presence.sum())
        n_mismatch_total = int(mismatch.sum())
        n_nested = int((presence & mismatch).sum())
        n_outside = int((~presence & mismatch).sum())
        audits.append({
            "diagnostic_pair": label,
            "n_presence": n_presence,
            "n_mismatch_total": n_mismatch_total,
            "n_mismatch_within_presence": n_nested,
            "n_mismatch_outside_presence": n_outside,
            "total_diagnostic_cases_divided_by_presence_percent": n_mismatch_total / n_presence * 100.0,
            "strict_conditional_mismatch_percent": n_nested / n_presence * 100.0,
        })
    audit = pd.DataFrame(audits)
    audit.to_csv(args.output_dir / "Figure_5_conditional_mismatch_audit.csv", index=False)

    r7_row = audit.loc[audit.diagnostic_pair.eq("R7/R7b")].iloc[0]
    r8_row = audit.loc[audit.diagnostic_pair.eq("R8/R8b")].iloc[0]
    combined_row = r6.loc[r6["Category"].eq("Technical outerwear combined")].iloc[0]
    qa = pd.DataFrame([
        {"check": "input_row_count", "passed": len(df) == 47522,
         "observed": len(df), "expected": 47522},
        {"check": "technical_outerwear_variant_count", "passed": int(combined_row["Variants (n)"]) == 4178,
         "observed": int(combined_row["Variants (n)"]), "expected": 4178},
        {"check": "technical_outerwear_R6_default_rounds_to_19_7",
         "passed": round(float(combined_row["Default"]), 1) == 19.7,
         "observed": float(combined_row["Default"]), "expected": 19.7},
        {"check": "r7b_outside_r7", "passed": int(r7_row["n_mismatch_outside_presence"]) == 82,
         "observed": int(r7_row["n_mismatch_outside_presence"]), "expected": 82},
        {"check": "r7_strict_conditional_rounds_to_34_8",
         "passed": round(float(r7_row["strict_conditional_mismatch_percent"]), 1) == 34.8,
         "observed": float(r7_row["strict_conditional_mismatch_percent"]), "expected": 34.8},
        {"check": "r8b_nested_in_r8", "passed": int(r8_row["n_mismatch_outside_presence"]) == 0,
         "observed": int(r8_row["n_mismatch_outside_presence"]), "expected": 0},
        {"check": "r8_strict_conditional_rounds_to_54_6",
         "passed": round(float(r8_row["strict_conditional_mismatch_percent"]), 1) == 54.6,
         "observed": float(r8_row["strict_conditional_mismatch_percent"]), "expected": 54.6},
    ])
    qa.to_csv(args.output_dir / "Table_S6_and_Figure_5_QA.csv", index=False)
    if not qa["passed"].all():
        raise RuntimeError("One or more QA checks failed")

    summary = [
        f"Input variants: {len(df):,}",
        "",
        "R6 technical-outerwear rule-boundary sensitivity (%):",
        r6.to_string(index=False, float_format=lambda x: f"{x:.1f}"),
        "",
        "Mismatch nesting audit:",
        audit.to_string(index=False, float_format=lambda x: f"{x:.2f}"),
    ]
    (args.output_dir / "Table_S6_and_Figure_5_calculation_summary.txt").write_text(
        "\n".join(summary) + "\n", encoding="utf-8"
    )
    print(f"Outputs written to: {args.output_dir}")
    print(f"QA checks passed: {int(qa['passed'].sum())}/{len(qa)}")


if __name__ == "__main__":
    main()
