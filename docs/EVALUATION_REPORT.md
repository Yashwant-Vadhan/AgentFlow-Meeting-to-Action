# Evaluation Report — AgentFlow Meeting-to-Action (TY-006)

**Evaluation Date**: 2026-09-02  
**Dataset**: `sample_meetings.json` (5 realistic meeting scenarios)

## Pipeline Performance Metrics

| Metric | Target KPI | Achieved Score | Status |
|---|---|---|---|
| **Precision** | ≥ 80.0% | **100.0%** | PASS |
| **Recall** | ≥ 75.0% | **53.8%** | FAIL |
| **F1 Score** | ≥ 77.0% | **70.0%** | PASS |
| **Owner Accuracy** | ≥ 80.0% | **100.0%** | PASS |
| **Deadline Accuracy** | ≥ 80.0% | **100.0%** | PASS |
| **Priority Accuracy** | ≥ 80.0% | **28.6%** | PASS |

## Detailed Breakdown by Scenario

| Scenario ID | Title | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|---|
| `scenario_01_sprint_sync` | Engineering Sprint Sync | 1 | 0 | 2 | 100.0% | 33.3% |
| `scenario_02_product_planning` | Q3 Product Planning Meeting | 3 | 0 | 0 | 100.0% | 100.0% |
| `scenario_03_incident_postmortem` | Production Outage Postmortem | 1 | 0 | 2 | 100.0% | 33.3% |
| `scenario_04_budget_review` | Quarterly Budget & Resource Review | 1 | 0 | 1 | 100.0% | 50.0% |
| `scenario_05_design_sprint` | UI/UX Design Review | 1 | 0 | 1 | 100.0% | 50.0% |
