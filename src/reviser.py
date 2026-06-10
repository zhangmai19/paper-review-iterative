"""
Reviser Module — address review criticisms and produce revised paper.

Supports optional human feedback injection between rounds.
"""

import re
from typing import Dict, Optional

from .prompts.revise import REVISE_PROMPT
from .utils import console, llm_chat


def _extract_latex(text: str) -> Optional[str]:
    """Extract LaTeX content from LLM response."""
    latex_match = re.search(r'```(?:latex|tex)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if latex_match:
        return latex_match.group(1).strip()
    doc_start = text.find('\\documentclass')
    if doc_start >= 0:
        return text[doc_start:].strip()
    begin_doc = text.find('\\begin{document}')
    if begin_doc >= 0:
        return text[begin_doc:].strip()
    return None


def _extract_change_log(text: str) -> str:
    """Extract change log from LLM response."""
    log_match = re.search(r'```change_log\s*\n?(.*?)\n?```', text, re.DOTALL)
    if log_match:
        return log_match.group(1).strip()
    parts = re.split(r'```(?:latex|tex)?\s*\n', text, maxsplit=2)
    if len(parts) >= 2:
        after = parts[-1]
        after = re.sub(r'```', '', after)
        if len(after.strip()) > 20:
            return after.strip()
    return ""


class Reviser:
    """Paper reviser that addresses review criticisms using LLM API."""

    def __init__(self, llm, model: str = "claude-sonnet-4-6"):
        self.llm = llm
        self.model = model

    def revise(
        self,
        paper_content: str,
        review_feedback: str,
        human_feedback: Optional[str] = None,
    ) -> Dict:
        """Revise a paper based on review feedback and optional human input."""
        console.print("\n[bold]✏️  开始修改 — Revising paper...[/bold]")

        human_section = ""
        if human_feedback and human_feedback.strip():
            human_section = f"""
## ⚠️ 人工额外修改要求 (Human Additional Requirements)
以下是人类审稿人额外提出的修改要求，这些要求必须优先处理：

{human_feedback.strip()}

请确保上述人工要求得到充分的重视和落实。
"""
            console.print(f"  [yellow]📝[/yellow] 已注入人工反馈 ({len(human_feedback)} 字)")

        prompt = REVISE_PROMPT.replace(
            "{paper_content}", paper_content
        ).replace(
            "{review_comments}", review_feedback
        ).replace(
            "{human_feedback_section}", human_section
        )

        SYSTEM = "你是一位严谨的学术论文修改专家。请根据审查意见逐一修改论文。你必须输出完整的修改后论文（LaTeX格式），然后附上修改说明。不要遗漏任何部分。"

        try:
            result_text = llm_chat(self.llm, self.model, SYSTEM, prompt,
                                   max_tokens=32768, temperature=0.4)
            revised_text = _extract_latex(result_text)
            change_log = _extract_change_log(result_text)

            if revised_text is None:
                console.print("  [yellow]⚠️[/yellow] 未能解析出LaTeX输出，使用原文")
                revised_text = paper_content
                change_log = "修改失败：未能从API响应中提取修改后的论文。"

            console.print(f"  [green]✓[/green] 修改完成 — 长度: {len(paper_content)} → {len(revised_text)} 字符")

            return {
                "revised_text": revised_text,
                "change_log": change_log,
                "raw_response": result_text,
                "success": revised_text is not None,
            }

        except Exception as e:
            console.print(f"  [red]✗[/red] 修改失败: {e}")
            return {
                "revised_text": paper_content,
                "change_log": f"修改API调用失败: {e}",
                "raw_response": "",
                "success": False,
                "error": str(e),
            }
