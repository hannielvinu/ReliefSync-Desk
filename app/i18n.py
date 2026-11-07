ACKS = {
    "en": "Recorded for volunteer review. Not an emergency service.",
    "ta": "தன்னார்வலர்கள் பரிசீலிக்கப் பதிவு செய்யப்பட்டது. இது அவசர சேவை அல்ல.",
    "es": "Registrado para revisión de voluntarios. No es un servicio de emergencias.",
    "de": "Zur Prüfung durch Freiwillige erfasst. Kein Notfalldienst.",
}
LOCATION = {
    "en": "Please share a location pin or the nearest landmark.",
    "ta": "உங்கள் இருப்பிடப் புள்ளி அல்லது அருகிலுள்ள அடையாள இடத்தைப் பகிரவும்.",
    "es": "Comparte tu ubicación o un punto de referencia cercano.",
    "de": "Bitte teile deinen Standort oder einen nahen Orientierungspunkt.",
}


def acknowledgement(language: str, location_missing: bool = False) -> str:
    return (LOCATION if location_missing else ACKS).get(language, (LOCATION if location_missing else ACKS)["en"])
