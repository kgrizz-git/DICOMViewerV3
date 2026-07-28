"""Name and patient identifier token matching for filename and content scanning."""

from __future__ import annotations

import os
import re

PATIENT_NAME_TOKENS: frozenset[str] = frozenset([
    "abdi", "abigail", "adams", "adeyemi", "aguilar", "aiden", "alexander", "allen",
    "alvarez", "amanda", "amelia", "amy", "anderson", "andrew", "angela", "anna", "anthony",
    "asher", "ashley", "aurora", "ava", "bailey", "baker", "barbara", "bell", "benjamin",
    "betty", "brandon", "brian", "brown", "callahan", "camila", "campbell", "carol", "carter",
    "castillo", "charles", "chavez", "chen", "chloe", "choi", "chowdhury", "christopher",
    "clark", "cohen", "coleman", "cook", "cooper", "cortez", "cruz", "cynthia", "daniel",
    "david", "davies", "davis", "deborah", "delgado", "delilah", "dennis", "desai", "diallo",
    "donald", "donna", "donnelly", "dorothy", "edward", "edwards", "elijah", "elizabeth",
    "ella", "emily", "emma", "emmett", "eric", "ethan", "evans", "evelyn", "ezra", "fitzgerald",
    "flores", "frank", "friedman", "fuentes", "garcia", "gary", "george", "goldberg",
    "gonzalez", "grayson", "green", "gregory", "guerrero", "gupta", "gutierrez", "hall",
    "harper", "harris", "hazel", "hernandez", "hill", "howard", "huang", "hudson", "hughes",
    "isabella", "iyer", "jace", "jack", "jackson", "jacob", "james", "jang", "jason", "jayden",
    "jeffrey", "jennifer", "jeong", "jerry", "jessica", "jimenez", "john", "johnson",
    "jonathan", "jones", "jordan", "joseph", "joshua", "julian", "justin", "kai", "kang",
    "kapoor", "karen", "kathleen", "katz", "kelly", "kenneth", "kevin", "khan", "kim",
    "kimberly", "king", "kumar", "larry", "laura", "layla", "lee", "leo", "levine", "lewis",
    "liam", "linda", "lisa", "liu", "logan", "lopez", "lucas", "margaret", "mark", "martin",
    "martinez", "mary", "mason", "mateo", "matthew", "mcdonald", "mehta", "melissa",
    "mendoza", "mia", "michael", "michelle", "mila", "miller", "mitchell", "moore", "morales",
    "morgan", "morris", "murphy", "mwangi", "nair", "nancy", "nelson", "nguyen", "nicholas",
    "noah", "nora", "nwosu", "obrien", "okafor", "oliver", "olivia", "ortiz", "patel",
    "patricia", "patrick", "paul", "penelope", "perez", "ramirez", "ramos", "raymond",
    "rebecca", "reddy", "reyes", "richard", "riley", "rivera", "robert", "roberts",
    "robinson", "rodriguez", "rojas", "romero", "ronald", "rosenberg", "ruiz", "russell",
    "ryan", "ryder", "salazar", "samuel", "sanchez", "sandra", "sarah", "scarlett",
    "schwartz", "scott", "sebastian", "shah", "sharma", "sharon", "shirley", "singh", "smith",
    "sophia", "stephanie", "stephen", "steven", "sullivan", "susan", "taylor", "theo",
    "thomas", "thompson", "timothy", "torres", "turner", "vasquez", "violet", "walker",
    "wang", "watson", "white", "william", "williams", "wilson", "wood", "wright", "yoon",
    "young", "zhang", "zhao", "zhou", "zoey"
])

SAFE_NAME_COMPOUNDS: frozenset[str] = frozenset([
    "smith_waterman", "robinson_crusoe", "martin_fowler", "gupta_blei", "lee_angle",
    "cooper_pair", "hill_climbing", "bell_curve", "cook_distance", "green_function",
    "young_modulus", "checkbox_checkmark_white"
])

SAFE_DIR_COMPOUNDS: frozenset[str] = frozenset([
    "smith_lab", "davidson_group"
])

PATIENT_IDENTIFIER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|(?<=[\s_.\-]))"
    r"(?:"
    r"(?:mrn|patientid|pid|studyid|encounter|caseid)[\s_.\-]?\d{3,}"
    r"|"
    r"acc(?:ession|n)?[\s_.\-]?\d{5,}"
    r")",
    re.IGNORECASE,
)


_CONTENT_CARVEOUT_PREFIXES = ("dev-docs/", "user-docs/")


def _is_content_carved_out(path: str) -> bool:
    """Return True when a repository path is exempt from name/identifier content scanning."""
    normalized = str(path).replace("\\", "/")
    if "/" not in normalized and normalized.endswith(".md"):
        return True
    return normalized.startswith(_CONTENT_CARVEOUT_PREFIXES)


class PathCarveoutPattern:
    """Marker wrapper for regex patterns subject to content carve-out rules.

    Carve-out decisions are made by callers via _is_content_carved_out rather
    than inside this class, so the pattern itself is always applied when search
    is called directly.
    """

    def __init__(self, pattern: re.Pattern[str]) -> None:
        self.pattern = pattern

    def search(self, text: str) -> re.Match[str] | None:
        return self.pattern.search(text)


_name_regex = re.compile(
    r"(?<![A-Za-z0-9])(?:" + "|".join(sorted(PATIENT_NAME_TOKENS)) + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)

IDENTIFIER_CONTENT_PATTERN = PathCarveoutPattern(PATIENT_IDENTIFIER_PATTERN)
NAME_CONTENT_PATTERN = PathCarveoutPattern(_name_regex)


def name_in_path(path: str) -> str | None:
    """Check a path (every component) for patient names or structured identifiers.

    Returns the rule category if found, else None.
    """
    normalized = str(path).replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]

    for i, component in enumerate(parts):
        if not component or component in (".", ".."):
            continue

        # 1. Check patient-identifier-in-filename on the component
        if PATIENT_IDENTIFIER_PATTERN.search(component):
            return "patient-identifier-in-filename"

        # 2. Check patient-name-in-filename on the component
        stem, _ = os.path.splitext(component)
        stem_folded = stem.casefold()

        is_basename = (i == len(parts) - 1)
        safe_compounds = SAFE_NAME_COMPOUNDS if is_basename else SAFE_DIR_COMPOUNDS
        if stem_folded in safe_compounds:
            continue
        # A derivative (e.g. martin_fowler_refactoring) is exempt only when the
        # trailing suffix tokens are not themselves patient names.
        safe_derivative = False
        for c in safe_compounds:
            for sep in ("_", "-", "."):
                prefix = c + sep
                if stem_folded.startswith(prefix):
                    suffix = stem_folded[len(prefix):]
                    suffix_tokens = [t for t in re.split(r"[-_.\s]", suffix) if len(t) > 1]
                    if not any(t in PATIENT_NAME_TOKENS for t in suffix_tokens):
                        safe_derivative = True
                    break
            if safe_derivative:
                break
        if safe_derivative:
            continue

        # Include ^ so DICOM-style LastName^FirstName paths are tokenised correctly.
        tokens = re.split(r"[-_.\s^]", stem_folded)
        for tok in tokens:
            if len(tok) <= 1:
                continue
            if tok in PATIENT_NAME_TOKENS:
                return "patient-name-in-filename"

    return None
