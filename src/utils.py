"""Utility functions: logging, Rich console, LLM client, helpers."""

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

    # Set defaults
    config.setdefault("provider", "anthropic")
    config.setdefault("max_rounds", 5)
    config.setdefault("convergence_threshold", 0.3)
    config.setdefault("parallel_reviews", True)
    config.setdefault("output_dir", "output")
    config.setdefault("dimensions", ["format", "language", "ai_free", "math", "logic", "significance"])
    config.setdefault("latex", {})
    config["latex"].setdefault("compiler", "pdflatex")
    config["latex"].setdefault("auto_compile", False)
    config["latex"].setdefault("serve_preview", False)
    config["latex"].setdefault("preview_port", 8765)

    # API key: env var takes precedence
    provider = config.get("provider", "anthropic")
    if provider == "deepseek":
        config.setdefault("model", "deepseek-v4-pro")
        env_key = os.environ.get("DEEPSEEK_API_KEY")
    else:
        config.setdefault("model", "claude-sonnet-4-6")
        env_key = os.environ.get("ANTHROPIC_API_KEY")

    if env_key:
        config["api_key"] = env_key

    return config


def create_llm_client(config: dict):
    """Create an LLM client based on provider config.

    Returns (provider_type, client) tuple.
    - provider_type: "openai" or "anthropic"
    - client: OpenAI or Anthropic client instance

    For DeepSeek uses OpenAI SDK with native endpoint (avoids 10-min timeout
    limitation of DeepSeek's Anthropic-compatible endpoint).
    For Anthropic uses standard Anthropic SDK.
    """
    from anthropic import Anthropic
    from openai import OpenAI

    provider = config.get("provider", "anthropic")
    api_key = config.get("api_key", "")

    if provider == "deepseek":
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        return ("openai", client)
    else:
        client = Anthropic(api_key=api_key)
        return ("anthropic", client)


def llm_chat(llm, model: str, system: str, user_message: str,
             max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """Unified chat call — works with both Anthropic and OpenAI clients.

    Args:
        llm: (provider_type, client) tuple from create_llm_client()
        model: Model name
        system: System prompt
        user_message: User message content
        max_tokens: Max output tokens
        temperature: Sampling temperature

    Returns:
        Text response string
    """
    provider_type, client = llm

    if provider_type == "openai":
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    else:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        for block in response.content:
            if hasattr(block, 'text') and block.type == 'text':
                return block.text
        for block in response.content:
            if hasattr(block, 'text'):
                return getattr(block, 'text', '')
        return ""


def print_banner():
    """Print the tool banner."""
    banner = """
[bold cyan]╔════════════════════════════════════════════════════╗
║  📄  Paper Review-Iterate System  📄               ║
║  论文反复评审修改系统                                ║
╚════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner)


def print_review_summary(scores: dict, review_results: dict, round_num: int):
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

    for dim_key, dim_name in dim_names.items():
        score = scores.get(dim_key, 1.0) if isinstance(scores.get(dim_key), (int, float)) else scores.get(dim_key, {}).get("score", 1.0)
        level = _score_to_level(score)
        r = review_results.get(dim_key, {})
        issues = r.get("key_issues", []) if isinstance(r, dict) else []
        issues_str = "; ".join(issues[:2]) if issues else "—"
        table.add_row(dim_name, f"{score:.2f}", level, issues_str)

    avg = sum(
        v if isinstance(v, (int, float)) else v.get("score", 1.0)
        for v in scores.values()
    ) / max(len(scores), 1)
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
