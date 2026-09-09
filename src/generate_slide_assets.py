"""
generate_slide_assets.py

Generates crisp, high-resolution visual assets for the Technical Approach slide:
1. Bloch Sphere Quantum State Superposition Diagram (outputs/bloch_sphere_vector.png)
2. Road Graph Extraction & Hierarchy Diagram (outputs/road_graph_vector.png)
3. Multi-Vehicle Dispatch Map Crop (outputs/route_dispatch_snippet.png)
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 1. Bloch Sphere Diagram
def generate_bloch_sphere():
    fig = plt.figure(figsize=(4, 4), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')

    # Draw sphere wireframe
    u = np.linspace(0, 2 * np.pi, 50)
    v = np.linspace(0, np.pi, 25)
    x = np.outer(np.cos(u), np.sin(v))
    y = np.outer(np.sin(u), np.sin(v))
    z = np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_wireframe(x, y, z, color='#94a3b8', alpha=0.18, linewidth=0.6)

    # Equator circle
    theta = np.linspace(0, 2 * np.pi, 100)
    ax.plot(np.cos(theta), np.sin(theta), np.zeros_like(theta), color='#64748b', linestyle='--', linewidth=1.0)

    # Coordinate Axes
    ax.plot([-1.3, 1.3], [0, 0], [0, 0], color='#475569', linewidth=1.2)
    ax.plot([0, 0], [-1.3, 1.3], [0, 0], color='#475569', linewidth=1.2)
    ax.plot([0, 0], [0, 0], [-1.3, 1.3], color='#0f172a', linewidth=1.5)

    # State Vector |psi>
    th, ph = np.pi / 3.2, np.pi / 4.0
    vx = np.sin(th) * np.cos(ph)
    vy = np.sin(th) * np.sin(ph)
    vz = np.cos(th)
    ax.quiver(0, 0, 0, vx, vy, vz, color='#2563eb', arrow_length_ratio=0.15, linewidth=2.5)

    # Labels
    ax.text(0, 0, 1.42, r"$|0\rangle$", color='#0f172a', fontsize=12, fontweight='bold', ha='center')
    ax.text(0, 0, -1.48, r"$|1\rangle$", color='#0f172a', fontsize=12, fontweight='bold', ha='center')
    ax.text(vx * 1.15, vy * 1.15, vz * 1.12, r"$|\psi\rangle$", color='#1d4ed8', fontsize=12, fontweight='bold')
    ax.text(1.4, 0, 0, "X", color='#475569', fontsize=9, fontweight='bold')
    ax.text(0, 1.4, 0, "Y", color='#475569', fontsize=9, fontweight='bold')
    ax.text(0.12, 0, 1.25, "Z", color='#0f172a', fontsize=9, fontweight='bold')

    ax.set_axis_off()
    ax.view_init(elev=20, azim=40)
    plt.tight_layout()
    p = os.path.join(OUTPUT_DIR, "bloch_sphere_vector.png")
    plt.savefig(p, dpi=300, facecolor='#ffffff', bbox_inches='tight')
    plt.close()
    print(f"Generated Bloch Sphere: {p}")

# 2. Road Network Graph Vector Snippet
def generate_road_graph_snippet():
    fig, ax = plt.subplots(figsize=(4.5, 3.2), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    ax.set_facecolor('#f8fafc')

    # Synthetic street grid with arterial and residential hierarchy
    np.random.seed(101)
    n_pts = 35
    xs = np.random.uniform(10, 90, n_pts)
    ys = np.random.uniform(10, 90, n_pts)

    # Primary Arterials
    ax.plot([15, 85], [30, 30], color='#f59e0b', lw=3.2, zorder=2, label='Primary Arterial (BPR Impedance)')
    ax.plot([15, 85], [70, 70], color='#f59e0b', lw=3.2, zorder=2)
    ax.plot([35, 35], [15, 85], color='#f59e0b', lw=3.2, zorder=2)
    ax.plot([65, 65], [15, 85], color='#f59e0b', lw=3.2, zorder=2)

    # Residential / Connecting Edges
    for i in range(n_pts):
        for j in range(i + 1, n_pts):
            d = np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if d < 22:
                ax.plot([xs[i], xs[j]], [ys[i], ys[j]], color='#cbd5e1', lw=1.0, zorder=1)

    # Nodes (Intersections)
    ax.scatter(xs, ys, color='#0284c7', s=24, edgecolors='#ffffff', lw=0.8, zorder=3)
    ax.scatter([50], [50], color='#dc2626', s=90, marker='*', zorder=4, label='Central Depot (Hub)')

    ax.set_title("OpenStreetMap Graph Topology (Delhi / Mumbai)", fontsize=9.5, fontweight='bold', color='#1e293b', pad=6)
    ax.legend(loc='lower right', fontsize=6.5, frameon=True, facecolor='#ffffff', edgecolor='#e2e8f0')
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color('#e2e8f0')
    plt.tight_layout()
    p = os.path.join(OUTPUT_DIR, "road_graph_vector.png")
    plt.savefig(p, dpi=300, facecolor='#ffffff', bbox_inches='tight')
    plt.close()
    print(f"Generated Road Graph Snippet: {p}")

if __name__ == "__main__":
    generate_bloch_sphere()
    generate_road_graph_snippet()
