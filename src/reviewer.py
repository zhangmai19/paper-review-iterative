"""
Reviewer Module — runs multi-dimension academic reviews using Claude API.

Supports parallel and sequential execution across 6 review dimensions:
format, language, ai_free, math, logic, significance.
"""

import json
import re
import concurrent.futures
from typing import Dict, Optional, List

from anthropic import Anthropic

from .prompts.format_review import FORMAT_REVIEW_PROMPT
from .prompts.language_review import LANGUAGE_REVIEW_PROMPT
from .prompts.ai_detection_review import AI_FREE_REVIEW_PROMPT
from .prompts.math_review import MATH_REVIEW_PROMPT
from .prompts.logic_review import LOGIC_REVIEW_PROMPT
from .prompts.significance_review import SIGNIFICANCE_REVIEW_PROMPT
from .humanizer_patterns import analyze_ai_patterns
from .utils import console


REVIEW_PROMPTS = {
    "format":      ("格式 Format", FORMAT_REVIEW_PROMPT),
    "language":    ("用语规范 Language", LANGUAGE_REVIEW_PROMPT),
    "ai_free":     ("无AI特点 AI-Free", AI_FREE_REVIEW_PROMPT),
    "math":        ("数学推导 Math", MATH_REVIEW_PROMPT),
    "logic":       ("行文逻辑 Logic", LOGIC_REVIEW_PROMPT),
    "significance": ("研究意义 Significance", SIGNIFICANCE_REVIEW_PROMPT),
}


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try ```json block first
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try plain JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _run_single_review(
    client: Anthropic,
    model: str,
    dim_key: str,
    paper_content: str,
) -> Dict:
    """Run a single review dimension."""
    dim_name, prompt_template = REVIEW_PROMPTS[dim_key]
    prompt = prompt_template.format(paper_content=paper_content)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.3,  # low temp for consistent, critical reviews
            system="你是一位严格的学术审稿人。请以批判性的眼光仔细审查论文，输出结构化的JSON审查报告。不要客气，要指出真正的问题。",
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text
        parsed = _extract_json(result_text)

        if parsed:
            return {
                "dimension": dim_key,
                "name": dim_name,
                "score": float(parsed.get("score", 0.5)),
                "severity": parsed.get("severity", "medium"),
                "key_issues": parsed.get("key_issues", []),
                "raw_response": result_text,
                "parsed": parsed,
                "error": None,
            }
        else:
            # If JSON parsing failed, treat the whole response as detailed feedback
            return {
                "dimension": dim_key,
                "name": dim_name,
                "score": 0.5,  # default score
                "severity": "medium",
                "key_issues": ["(JSON解析失败，请查看详细反馈)"],
                "raw_response": result_text,
                "parsed": {"detailed_feedback": result_text},
                "error": "JSON parsing failed",
            }

    except Exception as e:
        return {
            "dimension": dim_key,
            "name": dim_name,
            "score": 1.0,
            "severity": "error",
            "key_issues": [f"API调用失败: {str(e)}"],
            "raw_response": "",
            "parsed": {},
            "error": str(e),
        }


class Reviewer:
    """Multi-dimension academic paper reviewer using Claude API."""

    def __init__(self, client: Anthropic, model: str = "claude-sonnet-4-6"):
        self.client = client
        self.model = model

    def review(
        self,
        paper_content: str,
        dimensions: Optional[List[str]] = None,
        parallel: bool = True,
    ) -> Dict:
        """
        Run reviews across specified dimensions.

        Args:
            paper_content: The paper text to review.
            dimensions: List of dimension keys. Default: all 6.
            parallel: Run reviews in parallel.

        Returns:
            Dict with dimension results and aggregate scores.
        """
        if dimensions is None:
            dimensions = list(REVIEW_PROMPTS.keys())

        # Filter to valid dimensions
        dimensions = [d for d in dimensions if d in REVIEW_PROMPTS]

        if not dimensions:
            raise ValueError("No valid review dimensions specified")

        console.print(f"\n[bold]🔍 开始评审 — {len(dimensions)} 个维度[/bold]")
        if parallel and len(dimensions) > 1:
            console.print("[dim]并行模式 — parallel mode[/dim]\n")
        else:
            console.print("[dim]串行模式 — sequential mode[/dim]\n")

        results = {}

        # Also run local AI pattern detection (no API call needed)
        if "ai_free" in dimensions:
            console.print("  [cyan]🔍[/cyan] 运行本地AI特征检测 (local AI pattern scan)...")
            pattern_report = analyze_ai_patterns(paper_content)
            results["_ai_pattern_report"] = pattern_report
            console.print(f"  [dim]   → 检测到 {len(pattern_report.matches)} 个AI特征, "
                         f"本地评分: {pattern_report.total_score:.2f}[/dim]")

        if parallel and len(dimensions) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(dimensions)) as executor:
                futures = {
                    executor.submit(
                        _run_single_review, self.client, self.model, dim, paper_content
                    ): dim
                    for dim in dimensions
                }
                for future in concurrent.futures.as_completed(futures):
                    dim = futures[future]
                    dim_name = REVIEW_PROMPTS[dim][0]
                    try:
                        result = future.result()
                        results[dim] = result
                        score = result.get("score", "?")
                        console.print(f"  [green]✓[/green] {dim_name}: score={score}")
                    except Exception as e:
                        results[dim] = {
                            "dimension": dim, "name": dim_name,
                            "score": 1.0, "severity": "error",
                            "key_issues": [str(e)], "error": str(e),
                        }
                        console.print(f"  [red]✗[/red] {dim_name}: 失败 — {e}")
        else:
            for dim in dimensions:
                dim_name = REVIEW_PROMPTS[dim][0]
                result = _run_single_review(self.client, self.model, dim, paper_content)
                results[dim] = result
                score = result.get("score", "?")
                icon = "✓" if result.get("error") is None else "✗"
                color = "green" if result.get("error") is None else "red"
                console.print(f"  [{color}]{icon}[/{color}] {dim_name}: score={score}")

        return results

    def get_scores(self, results: Dict) -> Dict[str, float]:
        """Extract dimension scores from review results."""
        scores = {}
        for dim in REVIEW_PROMPTS:
            if dim in results:
                scores[dim] = results[dim].get("score", 1.0)
        return scores

    def aggregate_feedback(self, results: Dict) -> str:
        """Aggregate all review feedback into a single document."""
        sections = ["# 📋 综合审查报告 — Comprehensive Review Report\n"]

        for dim_key, (dim_name, _) in REVIEW_PROMPTS.items():
            if dim_key not in results:
                continue
            r = results[dim_key]
            score = r.get("score", "?")
            severity = r.get("severity", "?")

            sections.append(f"\n## {dim_name}\n")
            sections.append(f"**评分 Score**: {score} | **严重程度**: {severity}\n")

            key_issues = r.get("key_issues", [])
            if key_issues:
                sections.append("\n### 关键问题 Key Issues\n")
                for issue in key_issues:
                    sections.append(f"- ⚠️ {issue}")

            parsed = r.get("parsed", {})
            detailed = parsed.get("detailed_feedback", "")
            if detailed:
                sections.append(f"\n### 详细反馈 Detailed Feedback\n{detailed}")

            # Include specific fixes if present
            specific_fixes = parsed.get("specific_fixes", [])
            if specific_fixes:
                sections.append("\n### 具体修改建议 Specific Fixes\n")
                for fix in specific_fixes:
                    loc = fix.get("location", "?")
                    issue = fix.get("issue", fix.get("description", "?"))
                    sug = fix.get("fix", fix.get("suggestion", fix.get("suggested", "?")))
                    sections.append(f"- **{loc}**: {issue} → {sug}")

            # Include AI pattern details
            if dim_key == "ai_free":
                detected = parsed.get("detected_patterns", [])
                if detected:
                    sections.append("\n### 检测到的AI特征 Detected AI Patterns\n")
                    for pat in detected:
                        sections.append(f"- **{pat.get('pattern', '?')}** [{pat.get('category', '?')}]")
                        for inst in pat.get("instances", []):
                            sections.append(f"  - `{inst}`")
                        if pat.get("suggestion"):
                            sections.append(f"  - 建议: {pat['suggestion']}")

            if r.get("error"):
                sections.append(f"\n⚠️ 错误: {r['error']}")

        return '\n'.join(sections)
