# Variation F: Multi-Seed Monte Carlo Statistical Rigor (10 Seeds)

| Metric                    | Quantum HQ-GLS          | Google OR-Tools (Exact)   | Delta-Well QPSO   | Classical GA   |
|:--------------------------|:------------------------|:--------------------------|:------------------|:---------------|
| Mean Distance (km)        | 119.40                  | 120.32                    | 134.12            | 140.61         |
| Std Dev (km)              | 7.53                    | 7.88                      | 10.33             | 11.72          |
| Min Distance (km)         | 105.64                  | 109.37                    | 117.03            | 121.35         |
| Max Distance (km)         | 131.39                  | 133.04                    | 151.26            | 158.72         |
| p-value vs GA (t-test)    | 4.1650e-06 (p < 0.001)  | -                         | -                 | -              |
| p-value vs Exact (t-test) | 0.198 (Not sig / Equal) | -                         | -                 | -              |