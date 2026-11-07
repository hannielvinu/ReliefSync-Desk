# Demonstration scripts

Use only fictional requests. State that the demo is not an emergency service and name the extractor actually running. The local video is a silent simulated walkthrough, not proof of a deployed bot.

## Three-minute live presentation

| Time | Action / narration |
| --- | --- |
| 0:00–0:25 | “During Chennai’s December 2023 floods, residents reported busy or unanswered civic helplines. Volunteers also faced repeated requests and coordination difficulties.” Show the sourced About page links. Do not imply partnership or official integration. |
| 0:25–0:45 | Show the fictional group messages or explain their multilingual, unstructured nature. “The coordinator needs a usable queue, not another chat to read.” |
| 0:45–1:10 | Dashboard → 10× → Run drill. Point out Simulated, demo-mode notice and current extractor badge. “These are synthetic messages. Today this is [Fallback / configured provider], as the cards show.” |
| 1:10–1:30 | Open the insulin need. Show location source, capped fallback confidence, urgency and redacted original message. Show the repeat-count chip and separate incident clusters if present. |
| 1:30–2:00 | Expand the insulin match’s breakdown and exact notification preview. “A suggestion changes no real-world commitment. A person reviews and confirms it.” Approve. |
| 2:00–2:20 | For simulation show `would_send`. With a separately configured real test group, show the actual approved notification. Never substitute the preview for a real-delivery claim. |
| 2:20–2:40 | Show stats, optional self-reported country counts, and `/eval`. Identify the synthetic dataset and extractor used. Do not call simulated participants real adoption. |
| 2:40–3:00 | Show Safety and close: “A compact dispatch co-pilot, with human judgment before every connection. The prototype does not verify volunteers or replace emergency services.” |

## Two-minute narrated video

0:00–0:15 — Problem and source: Chennai helpline access and coordination difficulty, with source link visible.

0:15–0:35 — Run drill. “Fictional Tamil, Tanglish, English, Spanish and German messages enter a shared desk.”

0:35–0:55 — Open insulin card. “A structured card shows resource, urgency, confidence and approximate location; repeated reports are grouped.”

0:55–1:20 — Show compatible insulin offer, score and preview. Approve, then complete. “Only human approval can authorise a notification. This simulated pair would send nothing to real Telegram.”

1:20–1:40 — Show evaluation and extractor disclosure. “This is a synthetic smoke benchmark, not a field-accuracy claim.”

1:40–2:00 — Show Join, Safety and public URL once deployed. “Volunteer identities still need verification. This is not an emergency service.”

To generate a silent local walkthrough with the running server:

```bash
python scripts/screenshots.py --record
```

Output `reports/demo-walkthrough.webm` is ignored by Git. Add voice narration or record a separate final video after deployment. If a submission portal requires MP4 or a video-hosting URL, convert/upload the recording using your account. Never label the local recording as a live Vultr/Telegram verification.

## Fallback plan

If the provider fails, keep the visible fallback label and explain the limited rules. If Telegram or internet is unavailable, run the offline drill and show the notification preview as a preview. If the app cannot start during presentation, use screenshots in `docs/screenshots/` or the recorded local walkthrough and state it is prerecorded. Map tiles require internet but the request board remains usable.

Evidence links: [The News Minute](https://www.thenewsminute.com/amp/story/tamil-nadu/chennai-floods-helplines-inundated-people-struggle-to-contact-authorities), [DT Next volunteer coordination](https://www.dtnext.in/news/city/volunteers-the-undying-spirit-of-chennai-soars-on-social-media-753635).
