"""
Paper Manager — load, parse, save, and diff LaTeX (.tex) and Markdown (.md) papers.
Tracks iteration metadata and generates diffs between versions.
"""

import os
import re
import difflib
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PaperSection:
    """A section of the paper."""
    heading: str           # section heading (e.g., "Introduction", "Methodology")
    level: int             # 0 = title, 1 = section, 2 = subsection, 3 = subsubsection
    content: str           # full text content of this section
    start_line: int
    end_line: int


@dataclass
class Paper:
    """Represents an academic paper in LaTeX or Markdown format."""
    file_path: str
    format: str            # "latex" or "markdown"
    raw_text: str
    sections: List[PaperSection] = field(default_factory=list)
    preamble: str = ""     # LaTeX preamble (everything before \begin{document})
    body: str = ""         # main body content
    metadata: Dict = field(default_factory=dict)


@dataclass
class IterationRecord:
    """Metadata for one review-revise round."""
    round_num: int
    timestamp: str
    paper_hash: str
    review_scores: Dict[str, float]
    avg_score: float
    human_feedback: Optional[str] = None
    diff_summary: str = ""


class PaperManager:
    """Handles all paper I/O, parsing, saving, and diffing."""

    SUPPORTED_FORMATS = [".tex", ".md", ".markdown", ".txt"]

    @staticmethod
    def detect_format(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext in [".tex", ".ltx", ".latex"]:
            return "latex"
        elif ext in [".md", ".markdown"]:
            return "markdown"
        elif ext == ".txt":
            return "text"
        else:
            return "text"

    @staticmethod
    def load(file_path: str) -> Paper:
        """Load a paper from file, auto-detecting format."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Paper not found: {file_path}")

        fmt = PaperManager.detect_format(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        paper = Paper(
            file_path=file_path,
            format=fmt,
            raw_text=raw_text,
            metadata={
                "filename": os.path.basename(file_path),
                "size_bytes": os.path.getsize(file_path),
                "load_time": datetime.now().isoformat(),
                "hash": hashlib.sha256(raw_text.encode()).hexdigest()[:16],
            }
        )

        if fmt == "latex":
            PaperManager._parse_latex(paper)
        else:
            PaperManager._parse_markdown(paper)

        return paper

    @staticmethod
    def _parse_latex(paper: Paper):
        """Parse LaTeX document into preamble, body, and sections."""
        text = paper.raw_text

        # Split preamble and body
        doc_begin = re.search(r'\\begin\{document\}', text)
        doc_end = re.search(r'\\end\{document\}', text)

        if doc_begin:
            paper.preamble = text[:doc_begin.start()]
            body_start = doc_begin.end()
            paper.body = text[body_start:doc_end.start()] if doc_end else text[body_start:]
        else:
            paper.preamble = ""
            paper.body = text

        # Parse sections from body
        section_pattern = re.compile(
            r'\\(section|subsection|subsubsection|chapter|part)\{([^}]*)\}',
            re.MULTILINE
        )

        lines = paper.body.split('\n')
        section_matches = list(section_pattern.finditer(paper.body))

        level_map = {
            'part': 0, 'chapter': 0,
            'section': 1, 'subsection': 2, 'subsubsection': 3
        }

        for idx, match in enumerate(section_matches):
            cmd = match.group(1)
            title = match.group(2)
            start = match.start()
            end = section_matches[idx + 1].start() if idx + 1 < len(section_matches) else len(paper.body)

            # Find line numbers
            start_line = paper.body[:start].count('\n') + 1
            end_line = paper.body[:end].count('\n') + 1

            paper.sections.append(PaperSection(
                heading=title.strip(),
                level=level_map.get(cmd, 1),
                content=paper.body[start:end].strip(),
                start_line=start_line,
                end_line=end_line,
            ))

    @staticmethod
    def _parse_markdown(paper: Paper):
        """Parse Markdown document into sections."""
        text = paper.raw_text
        lines = text.split('\n')

        section_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

        section_matches = list(section_pattern.finditer(text))

        for idx, match in enumerate(section_matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            start = match.start()
            end = section_matches[idx + 1].start() if idx + 1 < len(section_matches) else len(text)

            start_line = text[:start].count('\n') + 1
            end_line = text[:end].count('\n') + 1

            paper.sections.append(PaperSection(
                heading=title,
                level=min(level, 3),
                content=text[start:end].strip(),
                start_line=start_line,
                end_line=end_line,
            ))

        paper.body = text

    @staticmethod
    def save(paper: Paper, output_path: str) -> str:
        """Save a paper to file. Returns the output path."""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(paper.raw_text)
        return output_path

    @staticmethod
    def save_revision(original: Paper, revised_text: str, output_path: str) -> Paper:
        """Save a revised version and return the new Paper object."""
        revised = Paper(
            file_path=output_path,
            format=original.format,
            raw_text=revised_text,
            metadata={
                **original.metadata,
                "revised_from": original.file_path,
                "save_time": datetime.now().isoformat(),
                "hash": hashlib.sha256(revised_text.encode()).hexdigest()[:16],
            }
        )

        if revised.format == "latex":
            PaperManager._parse_latex(revised)
        else:
            PaperManager._parse_markdown(revised)

        PaperManager.save(revised, output_path)
        return revised

    @staticmethod
    def diff(original: Paper, revised: Paper, context_lines: int = 3) -> str:
        """Compute a unified diff between two papers."""
        diff = difflib.unified_diff(
            original.raw_text.splitlines(keepends=True),
            revised.raw_text.splitlines(keepends=True),
            fromfile=os.path.basename(original.file_path),
            tofile=os.path.basename(revised.file_path),
            n=context_lines,
        )
        return ''.join(diff)

    @staticmethod
    def diff_summary(diff_text: str) -> str:
        """Generate a human-readable summary of changes."""
        added = diff_text.count('\n+') - diff_text.count('\n+++')
        removed = diff_text.count('\n-') - diff_text.count('\n---')
        lines = [f"📊 修改统计: +{added} 行添加, -{removed} 行删除"]

        if added > 0 and removed > 0:
            lines.append(f"净变化: {'+' if added > removed else ''}{added - removed} 行")

        # Identify changed sections
        changed_blocks = re.findall(r'@@ .*? @@(.*?)(?=@@|$)', diff_text, re.DOTALL)
        lines.append(f"🔍 修改块数: {len(changed_blocks)}")

        return '\n'.join(lines)

    @staticmethod
    def get_plain_text(paper: Paper) -> str:
        """Extract plain text from a paper (strip LaTeX commands for review)."""
        text = paper.body if paper.body else paper.raw_text

        if paper.format == "latex":
            # Remove LaTeX commands but keep content
            text = re.sub(r'\\\w+\{([^}]*)\}', r'\1', text)  # \cmd{arg}
            text = re.sub(r'\\\w+', '', text)                  # \cmd
            text = re.sub(r'\\begin\{[^}]*\}', '', text)       # \begin{env}
            text = re.sub(r'\\end\{[^}]*\}', '', text)         # \end{env}
            text = re.sub(r'%.*$', '', text, flags=re.MULTILINE)  # comments
            text = re.sub(r'\$[^$]*\$', '[公式]', text)        # inline math → placeholder
            text = re.sub(r'\$\$[^$]*\$\$', '[公式块]', text)  # display math
            text = re.sub(r'\n\s*\n', '\n\n', text)            # collapse blank lines

        return text.strip()

    @staticmethod
    def create_iteration_record(
        round_num: int,
        scores: Dict[str, float],
        diff_text: str,
        human_feedback: Optional[str] = None,
    ) -> IterationRecord:
        """Create an iteration metadata record."""
        avg = sum(scores.values()) / max(len(scores), 1) if scores else 1.0
        return IterationRecord(
            round_num=round_num,
            timestamp=datetime.now().isoformat(),
            paper_hash="",  # set by orchestrator
            review_scores=scores,
            avg_score=avg,
            human_feedback=human_feedback,
            diff_summary=PaperManager.diff_summary(diff_text),
        )
