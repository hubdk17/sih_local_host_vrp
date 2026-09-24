"""
generate_gls_road_network_icon.py

Generates transparent, ultra-bold, minimal-text icons for:
1. Guided Local Search (GLS) on a Real Road Network:
   - City road grid mesh
   - Central Depot & Delivery Nodes
   - Congested/Trapped bottleneck penalized with penalty lambda * p_e
   - Bold emerald GLS guided bypass route smoothly circumventing congestion
2. Guided Local Search (GLS) Mathematical Penalty Basin:
   - Penalty lambda * p_e lifting the local trap basin to force escape to global optimum

Outputs both transparent PNGs (for seamless PPT placement) and white PNGs.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

BASE_DIR = r"d:\Desktop\QPSO_SIH"
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs", "ppt_icons")
os.makedirs(OUTPUT_DIR, exist_ok=True)
ARTIFACT_DIR = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c"
WEB_ASSETS_DIR = os.path.join(BASE_DIR, "web", "assets", "graphs")

plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['mathtext.fontset'] = 'cm'

# =============================================================================
# 1. GLS ROAD NETWORK DYNAMIC PENALTY & BYPASS ICON
# =============================================================================
def render_gls_road_network_icon(transparent=True):
    suffix = "_trans.png" if transparent else "_white.png"
    bg = 'none' if transparent else 'white'

    fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=300, facecolor=bg)
    ax.set_facecolor(bg)

    # 1. City Road Grid Mesh (Light background network)
    grid_color = '#94a3b8' if transparent else '#cbd5e1'
    grid_alpha = 0.5 if transparent else 0.6

    for y_pos in [-2.0, -1.0, 0.0, 1.0, 2.0]:
        ax.plot([-2.6, 2.6], [y_pos, y_pos], color=grid_color, lw=2.2, ls='-', alpha=grid_alpha, zorder=1)
    for x_pos in [-2.0, -1.0, 0.0, 1.0, 2.0]:
        ax.plot([x_pos, x_pos], [-2.6, 2.6], color=grid_color, lw=2.2, ls='-', alpha=grid_alpha, zorder=1)

    # Diagonal arterial connectors
    ax.plot([-2.0, 0.0], [-1.0, 2.0], color=grid_color, lw=1.6, ls=':', alpha=grid_alpha, zorder=1)
    ax.plot([0.0, 2.0], [2.0, -1.0], color=grid_color, lw=1.6, ls=':', alpha=grid_alpha, zorder=1)
    ax.plot([-2.0, 0.0], [1.0, -2.0], color=grid_color, lw=1.6, ls=':', alpha=grid_alpha, zorder=1)
    ax.plot([0.0, 2.0], [-2.0, 1.0], color=grid_color, lw=1.6, ls=':', alpha=grid_alpha, zorder=1)

    # 2. Key Nodes
    depot_x, depot_y = -1.8, -1.2
    s1_x, s1_y = -1.0, 0.0
    b1_x, b1_y = 0.0, 0.0
    dest_x, dest_y = 1.8, 0.0
    bp1_x, bp1_y = -0.45, 1.65
    bp2_x, bp2_y = 0.95, 1.65

    # 3. PENALIZED TRAFFIC BOTTLENECK (Trapped Legacy Path)
    ax.plot([s1_x, b1_x], [s1_y, b1_y], color='#ef4444', lw=7.0, ls='--', alpha=0.9, zorder=3)
    ax.plot([b1_x, dest_x], [b1_y, dest_y], color='#ef4444', lw=7.0, ls='--', alpha=0.9, zorder=3)

    # Penalty Barrier Node
    ax.scatter([b1_x], [b1_y], s=580, color='#dc2626', edgecolors='#7f1d1d', lw=3.5, zorder=6)
    ax.scatter([b1_x], [b1_y], s=1100, facecolors='none', edgecolors='#ef4444', lw=2.5, ls='--', alpha=0.9, zorder=5)
    ax.scatter([b1_x], [b1_y], s=280, marker='X', color='#ffffff', zorder=7)

    # Penalty Badge (Super clean & bold)
    ax.text(b1_x - 0.2, -0.65, "PENALIZED BOTTLENECK (+λ)", color='#b91c1c', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#fef2f2', edgecolor='#ef4444', lw=2.5))

    # 4. GUIDED LOCAL SEARCH (GLS) OPTIMAL BYPASS ROUTE
    route_x = [depot_x, s1_x, bp1_x, bp2_x, dest_x]
    route_y = [depot_y, s1_y, bp1_y, bp2_y, dest_y]

    from scipy.interpolate import splprep, splev
    tck, u = splprep([route_x, route_y], s=0, k=2)
    unew = np.linspace(0, 1, 300)
    out = splev(unew, tck)
    # Heavy outer stroke
    ax.plot(out[0], out[1], color='#047857', lw=8.5, solid_capstyle='round', zorder=4)
    # Vibrant neon inner line
    ax.plot(out[0], out[1], color='#10b981', lw=4.5, solid_capstyle='round', zorder=5)

    # Directional Arrows on the bypass
    ax.annotate("", xy=(0.35, 1.70), xytext=(-0.1, 1.70),
                arrowprops=dict(arrowstyle="-|>,head_width=0.85,head_length=1.1", color='#065f46', lw=4.5), zorder=8)
    ax.annotate("", xy=(1.55, 0.7), xytext=(1.25, 1.25),
                arrowprops=dict(arrowstyle="-|>,head_width=0.85,head_length=1.1", color='#065f46', lw=4.5), zorder=8)

    # Guided Bypass Badge (Top Center)
    ax.text(0.25, 2.30, "⚡ GUIDED BYPASS (GLS) ⚡",
            color='#065f46', fontsize=13, fontweight='bold', ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#ecfdf5', edgecolor='#10b981', lw=2.8))

    # 5. Delivery Nodes & Depot Markers
    # Depot Marker
    ax.scatter([depot_x], [depot_y], s=580, marker='H', color='#d97706', edgecolors='#78350f', lw=3.5, zorder=7)
    ax.text(depot_x, depot_y - 0.55, "DEPOT", color='#92400e', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#fffbeb', edgecolor='#f59e0b', lw=2.2))

    # Stop 1 Marker
    ax.scatter([s1_x], [s1_y], s=380, color='#0284c7', edgecolors='#0369a1', lw=3, zorder=7)
    ax.text(s1_x - 0.45, s1_y + 0.35, "STOP 1", color='#0369a1', fontsize=11, fontweight='bold', ha='center', zorder=9)

    # Destination Marker
    ax.scatter([dest_x], [dest_y], s=580, color='#059669', edgecolors='#065f46', lw=3.5, zorder=7)
    ax.scatter([dest_x], [dest_y], s=1150, facecolors='none', edgecolors='#10b981', lw=3, ls='--', alpha=0.9, zorder=6)
    ax.text(dest_x, dest_y - 0.60, "DESTINATION", color='#047857', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#ecfdf5', edgecolor='#10b981', lw=2.2))

    ax.set_xlim(-2.55, 2.55)
    ax.set_ylim(-2.45, 2.65)
    ax.axis('off')

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    filename = f"icon_gls_road_network{suffix}"
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(ARTIFACT_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(WEB_ASSETS_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Generated: {filename}")


# =============================================================================
# 2. GLS PENALTY LANDSCAPE & BASIN LIFT ICON
# =============================================================================
def render_gls_landscape_icon(transparent=True):
    suffix = "_trans.png" if transparent else "_white.png"
    bg = 'none' if transparent else 'white'

    fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=300, facecolor=bg)
    ax.set_facecolor(bg)

    x = np.linspace(-3.2, 3.2, 700)
    f_orig = 0.45 * (x**4 - 3.8 * x**2 + 0.6 * x) + 2.8
    penalty = 2.4 * np.exp(-((x + 1.45)**2) / 0.45)
    h_aug = f_orig + penalty

    # 1. Original Objective (Dashed Grey Line)
    ax.plot(x, f_orig, color='#64748b', lw=4.5, ls='--', alpha=0.85, zorder=2)
    ax.text(-2.1, 1.1, "Original f(s)\n(Trapped)", color='#64748b', fontsize=11, fontweight='bold', ha='center', zorder=5)

    # 2. Augmented Objective (Bold Orange / Amber Curve)
    ax.plot(x, h_aug, color='#ea580c', lw=7.0, solid_capstyle='round', zorder=4)

    # 3. Dynamic Penalty Upward Lift Arrow
    ax.annotate("", xy=(-1.45, 3.8), xytext=(-1.45, 1.8),
                arrowprops=dict(arrowstyle="->,head_width=0.8,head_length=1.0", color='#dc2626', lw=5.5), zorder=6)
    ax.scatter([-1.45], [1.7], s=350, color='#dc2626', edgecolors='#991b1b', lw=3, zorder=7)

    # Penalty Lift Badge
    ax.text(-1.45, 4.45, "PENALTY LIFT (+λ)",
            color='#9a3412', fontsize=12, fontweight='bold', ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff7ed', edgecolor='#ea580c', lw=2.2))

    # 4. Forced Escape Transition to Global Minimum
    opt_x, opt_y = 1.42, 0.75
    ax.annotate("", xy=(opt_x - 0.2, opt_y + 0.45), xytext=(-0.7, 3.0),
                arrowprops=dict(arrowstyle="-|>,head_width=0.9,head_length=1.2",
                                color='#059669', lw=6.5, connectionstyle="arc3,rad=-0.18"), zorder=8)

    # Forced Escape Badge
    ax.text(0.35, 2.5, "⚡ FORCED ESCAPE ⚡",
            color='#047857', fontsize=12.5, fontweight='bold', ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#ecfdf5', edgecolor='#10b981', lw=2.5))

    # 5. Global Optimum Point
    ax.scatter([opt_x], [opt_y], s=450, color='#059669', edgecolors='#065f46', lw=4, zorder=8)
    ax.scatter([opt_x], [opt_y], s=1000, facecolors='none', edgecolors='#10b981', lw=3, ls='--', alpha=0.95, zorder=7)
    ax.text(opt_x, 0.05, "OPTIMAL BYPASS", color='#047857', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=9,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#ecfdf5', edgecolor='#10b981', lw=2))

    ax.set_xlim(-2.8, 2.8)
    ax.set_ylim(-0.35, 4.95)
    ax.axis('off')

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    filename = f"icon_gls_landscape{suffix}"
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(ARTIFACT_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(WEB_ASSETS_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Generated: {filename}")


if __name__ == "__main__":
    render_gls_road_network_icon(transparent=True)
    render_gls_road_network_icon(transparent=False)

    render_gls_landscape_icon(transparent=True)
    render_gls_landscape_icon(transparent=False)
    print("Done generating updated GLS icons!")
