"""
generate_road_network_rough_diagram.py

Generates a stylized, high-contrast, schematic "Road Network Rough Diagram" icon
with transparent background (and white background), specifically designed for
PowerPoint slides as a clean, non-text-heavy mini image.

Features:
- Primary ring road & arterial highways (bold dark strokes)
- Secondary urban street grid & neighborhood connections
- Central logistics distribution depot hub (gold/amber)
- Multi-stop delivery nodes (cyan/emerald customer markers)
- Optimized multi-vehicle route paths flowing through the road network
- Minimal text, ultra-bold lines (5-8px) that stay razor-sharp at mini sizes
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

def render_road_network_rough_diagram(transparent=True):
    suffix = "_trans.png" if transparent else "_white.png"
    bg = 'none' if transparent else 'white'

    fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=300, facecolor=bg)
    ax.set_facecolor(bg)

    # 1. Base Secondary Street Grid (Soft grey network)
    grid_color = '#64748b' if transparent else '#94a3b8'
    grid_alpha = 0.4 if transparent else 0.45

    # Secondary rectangular street blocks
    for y in np.linspace(-2.2, 2.2, 9):
        ax.plot([-2.4, 2.4], [y, y], color=grid_color, lw=1.8, ls='-', alpha=grid_alpha, zorder=1)
    for x in np.linspace(-2.2, 2.2, 9):
        ax.plot([x, x], [-2.4, 2.4], color=grid_color, lw=1.8, ls='-', alpha=grid_alpha, zorder=1)

    # 2. Major Arterial Ring Road (Outer Highway Belt)
    theta = np.linspace(0, 2*np.pi, 200)
    # Organic circular ring road
    r_ring = 1.95 + 0.12 * np.sin(4 * theta)
    ring_x = r_ring * np.cos(theta)
    ring_y = r_ring * np.sin(theta)
    # Double stroke for highway look: dark base + bold road
    ax.plot(ring_x, ring_y, color='#0f172a' if not transparent else '#1e293b', lw=7.0, zorder=2)
    ax.plot(ring_x, ring_y, color='#475569' if not transparent else '#64748b', lw=3.0, ls='--', alpha=0.8, zorder=3)

    # 3. Major Cross-City Arterial Expressways (Curved Highways)
    hway_x1 = np.linspace(-2.4, 2.4, 150)
    hway_y1 = 0.35 * np.sin(1.2 * hway_x1)
    ax.plot(hway_x1, hway_y1, color='#0f172a' if not transparent else '#1e293b', lw=6.5, zorder=2)

    hway_y2 = np.linspace(-2.4, 2.4, 150)
    hway_x2 = 0.4 * np.sin(1.2 * hway_y2)
    ax.plot(hway_x2, hway_y2, color='#0f172a' if not transparent else '#1e293b', lw=6.5, zorder=2)

    # Diagonal arterial bypasses
    ax.plot([-1.8, 1.8], [-1.8, 1.8], color='#334155', lw=3.8, alpha=0.6, zorder=2)
    ax.plot([-1.8, 1.8], [1.8, -1.8], color='#334155', lw=3.8, alpha=0.6, zorder=2)

    # 4. Central Logistics Depot Hub
    depot_x, depot_y = -0.45, -0.45
    ax.scatter([depot_x], [depot_y], s=750, marker='H', color='#d97706', edgecolors='#78350f', lw=4, zorder=8)
    ax.scatter([depot_x], [depot_y], s=1300, facecolors='none', edgecolors='#f59e0b', lw=2.5, ls='--', alpha=0.85, zorder=7)
    # Minimal bold badge
    ax.text(depot_x - 0.55, depot_y - 0.45, "HUB DEPOT", color='#92400e', fontsize=12, fontweight='bold',
            ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#fffbeb', edgecolor='#f59e0b', lw=2.2))

    # 5. Delivery Stops (Customer Nodes) Scattered on Road Network
    stops = [
        (-1.6, 1.1),
        (-0.8, 1.7),
        (0.6, 1.6),
        (1.6, 1.2),
        (1.7, -0.6),
        (1.1, -1.6),
        (-0.5, -1.8),
        (-1.7, -0.8)
    ]
    for sx, sy in stops:
        ax.scatter([sx], [sy], s=380, color='#0284c7', edgecolors='#0369a1', lw=3, zorder=7)

    # 6. Active Vehicle Route Trajectories (Emerald Green & Cyan Routes)
    # Route 1: North loop
    r1_nodes = [
        (depot_x, depot_y),
        (-1.1, 0.0),
        (-1.6, 1.1),
        (-0.8, 1.7),
        (0.6, 1.6),
        (1.6, 1.2),
        (0.5, 0.2),
        (depot_x, depot_y)
    ]
    rx1, ry1 = zip(*r1_nodes)
    from scipy.interpolate import splprep, splev
    tck1, u1 = splprep([rx1, ry1], s=0, k=2)
    unew1 = np.linspace(0, 1, 200)
    out1 = splev(unew1, tck1)
    ax.plot(out1[0], out1[1], color='#059669', lw=6.5, solid_capstyle='round', zorder=5)
    ax.plot(out1[0], out1[1], color='#34d399', lw=3.0, solid_capstyle='round', zorder=6)

    # Route 2: South loop
    r2_nodes = [
        (depot_x, depot_y),
        (0.0, -0.8),
        (1.1, -1.6),
        (1.7, -0.6),
        (1.1, 0.0),
        (-0.5, -1.8),
        (-1.7, -0.8),
        (depot_x, depot_y)
    ]
    rx2, ry2 = zip(*r2_nodes)
    tck2, u2 = splprep([rx2, ry2], s=0, k=2)
    unew2 = np.linspace(0, 1, 200)
    out2 = splev(unew2, tck2)
    ax.plot(out2[0], out2[1], color='#0284c7', lw=5.5, ls='--', solid_capstyle='round', zorder=5)

    # Route Direction Arrows
    ax.annotate("", xy=(-0.1, 1.68), xytext=(-0.4, 1.68),
                arrowprops=dict(arrowstyle="-|>,head_width=0.7,head_length=0.9", color='#047857', lw=3.5), zorder=7)
    ax.annotate("", xy=(1.5, -1.1), xytext=(1.3, -1.4),
                arrowprops=dict(arrowstyle="-|>,head_width=0.7,head_length=0.9", color='#0369a1', lw=3.5), zorder=7)

    # Top Badge: Minimal & Bold
    ax.text(0.0, 2.30, "URBAN ROAD NETWORK GRID",
            color='#065f46', fontsize=12.5, fontweight='bold', ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#ecfdf5', edgecolor='#10b981', lw=2.2))

    # Bottom Delivery Grid Badge: Minimal & Bold
    ax.text(0.65, -2.25, "DELIVERY STOPS & CORRIDORS",
            color='#0369a1', fontsize=11.5, fontweight='bold', ha='center', va='center', zorder=10,
            bbox=dict(boxstyle='round,pad=0.25', facecolor='#f0f9ff', edgecolor='#0284c7', lw=2.0))

    ax.set_xlim(-2.55, 2.55)
    ax.set_ylim(-2.55, 2.55)
    ax.axis('off')

    plt.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    filename = f"icon_road_network_rough{suffix}"
    out_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out_path, dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(ARTIFACT_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    fig.savefig(os.path.join(WEB_ASSETS_DIR, filename), dpi=300, transparent=transparent, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    print(f"Generated: {filename}")


if __name__ == "__main__":
    render_road_network_rough_diagram(transparent=True)
    render_road_network_rough_diagram(transparent=False)
    print("Done generating Road Network Rough Diagram icons!")
