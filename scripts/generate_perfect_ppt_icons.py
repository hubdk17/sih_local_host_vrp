"""
generate_perfect_ppt_icons.py

Final, pixel-perfect, publication-grade PPT Small Icon Generator.
Produces:
1. icon_quantum_tunneling_white.png
2. icon_quantum_tunneling_trans.png
3. icon_quantum_tunneling_card.png
4. icon_quantum_delta_well_white.png
5. icon_quantum_delta_well_trans.png
6. icon_quantum_delta_well_card.png
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

BASE_DIR = r"d:\Desktop\QPSO_SIH"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ppt_icons")
os.makedirs(OUTPUT_DIR, exist_ok=True)
ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c"

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['mathtext.fontset'] = 'cm'

# =============================================================================
# 1. QUANTUM TUNNELING OPERATOR - PERFECT PPT ICON
# =============================================================================
def render_tunneling(style="white"):
    is_trans = (style == "trans")
    is_card = (style == "card")
    bg = 'white' if not is_trans else 'none'

    fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=300, facecolor=bg)
    ax.set_facecolor(bg)

    # Optional card border with rounded corners
    if is_card:
        card = patches.FancyBboxPatch((-2.58, -0.68), 5.16, 5.86,
                                      boxstyle="round,pad=0.08,rounding_size=0.35",
                                      facecolor="#ffffff", edgecolor="#0284c7",
                                      lw=3.0, alpha=1.0, zorder=0)
        ax.add_patch(card)

    # Potential energy landscape:
    # V(x) = 0.45 * (x^4 - 4.1*x^2 - 1.2*x) + 3.4
    x = np.linspace(-2.55, 2.55, 600)
    V = 0.45 * (x**4 - 4.1 * x**2 - 1.2 * x) + 3.4

    # Minima and Barrier Peak:
    # Left local trap: x ~ -1.41, V ~ 2.45
    # Right global optimum: x ~ 1.54, V ~ 0.82
    # Barrier peak: x ~ -0.15, V ~ 3.48
    trap_x, trap_y = -1.41, 2.48
    opt_x, opt_y = 1.54, 0.85
    barrier_x, barrier_y = -0.15, 3.48

    # 1. Fill under curve for soft depth
    ax.fill_between(x, V, 5.0, color='#f8fafc', alpha=0.85 if not is_trans else 0.25, zorder=1)

    # 2. Main Potential Energy Curve (Ultra Bold)
    ax.plot(x, V, color='#0f172a', lw=7.0, solid_capstyle='round', zorder=5)

    # 3. Energy Level E dashed horizontal line
    E_lvl = 3.35
    ax.axhline(E_lvl, xmin=0.1, xmax=0.9, color='#94a3b8', ls=':', lw=2.2, zorder=3, alpha=0.8)
    ax.text(2.05, E_lvl + 0.14, "Energy E", color='#64748b', fontsize=11, fontweight='bold', ha='center', zorder=6)

    # 4. Classical Trajectory: Blocked Arrow
    ax.annotate("", xy=(-0.45, E_lvl), xytext=(-2.1, E_lvl),
                arrowprops=dict(arrowstyle="->,head_width=0.7,head_length=0.8", color='#dc2626', lw=5.0), zorder=6)
    # Red X at barrier wall
    ax.scatter([-0.45], [E_lvl], s=350, marker='X', color='#dc2626', zorder=9)
    ax.text(-1.3, E_lvl + 0.38, "CLASSICAL: BLOCKED", color='#dc2626', fontsize=11, fontweight='bold',
            ha='center', va='center', zorder=8,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#fff1f2', edgecolor='#fca5a5', lw=2))

    # 5. Quantum Wavepacket penetrating the barrier
    # Wave along E_lvl:
    xt_in = np.linspace(-1.35, -0.4, 70)
    xt_bar = np.linspace(-0.4, 0.35, 70)
    xt_out = np.linspace(0.35, 1.45, 90)

    # Incident wave (cyan/blue)
    ax.plot(xt_in, E_lvl + 0.28 * np.sin(20 * xt_in), color='#0284c7', lw=3.2, zorder=7)
    # Tunneling decaying wave inside barrier (dashed purple/cyan)
    decay = np.exp(-2.2 * (xt_bar + 0.4))
    ax.plot(xt_bar, E_lvl + 0.28 * decay * np.sin(20 * xt_bar), color='#7c3aed', lw=3.0, ls='--', zorder=7)
    # Transmitted wave on the other side (emerald)
    ax.plot(xt_out, E_lvl + 0.18 * np.sin(20 * xt_out), color='#059669', lw=3.2, zorder=7)

    # 6. Smooth Curved Tunneling Transition Arrow from Trap -> Optimum
    arc = patches.FancyArrowPatch((trap_x + 0.2, trap_y - 0.2),
                                  (opt_x - 0.2, opt_y + 0.45),
                                  connectionstyle="arc3,rad=-0.16",
                                  arrowstyle="-|>,head_width=8,head_length=11",
                                  color="#0284c7", lw=6.0, zorder=8)
    ax.add_patch(arc)

    # 7. Quantum Tunneling Badge (Above the arrow)
    ax.text(-0.02, 2.4, "⚡ QUANTUM TUNNELING ⚡\nDirect Barrier Penetration",
            color='#0369a1', fontsize=11.5, fontweight='bold', ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#f0f9ff', edgecolor='#0284c7', lw=2.5))

    # 8. Left Well: Local Trap Marker & Badge
    ax.scatter([trap_x], [trap_y], s=350, color='#dc2626', edgecolors='#991b1b', lw=3.5, zorder=8)
    ax.scatter([trap_x], [trap_y], s=750, facecolors='none', edgecolors='#ef4444', lw=2.5, ls='--', alpha=0.9, zorder=7)
    ax.text(trap_x, 1.75, "LOCAL TRAP\n(Deceptive Min)", color='#b91c1c', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#fef2f2', edgecolor='#ef4444', lw=2))

    # 9. Right Well: Global Optimum Marker & Badge
    ax.scatter([opt_x], [opt_y], s=420, color='#059669', edgecolors='#065f46', lw=4, zorder=8)
    ax.scatter([opt_x], [opt_y], s=900, facecolors='none', edgecolors='#10b981', lw=3, ls='--', alpha=0.95, zorder=7)
    ax.text(opt_x, 0.32, "GLOBAL OPTIMUM\n(Optimal Fleet Route)", color='#047857', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#ecfdf5', edgecolor='#10b981', lw=2.2))

    # 10. Barrier Top Label
    ax.text(barrier_x, 4.25, "ENERGY BARRIER", color='#475569', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=7,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#f8fafc', edgecolor='#94a3b8', lw=1.8))

    ax.set_xlim(-2.55, 2.55)
    ax.set_ylim(-0.02, 4.75)
    ax.axis('off')

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    filename = f"icon_quantum_tunneling_{style}.png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=300, transparent=is_trans, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(ARTIFACT_DIR, filename), dpi=300, transparent=is_trans, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Generated: {filename}")


# =============================================================================
# 2. QUANTUM DELTA-WELL - PERFECT PPT ICON
# =============================================================================
def render_delta_well(style="white"):
    is_trans = (style == "trans")
    is_card = (style == "card")
    bg = 'white' if not is_trans else 'none'

    fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=300, facecolor=bg)
    ax.set_facecolor(bg)

    if is_card:
        card = patches.FancyBboxPatch((-4.85, -0.19), 9.7, 1.25,
                                      boxstyle="round,pad=0.08,rounding_size=0.35",
                                      facecolor="#ffffff", edgecolor="#0284c7",
                                      lw=3.0, alpha=1.0, zorder=0)
        ax.add_patch(card)

    x = np.linspace(-4.8, 4.8, 800)
    L = 1.3
    p = 0.0
    psi_sq = (1.0 / L) * np.exp(-2.0 * np.abs(x - p) / L)

    # 1. Main Exponential Wavepacket
    ax.plot(x, psi_sq, color='#0284c7', lw=7.0, zorder=5, solid_capstyle='round')

    # Shaded Gradient Area under the curve
    ax.fill_between(x, psi_sq, color='#38bdf8', alpha=0.30, zorder=2)
    # Darker core fill
    core_mask = np.abs(x) < 1.05
    ax.fill_between(x[core_mask], psi_sq[core_mask], color='#0284c7', alpha=0.28, zorder=3)

    # 2. Central Attractor Line (Clipped neatly inside peak)
    ax.plot([0, 0], [0.0, 0.77], color='#d97706', lw=4.5, ls='--', alpha=0.95, zorder=4)
    ax.scatter([0], [0.77], s=350, color='#d97706', edgecolors='#92400e', lw=3.5, zorder=7)

    # Attractor Target Badge (Top)
    ax.text(0.0, 0.88, "ATTRACTOR BEST (p)", color='#92400e', fontsize=13, fontweight='bold',
            ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#fffbeb', edgecolor='#f59e0b', lw=2.5))

    # 3. Dense Focal Core Exploitation (Center Area)
    ax.annotate("FOCAL EXPLOITATION\n(High-Probability Core)",
                xy=(0.0, 0.44), xytext=(-2.35, 0.58),
                arrowprops=dict(arrowstyle="-|>,head_width=0.7,head_length=0.9", color='#0369a1', lw=4.0),
                color='#0c4a6e', fontsize=12, fontweight='bold', ha='center', va='center', zorder=10,
                bbox=dict(boxstyle='round,pad=0.35', facecolor='#f0f9ff', edgecolor='#0284c7', lw=2.2))

    # 4. Infinite Horizon Tails (Left & Right Outward Arrows)
    ax.annotate("", xy=(-4.5, 0.05), xytext=(-2.0, 0.05),
                arrowprops=dict(arrowstyle="->,head_width=0.8,head_length=1.0", color='#0284c7', lw=5.5), zorder=6)
    ax.annotate("", xy=(4.5, 0.05), xytext=(2.0, 0.05),
                arrowprops=dict(arrowstyle="->,head_width=0.8,head_length=1.0", color='#0284c7', lw=5.5), zorder=6)

    # Infinite Horizon Badge at bottom center
    ax.text(0.0, -0.08, "INFINITE SEARCH HORIZON\n(Explores Entire Solution Space)",
            color='#0369a1', fontsize=12, fontweight='bold', ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#f0f9ff', edgecolor='#0284c7', lw=2.5))

    # Formula Pill Badge in top right corner
    ax.text(2.65, 0.68, r"$|\Psi(x)|^2 = \frac{1}{L}e^{-\frac{2|x-p|}{L}}$",
            color='#0f172a', fontsize=12.5, fontweight='bold', ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#ffffff', edgecolor='#cbd5e1', lw=2))

    ax.set_xlim(-4.9, 4.9)
    ax.set_ylim(-0.19, 1.02)
    ax.axis('off')

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    filename = f"icon_quantum_delta_well_{style}.png"
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=300, transparent=is_trans, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(ARTIFACT_DIR, filename), dpi=300, transparent=is_trans, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Generated: {filename}")


if __name__ == "__main__":
    for style in ["white", "trans", "card"]:
        render_tunneling(style)
        render_delta_well(style)
    print("Done!")
