"""OneTech eklentisi ve stüdyo için ortak, yerel prompt maskeleme kuralları."""

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from threading import Lock


RULES_PATH = Path(__file__).with_name("prompt_rules.json")
_RULE_LOCK = Lock()
MAX_PROMPT_CHARS = 50_000


@dataclass(frozen=True)
class Match:
    original: str
    mask: str
    score: int
    type: str
    startIndex: int
    endIndex: int


EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE = re.compile(r"(?<!\d)(?:\+?90[\s().-]*|0[\s().-]*)?5\d{2}[\s().-]*\d{3}[\s().-]*\d{2}[\s().-]*\d{2}(?!\d)")
TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
IBAN = re.compile(r"\bTR[\s-]?(?:\d[\s-]?){24}\b", re.I)
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
API_KEY = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9_]{20,})\b")
LABELLED_NAME = re.compile(r"(?im)(?<=^)(?:ad\s*soyad|adı\s*soyadı|isim\s*soyisim)\s*:\s*([^\r\n,;]{3,80})")


def _valid_tckn(value: str) -> bool:
    digits = [int(ch) for ch in value]
    return len(digits) == 11 and digits[0] != 0 and (
        (sum(digits[:9:2]) * 7 - sum(digits[1:8:2])) % 10 == digits[9]
    ) and sum(digits[:10]) % 10 == digits[10]


def _valid_card(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _valid_iban(value: str) -> bool:
    compact = re.sub(r"[\s-]", "", value).upper()
    if len(compact) != 26 or not compact.startswith("TR"):
        return False
    converted = "".join(str(ord(ch) - 55) if ch.isalpha() else ch for ch in compact[4:] + compact[:4])
    return int(converted) % 97 == 1


def get_rules() -> list[str]:
    with _RULE_LOCK:
        if not RULES_PATH.exists():
            return []
        data = json.loads(RULES_PATH.read_text(encoding="utf-8"))
        return [str(rule) for rule in data if isinstance(rule, str)]


def save_rules(rules: list[str]) -> None:
    cleaned = list(dict.fromkeys(rule.strip() for rule in rules if rule.strip()))
    if len(cleaned) > 50 or any(len(rule) > 100 for rule in cleaned):
        raise ValueError("En fazla 50 kural ve kural başına 100 karakter kullanılabilir.")
    with _RULE_LOCK:
        temporary = RULES_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(RULES_PATH)


def analyze_prompt(prompt: str, rules: list[str] | None = None) -> dict:
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"İstem en fazla {MAX_PROMPT_CHARS} karakter olabilir.")
    candidates: list[Match] = []

    def add(pattern: re.Pattern, mask: str, score: int, label: str, validator=None):
        for found in pattern.finditer(prompt):
            start, end = found.span()
            while start < end and prompt[start].isspace():
                start += 1
            while end > start and prompt[end - 1].isspace():
                end -= 1
            original = prompt[start:end]
            if original and (validator is None or validator(original)):
                candidates.append(Match(original, mask, score, label, start, end))

    add(EMAIL, "[E-POSTA]", 30, "E-posta")
    add(PHONE, "[TELEFON]", 25, "Telefon")
    add(TCKN, "[TC-KIMLIK]", 45, "T.C. kimlik", _valid_tckn)
    add(IBAN, "[IBAN]", 45, "IBAN", _valid_iban)
    add(CARD, "[KART]", 50, "Kart numarası", _valid_card)
    add(API_KEY, "[API-ANAHTARI]", 60, "API anahtarı")
    for found in LABELLED_NAME.finditer(prompt):
        start, end = found.span(1)
        original = prompt[start:end].strip()
        if original:
            candidates.append(Match(original, "[AD-SOYAD]", 20, "Ad soyad", start, start + len(original)))
    for rule in (get_rules() if rules is None else rules):
        if rule:
            for found in re.finditer(re.escape(rule), prompt, re.I):
                candidates.append(Match(found.group(), "[OZEL-KURAL]", 50, "Özel kural", found.start(), found.end()))

    # Uzun eşleşme öncelikli; iç içe aralıklar iki defa maskelenmez.
    candidates.sort(key=lambda item: (-(item.endIndex - item.startIndex), item.startIndex))
    selected: list[Match] = []
    for candidate in candidates:
        if all(candidate.endIndex <= other.startIndex or candidate.startIndex >= other.endIndex for other in selected):
            selected.append(candidate)
    selected.sort(key=lambda item: item.startIndex)
    return {"originalPrompt": prompt, "matches": [asdict(item) for item in selected]}


def mask_prompt(prompt: str, matches: list[dict], enabled: list[bool] | None = None) -> str:
    """Eşleşmeleri karakter aralıklarına göre değiştir; aynı metnin farklı geçişleri bağımsızdır."""
    if enabled is None:
        enabled = [True] * len(matches)
    result = prompt
    for match, active in reversed(list(zip(matches, enabled))):
        if active:
            result = result[:match["startIndex"]] + match["mask"] + result[match["endIndex"]:]
    return result
