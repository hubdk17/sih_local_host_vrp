"""
Standalone Generator: Bold, Clean Heaviside Ceiling Switching Graph
===================================================================
Regenerates the Heaviside Unit Step and Sigmoidal Relaxation graph:
- Extra bold lines:
    * Heaviside step: linewidth=6.0 (rich gold/amber #c27803)
    * Sigmoidal relaxation: linewidth=4.0, dashed #0284c7
    * Ceiling boundary: linewidth=3.5, dotted #991b1b
- Shaded phase zones fill precisely [0, 1] in y, matching original layout:
    * Phase 1 (0 to 10): Soft mint green #10b981 (alpha=0.14)
    * Phase 2 (10 to 40): Soft ice blue #38bdf8 (alpha=0.14)
- Removes the cluttered text/legend box from inside the graph area
- Large bold typography on axes (15pt bold labels, 13pt bold ticks) for perfect legibility even when viewed small
- Generates:
    1. heaviside_ceiling_switching_bold.png (Clean horizontal legend docked above plot)
    2. heaviside_ceiling_switching_pure.png (Pure minimalist - zero legend text)
    3. heaviside_ceiling_switching_badges.png (With clean top phase header badges)
    4. Dark theme counterparts for each
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

FINAL_DIR = r"d:\Desktop\QPSO_SIH\final_graphs"
WEB_DIR = r"d:\Desktop\QPSO_SIH\web\assets\graphs"
os.makedirs(FINAL_DIR, exist_ok=True)
os.makedirs(WEB_DIR, exist_ok=True)

# Calculation coordinates
k_range = np.linspace(0, 40, 600)
k_ceiling = 10.0

# Exact piecewise step coordinates: flat at 0 until 10, vertical jump to 1, flat at 1
k_step = np.array([0.0, 10.0, 10.0, 40.0])
y_step = np.array([0.0, 0.0, 1.0, 1.0])

# Smooth sigmoid relaxation centered at K=10 with slope factor 1.5
sigmoid_relax = 1.0 / (1.0 + np.exp(-1.5 * (k_range - k_ceiling)))


def generate_heaviside_graph(mode='clean_top', theme='white'):
    """
    mode: 'clean_top' | 'pure' | 'badges'
    theme: 'white' | 'dark'
    """
    is_dark = (theme == 'dark')
    bg_color = '#0a0e17' if is_dark else '#ffffff'
    card_color = '#111827' if is_dark else '#ffffff'
    border_color = '#374151' if is_dark else '#94a3b8'
    text_color = '#f8fafc' if is_dark else '#0f172a'
    tick_color = '#cbd5e1' if is_dark else '#1e293b'
    grid_color = '#1e293b' if is_dark else '#f1f5f9'

    # Palette
    c_gold = '#d97706' if is_dark else '#b45309'      # Warm gold/amber
    c_blue = '#38bdf8' if is_dark else '#0284c7'      # Vibrant blue
    c_red = '#f87171' if is_dark else '#991b1b'       # Dotted boundary
    c_green_fill = '#10b981'
    c_blue_fill = '#38bdf8'

    fig, ax = plt.subplots(figsize=(9.2, 5.8), dpi=300, facecolor=bg_color)
    ax.set_facecolor(card_color)

    # 1. Shaded Phase Regions [y: 0.0 to 1.0]
    alpha_zone = 0.16 if is_dark else 0.12
    ax.fill_between(k_range, 0.0, 1.0, where=(k_range <= k_ceiling),
                    color=c_green_fill, alpha=alpha_zone, zorder=1)
    ax.fill_between(k_range, 0.0, 1.0, where=(k_range >= k_ceiling),
                    color=c_blue_fill, alpha=alpha_zone, zorder=1)

    # 2. Vertical Ceiling Boundary (Bold dotted line extending full height)
    boundary_label = r'Ceiling Boundary ($K_{\mathrm{crit}} = 10$)' if mode in ['clean_top', 'badges'] else None
    ax.axvline(k_ceiling, color=c_red, linestyle=':', linewidth=3.5, zorder=3, label=boundary_label)

    # 3. Sigmoidal Relaxation Curve (Bold dashed curve)
    sigmoid_label = r'Sigmoidal Relaxation $\sigma(K - 10)$' if mode in ['clean_top', 'badges'] else None
    ax.plot(k_range, sigmoid_relax, color=c_blue, linestyle='--', linewidth=4.0, zorder=4, label=sigmoid_label)

    # 4. Heaviside Unit Step Curve (Extra bold solid step)
    step_label = r'Heaviside Unit Step $\Theta(K - 10)$' if mode in ['clean_top', 'badges'] else None
    ax.plot(k_step, y_step, color=c_gold, linewidth=6.0, solid_capstyle='butt', zorder=5, label=step_label)

    # Optional mode 'badges': Clean unobtrusive text tags at top of each zone
    if mode == 'badges':
        badge_bg = '#1f2937' if is_dark else '#e2e8f0'
        ax.text(5.0, 1.06, 'PHASE 1: MICRO-PRECISION (K ≤ 10)',
                ha='center', va='center', fontsize=9.5, fontweight='bold',
                color='#059669' if not is_dark else '#34d399',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_bg, edgecolor='none', alpha=0.9))
        ax.text(25.0, 1.06, 'PHASE 2: TURING MEGA-SCALE (K > 10)',
                ha='center', va='center', fontsize=9.5, fontweight='bold',
                color='#0284c7' if not is_dark else '#38bdf8',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=badge_bg, edgecolor='none', alpha=0.9))

    # 5. Spines & Axes Formatting
    for spine in ax.spines.values():
        spine.set_edgecolor(border_color)
        spine.set_linewidth(1.8)

    ax.tick_params(axis='both', which='major', colors=tick_color, labelsize=13.5, width=1.8, length=6)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight('bold')

    ax.set_xlim(0, 40)
    ax.set_ylim(-0.06, 1.15)
    ax.set_xticks(np.arange(0, 45, 5))
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])

    # Subtle grid
    ax.grid(True, linestyle=':', alpha=0.45, color=grid_color, linewidth=1.0)

    # Bold Axis Labels
    ax.set_xlabel('Number of Depots (K)', fontsize=15, fontweight='bold', color=text_color, labelpad=10)
    ax.set_ylabel(r'Engine Selection Value $\Theta(K)$', fontsize=15, fontweight='bold', color=text_color, labelpad=12)

    # 6. Legend (Only outside the plot, docked at the top, leaving plot canvas 100% clean)
    if mode == 'clean_top':
        legend = ax.legend(
            loc='lower center',
            bbox_to_anchor=(0.5, 1.02),
            ncol=3,
            frameon=True,
            facecolor=card_color,
            edgecolor=border_color,
            fontsize=11.5,
            handlelength=2.4,
            handletextpad=0.6,
            columnspacing=1.6
        )
        for text in legend.get_texts():
            text.set_color(text_color)
            text.set_fontweight('bold')

    plt.tight_layout()

    # Determine filename
    base_name = f"heaviside_ceiling_switching_{mode}"
    if theme == 'dark':
        base_name += "_dark"
    filename = f"{base_name}.png"

    path_final = os.path.join(FINAL_DIR, filename)
    path_web = os.path.join(WEB_DIR, filename)

    fig.savefig(path_final, dpi=300, facecolor=bg_color, bbox_inches='tight')
    fig.savefig(path_web, dpi=300, facecolor=bg_color, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Saved: {path_final}")
    return path_final


if __name__ == '__main__':
    for theme in ['white', 'dark']:
        # 1. Clean Top (Legend docked above canvas, zero text inside plot)
        generate_heaviside_graph(mode='clean_top', theme=theme)
        # 2. Pure (Zero legend text anywhere)
        generate_heaviside_graph(mode='pure', theme=theme)
        # 3. Badges (Minimal phase badges at top margin)
        generate_heaviside_graph(mode='badges', theme=theme)

    print("\n[SUCCESS] Generated all bold, clean Heaviside graph variations!")
