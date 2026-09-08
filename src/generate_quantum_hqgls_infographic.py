import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.patches as patches

def generate_infographic():
    # Set up styling
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['mathtext.fontset'] = 'cm'

    # Dimensions: 16:10 or 16:9 aspect ratio, high DPI
    fig = plt.figure(figsize=(15, 9.5), dpi=300, facecolor='#0B111E')
    gs = GridSpec(2, 2, figure=fig, hspace=0.32, wspace=0.24,
                  left=0.06, right=0.96, top=0.88, bottom=0.07)

    # Global Title
    fig.suptitle("QUANTUM HQ-GLS ENGINE: 4 CORE MATHEMATICAL PILLARS",
                 fontsize=18, fontweight='bold', color='#FFFFFF', y=0.975, ha='center')
    fig.text(0.5, 0.935,
             "Probabilistic Wavepacket Sampling  •  Transverse Tunneling  •  Dynamic Penalty Memory  •  BPR Urban Congestion",
             fontsize=11.5, color='#94A3B8', ha='center')

    # Color Palette
    BG_CARD = '#111A2E'
    BORDER_CARD = '#1E293B'
    CYAN = '#00E5FF'
    BLUE = '#38BDF8'
    ORANGE = '#F59E0B'
    EMERALD = '#10B981'
    RED = '#EF4444'
    PURPLE = '#A855F7'
    TEXT_MUTED = '#94A3B8'
    TEXT_WHITE = '#F8FAFC'

    # =========================================================================
    # PANEL 1: Quantum Delta-Well State Representation
    # =========================================================================
    ax1 = fig.add_subplot(gs[0, 0], facecolor=BG_CARD)
    ax1.set_title("1. Quantum Delta-Well State Representation", fontsize=13, fontweight='bold', color=CYAN, pad=12, loc='left')

    x1 = np.linspace(-6, 6, 1000)
    L = 1.6
    p = 0.0
    psi_sq = (1.0 / L) * np.exp(-2.0 * np.abs(x1 - p) / L)

    # Plot wavepacket probability density
    ax1.plot(x1, psi_sq, color=CYAN, lw=2.5, label=r"$|\Psi(x)|^2 = \frac{1}{L}\exp\left(-\frac{2|x-p|}{L}\right)$")
    ax1.fill_between(x1, psi_sq, color=CYAN, alpha=0.18)

    # Delta well representation
    ax1.axvline(0, color=ORANGE, lw=1.5, ls='--', alpha=0.7)
    ax1.annotate(r"Attractor Point $p$ (Global Best)", xy=(0, 0.62), xytext=(0.8, 0.58),
                 arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.5),
                 color=ORANGE, fontsize=10, fontweight='bold')

    # Infinite search tail annotations
    ax1.annotate("Dense Focal Exploitation\n(High probability core)", xy=(0, 0.35), xytext=(-3.8, 0.42),
                 arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.2),
                 color=TEXT_WHITE, fontsize=9.5)

    ax1.annotate("Infinite Search Horizon\n(Non-zero probability tails\nexplore entire city)", xy=(4.2, 0.03), xytext=(2.2, 0.18),
                 arrowprops=dict(arrowstyle="->", color=BLUE, lw=1.2),
                 color='#CBD5E1', fontsize=9.5)

    # Equation box
    ax1.text(0.04, 0.20, r"$|\Psi(x)|^2 = \frac{1}{L}\exp\left(-\frac{2|x-p|}{L}\right)$" + "\n" + r"$x = p \pm \frac{L}{2}\ln(1/u)$",
             transform=ax1.transAxes, fontsize=10.5, color=CYAN,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#0B111E', edgecolor=BORDER_CARD, lw=1.2))

    ax1.set_xlabel("Solution Space Coordinate (x)", color=TEXT_MUTED, fontsize=10)
    ax1.set_ylabel(r"Probability Density $|\Psi(x)|^2$", color=TEXT_MUTED, fontsize=10)
    ax1.tick_params(colors=TEXT_MUTED, labelsize=8.5)
    ax1.set_ylim(-0.02, 0.72)
    ax1.set_xlim(-6, 6)
    ax1.grid(True, color='#1E293B', ls=':', alpha=0.6)
    for spine in ax1.spines.values():
        spine.set_edgecolor(BORDER_CARD)

    # =========================================================================
    # PANEL 2: Transverse-Field Quantum Tunneling Operator
    # =========================================================================
    ax2 = fig.add_subplot(gs[0, 1], facecolor=BG_CARD)
    ax2.set_title("2. Transverse-Field Quantum Tunneling Operator", fontsize=13, fontweight='bold', color=PURPLE, pad=12, loc='left')

    x2 = np.linspace(-3.2, 3.2, 1000)
    # Double-well potential: V(x) = a x^4 - b x^2 + c x
    V = 0.5 * (x2**4 - 4.5 * x2**2 + 0.8 * x2) + 3.0

    ax2.plot(x2, V, color='#64748B', lw=2.5, label="Combinatorial Cost Landscape V(x)")

    # Energy level line
    E_level = 3.6
    ax2.axhline(E_level, color='#475569', ls=':', lw=1.2)
    ax2.text(2.3, E_level + 0.15, "Energy Level E", color='#94A3B8', fontsize=8.5)

    # Classical trapped trajectory (red bouncing arrow)
    ax2.annotate("", xy=(-1.0, 3.6), xytext=(-2.2, 3.6),
                 arrowprops=dict(arrowstyle="->", color=RED, lw=2.5))
    ax2.text(-2.4, 4.3, "Classical Trajectory:\nBLOCKED by Barrier (E < V)", color=RED, fontsize=9, fontweight='bold')

    # Quantum tunneling wavepacket (oscillating through barrier)
    xt_left = np.linspace(-2.2, -0.8, 150)
    xt_bar = np.linspace(-0.8, 0.8, 150)
    xt_right = np.linspace(0.8, 2.2, 150)

    # Sinusoidal wave on left
    psi_left = E_level + 0.45 * np.sin(14 * xt_left)
    # Decaying wave in barrier
    psi_bar = E_level + 0.45 * np.exp(-2.2 * (xt_bar + 0.8)) * np.sin(14 * xt_bar)
    # Transmitted wave on right
    psi_right = E_level + 0.18 * np.sin(14 * xt_right)

    ax2.plot(xt_left, psi_left, color=PURPLE, lw=2)
    ax2.plot(xt_bar, psi_bar, color=PURPLE, lw=1.8, ls='--')
    ax2.plot(xt_right, psi_right, color=EMERALD, lw=2)

    # Big Tunneling Arrow right through the peak
    ax2.annotate("", xy=(1.5, 2.0), xytext=(-1.5, 3.0),
                 arrowprops=dict(arrowstyle="-|>", color=CYAN, lw=3, mutation_scale=18))
    ax2.text(-0.4, 5.7, "Quantum Tunneling:\n" + r"$P_{tunnel} \propto \exp(-2\int \sqrt{2m(V-E)}\,dx)$",
             color=CYAN, fontsize=9.5, fontweight='bold', ha='center',
             bbox=dict(boxstyle='round,pad=0.4', facecolor='#0B111E', edgecolor=BORDER_CARD))

    # Minima markers
    ax2.plot([-1.55], [1.7], 'o', color=RED, ms=8)
    ax2.text(-1.55, 0.9, "Deceptive Local\nMinimum (Trap)", color=RED, fontsize=9, ha='center')

    ax2.plot([1.45], [0.5], 'o', color=EMERALD, ms=9)
    ax2.text(1.45, -0.3, "Global Minimum\n(Optimal Fleet Route)", color=EMERALD, fontsize=9, ha='center', fontweight='bold')

    ax2.set_xlabel("Combinatorial Configuration Space", color=TEXT_MUTED, fontsize=10)
    ax2.set_ylabel("Cost / Energy Landscape", color=TEXT_MUTED, fontsize=10)
    ax2.tick_params(colors=TEXT_MUTED, labelsize=8.5)
    ax2.set_ylim(-0.8, 7.2)
    ax2.grid(True, color='#1E293B', ls=':', alpha=0.6)
    for spine in ax2.spines.values():
        spine.set_edgecolor(BORDER_CARD)

    # =========================================================================
    # PANEL 3: Guided Local Search (GLS) Memory & Dynamic Penalties
    # =========================================================================
    ax3 = fig.add_subplot(gs[1, 0], facecolor=BG_CARD)
    ax3.set_title("3. Guided Local Search (GLS) Dynamic Penalties", fontsize=13, fontweight='bold', color=ORANGE, pad=12, loc='left')

    x3 = np.linspace(-4, 4, 1000)
    # Original landscape with deep local trap at x = -1.5
    f_orig = 0.5 * x3**2 - 1.8 * np.exp(-((x3 + 1.5)**2) / 0.4) - 2.5 * np.exp(-((x3 - 1.8)**2) / 0.6) + 3.0
    # Penalty function placed right at the trapped basin
    penalty = 2.6 * np.exp(-((x3 + 1.5)**2) / 0.35)
    # Augmented landscape h(s) = f(s) + penalty
    h_aug = f_orig + penalty

    ax3.plot(x3, f_orig, color='#64748B', lw=2, ls='--', label=r"Original Objective $f(s)$ (Trapped)")
    ax3.plot(x3, h_aug, color=ORANGE, lw=2.8, label=r"Augmented Objective $h(s) = f(s) + \lambda \sum p_e I_e$")

    # Arrow showing basin being lifted
    ax3.annotate("", xy=(-1.5, 3.8), xytext=(-1.5, 1.6),
                 arrowprops=dict(arrowstyle="->", color=ORANGE, lw=2.5))
    ax3.text(-1.5, 4.2, r"Penalty $\lambda p_e$ Lifts Trap", color=ORANGE, fontsize=9.5, fontweight='bold', ha='center')

    # Arrow showing escape to global minimum
    ax3.annotate("", xy=(1.8, 1.2), xytext=(-0.8, 3.2),
                 arrowprops=dict(arrowstyle="-|>", color=EMERALD, lw=2.5, connectionstyle="arc3,rad=-0.2"))
    ax3.text(0.4, 2.7, "Forced Escape to\nUndiscovered Bypass", color=EMERALD, fontsize=9, fontweight='bold')

    # Equation annotation box
    ax3.text(0.04, 0.12, r"$h(s) = f(s) + \lambda \sum_{e} p_e \cdot I_e(s)$" + "\n" + r"$util(s, e) = \frac{c_e}{1 + p_e}$",
             transform=ax3.transAxes, fontsize=10, color=ORANGE,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#0B111E', edgecolor=BORDER_CARD, lw=1.2))

    ax3.set_xlabel("Route Neighborhood State (s)", color=TEXT_MUTED, fontsize=10)
    ax3.set_ylabel("Augmented Evaluation Cost", color=TEXT_MUTED, fontsize=10)
    ax3.tick_params(colors=TEXT_MUTED, labelsize=8.5)
    ax3.set_ylim(0, 6.2)
    ax3.set_xlim(-4, 4)
    ax3.grid(True, color='#1E293B', ls=':', alpha=0.6)
    ax3.legend(facecolor='#0B111E', edgecolor=BORDER_CARD, labelcolor=TEXT_WHITE, fontsize=8.5, loc='upper right')
    for spine in ax3.spines.values():
        spine.set_edgecolor(BORDER_CARD)

    # =========================================================================
    # PANEL 4: Dynamic Urban Congestion Coupling (BPR Model)
    # =========================================================================
    ax4 = fig.add_subplot(gs[1, 1], facecolor=BG_CARD)
    ax4.set_title("4. Dynamic Urban Congestion Coupling (BPR Model)", fontsize=13, fontweight='bold', color=EMERALD, pad=12, loc='left')

    vc = np.linspace(0, 1.5, 1000)
    alpha = 0.15
    beta = 4.0
    # BPR curve: t_e / t_e^0 = 1 + alpha * (v/c)^beta
    time_ratio = 1.0 + alpha * (vc**beta)

    ax4.plot(vc, time_ratio, color=EMERALD, lw=3, label=r"BPR: $t_e = t_e^0 [1 + \alpha(v/c)^\beta]$")

    # Fill zones
    # Free-flow: vc < 0.8
    ax4.axvspan(0, 0.8, color=EMERALD, alpha=0.08)
    ax4.text(0.4, 1.12, "Free Flow Regime\n(Normal Speeds)", color=EMERALD, fontsize=9, ha='center')

    # Capacity threshold: vc = 1.0
    ax4.axvline(1.0, color=ORANGE, ls='--', lw=1.5)
    ax4.text(1.0, 1.55, "Design Capacity\n(v/c = 1.0)", color=ORANGE, fontsize=8.5, ha='center')

    # Breakdown regime: vc > 1.0
    ax4.axvspan(1.0, 1.5, color=RED, alpha=0.12)
    ax4.text(1.28, 2.1, "Severe CBD Gridlock\n(Exponential Delay)", color=RED, fontsize=9.5, fontweight='bold', ha='center')

    # Highlight point at v/c = 1.3
    vc_pt = 1.3
    tr_pt = 1.0 + alpha * (vc_pt**beta)
    ax4.plot([vc_pt], [tr_pt], 'o', color=RED, ms=8)
    ax4.annotate(f"+{((tr_pt-1)*100):.0f}% Travel Time Surge!\n(Triggers Quantum Reroute)",
                 xy=(vc_pt, tr_pt), xytext=(0.75, 2.4),
                 arrowprops=dict(arrowstyle="->", color=RED, lw=1.5),
                 color=RED, fontsize=9.5, fontweight='bold')

    # Formula Box
    ax4.text(0.04, 0.72, r"$t_e = t_e^0 \left[1 + 0.15 \left(\frac{v}{c}\right)^4\right]$" + "\nCoupled to Live OSM Graph",
             transform=ax4.transAxes, fontsize=10, color=EMERALD,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#0B111E', edgecolor=BORDER_CARD, lw=1.2))

    ax4.set_xlabel("Volume-to-Capacity Ratio (v / c)", color=TEXT_MUTED, fontsize=10)
    ax4.set_ylabel(r"Travel Time Multiplier ($t_e / t_e^0$)", color=TEXT_MUTED, fontsize=10)
    ax4.tick_params(colors=TEXT_MUTED, labelsize=8.5)
    ax4.set_xlim(0, 1.5)
    ax4.set_ylim(0.9, 2.8)
    ax4.grid(True, color='#1E293B', ls=':', alpha=0.6)
    ax4.legend(facecolor='#0B111E', edgecolor=BORDER_CARD, labelcolor=TEXT_WHITE, fontsize=8.5, loc='lower right')
    for spine in ax4.spines.values():
        spine.set_edgecolor(BORDER_CARD)

    # Save to outputs and artifacts
    out_path = r"d:\Desktop\QPSO_SIH\outputs\quantum_hqgls_mathematical_pillars_infographic.png"
    plt.savefig(out_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"Infographic saved to {out_path}")

    artifact_path = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c\quantum_hqgls_mathematical_pillars_infographic.png"
    plt.savefig(artifact_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    print(f"Artifact copy saved to {artifact_path}")
    plt.close()

if __name__ == "__main__":
    generate_infographic()
