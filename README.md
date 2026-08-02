# Garment disruptor rule analysis

[![Analysis DOI](https://zenodo.org/badge/DOI/10.5281%2Fzenodo.20037099.svg)](https://doi.org/10.5281/zenodo.20037099)
[![Dataset DOI](https://zenodo.org/badge/DOI/10.5281%2Fzenodo.20006389.svg)](https://doi.org/10.5281/zenodo.20006389)

This repository contains the reproducible analysis workflow, derived outputs, figure source files, supplementary-table calculations, and final figure artwork for the manuscript:

> **Embedded garment features constrain textile waste sorting and fibre-to-fibre recycling**

The workflow applies a transparent rule-based framework to a component-normalized garment-variant dataset. It evaluates eight core disruptor indicators (R1–R8), two material-mismatch diagnostics (R7b and R8b), and conservative, default, and expanded rule boundaries. The archived outputs support the manuscript's pooled variant-level results, portal-specific analyses, distinct-product analyses, category comparisons, rule-boundary sensitivity checks, and figure calculations.

## Companion input dataset

The analysis uses:

```text
6_JSONL_component_normalized.jsonl
```

This input file is **not duplicated in this analysis repository**. It is maintained in the companion garment-variant dataset repository and archived with the associated dataset release:

- Dataset repository: https://github.com/kai-li-1994/garment-variant-dataset
- Dataset archive: https://doi.org/10.5281/zenodo.20006389
- Associated article: Li, K., & Walther, G. (2026). *A harmonized fast-fashion garment-variant dataset for textile circularity and sustainability assessment*. **Data in Brief, 67**, 113017. https://doi.org/10.1016/j.dib.2026.113017

To rerun the analysis, download or copy `6_JSONL_component_normalized.jsonl` from the companion dataset release and pass its local path to the scripts as shown below.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── LICENSE
├── .gitignore
│
├── 01_evaluate_disruptor_rules_v2.py
├── 02_generate_figures_2_to_6_and_S1_v2.py
├── 03_generate_tables_S2_to_S5_v2.py
├── 04_generate_table_S6_and_figure_5_audit_v2.py
│
├── outputs_v2/
│   ├── disruptor_rule_flags_by_variant.csv
│   ├── disruptor_rule_summary.csv
│   ├── disruptor_aggregate_summary.csv
│   ├── disruptor_match_evidence.csv
│   ├── disruptor_trigger_diagnostics.csv
│   ├── disruptor_category_diagnostics.csv
│   ├── disruptor_regex_inventory.csv
│   ├── hardware_material_disclosure_summary.csv
│   ├── disruptor_summary_readable.txt
│   ├── rule_evaluation_QA.csv
│   └── rule_evaluation_output_manifest.csv
│
├── figures_2_to_6_and_S1_v2/
│   ├── Figure_2_aggregate_prevalence.pdf
│   ├── Figure_2_aggregate_prevalence.svg
│   ├── Figure_2_source_values.csv
│   ├── Figure_3_removable_hardware_indicators.pdf
│   ├── Figure_3_removable_hardware_indicators.svg
│   ├── Figure_3_panel_a_source_values.csv
│   ├── Figure_3_panels_b_to_d_top_terms.csv
│   ├── Figure_3_panel_e_term_distribution.csv
│   ├── Figure_3_panel_f_hardware_disclosure.csv
│   ├── Figure_4_retained_barrier_indicators.pdf
│   ├── Figure_4_retained_barrier_indicators.svg
│   ├── Figure_4_panel_a_source_values.csv
│   ├── Figure_4_panels_b_to_f_top_terms.csv
│   ├── Figure_4_panel_g_barrier_count.csv
│   ├── Figure_5_material_mismatch.pdf
│   ├── Figure_5_material_mismatch.svg
│   ├── Figure_5_panels_c_and_d_top_mismatch_pairs.csv
│   ├── Figure_5_source_values_and_nesting_audit.csv
│   ├── Figure_6_category_prevalence_worked_example.pdf
│   ├── Figure_6_category_prevalence_worked_example.svg
│   ├── Figure_6_source_values.csv
│   ├── Figure_S1_category_rule_heatmap.pdf
│   ├── Figure_S1_category_rule_heatmap.svg
│   ├── Figure_S1_source_values.csv
│   ├── Figures_2_to_6_and_S1_QA.csv
│   └── figure_output_manifest.csv
│
├── tables_S2_to_S5_v2/
│   ├── Table_S2_Panel_A_dataset_construction_flow.csv
│   ├── Table_S2_Panel_B_sample_structure.csv
│   ├── Table_S3_aggregate_prevalence.csv
│   ├── Table_S4_rule_level_pooled_vs_product.csv
│   ├── Table_S5_portal_specific_prevalence.csv
│   ├── Tables_S2_to_S5.docx
│   ├── analysis_design.csv
│   ├── calculation_summary.txt
│   ├── complementary_prevalence_long.csv
│   ├── complementary_prevalence_wide.csv
│   ├── cross_market_product_family_agreement.csv
│   ├── cross_market_product_family_overlap.csv
│   ├── product_family_key_audit.csv
│   ├── qa_checks.csv
│   ├── sample_structure_summary.csv
│   └── within_product_agreement.csv
│
├── table_S6_and_figure_5_audit_v2/
│   ├── Table_S6_technical_outerwear_R6_sensitivity.csv
│   ├── Figure_5_conditional_mismatch_audit.csv
│   ├── Table_S6_and_Figure_5_QA.csv
│   └── Table_S6_and_Figure_5_calculation_summary.txt
│
└── figures_polish_adobe_illustrator/
    ├── schemetic.ai
    ├── schemetic.svg
    ├── figure2_aggregate_prevalence.ai
    ├── figure2_aggregate_prevalence.svg
    ├── figure3_removable_disruptors.ai
    ├── figure3_removable_disruptors.svg
    ├── figure4_retained_barriers.ai
    ├── figure4_retained_barriers.svg
    ├── figure5_mismatch_diagnostics.ai
    ├── figure5_mismatch_diagnostics.svg
    ├── figure6_v2.ai
    └── figure6_v2.svg
```

The tree above documents the files currently archived in the repository. Some filenames retain earlier internal naming for continuity, while the manuscript and publication-facing figure labels use the finalized terminology described below.

## Analysis scripts

| Script | Purpose | Main output |
|---|---|---|
| `01_evaluate_disruptor_rules_v2.py` | Applies the R1–R8 rule framework and R7b/R8b diagnostics to `6_JSONL_component_normalized.jsonl` under conservative, default, and expanded rule boundaries. Exports row-level flags, aggregate summaries, match evidence, diagnostics, the regex inventory, hardware-material disclosure results, and QA files. | `outputs_v2/` |
| `02_generate_figures_2_to_6_and_S1_v2.py` | Generates main-text Figures 2–6 and Supplementary Figure S1 from the rule-evaluation outputs. Exports PDF and SVG figures, figure-specific source-value files, a manifest, and QA checks. Figure 1 is not generated by this script. | `figures_2_to_6_and_S1_v2/` |
| `03_generate_tables_S2_to_S5_v2.py` | Produces the pooled variant-level, portal-specific, and distinct-product analyses; creates Supplementary Tables S2–S5; and exports product-family, agreement, design, and QA files. | `tables_S2_to_S5_v2/` |
| `04_generate_table_S6_and_figure_5_audit_v2.py` | Generates the R6 technical-outerwear sensitivity results for Supplementary Table S6 and audits the R7b/R8b nesting and strict conditional mismatch calculations used in Figure 5. | `table_S6_and_figure_5_audit_v2/` |

## Analytical terminology

The publication-facing terminology is:

| Group | Rule IDs | Meaning |
|---|---|---|
| **Removable-hardware indicators** | R1–R3 | Metal-specified or metal-conventional hardware, plastic-specified hardware, and material-ambiguous hardware cues. |
| **Retained-barrier indicators** | R4–R8 | Fabric attached trim, decorative or non-textile attachments, surface print or coating barriers, lining or multilayer presence, and secondary-component presence. |
| **Core disruptor indicators** | R1–R8 | The combined set of removable-hardware and retained-barrier indicators. |
| **Material-mismatch diagnostics** | R7b, R8b | Comparisons between the selected surface reference and hidden or secondary garment components. These diagnostics are reported separately and are not included in the retained-barrier or overall core-disruptor aggregates. |

Some machine-readable column names retain legacy identifiers such as `any_removable_disruptor_*`, `any_retained_barrier_*`, and `any_disruptor_overall_*` to preserve compatibility with the established workflow. Their publication-facing meanings are documented in the output manifests and supplementary-table files.

## Rule-boundary settings

The workflow implements three operational settings:

- **Conservative**: the narrowest rule boundaries, retaining the clearest evidence.
- **Default**: the primary analytical specification used for the main manuscript results.
- **Expanded**: broader but still plausible terminology used for rule-boundary sensitivity analysis.

Differences across settings represent sensitivity to operational rule definitions, not statistical confidence intervals.

## Output folders

### `outputs_v2/`

This is the primary reproducibility layer produced by `01_evaluate_disruptor_rules_v2.py`.

- `disruptor_rule_flags_by_variant.csv` contains one row per colour-specific garment variant and the complete set of rule, diagnostic, and aggregate flags.
- `disruptor_rule_summary.csv` reports rule-level counts and prevalence by setting.
- `disruptor_aggregate_summary.csv` reports the removable-hardware, retained-barrier, and overall core-disruptor aggregates.
- `disruptor_match_evidence.csv` records the field and matched expression supporting each rule assignment.
- `disruptor_trigger_diagnostics.csv` summarizes matched trigger terms.
- `disruptor_category_diagnostics.csv` summarizes rule evidence by garment category.
- `disruptor_regex_inventory.csv` documents the executed include and exclude patterns.
- `hardware_material_disclosure_summary.csv` reports whether R1–R3 hardware cues include explicit material information.
- `rule_evaluation_QA.csv` records core integrity checks.
- `rule_evaluation_output_manifest.csv` describes the generated files.

The row-level flags and machine-readable CSV files are authoritative for recalculation. The readable text summary is provided for rapid inspection.

### `figures_2_to_6_and_S1_v2/`

This folder contains the figures generated directly by Python, together with the source values used for each figure.

- Figures 2–6 are main-text figures.
- Figure S1 is the complete category-by-rule heatmap in the Supplementary Information.
- Figure-specific CSV files expose the values plotted in each panel.
- `Figures_2_to_6_and_S1_QA.csv` records checks on the input row count, mismatch nesting, conditional percentages, and category display labels.
- `figure_output_manifest.csv` maps figure numbers to generated file stems.

### `tables_S2_to_S5_v2/`

This folder documents the complementary prevalence analyses and Supplementary Tables S2–S5.

It includes:

- publication-facing table CSV files and a combined Word document;
- the long and wide calculation datasets;
- the explicit analytical-design table;
- product-family key and overlap audits;
- within-product and cross-market agreement files;
- sample-structure summaries; and
- QA checks.

The distinct-product analysis counts each retailer-specific product family once and classifies it as flagged when at least one observed variant satisfies the corresponding indicator.

### `table_S6_and_figure_5_audit_v2/`

This folder contains:

- the R6 sensitivity analysis for technical outerwear used in Supplementary Table S6;
- the R7/R7b and R8/R8b nesting audit;
- the strict conditional mismatch calculations used in Figure 5; and
- associated QA and readable calculation summaries.

### `figures_polish_adobe_illustrator/`

Figures 2–6 and Supplementary Figure S1 were first generated reproducibly with `02_generate_figures_2_to_6_and_S1_v2.py`. The publication figures were then polished in Adobe Illustrator to improve typography, spacing, panel alignment, and publication-facing labels. This polishing did not change the underlying calculated values.

This folder contains:

- editable Adobe Illustrator (`.ai`) files; and
- final exported scalable vector graphics (`.svg`) used for manuscript preparation.

Figure 1 is original schematic artwork and is represented by `schemetic.ai` and `schemetic.svg`; it is not generated by the Python figure script.

For numerical verification, use the source-value CSV files in `figures_2_to_6_and_S1_v2/`. For the final visual presentation, use the corresponding exported SVG files in `figures_polish_adobe_illustrator/`.

## Software requirements

The workflow requires Python 3.10 or later and the following packages:

```text
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
python-docx
```

Install the listed dependencies with:

```bash
pip install -r requirements.txt
pip install python-docx
```

`python-docx` is required by `03_generate_tables_S2_to_S5_v2.py` to create `Tables_S2_to_S5.docx`.

## Reproducing the workflow

The following example assumes that the repository is the current working directory and that the companion JSONL file has been downloaded to a local path.

### 1. Evaluate the disruptor rules

```bash
python 01_evaluate_disruptor_rules_v2.py \
  --input-jsonl /path/to/6_JSONL_component_normalized.jsonl \
  --output-dir outputs_v2
```

### 2. Generate Figures 2–6 and Supplementary Figure S1

```bash
python 02_generate_figures_2_to_6_and_S1_v2.py \
  --data-dir outputs_v2 \
  --output-dir figures_2_to_6_and_S1_v2
```

### 3. Generate Supplementary Tables S2–S5

```bash
python 03_generate_tables_S2_to_S5_v2.py \
  --jsonl /path/to/6_JSONL_component_normalized.jsonl \
  --flags-csv outputs_v2/disruptor_rule_flags_by_variant.csv \
  --rule-summary-csv outputs_v2/disruptor_rule_summary.csv \
  --output-dir tables_S2_to_S5_v2
```

### 4. Generate Supplementary Table S6 and audit Figure 5

```bash
python 04_generate_table_S6_and_figure_5_audit_v2.py \
  --flags-csv outputs_v2/disruptor_rule_flags_by_variant.csv \
  --output-dir table_S6_and_figure_5_audit_v2
```

The scripts also contain a local project-path fallback used during development. Passing explicit command-line paths, as shown above, is recommended for reuse on another system.

## Interpretation limits

The outputs identify observable indicators from retailer-disclosed product information. They should not be interpreted as:

- physical garment teardown results;
- verified hardware composition;
- direct measures of removability;
- recycler-specific acceptance decisions;
- process-specific recycling yields or efficiencies; or
- statistical estimates for the global apparel market.

The conservative, default, and expanded settings evaluate rule-boundary sensitivity. They do not substitute for external validation against physical garments or recycler-specific testing.

## Data and code availability

The companion garment-variant dataset and dataset-construction workflow are archived separately:

- GitHub: https://github.com/kai-li-1994/garment-variant-dataset
- Zenodo: https://doi.org/10.5281/zenodo.20006389

This analysis repository archives the revised disruptor-rule workflow, derived outputs, figure source values, supplementary-table calculations, QA files, and final figure artwork:

- GitHub: https://github.com/kai-li-1994/garment-disruptor-rule-analysis
- Zenodo concept DOI: https://doi.org/10.5281/zenodo.20037099

## Citation

When using the input garment-variant dataset, cite:

> Li, K., & Walther, G. (2026). A harmonized fast-fashion garment-variant dataset for textile circularity and sustainability assessment. *Data in Brief, 67*, 113017. https://doi.org/10.1016/j.dib.2026.113017

Please also cite the archived analysis release and the associated manuscript when using the rule framework, scripts, or derived outputs.

## Acknowledgements

This research was supported by the Werner Siemens Foundation through the WSS Research Centre Catalaix, a Project of the Century funded by the Werner Siemens Foundation.

The dataset and analysis workflow were prepared by [Dr. Kai Li](https://www.om.rwth-aachen.de/gruppenleitung/kai-li/) and [Prof. Grit Walther](https://www.om.rwth-aachen.de/lehrstuhlleitung/prof-dr-grit-walther/?setlang=en) at the Chair of Operations Management, RWTH Aachen University.

## License

This repository is released under the MIT License. See `LICENSE` for details.
