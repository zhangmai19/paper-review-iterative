"""
LaTeX Compiler & Live Preview — compiles .tex to PDF and serves via HTTP.

Supports pdflatex, xelatex, lualatex compilers.
Launches a lightweight HTTP server for real-time PDF preview in browser.
"""

import os
import subprocess
import shutil
import threading
import http.server
import socketserver
from pathlib import Path
from typing import Optional, Tuple

from .utils import console


def find_compiler(compiler: str = "pdflatex") -> Optional[str]:
    """Find the LaTeX compiler binary."""
    path = shutil.which(compiler)
    return path


def get_available_compiler() -> Optional[str]:
    """Find the first available LaTeX compiler."""
    for c in ["pdflatex", "xelatex", "lualatex"]:
        if shutil.which(c):
            return c
    return None


def compile_latex(
    tex_path: str,
    compiler: str = "pdflatex",
    output_dir: Optional[str] = None,
    runs: int = 2,
) -> Tuple[bool, str, Optional[str]]:
    """
    Compile a .tex file to PDF.

    Args:
        tex_path: Path to .tex file.
        compiler: LaTeX compiler to use.
        output_dir: Output directory for auxiliary files. Default: same as .tex.
        runs: Number of compilation runs (for TOC, references, etc.).

    Returns:
        (success, log_output, pdf_path)
    """
    if not os.path.exists(tex_path):
        return False, f"File not found: {tex_path}", None

    tex_dir = os.path.dirname(os.path.abspath(tex_path))
    tex_name = os.path.basename(tex_path)

    if output_dir is None:
        output_dir = tex_dir

    os.makedirs(output_dir, exist_ok=True)

    compiler_path = find_compiler(compiler)
    if not compiler_path:
        # Try to find any available compiler
        alt = get_available_compiler()
        if alt:
            console.print(f"  [yellow]⚠️[/yellow] {compiler} 未找到，使用 {alt}")
            compiler = alt
            compiler_path = find_compiler(alt)
        else:
            return False, f"LaTeX编译器未找到。请安装 texlive: sudo apt install texlive-latex-base texlive-latex-extra", None

    log_output = ""
    pdf_path = os.path.join(output_dir, os.path.splitext(tex_name)[0] + ".pdf")

    for run in range(runs):
        try:
            result = subprocess.run(
                [compiler_path,
                 "-interaction=nonstopmode",
                 "-output-directory", output_dir,
                 tex_name],
                cwd=tex_dir,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
            )
            log_output += result.stdout + "\n" + result.stderr

            if result.returncode != 0:
                # Check if it's a non-fatal error
                if "Fatal error" in result.stderr or "Fatal error" in result.stdout:
                    return False, log_output, None

        except subprocess.TimeoutExpired:
            return False, f"编译超时 (>60s)\n{log_output}", None
        except Exception as e:
            return False, f"编译异常: {e}\n{log_output}", None

    if os.path.exists(pdf_path):
        return True, log_output, pdf_path
    else:
        return False, f"PDF未生成\n{log_output}", None


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Quiet HTTP handler for serving PDF files."""
    def log_message(self, format, *args):
        pass  # suppress logs


def start_preview_server(
    directory: str,
    port: int = 8765,
    background: bool = True,
) -> Optional[threading.Thread]:
    """
    Start an HTTP server to serve the output directory (for PDF preview).

    Args:
        directory: Directory to serve.
        port: Port number.
        background: Run in background thread.

    Returns:
        Thread if background=True, else None.
    """
    os.makedirs(directory, exist_ok=True)

    # Change to directory so handler serves from there
    original_dir = os.getcwd()

    class Handler(QuietHTTPHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    try:
        # Try to bind; if port is in use, try next
        max_tries = 5
        for offset in range(max_tries):
            try:
                httpd = socketserver.TCPServer(("", port + offset), Handler)
                actual_port = port + offset
                break
            except OSError:
                if offset == max_tries - 1:
                    raise
                continue

        if background:
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            console.print(f"  [green]🌐[/green] PDF预览服务: http://localhost:{actual_port}/ (后台运行)")
            return thread
        else:
            console.print(f"  [green]🌐[/green] PDF预览服务: http://localhost:{actual_port}/")
            console.print("  [dim]按 Ctrl+C 停止[/dim]")
            httpd.serve_forever()
            return None

    except OSError as e:
        console.print(f"  [yellow]⚠️[/yellow] 无法启动预览服务器: {e}")
        return None


class LatexPreviewer:
    """Manages LaTeX compilation and optional live preview."""

    def __init__(
        self,
        compiler: str = "pdflatex",
        auto_compile: bool = True,
        serve_preview: bool = True,
        preview_port: int = 8765,
    ):
        self.compiler = compiler
        self.auto_compile = auto_compile
        self.serve_preview = serve_preview
        self.preview_port = preview_port
        self.server_thread = None
        self.preview_started = False

    def start_preview(self, output_dir: str):
        """Start the preview server if not already running."""
        if self.serve_preview and not self.preview_started:
            self.server_thread = start_preview_server(
                output_dir, self.preview_port, background=True
            )
            self.preview_started = True

    def compile_and_show(self, tex_path: str, output_dir: str) -> Optional[str]:
        """
        Compile a .tex file and return the PDF path.

        Used as the post_revision_callback in Orchestrator.
        """
        if not self.auto_compile:
            return None

        console.print(f"\n[bold]🔧 编译LaTeX...[/bold]")
        success, log, pdf_path = compile_latex(
            tex_path,
            compiler=self.compiler,
            output_dir=output_dir,
        )

        if success:
            console.print(f"  [green]✓[/green] PDF编译成功: {pdf_path}")
            return pdf_path
        else:
            # Show abbreviated error
            error_lines = [l for l in log.split('\n') if l.startswith('!')]
            if error_lines:
                console.print(f"  [red]✗[/red] 编译失败: {error_lines[0][:100]}")
            else:
                console.print(f"  [red]✗[/red] 编译失败 (查看 .log 文件获取详情)")
            return None

    def on_revision_complete(self, tex_path: str, round_num: int):
        """Callback for post-revision: compile and show preview."""
        output_dir = os.path.dirname(os.path.abspath(tex_path))

        # Start preview server on first call
        if not self.preview_started:
            self.start_preview(output_dir)

        # Compile
        self.compile_and_show(tex_path, output_dir)
