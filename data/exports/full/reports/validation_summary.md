# YottaFlex Integrity & Reconciliation Validation Summary

- **Dataset:** `/Users/amanreddyj/Downloads/YottaFlexproject/data/exports/full`
- **Checks Executed:** `9`
- **Total Quarantined Exceptions:** `10`

## Check Matrix

| # | Validation Check | Records Checked | Violations Caught | Status |
| :---: | :--- | ---: | ---: | :---: |
| 1 | PK Uniqueness & ID Nomenclature Regex | 149,723 | 0 | **PASS** |
| 2 | Foreign-Key Referential Integrity | 293,050 | 0 | **PASS** |
| 3 | Allowed Enums & Numeric Domain Bounds | 556,672 | 0 | **PASS** |
| 4 | Temporal & Disposition-After-Alert Ordering | 12,078 | 2 | **FAIL** |
| 5 | Running Balance & Overdraft Reconciliation | 107,000 | 2 | **FAIL** |
| 6 | Closed-Account Posting Enforcement | 100,000 | 2 | **FAIL** |
| 7 | Transfer-Leg Double-Entry Reconciliation | 4,640 | 2 | **FAIL** |
| 8 | Alert Trigger Fact Traceability | 923 | 2 | **FAIL** |
| 9 | Lifecycle Transitions & Bridge Uniqueness | 13,365 | 0 | **PASS** |

## Quarantined Exceptions by Issue Type

| Issue Type | Count |
| :--- | ---: |
| `DISPOSITION_PRECEDES_ALERT` | 2 |
| `NEGATIVE_BALANCE_NO_OVERDRAFT` | 2 |
| `ORPHAN_ALERT_NO_TRIGGER` | 2 |
| `TXN_ON_CLOSED_ACCOUNT` | 2 |
| `UNRECONCILED_TRANSFER_LEG` | 2 |
