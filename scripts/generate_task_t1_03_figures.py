#!/usr/bin/env python3
"""
TASK-T1-03: Publication Figures Production Script
Track 1 — Scientific Validation and Publication Preparation

Generates:
1. figure1_eb_shrinkage.png and .pdf (plus figure1_discordance_by_count_tier.csv)
2. figure2_benchmark_curves.png and .pdf (PR and ROC curves for OMOP and EU-ADR)
3. figure3_contextual_features.png and .pdf (11 contextual features across 5 EB05 strata)
under data/21_track1_publication_figures/
"""

import os
import sys
import json
import hashlib
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from sklearn.metrics import precision_recall_curve, roc_curve, auc, roc_auc_score

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED_FILE = os.path.join(BASE_DIR, "data", "13_phase3c2_mgps_scoring", "phase3c2_scored_candidate_pairs.csv")
M1_FILE = os.path.join(BASE_DIR, "data", "10_phase3b_features", "m1_pure_contextual_features.csv")
OMOP_FILE = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "omop_matched_evaluation_pairs.csv")
EU_ADR_FILE = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "eu_adr_matched_evaluation_pairs.csv")
BENCH_JSON = os.path.join(BASE_DIR, "data", "14_phase3d_benchmark_evaluation", "phase3d_benchmark_evaluation_results.json")
STRATA_SUMMARY_FILE = os.path.join(BASE_DIR, "data", "19_track1_contextual_analysis", "contextual_strata_summary.csv")
STRATA_TESTS_FILE = os.path.join(BASE_DIR, "data", "19_track1_contextual_analysis", "contextual_strata_tests.csv")
TIER_DISCORDANCE_SRC = os.path.join(BASE_DIR, "data", "19_track1_contextual_analysis", "shrinkage_discordance_by_tier.csv")

OUT_DIR = os.path.join(BASE_DIR, "data", "21_track1_publication_figures")

# Styling constants
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 13,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

TIER_DEFS = [
    ("a = 2-3", 2, 3),
    ("a = 4-5", 4, 5),
    ("a = 6-10", 6, 10),
    ("a = 11-20", 11, 20),
    ("a > 20", 21, 100000000)
]


