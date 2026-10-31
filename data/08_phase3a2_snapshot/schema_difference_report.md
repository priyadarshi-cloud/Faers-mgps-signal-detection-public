# Phase 3A.2 — Cross-Quarter Schema Difference Report
**Generated:** 2026-10-11T01:42:13.501767
**Quarters scanned:** 2014Q1 – 2023Q4  (40 total)

> [!NOTE]
> Columns listed below are in LOWERCASE. Each section shows the union of all
> columns seen across all 40 quarters for that table, along with which quarters
> first introduced each column.

## DEMO
- Quarters with file: **40/40**
- Column union size: **26**
- Columns present in ALL quarters: **21**
- Columns NOT in all quarters (introduced or removed): **5**

### Columns not present in all quarters
| Column | First seen | Present in N quarters |
|--------|-----------|----------------------|
| `age_grp` | 2014Q3 | 38/40 |
| `auth_num` | 2014Q3 | 38/40 |
| `gndr_cod` | 2014Q1 | 2/40 |
| `lit_ref` | 2014Q3 | 38/40 |
| `sex` | 2014Q3 | 38/40 |

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `age` | 2014Q1 |
| `age_cod` | 2014Q1 |
| `age_grp` | 2014Q3 |
| `auth_num` | 2014Q3 |
| `caseid` | 2014Q1 |
| `caseversion` | 2014Q1 |
| `e_sub` | 2014Q1 |
| `event_dt` | 2014Q1 |
| `fda_dt` | 2014Q1 |
| `gndr_cod` | 2014Q1 |
| `i_f_code` | 2014Q1 |
| `init_fda_dt` | 2014Q1 |
| `lit_ref` | 2014Q3 |
| `mfr_dt` | 2014Q1 |
| `mfr_num` | 2014Q1 |
| `mfr_sndr` | 2014Q1 |
| `occp_cod` | 2014Q1 |
| `occr_country` | 2014Q1 |
| `primaryid` | 2014Q1 |
| `reporter_country` | 2014Q1 |
| `rept_cod` | 2014Q1 |
| `rept_dt` | 2014Q1 |
| `sex` | 2014Q3 |
| `to_mfr` | 2014Q1 |
| `wt` | 2014Q1 |
| `wt_cod` | 2014Q1 |

---

## DRUG
- Quarters with file: **40/40**
- Column union size: **20**
- Columns present in ALL quarters: **19**
- Columns NOT in all quarters (introduced or removed): **1**

### Columns not present in all quarters
| Column | First seen | Present in N quarters |
|--------|-----------|----------------------|
| `prod_ai` | 2014Q3 | 38/40 |

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `cum_dose_chr` | 2014Q1 |
| `cum_dose_unit` | 2014Q1 |
| `dechal` | 2014Q1 |
| `dose_amt` | 2014Q1 |
| `dose_form` | 2014Q1 |
| `dose_freq` | 2014Q1 |
| `dose_unit` | 2014Q1 |
| `dose_vbm` | 2014Q1 |
| `drug_seq` | 2014Q1 |
| `drugname` | 2014Q1 |
| `exp_dt` | 2014Q1 |
| `lot_num` | 2014Q1 |
| `nda_num` | 2014Q1 |
| `primaryid` | 2014Q1 |
| `prod_ai` | 2014Q3 |
| `rechal` | 2014Q1 |
| `role_cod` | 2014Q1 |
| `route` | 2014Q1 |
| `val_vbm` | 2014Q1 |

---

## REAC
- Quarters with file: **40/40**
- Column union size: **4**
- Columns present in ALL quarters: **3**
- Columns NOT in all quarters (introduced or removed): **1**

### Columns not present in all quarters
| Column | First seen | Present in N quarters |
|--------|-----------|----------------------|
| `drug_rec_act` | 2014Q3 | 38/40 |

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `drug_rec_act` | 2014Q3 |
| `primaryid` | 2014Q1 |
| `pt` | 2014Q1 |

---

## OUTC
- Quarters with file: **40/40**
- Column union size: **3**
- Columns present in ALL quarters: **3**
- Columns NOT in all quarters (introduced or removed): **0**

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `outc_cod` | 2014Q1 |
| `primaryid` | 2014Q1 |

---

## RPSR
- Quarters with file: **40/40**
- Column union size: **3**
- Columns present in ALL quarters: **3**
- Columns NOT in all quarters (introduced or removed): **0**

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `primaryid` | 2014Q1 |
| `rpsr_cod` | 2014Q1 |

---

## THER
- Quarters with file: **40/40**
- Column union size: **7**
- Columns present in ALL quarters: **7**
- Columns NOT in all quarters (introduced or removed): **0**

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `dsg_drug_seq` | 2014Q1 |
| `dur` | 2014Q1 |
| `dur_cod` | 2014Q1 |
| `end_dt` | 2014Q1 |
| `primaryid` | 2014Q1 |
| `start_dt` | 2014Q1 |

---

## INDI
- Quarters with file: **40/40**
- Column union size: **4**
- Columns present in ALL quarters: **4**
- Columns NOT in all quarters (introduced or removed): **0**

### Complete column union (all quarters)
| Column | First seen |
|--------|-----------|
| `caseid` | 2014Q1 |
| `indi_drug_seq` | 2014Q1 |
| `indi_pt` | 2014Q1 |
| `primaryid` | 2014Q1 |

---
