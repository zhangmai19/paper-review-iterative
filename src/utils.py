"""Utility functions: logging, Rich console, helpers."""

import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout

console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file, with env var fallback for API key."""
    import yaml

    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # API key from env var takes precedence
    if os.environ.get("ANTHROPIC_API_KEY"):
        config["api_key"] = os.environ["ANTHROPIC_API_KEY"]

    # Set defaults
    config.setdefault("model", "claude-sonnet-4-6")
    config.setdefault("max_rounds", 5)
    config.setdefault("convergence_threshold", 0.3)
    config.setdefault("parallel_reviews", True)
    config.setdefault("output_dir", "output")
    config.setdefault("dimensions", ["format", "language", "ai_free", "math", "logic", "significance"])
    config.setdefault("latex", {})
    config["latex"].setdefault("compiler", "pdflatex")
    config["latex"].setdefault("auto_compile", True)
    config["latex"].setdefault("serve_preview", True)
    config["latex"].setdefault("preview_port", 8765)

    return config


def print_banner():
    """Print the tool banner."""
    banner = """
[bold cyan]╔════════════════════════════════════════════════════╗
║  📄  Paper Review-Iterate System  📄               ║
║  论文反复评审修改系统                                ║
╚════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner)


def print_review_summary(scores: dict, round_num: int):
    """Print a formatted review summary table."""
    dim_names = {
        "format": "格式 Format",
        "language": "用语规范 Language",
        "ai_free": "无AI特点 AI-Free",
        "math": "数学推导 Math",
        "logic": "行文逻辑 Logic",
        "significance": "研究意义 Significance",
    }

    table = Table(title=f"📋 第 {round_num} 轮评审报告 — Review Round {round_num}")
    table.add_column("维度 Dimension", style="cyan", width=24)
    table.add_column("评分 Score", style="yellow", width=12)
    table.add_column("等级", style="magenta", width=12)
    table.add_column("关键问题", style="red", width=40)

    for dim, info in scores.items():
        score = info.get("score", 1.0)
        level = _score_to_level(score)
        issues = info.get("key_issues", [])
        issues_str = "; ".join(issues[:2]) if issues else "—"
        table.add_row(dim_names.get(dim, dim), f"{score:.2f}", level, issues_str)

    avg = sum(v.get("score", 1.0) for v in scores.values()) / max(len(scores), 1)
    table.add_row("", "", "", "")
    table.add_row("[bold]综合平均[/bold]", f"[bold]{avg:.2f}[/bold]", _score_to_level(avg), "")

    console.print(table)
    return avg


def _score_to_level(score: float) -> str:
    """Convert numeric score to Chinese grade level."""
    if score <= 0.2:
        return "[green]优秀[/green]"
    elif score <= 0.4:
        return "[blue]良好[/blue]"
    elif score <= 0.6:
        return "[yellow]一般[/yellow]"
    elif score <= 0.8:
        return "[red]较差[/red]"
    else:
        return "[bold red]很差[/bold red]"


def print_diff_summary(diff_text: str, round_num: int):
    """Print a diff summary."""
    from rich.syntax import Syntax
    console.print(f"\n[bold]📝 第 {round_num} 轮修改差异 — Revision Diff[/bold]")
    if diff_text.strip():
        console.print(Syntax(diff_text[:3000], "diff", theme="monokai"))
    else:
        console.print("[dim]无显著差异[/dim]")


def section_progress():
    """Create a Rich progress context for sections."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )
