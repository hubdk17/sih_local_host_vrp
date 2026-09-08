import os
from PIL import Image, ImageDraw, ImageFont

def render_slide():
    # 16:9 Widescreen Full HD
    W, H = 1920, 1080
    im = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(im)

    # Color Palette matching SIH Template
    C_HEADER_NAVY = (31, 73, 125)
    C_FOOTER_BLUE = (22, 124, 197)
    C_DARK_TEXT = (25, 30, 36)
    C_MUTED_TEXT = (90, 100, 110)
    C_CARD_BG = (248, 250, 252)
    C_CARD_BORDER = (215, 222, 232)
    C_ACCENT_BLUE = (2, 132, 199)
    C_ACCENT_GREEN = (21, 128, 61)
    C_ACCENT_PURPLE = (126, 34, 206)

    def get_font(name, size, bold=False):
        font_paths = [
            f"C:/Windows/Fonts/{name}{'bd' if bold else ''}.ttf",
            f"C:/Windows/Fonts/{name}.ttf",
            f"C:/Windows/Fonts/{'arialbd' if bold else 'arial'}.ttf"
        ]
        for p in font_paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    f_title = get_font("times", 34, bold=True)
    f_subtitle = get_font("calibri", 18)
    f_oval = get_font("arial", 17, bold=True)
    f_oval_sub = get_font("arial", 16)
    f_main_hdr = get_font("arial", 28, bold=True)
    f_sec_hdr = get_font("calibri", 21, bold=True)
    f_body = get_font("calibri", 17)
    f_body_bold = get_font("calibri", 17, bold=True)
    f_kpi_val = get_font("arial", 21, bold=True)
    f_kpi_sub = get_font("calibri", 14)
    f_card_hdr = get_font("calibri", 17, bold=True)
    f_badge = get_font("arial", 13, bold=True)
    f_footer = get_font("arial", 16)

    # 1. Top Left Team Oval
    draw.ellipse([(45, 25), (255, 115)], outline=(142, 104, 179), width=2, fill=(250, 248, 255))
    draw.text((150, 48), "Your Team", fill=(60, 40, 90), font=f_oval_sub, anchor="mm")
    draw.text((150, 82), "Name / ID", fill=(60, 40, 90), font=f_oval, anchor="mm")

    # 2. Top Center Title
    draw.text((960, 48), "QUANTUM-INSPIRED HYBRID VRP ENGINE (Q-HQGLS)", fill=(17, 24, 39), font=f_title, anchor="mm")
    draw.text((960, 88), "Dynamic Congestion-Aware Multi-Depot Fleet Optimization for Indian Megacities", fill=(75, 85, 99), font=f_subtitle, anchor="mm")

    # 3. Top Right SIH Logo
    logo_path = r"d:\Desktop\QPSO_SIH\outputs\sih_logo_extracted.png"
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((260, 100), Image.Resampling.LANCZOS)
        im.paste(logo, (1630, 22), mask=logo)

    # 4. Main Section Header with 4-point Diamond vector
    # Draw vector diamond at (55, 157)
    dx, dy = 58, 157
    d_size = 10
    draw.polygon([(dx, dy - d_size), (dx + d_size, dy), (dx, dy + d_size), (dx - d_size, dy)], fill=C_HEADER_NAVY)
    
    hdr_text = " Proposed Solution (Describe your Idea/Solution/Prototype)"
    draw.text((75, 140), hdr_text, fill=C_HEADER_NAVY, font=f_main_hdr)
    # Underline
    draw.line([(50, 184), (1870, 184)], fill=C_HEADER_NAVY, width=3)

    # -------------------------------------------------------------
    # LEFT COLUMN: STRUCTURED TECHNICAL SECTIONS (X: 50 to 920)
    # -------------------------------------------------------------
    y = 202
    draw.text((50, y), "•  Detailed Explanation of the Proposed Solution:", fill=C_HEADER_NAVY, font=f_sec_hdr)
    y += 33
    b1_lines = [
        "–  Quantum-Inspired Hybrid Engine (Q-HQGLS): Synergizes Quantum-Behaved Particle",
        "   Swarm wavefunctions |Ψ|² with Guided Local Search (GLS) and 2-opt* topological edge exchange.",
        "–  Dynamic Traffic Impedance: Real OSM graph embedding with BPR travel-time cost formulation:",
        "   te = te⁰ (1 + α (v/c)β), actively penalizing peak-hour CBD bottlenecks in real-time."
    ]
    for line in b1_lines:
        draw.text((50, y), line, fill=C_DARK_TEXT, font=f_body)
        y += 24

    # Section 2
    y += 12
    draw.text((50, y), "•  How It Addresses the Problem:", fill=C_HEADER_NAVY, font=f_sec_hdr)
    y += 33
    b2_lines = [
        "–  Eradicates Gridlock Vulnerability: Actively re-allocates delivery clusters across multiple regional",
        "   depots based on live traffic congestion rather than static Euclidean straight lines.",
        "–  Tames Combinatorial Explosion: Scales to 1,000+ customer nodes in < 1.2s where classical",
        "   exact MIP formulations collapse due to O(n!) exponential catastrophe."
    ]
    for line in b2_lines:
        draw.text((50, y), line, fill=C_DARK_TEXT, font=f_body)
        y += 24

    # Section 3
    y += 12
    draw.text((50, y), "•  Innovation and Uniqueness of the Solution:", fill=C_HEADER_NAVY, font=f_sec_hdr)
    y += 33
    b3_lines = [
        "–  Quantum Tunneling Operator: Non-local state transitions penetrate high-cost fitness ridges,",
        "   preventing premature entrapment in deceptive local minima that permanently trap classical GAs.",
        "–  Turing Morphogenesis & Banburismus: Activator-inhibitor demand PDEs + Bayesian Deciban",
        "   edge pruning eliminates up to 34% of combinatorial search paths in < 10 ms.",
        "–  Statistically Certified Optimality: 95% CI [+0.43%, +2.10%] matching Google OR-Tools quality",
        "   with up to 8.6x execution speedup across N=30 paired Monte Carlo trials."
    ]
    for line in b3_lines:
        draw.text((50, y), line, fill=C_DARK_TEXT, font=f_body)
        y += 24

    # 4 KPI Badges
    kpi_y = 860
    kpi_w = 205
    kpi_gap = 14
    kpis = [
        ("8.6x Speedup", "vs Google OR-Tools", C_ACCENT_BLUE),
        ("[+0.4%, +2.1%]", "95% CI Proximity Gap", C_ACCENT_GREEN),
        ("-24.55% Cost", "Peak Congestion Trim", C_HEADER_NAVY),
        ("< 1.2s Latency", "At 1,000+ Nodes", C_ACCENT_PURPLE)
    ]
    for i, (kval, ksub, kcol) in enumerate(kpis):
        kx = 50 + i * (kpi_w + kpi_gap)
        draw.rounded_rectangle([(kx, kpi_y), (kx + kpi_w, kpi_y + 98)], radius=8, fill=C_CARD_BG, outline=C_CARD_BORDER, width=1)
        draw.text((kx + kpi_w // 2, kpi_y + 34), kval, fill=kcol, font=f_kpi_val, anchor="mm")
        draw.text((kx + kpi_w // 2, kpi_y + 70), ksub, fill=C_MUTED_TEXT, font=f_kpi_sub, anchor="mm")

    # -------------------------------------------------------------
    # RIGHT COLUMN: VISUAL BENCHMARK CARDS (X: 950 to 1870)
    # -------------------------------------------------------------
    rw = 920
    rx = 950

    # Card 1: Statistical Certificate
    c1_y = 202
    c1_h = 368
    draw.rounded_rectangle([(rx, c1_y), (rx + rw, c1_y + c1_h)], radius=8, fill=(255, 255, 255), outline=C_CARD_BORDER, width=1)
    draw.text((rx + 16, c1_y + 22), "EMPIRICAL VALIDATION: Statistical Proximity Certificate (N=30 vs Google OR-Tools)", fill=C_HEADER_NAVY, font=f_card_hdr)
    # Badge
    draw.rounded_rectangle([(rx + rw - 150, c1_y + 12), (rx + rw - 16, c1_y + 36)], radius=10, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    draw.text((rx + rw - 83, c1_y + 24), "Certified 95% CI", fill=(4, 120, 87), font=f_badge, anchor="mm")

    stat_path = r"d:\Desktop\QPSO_SIH\outputs\statistical_rigour\statistical_proximity_certificate.png"
    if os.path.exists(stat_path):
        s_img = Image.open(stat_path).convert("RGB")
        s_img.thumbnail((rw - 20, c1_h - 48), Image.Resampling.LANCZOS)
        px = rx + (rw - s_img.width) // 2
        py = c1_y + 44 + (c1_h - 48 - s_img.height) // 2
        im.paste(s_img, (px, py))

    # Card 2: Bengaluru Multi-Depot Congestion Route Map
    c2_y = 588
    c2_h = 372
    draw.rounded_rectangle([(rx, c2_y), (rx + rw, c2_y + c2_h)], radius=8, fill=(255, 255, 255), outline=C_CARD_BORDER, width=1)
    draw.text((rx + 16, c2_y + 22), "REAL-WORLD DEPLOYMENT: Multi-Depot Congestion Routing (Bengaluru OSM)", fill=C_HEADER_NAVY, font=f_card_hdr)
    # Badge
    draw.rounded_rectangle([(rx + rw - 145, c2_y + 12), (rx + rw - 16, c2_y + 36)], radius=10, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    draw.text((rx + rw - 80, c2_y + 24), "Live BPR Model", fill=(29, 78, 216), font=f_badge, anchor="mm")

    route_path = r"d:\Desktop\QPSO_SIH\outputs\national_benchmark\multidepot_congestion\bengaluru\bengaluru_multidepot_congestion_100_cust_routes.png"
    if os.path.exists(route_path):
        r_img = Image.open(route_path).convert("RGB")
        r_img.thumbnail((rw - 20, c2_h - 48), Image.Resampling.LANCZOS)
        px = rx + (rw - r_img.width) // 2
        py = c2_y + 44 + (c2_h - 48 - r_img.height) // 2
        im.paste(r_img, (px, py))

    # -------------------------------------------------------------
    # FOOTER BAR
    # -------------------------------------------------------------
    draw.rectangle([(0, 1025), (W, 1080)], fill=C_FOOTER_BLUE)
    draw.text((50, 1052), "@SIH Idea submission- Template", fill=(255, 255, 255), font=f_footer, anchor="lm")
    draw.text((1870, 1052), "2", fill=(255, 255, 255), font=f_footer, anchor="rm")

    # Save
    out_png = r"d:\Desktop\QPSO_SIH\outputs\SIH_2026_Proposed_Solution_Main_Slide.png"
    im.save(out_png, quality=95)
    artifact_png = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c\SIH_2026_Proposed_Solution_Main_Slide.png"
    im.save(artifact_png, quality=95)
    print("Slide re-rendered successfully with crisp vector symbols and maximized graphics.")

if __name__ == "__main__":
    render_slide()
