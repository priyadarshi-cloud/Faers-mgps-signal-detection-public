# Third-Party Data Notices and Attribution

This document describes the provenance, bibliographic citations, and licensing terms for external reference standards and public datasets bundled with or referenced by this repository.

> **Scope Notice:**  
> The project software code (modules in `src/` and scripts in `scripts/`) is licensed under the **Apache License, Version 2.0** as set forth in the [`LICENSE`](LICENSE) file.  
> The third-party datasets and reference standards in `data/` are governed by their respective upstream licenses, public-domain determinations, and terms described below.

---

## 1. OMOP Reference Standard

- **Dataset Location:** `data/05_reference_standards/omop/`
  - `omopReferenceSet.rda` ($6,872$ bytes, SHA-256: `8d0964fce92c557d98cb751ec2aea7c1e3e1643696231a177128579a5662fa15`)
  - `omop_reference_set.csv` ($65,094$ bytes, SHA-256: `779fc1b2649a61221b496efa53072fccb4c8efe932a9f5bf02e8ef9ae5a61c6f`)
- **Upstream Repository:** Observational Health Data Sciences and Informatics (OHDSI) — [`OHDSI/MethodEvaluation`](https://github.com/OHDSI/MethodEvaluation)
- **Upstream Revision:** Release `v2.4.2` (Published 2026-09-18; maintainer Dr. Martijn Schuemie)
- **Bibliographic Citation:**
  > Ryan PB, Schuemie MJ, Welebob E, Duke J, Valentine S, Hartzema AG. Defining a reference set to support methodological research in drug safety. *Drug Safety*, 2013; 36(Suppl 1):S33–S47. DOI: [10.1007/s40264-013-0097-8](https://doi.org/10.1007/s40264-013-0097-8).
- **Upstream License & Terms:**
  - Distributed upstream under the **Apache License, Version 2.0**.
  - Verified upstream at `v2.4.2`: The license is formally declared in package metadata (`DESCRIPTION`: `License: Apache License 2.0`) and repository documentation (`README.md`). Inspection of the upstream repository tree confirms that no standalone `LICENSE` or `NOTICE` file is committed.
  - Upstream project acknowledgement: Supported in part through National Science Foundation grant IIS 1251151.
- **Derivative Nature:**
  - `omop_reference_set.csv` is a **transformed derivative** extracted directly from `omopReferenceSet.rda` via Python `pyreadr` and `pandas` serialization (see `scripts/load_omop_reference_set.py`).
  - Contains 399 evaluated drug–outcome pairs (165 positive controls, 234 negative controls across 4 health outcomes of interest).
  - Field-by-field verification confirms 0 differences across all records relative to the upstream R data frame.

---

## 2. EU-ADR Reference Standard

- **Dataset Location:** `data/05_reference_standards/eu_adr/`
  - `euadrReferenceSet.rda` ($2,988$ bytes, SHA-256: `5cea251e7ab03a232f871abfb448655b8474ffab325bb19b4fbae8d139203c32`)
  - `eu_adr_reference_set.csv` ($15,389$ bytes, SHA-256: `2195513ac9328c4bc95fc2fe30046c20bbf064ce1eb951d37a392c8f978774f1`)
- **Upstream Repository:** Observational Health Data Sciences and Informatics (OHDSI) — [`OHDSI/MethodEvaluation`](https://github.com/OHDSI/MethodEvaluation)
- **Upstream Revision:** Release `v2.4.2` (Published 2026-09-18; maintainer Dr. Martijn Schuemie)
- **Cryptographic Match:** The bundled binary file `euadrReferenceSet.rda` is **100% byte-identical** to the file distributed in OHDSI `MethodEvaluation` at `v2.4.2` and `main`.
- **Original Bibliographic Citation:**
  > Coloma PM, Avillach P, Salvo F, Schuemie MJ, Ferrajolo C, Pariente A, Fourrier-Reglat A, Molokhia M, Patadia V, van der Lei J, Sturkenboom M, Trifiro G. A reference standard for evaluation of methods for drug safety signal detection using electronic healthcare record databases. *Drug Safety*, 2013; 36(1):13–23. DOI: [10.1007/s40264-012-0002-x](https://doi.org/10.1007/s40264-012-0002-x).
- **Upstream License & Legal Provenance:**
  - Standardized into OMOP Concept IDs and distributed within the OHDSI `MethodEvaluation` package under the **Apache License, Version 2.0**.
  - Verified upstream at `v2.4.2`: The license is formally declared in package metadata (`DESCRIPTION`: `License: Apache License 2.0`) and repository documentation (`README.md`). Inspection of the upstream repository tree confirms that no standalone `LICENSE` or `NOTICE` file is committed.
  - Dr. Martijn Schuemie is both the author/maintainer of the Apache-2.0-licensed OHDSI package and a named co-author of the original Coloma et al. (2013) publication.
  - Copyright in the published journal article text, typesetting, and formatting belongs to Springer International Publishing AG. Factual clinical association data (drug–adverse event ground truth) and OMOP concept identifiers released under Apache 2.0 by OHDSI are redistributed here pursuant to the terms of the Apache License, Version 2.0.
- **Derivative Nature:**
  - `eu_adr_reference_set.csv` is a **transformed derivative** extracted directly from `euadrReferenceSet.rda` via Python `pyreadr` and `pandas` serialization.
  - Contains 93 evaluated drug–outcome pairs (43 positive controls, 50 negative controls across 10 health outcomes of interest). Field-by-field programmatic comparison confirms 0 differences across all 930 data cells relative to the upstream R data frame.
  - As documented by OHDSI, 93 pairs are distributed rather than the original 94 because Nimesulide (associated with acute liver injury) is absent from RxNorm and unavailable in many jurisdictions.

---

## 3. Primary FAERS Data (US FDA)

- **Source:** US Food and Drug Administration (FDA) Adverse Event Reporting System (FAERS) Public Dashboard and Quarterly ASCII Data Files.
- **URL:** [https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard](https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-public-dashboard)
- **Legal Status & Public Data Notice:**
  - FAERS data files are publicly distributed by the U.S. Food and Drug Administration without copyright restriction as public government data releases.
  - While government compilations and reports prepared by U.S. government officers or employees are subject to 17 U.S.C. § 105, individual adverse event narratives submitted by third-party reporters (manufacturers, healthcare professionals, consumers) are compiled and published by the FDA for open public access.
  - **FDA Disclaimer:** This analysis is an independent research effort. It was not conducted by or on behalf of the U.S. Food and Drug Administration and does not represent FDA views, findings, or endorsement.
- **Distribution Note:**
  - Raw FAERS archives (~14.7 GB extracted across 20 quarterly packages, 2014 Q1 to 2018 Q4) are **excluded** from this repository to ensure a lightweight footprint (~9.6 MB).
  - Users can download raw archives directly from the FDA using the automated script:
    ```bash
    python scripts/download_continuous_faers.py
    ```
  - Pre-computed, aggregated publication tables derived from FAERS are included in `data/20_track1_publication_tables/`.

---

## 4. SIDER Side-Effect Resource (Excluded)

- **Source:** EMBL (European Molecular Biology Laboratory) / Kuhn et al., *Molecular Systems Biology*, 2016.
- **Status:** SIDER 4.1 was audited during pipeline development and formally rejected (NO-GO) for positive-unlabeled learning due to the absence of temporal timestamps and low active ingredient coverage.
- **Exclusion:** All raw SIDER 4.1 data files and format text are **excluded** from this repository. Only non-proprietary provenance checksums (`data/04_audit_sider/sider_source_checksums.json`) and the original analytical feasibility report are retained.

---

## 5. Disclaimer of Liability

All reference standards and data sets are provided on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. Users are solely responsible for determining the appropriateness of using or redistributing the data.
