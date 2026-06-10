"""
AI Writing Pattern Detection — based on Wikipedia "Signs of AI Writing"
and the humanizer project (github.com/blader/humanizer).

Detects 24+ patterns across 5 categories, with 3-tier vocabulary.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

# ============================================================
# TIER 1 — Dead Giveaways (always flagged)
# ============================================================
TIER1_VOCAB = [
    "delve", "delve into", "delve deeper",
    "tapestry", "rich tapestry", "vibrant tapestry",
    "moreover", "furthermore", "additionally", "consequently", "thus", "hence",
    "notably", "importantly", "interestingly", "surprisingly",
    "pivotal", "pivotal moment", "pivotal role",
    "testament", "a testament to", "serves as a testament",
    "showcase", "showcases", "showcasing",
    "underscores", "underscoring", "highlighting", "highlight",
    "realm", "in the realm of", "realm of",
    "landscape", "evolving landscape", "changing landscape",
    "intricate", "intricately",
    "embodies", "epitomizes",
    "crucial", "paramount", "vital", "essential",
    "profound", "profoundly", "deeply",
    "unwavering", "unwaveringly",
    "indelible", "indelibly",
    "transformative",
    "groundbreaking",
    "revolutionary",
    "cutting-edge",
    "state-of-the-art",
    "robust",
    "paradigm", "paradigm shift",
    "game-changer",
    "seamless", "seamlessly",
    "holistic",
    "synergistic", "synergy",
    "bespoke",
    "curated",
    "meticulous", "meticulously",
    "thought-provoking",
    "game changing",
    "world-class",
    "best-in-class",
    "market-leading",
]

# ============================================================
# TIER 2 — Suspicious in Density (flagged when frequent)
# ============================================================
TIER2_VOCAB = [
    "comprehensive", "comprehensively",
    "sophisticated",
    "innovative", "innovation",
    "dynamic", "dynamically",
    "diverse", "diversity",
    "nuanced",
    "nuance",
    "compelling",
    "resonate", "resonates",
    "empower", "empowering", "empowerment",
    "embrace", "embracing",
    "foster", "fostering",
    "leverage", "leveraging",
    "optimize", "optimization",
    "streamline", "streamlined",
    "facilitate",
    "enable",
    "ensure",
    "significant", "significantly",
    "substantial", "substantially",
    "considerable", "considerably",
    "demonstrate", "demonstrates",
    "indicate", "indicates",
    "suggest", "suggests",
    "reveal", "reveals",
    "illustrate", "illustrates",
    "elucidate",
    "articulate",
    "delineate",
    "explicate",
    "contextualize",
    "situate",
    "foreground",
    "unpack",
    "interrogate",
    "complicate",
    "complicates",
    "gesture toward",
    "speak to",
    "reckon with",
    "grapple with",
    "wrestle with",
]

# ============================================================
# TIER 3 — Context-Dependent (only in academic writing context)
# ============================================================
TIER3_VOCAB = [
    "ultimately",
    "in other words",
    "that is to say",
    "put differently",
    "simply put",
    "in essence",
    "at its core",
    "fundamentally",
    "it is worth noting",
    "it should be noted",
    "it is important to note",
    "one might argue",
    "some might argue",
    "it could be argued",
    "as previously mentioned",
    "as noted earlier",
    "as discussed above",
    "in conclusion",
    "to summarize",
    "in summary",
    "to conclude",
    "moving forward",
    "going forward",
    "looking ahead",
    "in today's world",
    "in recent years",
    "in the modern era",
    "in the age of",
    "in the context of",
    "in light of",
]

# ============================================================
# PATTERN DEFINITIONS
# ============================================================

@dataclass
class PatternMatch:
    """A detected AI writing pattern instance."""
    pattern_name: str
    category: str
    severity: float       # 0.0–1.0
    match_text: str       # the matched substring
    line_number: int
    suggestion: str       # how to fix

@dataclass
class PatternReport:
    """Full AI pattern detection report."""
    total_score: float    # 0.0–1.0 (higher = more AI-like)
    matches: List[PatternMatch] = field(default_factory=list)
    tier1_density: float = 0.0
    tier2_density: float = 0.0
    burstiness: float = 0.0
    type_token_ratio: float = 0.0
    sentence_length_cv: float = 0.0   # coefficient of variation

# ============================================================
# DETECTION FUNCTIONS
# ============================================================

def detect_tier_vocab(text: str) -> List[PatternMatch]:
    """Detect Tier 1, 2, 3 AI vocabulary."""
    matches = []
    lines = text.split('\n')

    for i, line in enumerate(lines, 1):
        line_lower = line.lower()

        # Tier 1: always flag
        for word in TIER1_VOCAB:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(line):
                matches.append(PatternMatch(
                    pattern_name="AI词汇 (Tier1)",
                    category="language",
                    severity=0.9,
                    match_text=m.group(),
                    line_number=i,
                    suggestion=f'将 "{m.group()}" 替换为更自然的表达'
                ))

        # Tier 2: flag if density is high (tracked later)
        for word in TIER2_VOCAB:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(line):
                matches.append(PatternMatch(
                    pattern_name="AI词汇 (Tier2)",
                    category="language",
                    severity=0.5,
                    match_text=m.group(),
                    line_number=i,
                    suggestion=f'考虑将 "{m.group()}" 替换为更简洁的表达'
                ))

        # Tier 3: only flag in academic-heavy context
        for word in TIER3_VOCAB:
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(line):
                matches.append(PatternMatch(
                    pattern_name="AI词汇 (Tier3)",
                    category="language",
                    severity=0.3,
                    match_text=m.group(),
                    line_number=i,
                    suggestion=f'"{m.group()}" 可能是AI填充语，考虑删除或替换'
                ))

    return matches


def detect_significance_inflation(text: str) -> List[PatternMatch]:
    """Detect inflated significance claims."""
    patterns = [
        (r'marking a (?:pivotal|significant|crucial|major) (?:moment|turning point|shift)', 0.9),
        (r'serves as a testament to', 0.8),
        (r'stand(?:s|ing) as a (?:beacon|testament|monument|cornerstone)', 0.9),
        (r'a (?:landmark|watershed|defining) (?:moment|achievement|accomplishment)', 0.8),
        (r'profound(?:ly)? (?:impact|influence|effect|change|shift|implication)', 0.7),
        (r'reshap(?:e|ing) (?:the|our) understanding of', 0.8),
        (r'fundamentally (?:alter|change|transform|shift)', 0.7),
        (r'usher(?:s|ing|ed) in a new era', 0.9),
        (r'at the forefront of', 0.7),
        (r'breakthrough', 0.6),
        (r'unprecedented', 0.7),
    ]
    return _match_patterns(text, patterns, "意义夸大", "content")


def detect_vague_attributions(text: str) -> List[PatternMatch]:
    """Detect vague attributions without specific citations."""
    patterns = [
        (r'Experts (?:believe|suggest|argue|agree|note|claim|say)', 0.8),
        (r'Studies (?:show|suggest|indicate|demonstrate|reveal|prove|find)', 0.8),
        (r'Research (?:shows|suggests|indicates|demonstrates|reveals)', 0.7),
        (r'Many (?:scholars|researchers|scientists|experts) (?:believe|argue|suggest)', 0.8),
        (r'It is (?:widely|generally|commonly) (?:believed|accepted|known|understood)', 0.7),
        (r'According to (?:experts|researchers|scholars|scientists)', 0.7),
        (r'A growing body of (?:evidence|research|literature)', 0.6),
        (r'Critics (?:argue|say|claim|suggest|note)', 0.7),
        (r'Some (?:argue|say|believe|suggest|claim)', 0.5),
    ]
    return _match_patterns(text, patterns, "模糊引用", "content")


def detect_superficial_ing(text: str) -> List[PatternMatch]:
    """Detect superficial -ing clause patterns."""
    patterns = [
        (r'highlighting the (?:importance|significance|role|need|challenges)', 0.6),
        (r'reflecting the (?:complexity|diversity|nature|importance|challenges)', 0.6),
        (r'showcasing the (?:ability|potential|importance|power|versatility)', 0.7),
        (r'demonstrating the (?:importance|significance|power|potential|need)', 0.6),
        (r'underscoring the (?:importance|need|significance|challenges|role)', 0.6),
        (r'suggesting a (?:need|shift|trend|pattern|relationship)', 0.5),
    ]
    return _match_patterns(text, patterns, "肤浅分词分析", "content")


def detect_promotional_language(text: str) -> List[PatternMatch]:
    """Detect promotional/marketing language."""
    patterns = [
        (r'\b(?:nestled|breathtaking|stunning|vibrant|gorgeous|magnificent|exquisite)\b', 0.7),
        (r'\b(?:renowned|prestigious|esteemed|distinguished|eminent|illustrious)\b', 0.6),
        (r'\b(?:world-renowned|world-famous|internationally recognized)\b', 0.7),
        (r'\b(?:exceptional|extraordinary|remarkable|outstanding|superb|excellent)\b', 0.5),
        (r'\b(?:unmatched|unparalleled|unequalled|unsurpassed|peerless)\b', 0.6),
    ]
    return _match_patterns(text, patterns, "推销性语言", "content")


def detect_negative_parallelisms(text: str) -> List[PatternMatch]:
    """Detect 'it's not just X, it's Y' patterns."""
    patterns = [
        (r"It(?:'s| is) not (?:just|merely|only|simply) (\w+(?:\s+\w+){0,3}), it(?:'s| is) (\w+(?:\s+\w+){0,5})", 0.7),
        (r"not (?:just|merely|only|simply) a (\w+(?:\s+\w+){0,3}), but (?:a |also )?(\w+(?:\s+\w+){0,3})", 0.6),
        (r"more than (?:just|merely|simply) (\w+(?:\s+\w+){0,3})", 0.5),
        (r"This is not (?:just|merely|only|simply) (\w+(?:\s+\w+){0,5})", 0.6),
    ]
    return _match_patterns(text, patterns, "否定并列", "language")


def detect_em_dashes(text: str) -> List[PatternMatch]:
    """Detect em dashes — a strong AI writing signal."""
    matches = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        count = line.count('—') + line.count('--') + line.count('–')
        if count > 0:
            matches.append(PatternMatch(
                pattern_name="破折号使用",
                category="style",
                severity=min(0.3 * count, 1.0),
                match_text=line.strip()[:80],
                line_number=i,
                suggestion="AI生成文本倾向大量使用破折号，考虑替换为逗号、分号或句号"
            ))
    return matches


def detect_copula_avoidance(text: str) -> List[PatternMatch]:
    """Detect copula avoidance — 'serves as' instead of 'is', 'boasts' instead of 'has'."""
    patterns = [
        (r'\bserves as\b', 0.6, '考虑直接将 "serves as" 替换为 "is"'),
        (r'\bacts as\b', 0.5, '考虑将 "acts as" 替换为 "is"'),
        (r'\bfunctions as\b', 0.5, '考虑将 "functions as" 替换为 "is"'),
        (r'\bboasts\b(?!\s+(?:a|an|the|its|their)\s+(?:history|tradition|record|lineage))', 0.6, '"boasts" 是AI常用动词，替换为 "has" or "features"'),
        (r'\bpossesses\b', 0.5, '"possesses" 替换为 "has"'),
    ]
    result = []
    lines = text.split('\n')
    for pat, sev, sug in patterns:
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pat, line, re.IGNORECASE):
                result.append(PatternMatch("系词回避", "language", sev, m.group(), i, sug))
    return result


def detect_rule_of_three(text: str) -> List[PatternMatch]:
    """Detect rule-of-three adjective/noun sequences."""
    patterns = [
        (r'(\w+),\s*(\w+),\s*(?:and|&)\s*(\w+)\s*(?:approach|method|solution|strategy|framework|model|system|process|experience|journey|understanding|perspective|analysis|design|development|implementation)', 0.5),
    ]
    return _match_patterns(text, patterns, "三连排比", "language")


def detect_elegant_variation(text: str) -> List[PatternMatch]:
    """Detect elegant variation — cycling synonyms unnaturally."""
    # Check for 3+ synonyms used within close proximity (5 sentences)
    synonym_groups = [
        ['researcher', 'scholar', 'academic', 'scientist', 'investigator'],
        ['study', 'research', 'investigation', 'examination', 'inquiry', 'exploration'],
        ['important', 'significant', 'crucial', 'vital', 'essential', 'paramount'],
        ['shows', 'demonstrates', 'reveals', 'indicates', 'illustrates', 'highlights'],
        ['method', 'approach', 'technique', 'methodology', 'framework'],
        ['result', 'finding', 'outcome', 'discovery', 'insight'],
        ['problem', 'challenge', 'issue', 'difficulty', 'obstacle', 'limitation'],
    ]
    matches = []
    sentences = re.split(r'[.!?。！？]\s*', text)
    for group in synonym_groups:
        for i in range(len(sentences) - 2):
            window = ' '.join(sentences[i:i+5]).lower()
            found = [w for w in group if re.search(r'\b' + re.escape(w) + r'\b', window)]
            if len(found) >= 3:
                matches.append(PatternMatch(
                    "同义词轮换",
                    "language",
                    0.4,
                    f'在5句内使用了: {", ".join(found)}',
                    i + 1,
                    f'建议保持术语一致，不要过度轮换同义词: {", ".join(found)}'
                ))
                break
    return matches


def detect_false_ranges(text: str) -> List[PatternMatch]:
    """Detect false ranges — 'From X to Y' spanning unrelated extremes."""
    patterns = [
        (r'[Ff]rom (\w+(?:\s+\w+){0,3}) to (\w+(?:\s+\w+){0,3})', None),
    ]
    # High-severity known pairs
    known_pairs = [
        (r'from the Big Bang to', 0.9),
        (r'from quantum mechanics to', 0.8),
        (r'from artificial intelligence to', 0.7),
        (r'from ancient (?:times|civilizations) to', 0.8),
        (r'from molecules to', 0.7),
        (r'from the microscopic to', 0.8),
        (r'from neurons to', 0.7),
        (r'from genes to', 0.7),
        (r'from cells to', 0.7),
        (r'from the individual to', 0.6),
        (r'from theory to', 0.6),
        (r'from academia to', 0.6),
    ]
    result = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        for pat, sev in known_pairs:
            for m in re.finditer(pat, line, re.IGNORECASE):
                result.append(PatternMatch(
                    "虚假范围", "language",
                    sev, m.group(), i,
                    '"From X to Y" 句式过于空泛，请说明具体范围或删除'
                ))
    return result


def detect_chatbot_artifacts(text: str) -> List[PatternMatch]:
    """Detect chatbot-style communication patterns."""
    patterns = [
        (r'I hope this (?:helps|clarifies|answers|explains|sheds)', 0.9),
        (r'Let me know if you (?:have|need|want|would like)', 0.9),
        (r'Feel free to (?:ask|reach|contact|get in touch)', 0.9),
        (r'As (?:an AI|a language model|a large language model)', 0.95),
        (r'(?:As of|Based on) my (?:knowledge cutoff|training (?:data|cutoff)|last update)', 0.95),
        (r'(?:Great|Excellent|Good|Interesting|Fascinating) question', 0.8),
        (r"You(?:'re| are) (?:absolutely|completely|totally) right", 0.8),
        (r'I (?:completely|fully|totally|absolutely) agree', 0.7),
        (r"(?:That|This)(?:'s| is) (?:an? )?(?:excellent|great|wonderful|fantastic|interesting) (?:question|point|observation|perspective)", 0.8),
        (r"It(?:'s| is) (?:important|crucial|essential|vital|worthwhile) to (?:note|mention|remember|consider|understand)", 0.6),
        (r'^(?:Sure!|Of course!|Absolutely!|Certainly!|Great!|Excellent!)', 0.8),
        (r'^(?:Hi|Hello|Hey|Greetings|Dear)\b.{0,50}(?:I|we|let me|allow me)', 0.5),
    ]
    return _match_patterns(text, patterns, "聊天机器人痕迹", "communication")


def detect_formulaic_challenges(text: str) -> List[PatternMatch]:
    """Detect formulaic 'despite challenges' structures."""
    patterns = [
        (r'[Dd]espite (?:these |the |its |their )?(?:challenges|limitations|difficulties|obstacles|setbacks),.{0,80}(?:continue|remain|persist|thrive|flourish|grow|succeed|advance|progress)', 0.7),
        (r'[Ww]hile (?:challenges|limitations|obstacles) (?:remain|exist|persist),', 0.6),
        (r'[Nn]ot without (?:its |their )?(?:challenges|limitations|difficulties)', 0.6),
        (r'[Cc]hallenges (?:remain|persist|continue|abound), (?:but|yet|however)', 0.6),
    ]
    return _match_patterns(text, patterns, "公式化挑战段", "content")


def detect_hedging_excess(text: str) -> List[PatternMatch]:
    """Detect excessive hedging phrases."""
    patterns = [
        (r'\b(?:could potentially possibly|could possibly|might possibly|may potentially|could potentially)\b', 0.7),
        (r'\b(?:it is possible that|it may be that|it might be that|it could be that)\b', 0.6),
        (r'\b(?:to some extent|to a certain extent|to a degree|in some sense|in a sense)\b', 0.5),
        (r'\b(?:perhaps|maybe|possibly|potentially|arguably)\b', 0.3),
    ]
    matches = _match_patterns(text, patterns, "过度模糊限定", "filler")
    # Increase severity if density is high
    word_count = len(text.split())
    if word_count > 0 and len(matches) / (word_count / 100) > 3:
        for m in matches:
            m.severity = min(m.severity * 1.5, 1.0)
    return matches


def detect_generic_conclusions(text: str) -> List[PatternMatch]:
    """Detect generic/conclusory endings."""
    patterns = [
        (r'[Ff]uture (?:research|work|studies|investigation) (?:should|could|may|might|will|would|need to) (?:focus on|explore|examine|investigate|address|consider)', 0.7),
        (r'[Ff]urther (?:research|investigation|study|work|analysis) (?:is|are) (?:needed|required|necessary|warranted|called for)', 0.7),
        (r'[Mm]ore (?:research|work|studies) (?:is|are) needed', 0.6),
        (r'[Tt]his (?:study|paper|research|work) (?:has|provides|offers|contributes) (?:a |an )?(?:foundation|basis|stepping stone|starting point) for', 0.6),
        (r'[Tt]his (?:opens|paves) (?:the|a) (?:way|door|path) (?:for|to)', 0.7),
        (r'[Ii]n conclusion,?\s*(?:this|the|we|I|our|these)', 0.4),
        (r'[Tt]o (?:summarize|sum up|conclude),?\s*', 0.4),
    ]
    return _match_patterns(text, patterns, "模板化结论", "filler")


def detect_title_case_headings(text: str) -> List[PatternMatch]:
    """Detect excessive Title Case headings."""
    matches = []
    lines = text.split('\n')
    title_case_count = 0
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped and len(stripped) > 3 and len(stripped) < 120:
            words = stripped.split()
            if all(w[0].isupper() if w[0].isalpha() else True for w in words if len(w) > 2):
                title_case_count += 1
                if title_case_count > 2:
                    matches.append(PatternMatch(
                        "Title Case标题",
                        "style", 0.3, stripped[:80], i,
                        "过度使用Title Case标题是AI写作特征，考虑使用Sentence case"
                    ))
    return matches


def compute_burstiness(text: str) -> float:
    """Compute text burstiness (sentence length variance)."""
    sentences = re.split(r'[.!?。！？]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    mean_len = sum(lengths) / len(lengths)
    if mean_len == 0:
        return 0.0
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    cv = variance ** 0.5 / mean_len if mean_len > 0 else 0
    # Higher CV = more bursty = more human-like
    # Return AI-likeness: low CV = AI-like
    if cv > 1.0:
        return 0.0  # very bursty, human-like
    elif cv > 0.6:
        return 0.3
    elif cv > 0.4:
        return 0.5
    else:
        return 0.8


def compute_type_token_ratio(text: str) -> float:
    """Compute type-token ratio (lexical diversity)."""
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < 10:
        return 0.0
    unique = len(set(words))
    total = len(words)
    ttr = unique / total
    # AI text tends to have moderate TTR; very low or very high = human
    # AI sweet spot is often 0.45–0.65
    if 0.45 <= ttr <= 0.65:
        return 0.5
    else:
        return 0.2
    return ttr


# ============================================================
# MAIN ANALYSIS
# ============================================================

def _match_patterns(text: str, patterns: List, pattern_name: str, category: str) -> List[PatternMatch]:
    """Helper to apply regex patterns and produce PatternMatch objects."""
    matches = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        for pat, sev in patterns:
            for m in re.finditer(pat, line, re.IGNORECASE):
                matches.append(PatternMatch(
                    pattern_name, category, sev, m.group(), i,
                    f'检测到"{pattern_name}"模式，建议修改或删除'
                ))
    return matches


def analyze_ai_patterns(text: str) -> PatternReport:
    """Run all AI pattern detectors on the text and return a report."""
    all_matches = []

    # Content patterns
    all_matches.extend(detect_significance_inflation(text))
    all_matches.extend(detect_vague_attributions(text))
    all_matches.extend(detect_superficial_ing(text))
    all_matches.extend(detect_promotional_language(text))
    all_matches.extend(detect_formulaic_challenges(text))

    # Language patterns
    all_matches.extend(detect_tier_vocab(text))
    all_matches.extend(detect_negative_parallelisms(text))
    all_matches.extend(detect_copula_avoidance(text))
    all_matches.extend(detect_rule_of_three(text))
    all_matches.extend(detect_elegant_variation(text))
    all_matches.extend(detect_false_ranges(text))

    # Style patterns
    all_matches.extend(detect_em_dashes(text))
    all_matches.extend(detect_title_case_headings(text))

    # Communication patterns
    all_matches.extend(detect_chatbot_artifacts(text))

    # Filler/Hedging
    all_matches.extend(detect_hedging_excess(text))
    all_matches.extend(detect_generic_conclusions(text))

    # Statistical signals
    burstiness = compute_burstiness(text)
    ttr = compute_type_token_ratio(text)
    sent_cv = _compute_sentence_cv(text)

    # Count tier densities
    words = text.split()
    word_count = len(words) if words else 1
    tier1_count = sum(1 for m in all_matches if "Tier1" in m.pattern_name)
    tier2_count = sum(1 for m in all_matches if "Tier2" in m.pattern_name)
    tier1_density = tier1_count / (word_count / 100)
    tier2_density = tier2_count / (word_count / 100)

    # Composite score: weighted by severity, capped at 1.0
    if all_matches:
        # Logarithmic scaling to prevent runaway
        total_severity = sum(m.severity for m in all_matches)
        raw_score = total_severity / (1 + total_severity * 0.1)
        pattern_score = min(raw_score, 1.0)
    else:
        pattern_score = 0.0

    # Add statistical penalty
    uniformity_score = (0.5 * burstiness + 0.3 * (1 - ttr) + 0.2 * (1 - sent_cv))

    # Composite: 70% pattern + 30% statistical
    total_score = 0.7 * pattern_score + 0.3 * uniformity_score

    return PatternReport(
        total_score=total_score,
        matches=all_matches,
        tier1_density=tier1_density,
        tier2_density=tier2_density,
        burstiness=burstiness,
        type_token_ratio=ttr,
        sentence_length_cv=sent_cv,
    )


def _compute_sentence_cv(text: str) -> float:
    """Compute sentence length coefficient of variation."""
    sentences = re.split(r'[.!?。！？]\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) < 2:
        return 0.0
    mean_len = sum(lengths) / len(lengths)
    if mean_len == 0:
        return 0.0
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    cv = variance ** 0.5 / mean_len
    return min(cv / 2.0, 1.0)  # normalize: CV of ~1.0 maps to 0.5
