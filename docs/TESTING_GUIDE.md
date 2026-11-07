# Controlled storm-drill testing

The checked-in fixtures are simulated. No student cohort, international adoption or field deployment has been claimed.

## Invite 20–50 consenting students

Create a Telegram test group with a clear simulated-drill name and an explanation of what is stored, what becomes public, optional country reporting and `/forget`. Invite participants from several countries if available; do not invent countries or count nationalities from names/language. Provide the real deployed desk URL only after deployment and checks. Collect consent before posting any non-fictional information; prefer fictional needs exclusively.

Assign a few participants to each language: Tamil, Tanglish, English, Spanish and German. Ask each to post one concrete fictional need and another participant to post a nearby compatible offer. Examples are on `/join`. Include missing locations, a location-pin follow-up, an edited request, a same-sender duplicate, incompatible resources, distant localities, chatter and an obvious unverified rumour. Use only fake contact placeholders, not working telephone numbers. Never call an emergency number as part of testing.

One coordinator observes the board, confirms resource/location/urgency accuracy, and approves only verified fictional pairs. Ask senders to confirm the resulting mention and the absence of precise addresses. Test completion and `/forget`. Reset built-in simulated records separately; real Telegram tester records are not removed by demo reset.

## Feedback questions

- Did the desk recognise the need/offer, resource and language correctly?
- Was the location accurate enough without revealing a private address?
- Did the urgency make sense? Was the confidence/fallback label clear?
- Were duplicate reports grouped correctly? Did unrelated requests remain separate?
- Was the preview understandable before approval? Did the real notification arrive once?
- Could you use mobile tabs, keyboard controls and the details drawer?
- Was Tamil wording natural? Record the exact key/text and proposed correction in `docs/TAMIL_REVIEW.md`.

Set `FEEDBACK_URL` to a form you own, or use GitHub issues without personal information. Record observations and failures as well as successes. Do not turn positive informal comments into fabricated testimonials.

## Reading reach counters

`participants` counts hashed sender records, including fictional drill participants. `simulated_participants` is returned separately by `/api/stats`. Counts are not verified unique people. `/iam <country>` is optional and self-reported; country spelling is normalised for basic casing but not verified against a national registry. Country counts are distinct entered strings, not proof of geographic reach.

## Honest run log

For each session record date/time, commit SHA, deployed URL (if any), extractor configuration/mix, number of consenting test accounts, languages, tested transitions, failures and follow-up changes. Keep sensitive messages out of the log. Separate automated synthetic evaluation, mocked provider/Telegram tests, local browser checks and live integration checks. The real evaluation report comes only from `python scripts/eval.py`.
