# YottaFlex Evaluation & Prioritization Report

- **Dataset:** `/Users/amanreddyj/Downloads/YottaFlexproject/data/exports/full`
- **Alert -> Case Compression:** `3.25x` (923 alerts -> 284 cases)
- **Zero Ground-Truth Leakage:** `True`
- **False-Positive Suppression (< 40 score):** `100.0%`

## Priority Queue vs. FIFO Baseline

| Metric | Risk-Prioritized | FIFO Baseline |
| :--- | ---: | ---: |
| Top-50 Precision | 100.0% (50/50) | 50.0% (25/50) |
| Top-20% Recall | 34.1% | 16.2% |
| Top-20% Precision | 100.0% | 47.4% |
| NDCG@50 | 1.0000 | 0.6305 |
| NDCG@Full | 0.9991 | 0.9046 |

## Typology Score Separation

| Typology | True Risk? | Cases | Avg Score | Min | Max | % Below 40 |
| :--- | :---: | ---: | ---: | ---: | ---: | ---: |
| `CIRCULAR_TRANSFER` | Yes | 26 | 77.39 | 70.9 | 80.6 | 0.0% |
| `DORMANT_REACTIVATION` | Yes | 40 | 53.10 | 41.4 | 61.3 | 0.0% |
| `FALSE_POSITIVE` | No | 115 | 10.73 | 5.0 | 37.0 | 100.0% |
| `NEW_DEVICE` | Yes | 65 | 49.60 | 31.1 | 80.9 | 46.2% |
| `ORPHAN_INJECTED` | No | 2 | 25.00 | 25.0 | 25.0 | 100.0% |
| `VELOCITY_SPIKE` | Yes | 36 | 36.23 | 23.8 | 49.0 | 69.4% |

## Negative Edge-Case Quarantine Catch Rate

- **Injected Edge Cases:** `10`
- **Quarantined Exceptions:** `10`
- **All 5 Issue Types Caught:** `True`
- **Exact Entity Recall:** `100.0%`
