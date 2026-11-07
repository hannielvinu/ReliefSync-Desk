# Tamil review worksheet

Status: wording and technical consistency checked during implementation; **independent native-speaker review pending**. Do not describe this as native approval.

The complete UI review list is `strings.ta` in `static/js/i18n.js`. The corresponding English dictionary is adjacent. Backend acknowledgements are in `app/i18n.py`; approved notification wording is in `app/matcher.py`. Review all three, including narrow-screen line wrapping and Tamil glyph display. Self-hosted Noto Sans Tamil is provided.

| English meaning | Current Tamil | Review focus |
| --- | --- | --- |
| Volunteer coordination | தன்னார்வலர் ஒருங்கிணைப்பு | Natural for a dispatch coordinator |
| Request board | தேவைகள் பலகை | Should include offers without confusing users |
| Suggested connections | பரிந்துரைக்கப்பட்ட இணைப்புகள் | Human-review implication |
| Need / offer | தேவை / உதவி | Offer means help available, not commercial offer |
| Approve / reject | ஒப்புதல் அளி / நிராகரி | Clear action wording |
| Critical / high urgency | மிக அவசரம் / அதிக அவசரம் | Clear separation of urgency levels |
| Approximate locations only | தோராயமான இருப்பிடங்கள் மட்டும் | Privacy implication |
| Simulated data | கற்பனைத் தரவு | Clearly fictional, not real rescue data |
| Start drill | பயிற்சியைத் தொடங்கு | Avoid suggesting a real emergency |
| Share pin / landmark | உங்கள் இருப்பிடப் புள்ளி அல்லது அருகிலுள்ள அடையாள இடத்தைப் பகிரவும். | Common Telegram terminology |
| Not an emergency service | இது அவசர சேவை அல்ல. முதலில் உள்ளூர் அவசர சேவையைத் தொடர்புகொள்ளவும். | Understandable and unambiguous |
| Approved notification | ஒருங்கிணைப்பாளர் ஒப்புதல் அளித்துள்ளார். உதவியை உறுதிசெய்ய இருவரும் தனியாகத் தொடர்புகொள்ளவும். இது அவசர சேவை அல்ல. | Does not promise rescue or verified identities |

Record reviewer name/consent, date, dialect preference, keys checked, corrections and unresolved concerns. Do not publish reviewer personal details without permission. Test corrected strings at 360px and in the Telegram mobile app. Fixes should preserve the safety meaning, not merely shorten labels.
