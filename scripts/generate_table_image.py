import os
import matplotlib.pyplot as plt
import matplotlib.patheffects as patheffects

def generate_table_image():
    # Setup data
    columns = ["Algorithm", "Paper Citation", "Distance", "Gap vs Exact", "Runtime"]
    rows = [
        ["CW-1964", "Clarke & Wright (1964)", "33.4 km", "+10.3%", "0.01s"],
        ["Sun QPSO", "Sun et al. (2004/2012)", "67.4 km", "+122.5%", "0.13s"],
        ["Feld QUBO", "Feld et al. (2019)", "50.0 km", "+65.3%", "0.02s"],
        ["Ropke ALNS", "Ropke & Pisinger (2006)", "31.8 km", "+4.9%", "0.28s"],
        ["Exact GLS", "Google OR-Tools", "30.3 km", "+0.0%", "5.80s"],
        ["HQ-GLS (Ours)", "Proposed Quantum HQ-GLS", "30.6 km", "+0.9%", "3.02s"]
    ]
    
    # Create Figure with pure white background
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=300, facecolor='#ffffff')
    ax.axis('off')
    ax.axis('tight')

    # Column widths proportional to content
    col_widths = [0.20, 0.32, 0.16, 0.18, 0.14]
    
    # Table data with headers
    full_table_data = [columns] + rows
    
    table = ax.table(
        cellText=full_table_data,
        colWidths=col_widths,
        cellLoc='center',
        loc='center'
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 2.2)  # Generous cell height and padding
    
    # Style cells
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor('#d1d5db')  # Clean subtle border
        cell.set_linewidth(1.0)
        
        # Header row
        if r == 0:
            cell.set_facecolor('#e8f0fe')  # Soft professional executive blue-tinted slate
            cell.set_text_props(
                color='#0f172a',
                weight='bold',
                fontsize=11.5,
                family='sans-serif'
            )
            cell.set_height(0.14)
        # Highlighted last row (HQ-GLS Ours)
        elif r == len(full_table_data) - 1:
            cell.set_facecolor('#ecfdf5')  # Elegant mint-green accent
            cell.set_text_props(
                color='#047857',  # Rich emerald green
                weight='bold',
                fontsize=11.5,
                family='sans-serif'
            )
            cell.set_linewidth(1.5)
            cell.set_edgecolor('#10b981')
            cell.set_height(0.14)
        # Regular data rows
        else:
            cell.set_facecolor('#ffffff' if r % 2 != 0 else '#f8fafc')  # Subtle zebra striping
            # Exact GLS row can have subtle emphasis
            if "Exact GLS" in rows[r-1][0]:
                cell.set_text_props(color='#1e293b', weight='semibold', fontsize=11, family='sans-serif')
            else:
                cell.set_text_props(color='#334155', fontsize=11, family='sans-serif')
            cell.set_height(0.13)
            
        # Left-align citations for improved readability, keep others centered
        if c == 1:
            cell.set_text_props(ha='center')

    # Output paths
    output_dir = os.path.join(os.path.dirname(__file__), "..", "outputs")
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, "literature_benchmark_table_white.png")
    
    # Artifact directory for embedding in conversation
    artifact_dir = r"C:\Users\HP\.gemini\antigravity-ide\brain\4c35be51-fb24-4fcb-8c38-975f7b77724c"
    artifact_file = os.path.join(artifact_dir, "literature_benchmark_table_white.png")
    
    plt.tight_layout(pad=0.2)
    fig.savefig(out_file, dpi=300, facecolor='#ffffff', bbox_inches='tight')
    if os.path.exists(artifact_dir):
        fig.savefig(artifact_file, dpi=300, facecolor='#ffffff', bbox_inches='tight')
    plt.close(fig)
    print(f"Table successfully saved to:\n  1. {out_file}\n  2. {artifact_file}")

if __name__ == "__main__":
    generate_table_image()
