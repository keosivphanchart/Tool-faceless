"""Renders the two charts embedded in the PDF report as PNG bytes.
Matplotlib runs headless (Agg backend) since this is a server process."""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEVERITY_COLORS = {"healthy": "#2e9e5b", "warning": "#e0a72e", "critical": "#d64545"}


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def health_distribution_chart(summary: dict) -> bytes:
    labels = ["Healthy", "Warning", "Critical"]
    values = [summary["healthy"], summary["warning"], summary["critical"]]
    colors = [SEVERITY_COLORS["healthy"], SEVERITY_COLORS["warning"], SEVERITY_COLORS["critical"]]

    fig, ax = plt.subplots(figsize=(4, 4))
    nonzero = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
    if not nonzero:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.axis("off")
    else:
        ax.pie(
            [v for _, v, _ in nonzero],
            labels=[f"{l} ({v})" for l, v, _ in nonzero],
            colors=[c for _, _, c in nonzero],
            autopct="%1.0f%%",
            startangle=90,
        )
    ax.set_title("Server health distribution")
    return _fig_to_png(fig)


def resource_usage_chart(servers: list[dict]) -> bytes:
    names = [s["name"] for s in servers]
    cpu = [s["cpu"] or 0 for s in servers]
    ram = [s["ram"] or 0 for s in servers]
    disk = [s["disk"] or 0 for s in servers]

    x = range(len(names))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(6, len(names) * 1.2), 4))
    ax.bar([i - width for i in x], cpu, width, label="CPU %", color="#4478c9")
    ax.bar(list(x), ram, width, label="RAM %", color="#8a5fd6")
    ax.bar([i + width for i in x], disk, width, label="Disk %", color="#d68a5f")
    ax.axhline(85, color="#d64545", linestyle="--", linewidth=1, label="Critical threshold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("% used")
    ax.set_ylim(0, 100)
    ax.set_title("Resource usage per server")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _fig_to_png(fig)