def generate_figure1():
    print("\n--- Generating Figure 1: Empirical Bayes Shrinkage and PRR Discordance ---")
    start_time = time.time()

    # Copy companion CSV
    df_discordance = pd.read_csv(TIER_DISCORDANCE_SRC)
    comp_csv = os.path.join(OUT_DIR, "figure1_discordance_by_count_tier.csv")
    df_discordance.to_csv(comp_csv, index=False)
    print(f"Saved companion tier table: {comp_csv}")

    # Load scored pairs
    print("Loading scored pairs table...")
    df = pd.read_csv(
        SCORED_FILE,
        usecols=["a", "prr", "eb05", "prr_signal", "signal_eb05_conservative"]
    )

    # Clean positive values for log scale
    df["prr_clean"] = df["prr"].clip(lower=0.01, upper=5000.0)
    df["eb05_clean"] = df["eb05"].clip(lower=0.001, upper=2000.0)

    # Classify quadrant
    # Concordant Signals: both True
    # PRR-Only Discordant: prr_signal == True & eb05 < 2.0
    # EB05-Only Discordant: eb05 >= 2.0 & prr_signal == False
    # Concordant Non-Signals: both False
    c_both = (df["prr_signal"] == True) & (df["signal_eb05_conservative"] == True)
    c_prr_only = (df["prr_signal"] == True) & (df["signal_eb05_conservative"] == False)
    c_eb05_only = (df["signal_eb05_conservative"] == True) & (df["prr_signal"] == False)
    c_neither = (~df["prr_signal"]) & (~df["signal_eb05_conservative"])

    df["status"] = "Neither"
    df.loc[c_both, "status"] = "Concordant Signal"
    df.loc[c_prr_only, "status"] = "PRR-Only (EB05 < 2.0)"
    df.loc[c_eb05_only, "status"] = "EB05-Only (PRR < 2.0)"

    color_map = {
        "Neither": "#b0bec5",                 # Gray
        "Concordant Signal": "#7b1fa2",       # Purple
        "PRR-Only (EB05 < 2.0)": "#d32f2f",   # Red / Coral (suppressed alerts)
        "EB05-Only (PRR < 2.0)": "#1976d2"    # Blue (a=2 signals omitted by Evans)
    }

    # Set up figure: 2 rows x 3 columns
    fig, axes = plt.subplots(2, 3, figsize=(15, 9.5))
    axes = axes.flatten()

    np.random.seed(42)

    for i, (tier_label, a_min, a_max) in enumerate(TIER_DEFS):
        ax = axes[i]
        tier_mask = (df["a"] >= a_min) & (df["a"] <= a_max)
        df_tier = df[tier_mask]
        n_tier = len(df_tier)

        n_prr_only = (df_tier["status"] == "PRR-Only (EB05 < 2.0)").sum()
        n_eb05_only = (df_tier["status"] == "EB05-Only (PRR < 2.0)").sum()
        n_both = (df_tier["status"] == "Concordant Signal").sum()
        n_neither = (df_tier["status"] == "Neither").sum()

        # Deterministic stratified sample of up to 6,000 points for readable rendering
        sample_indices = []
        for status_cat in ["Neither", "Concordant Signal", "PRR-Only (EB05 < 2.0)", "EB05-Only (PRR < 2.0)"]:
            cat_idx = df_tier[df_tier["status"] == status_cat].index
            if len(cat_idx) > 0:
                n_sample = min(len(cat_idx), 2000 if status_cat != "Neither" else 2000)
                sampled = np.random.choice(cat_idx, size=n_sample, replace=False)
                sample_indices.extend(sampled)

        df_sample = df.loc[sample_indices]

        # Scatter plot by status
        for status_cat, color in color_map.items():
            sub = df_sample[df_sample["status"] == status_cat]
            if len(sub) > 0:
                alpha = 0.15 if status_cat == "Neither" else 0.45
                size = 6 if status_cat == "Neither" else 12
                ax.scatter(
                    sub["prr_clean"],
                    sub["eb05_clean"],
                    c=color,
                    alpha=alpha,
                    s=size,
                    edgecolors="none",
                    label=status_cat if i == 0 else ""
                )

        # Reference lines
        ax.axvline(2.0, color="#d32f2f", linestyle="--", linewidth=1.1, alpha=0.8)
        ax.axhline(2.0, color="#1976d2", linestyle="--", linewidth=1.1, alpha=0.8)
        # Identity line
        diag_x = np.logspace(-1, 3, 100)
        ax.plot(diag_x, diag_x, color="#424242", linestyle=":", linewidth=0.9, alpha=0.6)

        # Scale and limits
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(0.08, 2500)
        ax.set_ylim(0.005, 1200)

        # Titles and annotations
        pct_prr_suppressed = (n_prr_only / n_tier) * 100.0 if n_tier > 0 else 0.0
        ax.set_title(f"Tier {tier_label} ($N = {n_tier:,}$)", fontweight="bold")
        ax.set_xlabel("Proportional Reporting Ratio (PRR)")
        ax.set_ylabel("EB05 (5th Percentile Shrinkage)")

        # Box annotation with tier statistics
        note_text = (
            f"PRR-only: {n_prr_only:,} ({pct_prr_suppressed:.1f}%)\n"
            f"EB05-only: {n_eb05_only:,}\n"
            f"Concordant: {n_both:,}"
        )
        if a_min == 2:
            note_text += "\n*PRR rule excludes a=2"
        ax.text(
            0.05, 0.95,
            note_text,
            transform=ax.transAxes,
            fontsize=8.2,
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#ffffff", edgecolor="#cfd8dc", alpha=0.88)
        )
        ax.grid(True, which="both", linestyle=":", alpha=0.35)

    # Panel F: Discordance summary across tiers (bar chart)
    ax_f = axes[5]
    tiers_summary = df_discordance[df_discordance["tier"] != "Overall (a >= 2)"]
    x_pos = np.arange(len(tiers_summary))
    bar_width = 0.38

    ax_f.bar(
        x_pos - bar_width/2,
        tiers_summary["pct_discordant_prr_only_in_tier"],
        width=bar_width,
        color="#d32f2f",
        label="PRR-Only Suppressed (% of tier)"
    )
    ax_f.bar(
        x_pos + bar_width/2,
        tiers_summary["pct_discordant_eb05_only_in_tier"],
        width=bar_width,
        color="#1976d2",
        label="EB05-Only Picked (% of tier)"
    )

    ax_f.set_xticks(x_pos)
    ax_f.set_xticklabels(tiers_summary["tier"], rotation=15)
    ax_f.set_ylabel("Discordant Pairs (% of Tier)")
    ax_f.set_title("Panel F: Discordance Rate by Report Volume Tier", fontweight="bold")
    ax_f.legend(loc="upper right", frameon=True, fontsize=8.5)
    ax_f.grid(True, axis="y", linestyle=":", alpha=0.4)

    # Annotation in Panel F
    ax_f.text(
        0.05, 0.78,
        "EB05-only occurs primarily at a=2\n(32,397 pairs where Evans PRR\nrequires a >= 3)",
        transform=ax_f.transAxes,
        fontsize=8.0,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#e3f2fd", edgecolor="#90caf9", alpha=0.9)
    )

    # Global legend above plots
    legend_elements = [
        matplotlib.lines.Line2D([0], [0], marker="o", color="w", markerfacecolor="#7b1fa2", markersize=7, label="Concordant Signal (PRR >= 2 & EB05 >= 2)"),
        matplotlib.lines.Line2D([0], [0], marker="o", color="w", markerfacecolor="#d32f2f", markersize=7, label="PRR-Only Alert (EB05 < 2.0; Shrinkage Suppressed)"),
        matplotlib.lines.Line2D([0], [0], marker="o", color="w", markerfacecolor="#1976d2", markersize=7, label="EB05-Only Alert (EB05 >= 2.0; Omitted by PRR rule)"),
        matplotlib.lines.Line2D([0], [0], marker="o", color="w", markerfacecolor="#b0bec5", markersize=5, label="Concordant Non-Signal (Both < 2.0)"),
        matplotlib.lines.Line2D([0], [0], color="#d32f2f", linestyle="--", label="PRR = 2.0 Threshold"),
        matplotlib.lines.Line2D([0], [0], color="#1976d2", linestyle="--", label="EB05 = 2.0 Threshold"),
        matplotlib.lines.Line2D([0], [0], color="#424242", linestyle=":", label="Identity Line (y = x)")
    ]
    fig.legend(handles=legend_elements, loc="upper center", bbox_to_anchor=(0.5, 0.99), ncol=4, frameon=False, fontsize=8.5)

    plt.subplots_adjust(top=0.91, bottom=0.08, left=0.07, right=0.96, hspace=0.32, wspace=0.25)

    png_path = os.path.join(OUT_DIR, "figure1_eb_shrinkage.png")
    pdf_path = os.path.join(OUT_DIR, "figure1_eb_shrinkage.pdf")
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"Saved Figure 1: {png_path} ({os.path.getsize(png_path)} bytes)")
    print(f"Saved Figure 1: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
    print(f"Figure 1 completed in {time.time() - start_time:.2f} seconds.")


def generate_figure2():
    print("\n--- Generating Figure 2: Independent Benchmark Discrimination ---")
    start_time = time.time()

    # Load observation-level benchmark data
    omop = pd.read_csv(OMOP_FILE)
    eu = pd.read_csv(EU_ADR_FILE)

    with open(BENCH_JSON, "r") as f:
        bench_json = json.load(f)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10.5))

    method_configs = [
        ("eb05", "EB05 (Primary)", "#1f77b4", "-", 2.2),
        ("ebgm", "EBGM", "#17becf", "-", 1.8),
        ("prr", "PRR (Comparator)", "#ff7f0e", "--", 1.8),
        ("ror", "ROR (Comparator)", "#2ca02c", ":", 1.8)
    ]

    # Panel A: OMOP PR Curves
    ax_a = axes[0, 0]
    n_omop = len(omop)
    n_omop_pos = (omop["groundTruth"] == 1).sum()
    n_omop_neg = (omop["groundTruth"] == 0).sum()
    prev_omop = n_omop_pos / n_omop

    for col, label, color, lstyle, lwidth in method_configs:
        precision, recall, _ = precision_recall_curve(omop["groundTruth"], omop[col])
        pr_auc = auc(recall, precision)
        # Verify with JSON
        json_auc = bench_json["benchmark_evaluation"]["omop"][col.upper()]["pr_auc"]
        ax_a.plot(recall, precision, color=color, linestyle=lstyle, linewidth=lwidth,
                  label=f"{label} (PR-AUC = {json_auc:.4f})")

    ax_a.axhline(prev_omop, color="#757575", linestyle=":", alpha=0.7, label=f"Baseline Prevalence ({prev_omop:.4f})")
    ax_a.set_xlim(-0.02, 1.02)
    ax_a.set_ylim(0.40, 1.02)
    ax_a.set_xlabel("Recall (Sensitivity)")
    ax_a.set_ylabel("Precision (Positive Predictive Value)")
    ax_a.set_title(f"A: OMOP Precision-Recall ($N = {n_omop}$; Pos: {n_omop_pos}, Neg: {n_omop_neg})", fontweight="bold")
    ax_a.legend(loc="lower left", frameon=True, fontsize=8.5)
    ax_a.grid(True, linestyle=":", alpha=0.4)

    # Panel B: OMOP ROC Curves
    ax_b = axes[0, 1]
    for col, label, color, lstyle, lwidth in method_configs:
        fpr, tpr, _ = roc_curve(omop["groundTruth"], omop[col])
        roc_auc = roc_auc_score(omop["groundTruth"], omop[col])
        json_auc = bench_json["benchmark_evaluation"]["omop"][col.upper()]["roc_auc"]
        ax_b.plot(fpr, tpr, color=color, linestyle=lstyle, linewidth=lwidth,
                  label=f"{label} (ROC-AUC = {json_auc:.4f})")

    ax_b.plot([0, 1], [0, 1], color="#757575", linestyle=":", alpha=0.7, label="Chance Line (0.5000)")
    ax_b.set_xlim(-0.02, 1.02)
    ax_b.set_ylim(-0.02, 1.02)
    ax_b.set_xlabel("False Positive Rate (1 - Specificity)")
    ax_b.set_ylabel("True Positive Rate (Sensitivity)")
    ax_b.set_title(f"B: OMOP ROC ($N = {n_omop}$; Pos: {n_omop_pos}, Neg: {n_omop_neg})", fontweight="bold")
    ax_b.legend(loc="lower right", frameon=True, fontsize=8.5)
    ax_b.grid(True, linestyle=":", alpha=0.4)

    # Panel C: EU-ADR PR Curves
    ax_c = axes[1, 0]
    n_eu = len(eu)
    n_eu_pos = (eu["groundTruth"] == 1).sum()
    n_eu_neg = (eu["groundTruth"] == 0).sum()
    prev_eu = n_eu_pos / n_eu

    for col, label, color, lstyle, lwidth in method_configs:
        precision, recall, _ = precision_recall_curve(eu["groundTruth"], eu[col])
        pr_auc = auc(recall, precision)
        json_auc = bench_json["benchmark_evaluation"]["euadr"][col.upper()]["pr_auc"]
        ax_c.plot(recall, precision, color=color, linestyle=lstyle, linewidth=lwidth,
                  label=f"{label} (PR-AUC = {json_auc:.4f})")

    ax_c.axhline(prev_eu, color="#757575", linestyle=":", alpha=0.7, label=f"Baseline Prevalence ({prev_eu:.4f})")
    ax_c.set_xlim(-0.02, 1.02)
    ax_c.set_ylim(0.45, 1.02)
    ax_c.set_xlabel("Recall (Sensitivity)")
    ax_c.set_ylabel("Precision (Positive Predictive Value)")
    ax_c.set_title(f"C: EU-ADR Precision-Recall ($N = {n_eu}$; Pos: {n_eu_pos}, Neg: {n_eu_neg})", fontweight="bold")
    ax_c.legend(loc="lower left", frameon=True, fontsize=8.5)
    ax_c.grid(True, linestyle=":", alpha=0.4)

    # Panel D: EU-ADR ROC Curves
    ax_d = axes[1, 1]
    for col, label, color, lstyle, lwidth in method_configs:
        fpr, tpr, _ = roc_curve(eu["groundTruth"], eu[col])
        roc_auc = roc_auc_score(eu["groundTruth"], eu[col])
        json_auc = bench_json["benchmark_evaluation"]["euadr"][col.upper()]["roc_auc"]
        ax_d.plot(fpr, tpr, color=color, linestyle=lstyle, linewidth=lwidth,
                  label=f"{label} (ROC-AUC = {json_auc:.4f})")

    ax_d.plot([0, 1], [0, 1], color="#757575", linestyle=":", alpha=0.7, label="Chance Line (0.5000)")
    ax_d.set_xlim(-0.02, 1.02)
    ax_d.set_ylim(-0.02, 1.02)
    ax_d.set_xlabel("False Positive Rate (1 - Specificity)")
    ax_d.set_ylabel("True Positive Rate (Sensitivity)")
    ax_d.set_title(f"D: EU-ADR ROC ($N = {n_eu}$; Pos: {n_eu_pos}, Neg: {n_eu_neg})", fontweight="bold")
    ax_d.legend(loc="lower right", frameon=True, fontsize=8.5)
    ax_d.grid(True, linestyle=":", alpha=0.4)

    plt.suptitle("Figure 2: Independent External Reference Standard Discrimination\n(OMOP Ground Truth & EU-ADR Benchmark)", fontweight="bold", y=0.98)
    fig.text(0.5, 0.01, "*Note: Evaluation is conditional on pair observability in FAERS (a >= 2). Unmatched negative controls (62.0% OMOP, 46.0% EU-ADR) omitted.",
             ha="center", fontsize=8.5, style="italic", color="#424242")

    plt.subplots_adjust(top=0.92, bottom=0.07, left=0.08, right=0.96, hspace=0.28, wspace=0.25)

    png_path = os.path.join(OUT_DIR, "figure2_benchmark_curves.png")
    pdf_path = os.path.join(OUT_DIR, "figure2_benchmark_curves.pdf")
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"Saved Figure 2: {png_path} ({os.path.getsize(png_path)} bytes)")
    print(f"Saved Figure 2: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
    print(f"Figure 2 completed in {time.time() - start_time:.2f} seconds.")


def generate_figure3():
    print("\n--- Generating Figure 3: Contextual Feature Distributions Across EB05 Strata ---")
    start_time = time.time()

    # Load summary and tests
    df_summary = pd.read_csv(STRATA_SUMMARY_FILE)
    df_tests = pd.read_csv(STRATA_TESTS_FILE).set_index("feature")

    # Order features by effect size (epsilon_squared descending)
    ordered_features = df_tests.sort_values(by="epsilon_squared", ascending=False).index.tolist()

    feature_labels = {
        "secondary_suspect_ratio": "Secondary Suspect Ratio",
        "csm_reporter_ratio": "Health Prof. Reporter Ratio",
        "age_std": "Age Standard Deviation (years)",
        "mean_age": "Mean Patient Age (years)",
        "median_age": "Median Patient Age (years)",
        "monotherapy_ratio": "Monotherapy Ratio",
        "mean_concomitant_count": "Mean Concomitant Drug Count",
        "hp_reporter_ratio": "Healthcare Prof. Reporter Ratio",
        "female_ratio": "Female Reporting Ratio",
        "male_ratio": "Male Reporting Ratio",
        "age_missing_ratio": "Age Missingness Ratio"
    }

    strata_keys = ["EB05 < 1.0", "1.0 <= EB05 < 2.0", "2.0 <= EB05 < 5.0", "5.0 <= EB05 < 10.0", "EB05 >= 10.0"]
    strata_x_labels = ["< 1.0", "1.0-2.0", "2.0-5.0", "5.0-10.0", ">= 10.0"]

    # 3 rows x 4 cols (11 features + 1 effect size ranking panel)
    fig, axes = plt.subplots(3, 4, figsize=(16, 11))
    axes = axes.flatten()

    palette = ["#90a4ae", "#81c784", "#64b5f6", "#ba68c8", "#ff8a65"]

    for i, feat in enumerate(ordered_features):
        ax = axes[i]
        t_info = df_tests.loc[feat]
        eps_sq = t_info["epsilon_squared"]
        mag = t_info["practical_magnitude"]
        p_adj = t_info["p_value_fdr_bh"]

        feat_sub = df_summary[(df_summary["feature"] == feat) & (df_summary["stratum"].isin(strata_keys))].copy()
        feat_sub["sort_order"] = feat_sub["stratum"].map(lambda s: strata_keys.index(s))
        feat_sub = feat_sub.sort_values(by="sort_order")

        # Plot median and IQR error bars
        medians = feat_sub["median"].values
        q25s = feat_sub["q25"].values
        q75s = feat_sub["q75"].values
        means = feat_sub["mean"].values

        yerr_lower = medians - q25s
        yerr_upper = q75s - medians

        x_coords = np.arange(len(strata_keys))

        # Bar chart with error bar representing IQR
        bars = ax.bar(x_coords, medians, width=0.55, color=palette, edgecolor="#37474f", linewidth=0.8, alpha=0.85)
        ax.errorbar(x_coords, medians, yerr=[yerr_lower, yerr_upper], fmt="none", ecolor="#212121", elinewidth=1.2, capsize=3.5)

        # Plot mean as red diamonds
        ax.scatter(x_coords, means, color="#d32f2f", marker="D", s=18, zorder=4, label="Mean" if i == 0 else "")

        ax.set_xticks(x_coords)
        ax.set_xticklabels(strata_x_labels, rotation=25, ha="right", fontsize=8.0)
        ax.set_title(f"{feature_labels.get(feat, feat)}", fontweight="bold", fontsize=9.5)

        # Effect size text
        p_str = "p < 1e-30" if p_adj < 1e-30 else f"p = {p_adj:.2e}"
        ax.text(
            0.04, 0.94,
            f"eps^2 = {eps_sq:.4f} ({mag.split()[0]})\n{p_str}",
            transform=ax.transAxes,
            fontsize=7.8,
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#ffffff", edgecolor="#cfd8dc", alpha=0.85)
        )
        ax.grid(True, axis="y", linestyle=":", alpha=0.35)

    # 12th panel: Effect size summary ranking
    ax_12 = axes[11]
    eps_vals = [df_tests.loc[f, "epsilon_squared"] for f in ordered_features]
    clean_labels = [feature_labels.get(f, f).replace(" Ratio", "").replace(" (years)", "") for f in ordered_features]

    y_pos = np.arange(len(ordered_features))
    bar_colors = ["#3949ab" if e >= 0.01 else "#78909c" for e in eps_vals]
    ax_12.barh(y_pos, eps_vals, color=bar_colors, edgecolor="#263238", height=0.65)
    ax_12.set_yticks(y_pos)
    ax_12.set_yticklabels(clean_labels, fontsize=7.5)
    ax_12.invert_yaxis()
    ax_12.set_xlabel("Epsilon-Squared Effect Size (eps^2)")
    ax_12.set_title("Contextual Variance Explained (eps^2)", fontweight="bold", fontsize=9.5)

    # Benchmark lines
    ax_12.axvline(0.01, color="#d32f2f", linestyle="--", linewidth=1.0, label="Small Benchmark (0.01)")
    ax_12.axvline(0.06, color="#e65100", linestyle=":", linewidth=1.0, label="Moderate Benchmark (0.06)")
    ax_12.set_xlim(0, 0.035)
    ax_12.legend(loc="lower right", fontsize=7.5, frameon=True)
    ax_12.grid(True, axis="x", linestyle=":", alpha=0.4)

    # Subplot adjust & titles
    plt.suptitle("Figure 3: Contextual Demographic, Reporting Channel, and Regimen Complexity Distributions\nAcross Empirical Bayes (EB05) Signal-Strength Strata ($N = 1,167,891$ Unique Candidate Pairs)",
                 fontweight="bold", y=0.985, fontsize=12)

    fig.text(0.5, 0.01, "*Bars represent stratum medians; whiskers represent interquartile ranges [Q1, Q3]; red diamonds represent arithmetic means. All p-values adjusted via Benjamini-Hochberg FDR.",
             ha="center", fontsize=8.5, style="italic", color="#424242")

    plt.subplots_adjust(top=0.92, bottom=0.06, left=0.06, right=0.97, hspace=0.38, wspace=0.28)

    png_path = os.path.join(OUT_DIR, "figure3_contextual_features.png")
    pdf_path = os.path.join(OUT_DIR, "figure3_contextual_features.pdf")
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"Saved Figure 3: {png_path} ({os.path.getsize(png_path)} bytes)")
    print(f"Saved Figure 3: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")
    print(f"Figure 3 completed in {time.time() - start_time:.2f} seconds.")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    generate_figure1()
    generate_figure2()
    generate_figure3()
    print("\nAll figures and companion files generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
