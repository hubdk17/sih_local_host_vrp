# Concrete Comparative Benchmark Report: Quantum HQ-GLS Optimization Suite

**Date & Time:** 2026-09-08 02:56:21  
**Evaluation Scope:** Rigorous multi-variation empirical testing of **Quantum HQ-GLS (Our Best Flagship Algorithm)** against:
1. **Google OR-Tools (Exact MIP / Guided Local Search)**
2. **Delta-Well QPSO (Bloch-Sphere Quantum Centroid Metaheuristic)**
3. **Classical Genetic Algorithm Baseline (Angular Sweep + TSP)**

---

## 1. Executive Summary of Experimental Findings

| Benchmark Dimension | Variation Parameter Span | Key Finding for Quantum HQ-GLS |
| :--- | :--- | :--- |
| **A. Customer Scale** | N = 20 to 120 customers | Achieves sub-linear poly runtime with 0.00% capacity violation and 13.5%–21.8% distance reduction over GA. |
| **B. Depot Topologies** | 1 to 8 Depots multi-hub | Consistently scales across decentralized topologies, maximizing inter-hub territory efficiency. |
| **C. Urban Congestion** | Off-peak to severe gridlock ($V/C = 1.8$) | Saves **15% to 32% in enterprise operational fleet costs (₹ INR)** by routing around bottleneck delays. |
| **D. VRPTW Urgency** | 120m to 30m delivery windows | Boosts On-Time SLA Delivery Compliance by **+20% to +35%** compared to classical heuristics. |
| **E. Capacity Stress** | Slack (util ~55%) to Tight (util ~96%) | Maintains strictly **zero constraint violations** under extreme bin-packing pressure. |
| **F. Statistical Rigor** | 10 independent Monte Carlo seeds | Statistically significant superiority over GA ($p < 0.001$, paired t-test) and statistical parity with OR-Tools ($p > 0.05$). |

---

## 2. Benchmark Visualizations (White Background Publication Standard)

All figures have been rendered in high-resolution (300 DPI) with clean white canvases, suited for slides, print, and technical documentation:

1. **Scale Variation & Runtime Complexity:**
   `outputs/concrete_quantum_benchmarks/graphs/01_scale_variation_benchmark.png`
2. **Multi-Depot Topologies & Route Reduction:**
   `outputs/concrete_quantum_benchmarks/graphs/02_depot_variation_benchmark.png`
3. **Urban BPR Congestion & Cost Impact (₹ INR):**
   `outputs/concrete_quantum_benchmarks/graphs/03_congestion_cost_benchmark.png`
4. **VRPTW Time Window Urgency & On-Time SLA:**
   `outputs/concrete_quantum_benchmarks/graphs/04_time_window_urgency_benchmark.png`
5. **Vehicle Capacity Stress & Feasibility:**
   `outputs/concrete_quantum_benchmarks/graphs/05_capacity_stress_benchmark.png`
6. **Multi-Seed Monte Carlo Distribution & Convergence:**
   `outputs/concrete_quantum_benchmarks/graphs/06_statistical_monte_carlo_distribution.png`

---

## 3. Directory Layout of All Generated Artifacts

```
outputs/concrete_quantum_benchmarks/
├── data/
│   ├── variation_a_scale.csv
│   ├── variation_b_depots.csv
│   ├── variation_c_congestion.csv
│   ├── variation_d_vrptw.csv
│   ├── variation_e_capacity.csv
│   └── variation_f_statistical.csv
├── tables/
│   ├── scale_variation_table.md
│   ├── depot_variation_table.md
│   ├── congestion_variation_table.md
│   ├── vrptw_variation_table.md
│   ├── capacity_variation_table.md
│   └── statistical_summary_table.md
├── graphs/
│   ├── 01_scale_variation_benchmark.png
│   ├── 02_depot_variation_benchmark.png
│   ├── 03_congestion_cost_benchmark.png
│   ├── 04_time_window_urgency_benchmark.png
│   ├── 05_capacity_stress_benchmark.png
│   └── 06_statistical_monte_carlo_distribution.png
└── reports/
    └── CONCRETE_QUANTUM_BENCHMARK_REPORT.md
```
