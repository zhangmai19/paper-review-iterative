"""
Orchestrator — controls the review→revise iteration loop with convergence detection.

Manages:
- Iteration rounds with configurable max rounds
- Convergence detection (stop when avg score < threshold)
- Saving all artifacts per round
- Human feedback injection between rounds
- Live LaTeX compilation after each revision
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Callable

from anthropic import Anthropic

from .paper_manager import PaperManager, Paper, IterationRecord
from .reviewer import Reviewer
from .reviser import Reviser
from .utils import console, print_banner, print_review_summary, print_diff_summary


class Orchestrator:
    """Controls the iterative review-revise pipeline."""

    def __init__(
        self,
        llm,                  # (provider_type, client) tuple
        model: str = "claude-sonnet-4-6",
        max_rounds: int = 5,
        convergence_threshold: float = 0.3,
        parallel_reviews: bool = True,
        dimensions: Optional[List[str]] = None,
        output_dir: str = "output",
        latex_config: Optional[Dict] = None,
        human_feedback_callback: Optional[Callable[[int, Dict], Optional[str]]] = None,
        post_revision_callback: Optional[Callable[[str, int], None]] = None,
    ):
        self.llm = llm
        self.model = model
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.parallel_reviews = parallel_reviews
        self.dimensions = dimensions
        self.output_dir = output_dir
        self.latex_config = latex_config or {}
        self.human_feedback_callback = human_feedback_callback
        self.post_revision_callback = post_revision_callback

        self.reviewer = Reviewer(llm, model)
        self.reviser = Reviser(llm, model)

        # Tracking
        self.rounds: List[Dict] = []
        self.iteration_records: List[IterationRecord] = []
        self.converged = False
        self.converged_at_round = -1

    def run(self, paper_path: str) -> Dict:
        """Run the full iteration pipeline and return summary."""
        print_banner()
        console.print(f"[bold]📄 输入论文:[/bold] {paper_path}")
        console.print(f"[bold]🤖 模型:[/bold] {self.model}")
        console.print(f"[bold]🔄 最大轮数:[/bold] {self.max_rounds}")
        console.print(f"[bold]🎯 收敛阈值:[/bold] {self.convergence_threshold}")
        console.print(f"[bold]📐 维度:[/bold] {', '.join(self.dimensions or ['all'])}")
        console.print(f"[bold]📂 输出目录:[/bold] {self.output_dir}\n")

        # Ensure output directory
        base_output = Path(self.output_dir) / Path(paper_path).stem
        os.makedirs(base_output, exist_ok=True)

        # Load paper
        paper = PaperManager.load(paper_path)
        current_text = paper.raw_text

        console.print(f"[dim]论文格式: {paper.format} | 长度: {len(current_text)} 字符[/dim]")
        if paper.sections:
            console.print(f"[dim]检测到 {len(paper.sections)} 个章节[/dim]")

        # Save original copy
        PaperManager.save(paper, str(base_output / "00_original.tex"))

        # Iteration loop
        for round_num in range(1, self.max_rounds + 1):
            console.rule(f"[bold cyan]🔄 第 {round_num}/{self.max_rounds} 轮[/bold cyan]")

            # === REVIEW PHASE ===
            console.print(f"\n[bold]📖 评审阶段 — Review Phase[/bold]")
            review_results = self.reviewer.review(
                current_text,
                dimensions=self.dimensions,
                parallel=self.parallel_reviews,
            )

            # Check for local AI pattern report
            local_ai_report = review_results.pop("_ai_pattern_report", None)

            scores = self.reviewer.get_scores(review_results)

            # If we have a local AI detection score, blend it in
            if local_ai_report and "ai_free" in scores:
                local_score = local_ai_report.total_score
                api_score = scores["ai_free"]
                # Blend: 40% local + 60% API
                scores["ai_free"] = 0.4 * local_score + 0.6 * api_score
                review_results["ai_free"]["local_pattern_score"] = local_score

            avg = print_review_summary(scores, review_results, round_num)

            # Aggregate feedback
            feedback = self.reviewer.aggregate_feedback(review_results)

            # Inject local AI pattern details
            if local_ai_report and local_ai_report.matches:
                feedback += f"\n\n## 📊 本地AI特征扫描结果\n"
                feedback += f"检测到 **{len(local_ai_report.matches)}** 个AI写作特征\n"
                feedback += f"Tier1密度: {local_ai_report.tier1_density:.1f}/100词 | "
                feedback += f"Tier2密度: {local_ai_report.tier2_density:.1f}/100词\n"
                feedback += f"句长变异系数: {local_ai_report.sentence_length_cv:.2f} | "
                feedback += f"词汇多样性(TTR): {local_ai_report.type_token_ratio:.2f}\n\n"
                # Show top 10 most severe matches
                top_matches = sorted(local_ai_report.matches, key=lambda m: -m.severity)[:10]
                for m in top_matches:
                    feedback += f"- **{m.pattern_name}** (L{m.line_number}, sev={m.severity:.1f}): `{m.match_text[:60]}`\n"
                    feedback += f"  → {m.suggestion}\n"

            # Save review report
            review_path = str(base_output / f"R{round_num:02d}_review.md")
            with open(review_path, "w", encoding="utf-8") as f:
                f.write(feedback)
            console.print(f"  [dim]💾 审查报告已保存: {review_path}[/dim]")

            # Save scores JSON
            scores_path = str(base_output / f"R{round_num:02d}_scores.json")
            with open(scores_path, "w", encoding="utf-8") as f:
                json.dump({"round": round_num, "scores": scores, "average": avg,
                           "dimension_details": {d: {"score": r.get("score"), "key_issues": r.get("key_issues", [])}
                            for d, r in review_results.items()}}, f, ensure_ascii=False, indent=2)

            # === HUMAN FEEDBACK PHASE ===
            human_feedback = None
            if self.human_feedback_callback:
                human_feedback = self.human_feedback_callback(round_num, {"scores": scores, "average": avg})
                if human_feedback:
                    console.print(f"  [yellow]📝[/yellow] 人工反馈: {len(human_feedback)} 字")

            # === REVISE PHASE ===
            console.print(f"\n[bold]✏️  修改阶段 — Revision Phase[/bold]")
            revision_result = self.reviser.revise(
                current_text,
                feedback,
                human_feedback=human_feedback,
            )

            if not revision_result["success"]:
                console.print("[red]修改失败，停止迭代[/red]")
                break

            revised_text = revision_result["revised_text"]
            change_log = revision_result["change_log"]

            # Save revised paper
            revised_path = str(base_output / f"R{round_num:02d}_revised.tex")
            PaperManager.save_revision(paper, revised_text, revised_path)
            console.print(f"  [dim]💾 修改后论文: {revised_path}[/dim]")

            # Save change log
            changelog_path = str(base_output / f"R{round_num:02d}_changelog.md")
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write(f"# 修改说明 — Round {round_num}\n\n{change_log}")
            console.print(f"  [dim]💾 修改说明: {changelog_path}[/dim]")

            # Compute and save diff
            revised_paper = PaperManager.load(revised_path)
            diff_text = PaperManager.diff(paper, revised_paper)
            diff_path = str(base_output / f"R{round_num:02d}_diff.patch")
            with open(diff_path, "w", encoding="utf-8") as f:
                f.write(diff_text)
            print_diff_summary(diff_text, round_num)

            # Record iteration
            record = PaperManager.create_iteration_record(
                round_num, scores, diff_text, human_feedback
            )
            self.iteration_records.append(record)
            self.rounds.append({
                "round": round_num,
                "scores": scores,
                "avg_score": avg,
                "human_feedback": human_feedback,
                "change_log": change_log,
            })

            # Update for next round
            paper = revised_paper
            current_text = revised_text

            # Post-revision callback (e.g., LaTeX compile)
            if self.post_revision_callback:
                self.post_revision_callback(revised_path, round_num)

            # === CONVERGENCE CHECK ===
            if avg <= self.convergence_threshold:
                self.converged = True
                self.converged_at_round = round_num
                console.print(f"\n[bold green]🎉 论文已收敛! 第 {round_num} 轮平均评分 {avg:.2f} ≤ {self.convergence_threshold}[/bold green]")
                break
            else:
                console.print(f"\n[dim]平均评分 {avg:.2f} > 阈值 {self.convergence_threshold}，继续下一轮...[/dim]")

        # === FINAL SUMMARY ===
        return self._generate_summary(base_output)

    def _generate_summary(self, output_dir: Path) -> Dict:
        """Generate final summary report."""
        console.rule("[bold green]📊 迭代完成 — Iteration Complete[/bold green]")

        if self.converged:
            console.print(f"[bold green]✅ 论文在第 {self.converged_at_round} 轮收敛[/bold green]")
        else:
            console.print(f"[bold yellow]⚠️ 达到最大轮数 {self.max_rounds}，未完全收敛[/bold yellow]")

        # Show score progression
        console.print("\n[bold]📈 评分变化趋势:[/bold]")
        dims = list(self.rounds[0]["scores"].keys()) if self.rounds else []
        header = "Round  " + "  ".join(f"{d:>10}" for d in dims) + "  Avg"
        console.print(f"[dim]{header}[/dim]")
        for r in self.rounds:
            scores_str = "  ".join(f"{r['scores'].get(d, 0):>10.2f}" for d in dims)
            console.print(f"  {r['round']:>3}   {scores_str}  {r['avg_score']:>5.2f}")

        # Save summary JSON
        summary = {
            "converged": self.converged,
            "converged_at_round": self.converged_at_round,
            "total_rounds": len(self.rounds),
            "max_rounds": self.max_rounds,
            "rounds": [
                {
                    "round": r["round"],
                    "scores": r["scores"],
                    "avg_score": r["avg_score"],
                    "had_human_feedback": bool(r.get("human_feedback")),
                }
                for r in self.rounds
            ],
            "output_dir": str(output_dir),
            "timestamp": datetime.now().isoformat(),
        }

        summary_path = str(output_dir / "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        console.print(f"\n[dim]📄 总结报告: {summary_path}[/dim]")

        # Print final file listing
        console.print(f"\n[bold]📂 输出文件:[/bold]")
        for f in sorted(output_dir.iterdir()):
            size = f.stat().st_size
            console.print(f"  {'📄' if f.suffix in ['.tex','.md'] else '📊'} {f.name} ({size:,} bytes)")

        return summary

    async def run_async(self, paper_path: str) -> Dict:
        """Async wrapper (same as run for now, sync)."""
        return self.run(paper_path)
