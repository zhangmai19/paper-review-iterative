#!/usr/bin/env python3
"""
Paper Review-Iterate System — 论文反复评审修改系统

Iteratively reviews and revises academic papers using Claude API.
Six review dimensions × N rounds → converged high-quality paper.

Usage:
    python main.py paper.tex
    python main.py paper.tex --max-rounds 3 --model claude-opus-4-8
    python main.py paper.tex --dimensions format,logic,ai_free
"""

import sys
import os
from pathlib import Path

import click
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from src.utils import load_config, print_banner, console
from src.orchestrator import Orchestrator
from src.latex_preview import LatexPreviewer, get_available_compiler, compile_latex


def _get_human_feedback(round_num: int, review_info: dict) -> str | None:
    """Interactive callback: prompt user for additional feedback between rounds."""
    console.print()
    console.print(Panel(
        f"[bold yellow]📝 人工反馈阶段 — Human Feedback[/bold yellow]\n\n"
        f"当前轮次: 第 {round_num} 轮\n"
        f"平均评分: {review_info.get('average', 'N/A'):.2f}\n\n"
        f"你可以输入额外的修改要求（如：\"请重点修改引言部分的逻辑\"、\"公式(3)的推导有问题\"），\n"
        f"或直接按 Enter 跳过，让系统自动根据审查意见修改。\n\n"
        f"[dim]输入 'quit' 停止迭代，输入 'skip' 跳过人工反馈[/dim]",
        title="Human Feedback",
        border_style="yellow",
    ))

    try:
        feedback = Prompt.ask(
            "[bold yellow]✏️  人工修改要求[/bold yellow]",
            default="",
        )
        if feedback.strip().lower() == "quit":
            console.print("[red]用户请求停止[/red]")
            raise KeyboardInterrupt
        if feedback.strip().lower() == "skip":
            return None
        return feedback.strip() if feedback.strip() else None
    except (EOFError, KeyboardInterrupt):
        raise


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("paper", type=click.Path(exists=True), required=True)
@click.option(
    "--max-rounds", "-n", default=None, type=int,
    help="最大迭代轮数 (默认: 5)",
)
@click.option(
    "--model", "-m", default=None, type=str,
    help="Claude 模型 (默认: claude-sonnet-4-6)",
)
@click.option(
    "--dimensions", "-d", default=None, type=str,
    help="启用的审查维度，逗号分隔: format,language,ai_free,math,logic,significance (默认: 全部)",
)
@click.option(
    "--output-dir", "-o", default=None, type=str,
    help="输出目录 (默认: output/)",
)
@click.option(
    "--convergence", "-c", default=None, type=float,
    help="收敛阈值: 平均分低于此值停止 (默认: 0.3)",
)
@click.option(
    "--no-parallel", "serial", is_flag=True, default=False,
    help="串行模式（默认并行评审）",
)
@click.option(
    "--no-human", "no_human", is_flag=True, default=False,
    help="跳过人工反馈环节（全自动模式）",
)
@click.option(
    "--human-feedback-file", "-f", default=None, type=click.Path(exists=True),
    help="从文件读取人工反馈（每行一条，用 '---' 分隔不同轮次）",
)
@click.option(
    "--no-compile", "no_compile", is_flag=True, default=False,
    help="不编译LaTeX（跳过PDF生成）",
)
@click.option(
    "--no-preview", "no_preview", is_flag=True, default=False,
    help="不启动PDF预览服务",
)
@click.option(
    "--preview-port", "-p", default=8765, type=int,
    help="PDF预览服务端口 (默认: 8765)",
)
@click.option(
    "--compiler", default="pdflatex", type=str,
    help="LaTeX编译器: pdflatex, xelatex, lualatex (默认: pdflatex)",
)
@click.option(
    "--config", "config_path", default="config.yaml", type=click.Path(exists=True),
    help="配置文件路径 (默认: config.yaml)",
)
@click.option(
    "--api-key", default=None, type=str,
    help="Anthropic API Key (也可通过 ANTHROPIC_API_KEY 环境变量设置)",
)
@click.option(
    "--verbose", "-v", is_flag=True, default=False,
    help="详细输出模式",
)
def main(
    paper: str,
    max_rounds: int | None,
    model: str | None,
    dimensions: str | None,
    output_dir: str | None,
    convergence: float | None,
    serial: bool,
    no_human: bool,
    human_feedback_file: str | None,
    no_compile: bool,
    no_preview: bool,
    preview_port: int,
    compiler: str,
    config_path: str,
    api_key: str | None,
    verbose: bool,
):
    """
    论文反复评审修改系统 — Paper Review-Iterate System

    PAPER: 输入的论文文件路径（.tex 或 .md 格式）
    """

    # --- Load config ---
    if os.path.exists(config_path):
        config = load_config(config_path)
    else:
        config = load_config("nonexistent")  # use defaults

    # Override with CLI args
    final_model = model or config.get("model", "claude-sonnet-4-6")
    final_max_rounds = max_rounds or config.get("max_rounds", 5)
    final_threshold = convergence or config.get("convergence_threshold", 0.3)
    final_parallel = not serial
    final_output_dir = output_dir or config.get("output_dir", "output")
    final_compiler = compiler or config.get("latex", {}).get("compiler", "pdflatex")
    final_auto_compile = not no_compile
    final_serve_preview = not no_preview

    # Parse dimensions
    if dimensions:
        final_dimensions = [d.strip() for d in dimensions.split(",")]
    else:
        final_dimensions = config.get("dimensions", None)

    # API key resolution
    final_api_key = api_key or config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not final_api_key:
        console.print("\n[bold red]❌ 错误: 未设置 Anthropic API Key[/bold red]")
        console.print("\n请通过以下方式之一设置:")
        console.print("  1. 环境变量: export ANTHROPIC_API_KEY='sk-ant-...'")
        console.print("  2. 配置文件: 在 config.yaml 中设置 api_key")
        console.print("  3. 命令行参数: --api-key 'sk-ant-...'")
        console.print("\n获取 API Key: https://console.anthropic.com/")
        sys.exit(1)

    # --- Validate paper ---
    paper_path = Path(paper).resolve()
    if not paper_path.exists():
        console.print(f"[bold red]❌ 论文文件不存在: {paper}[/bold red]")
        sys.exit(1)

    if paper_path.suffix.lower() not in [".tex", ".md", ".markdown", ".txt"]:
        console.print(f"[yellow]⚠️ 未知文件格式: {paper_path.suffix}，将尝试按文本处理[/yellow]")

    # --- LaTeX pre-check ---
    if paper_path.suffix.lower() == ".tex" and final_auto_compile:
        available = get_available_compiler()
        if not available:
            console.print("[yellow]⚠️ LaTeX编译器未安装。PDF编译将被禁用。[/yellow]")
            console.print("[dim]安装: sudo apt install texlive-latex-base texlive-latex-extra[/dim]")
            final_auto_compile = False
        else:
            console.print(f"[dim]LaTeX编译器: {available}[/dim]")

    # --- Load human feedback from file ---
    human_feedbacks = {}
    if human_feedback_file:
        with open(human_feedback_file, "r", encoding="utf-8") as f:
            content = f.read()
        rounds = content.split("---")
        for i, fb in enumerate(rounds, 1):
            if fb.strip():
                human_feedbacks[i] = fb.strip()
        console.print(f"[dim]从 {human_feedback_file} 加载了 {len(human_feedbacks)} 条人工反馈[/dim]")

    def feedback_callback(round_num: int, review_info: dict) -> str | None:
        """Resolve human feedback from file or interactive prompt."""
        # File-based feedback takes precedence
        if round_num in human_feedbacks:
            return human_feedbacks[round_num]
        # Interactive mode
        if not no_human:
            return _get_human_feedback(round_num, review_info)
        return None

    # --- Setup LaTeX previewer ---
    previewer = LatexPreviewer(
        compiler=final_compiler,
        auto_compile=final_auto_compile,
        serve_preview=final_serve_preview,
        preview_port=preview_port,
    )

    # --- Initialize client ---
    client = Anthropic(api_key=final_api_key)

    # --- Run orchestrator ---
    print_banner()

    try:
        orchestrator = Orchestrator(
            client=client,
            model=final_model,
            max_rounds=final_max_rounds,
            convergence_threshold=final_threshold,
            parallel_reviews=final_parallel,
            dimensions=final_dimensions,
            output_dir=final_output_dir,
            latex_config={
                "compiler": final_compiler,
                "auto_compile": final_auto_compile,
                "serve_preview": final_serve_preview,
                "preview_port": preview_port,
            },
            human_feedback_callback=feedback_callback,
            post_revision_callback=previewer.on_revision_complete,
        )

        summary = orchestrator.run(str(paper_path))

        # Final compilation of the last version
        if final_auto_compile:
            # Find the last revised file
            output_base = Path(final_output_dir) / paper_path.stem
            last_revised = output_base / f"R{orchestrator.converged_at_round if orchestrator.converged else final_max_rounds:02d}_revised.tex"
            if last_revised.exists():
                console.print(f"\n[bold]🔧 最终编译: {last_revised.name}...[/bold]")
                success, log, pdf_path = compile_latex(
                    str(last_revised),
                    compiler=final_compiler,
                    output_dir=str(output_base),
                    runs=2,
                )
                if success:
                    console.print(f"  [green]✓[/green] 最终PDF: {pdf_path}")
                else:
                    console.print(f"  [yellow]⚠️[/yellow] 最终编译失败")

        console.print("\n[bold green]✅ 完成![/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ 用户中断[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ 错误: {e}[/bold red]")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
