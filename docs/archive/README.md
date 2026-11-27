# Historical Methodological Documentation Archive

This directory preserves historical technical architecture designs, feasibility audits, and methodological quality reports generated during the development and validation of the FAERS-MGPS research pipeline.

The authoritative, production-grade documentation of the realized software and empirical findings is maintained in the root [`README.md`](../../README.md) and [`DATA_NOTICES.md`](../../DATA_NOTICES.md).

---

## Archived Documents Inventory

| Document | Original Milestone | Description & Historical Purpose |
| :--- | :---: | :--- |
| [`research_architecture_blueprint.md`](research_architecture_blueprint.md) | Project Inception | Initial conceptual system architecture designed prior to pipeline realization. Describes early draft schemas, prospective openFDA/DailyMed integration concepts, and modular design requirements. |
| [`modelling_readiness_and_historical_label_audit.md`](modelling_readiness_and_historical_label_audit.md) | Quality Gate Review | Methodological investigation of historical training-label feasibility. Establishes the empirical rationale for rejecting versioned DailyMed SPL XML and FDA SrLC sources due to regulatory vs. publication timestamp mismatches, formally justifying the unsupervised empirical Bayes methodology. |
| [`pre_modelling_readiness_report.md`](pre_modelling_readiness_report.md) | Quality Gate Review | Quality audit protocol for retraction handling, case deduplication, and clinical outcome seriousness quarantine to prevent indication bias. |
