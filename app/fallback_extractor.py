import re

from app.geo import local_place
from app.i18n import acknowledgement
from app.models import Extraction
from app.security import redact

# Canonical multilingual resource vocabulary is shared with the matcher.
SYNONYMS = {
    "insulin": ("medical", ["insulin", "இன்சுலின்", "insulina"]),
    "oxygen": ("medical", ["oxygen", "ஆக்சிஜன்", "oxígeno", "sauerstoff"]),
    "boat": ("rescue", ["boat", "படகு", "bote", "boot", "padagu"]),
    "drinking water": ("water", ["water", "தண்ணீர்", "குடிநீர்", "agua", "wasser", "thanni", "thanneer"]),
    "food": ("food", ["food", "சாப்பாடு", "உணவு", "comida", "essen", "saapadu", "unavu"]),
    "medicine": ("medical", ["medicine", "மருந்து", "medicina", "medikament", "marunthu"]),
    "shelter": ("shelter", ["shelter", "தங்குமிடம்", "refugio", "unterkunft"]),
    "blanket": ("supplies", ["blanket", "போர்வை", "manta", "decke"]),
    "generator": ("power", ["generator", "ஜெனரேட்டர்", "generador"]),
    "pump": ("supplies", ["pump", "பம்ப்", "bomba", "pumpe"]),
    "transport": ("transport", ["transport", "வாகனம்", "transporte", "fahrzeug"]),
}
INJECTION = re.compile(r"ignore (?:your|all|previous|the) instructions|system prompt|reveal (?:your|the)|api[_ ]?key|jailbreak|<\|system", re.I)
RUMOUR = re.compile(r"rumou?r|unverified|alternative emergency|fake emergency|வதந்தி|número alternativo|gerücht", re.I)


def language_of(text: str) -> str:
    lower = text.casefold()
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    if any(w in lower for w in ("necesito", "ofrezco", "tenemos", "agua", "insulina", "comida", "bote", "refugio")):
        return "es"
    if any(w in lower for w in ("brauche", "biete", "wasser", "pumpe", "helfen", "keller", "boot")):
        return "de"
    if any(w in lower for w in ("venum", "irukku", "thanni", "saapadu", "padagu", "thevai")):
        return "ta"
    return "en"


def extract_fallback(text: str) -> Extraction:
    lower = text.casefold()
    lang = language_of(text)
    base = {"language": lang, "message_en": redact(text)[:200], "contains_contact_info": redact(text) != text, "confidence": 0.35}
    if INJECTION.search(text) or any(w in lower for w in ("buy now", "discount", "sale", "advertisement")):
        return Extraction(**base)
    flagged = bool(RUMOUR.search(text))
    resource = next(((canonical, category, word) for canonical, (category, words) in SYNONYMS.items() for word in words if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", lower)), None)
    if flagged:
        return Extraction(**base, intent="info", category="info", possible_misinformation=True, item="Unverified report", item_en="unverified report")
    if not resource:
        return Extraction(**base)
    canonical, category, original = resource
    offer = bool(re.search(r"\b(offer|offering|available|have|can provide|can help|biete|ofrezco|tenemos|irukku)\b|கிடைக்கும்|உள்ளது|தருகிறோம்|வழங்க", lower))
    need = bool(re.search(r"\b(need|needed|need(ed)?|help|trapped|urgent|require|necesito|necesitamos|brauche|brauchen|venum|thevai)\b|வேண்டும்|தேவை|சிக்கி", lower))
    if not offer and not need:
        return Extraction(**base)
    flags = [flag for flag, words in {"medical": ["insulin", "oxygen", "இன்சுலின்"], "elderly": ["elderly", "முதிய", "anciano", "ältere"], "child": ["baby", "infant", "child", "குழந்தை", "bebé", "kind"], "pregnant": ["pregnant", "கர்ப்பிணி", "embarazada"], "disabled": ["disabled", "wheelchair", "மாற்றுத்திறனாளி"]}.items() if any(word in lower for word in words)]
    urgency = 1 if offer else 5 if canonical in {"insulin", "oxygen"} or any(w in lower for w in ("trapped", "drowning", "சிக்கி")) else 4 if flags else 3 if category in {"food", "water", "shelter", "medical", "rescue"} else 2
    place = local_place(text)
    quantity = re.search(r"\b(\d{1,4})\s+(?:bottles|litres|meals|boats|blankets|people)\b", lower)
    return Extraction(**base, is_actionable=True, intent="offer" if offer else "need", category=category, item=original, item_en=canonical, quantity=int(quantity[1]) if quantity else None, location_text=place["name"] if place else "", urgency=urgency, urgency_reason="Rule-based triage; coordinator verification required", vulnerable_flags=flags, romanized=lang == "ta" and not bool(re.search(r"[\u0b80-\u0bff]", text)), ack_text=acknowledgement(lang, not place))
