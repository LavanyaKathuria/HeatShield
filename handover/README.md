# Alerting — handover

**Archive:** the active WhatsApp implementation now lives in `src/alerts/`.
Follow [current setup](../docs/WHATSAPP_ALERTS.md), including explicit opt-in,
production templates and the persistent dispatch ledger. The notes below describe
the earlier handover and are preserved for historical context.

The alerting layer was removed from the running system so it can be built
separately. **The code and content here are complete and working** — they were
running end to end before being lifted out. Nothing here needs rewriting from
scratch; it needs reconnecting.

## What's in here

| file | what it does |
|---|---|
| `advisories.py` | The advisory catalogue: which message applies to which audience at which level, plus lead-timed institutional checklists |
| `engine.py` | Targeting. Decides who receives what, based on the groups a household actually contains, and picks channels |
| `render.py` | Turns keys + language into the exact text per channel (SMS segment budget, WhatsApp formatting, voice scripts) |
| `dispatch.py` | WhatsApp delivery via the Twilio Sandbox. Dry-run by default |
| `advisory-content/{en,hi,gu}.json` | ~160 keys × 3 languages. The genuinely expensive part — written to be acted on, with a number or a time in every instruction |

## What it still depends on

Only two things, both still live in the main codebase:

```python
from src.risk import levels     # group_levels(), overall_level(), LEVEL_RANK
from src.risk import scenario   # replay() - real past heatwaves for testing
```

`src/risk/levels.py` already computes a per-group level for every ward and
every forecast day. `weather_pipeline` writes it to `group_levels` on each
row, and the API returns it. **So the hard part — deciding when and for whom
an alert is warranted — is done and running.** What was removed is only the
part that turns that decision into a message and sends it.

## Reconnecting it

1. Move these files back to `src/alerts/` (keep `advisory-content` as
   `src/alerts/content`).
2. Fix the imports: they reference `src.alerts.triggers`, which is now
   `src.risk.levels`. The function names are unchanged.
3. Re-add the API endpoints — `/alerts/preview`, `/alerts/institution`,
   `/alerts/opt-in`. They were deleted from `src/api.py`; git history has them.
4. `pip install twilio` and create `.env`:
   ```
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   TWILIO_SANDBOX_JOIN_CODE=join <your-code>
   ```

## Things worth not relearning the hard way

- **Devanagari and Gujarati cost 70 characters per SMS segment, not 160.**
  `render.py` already accounts for this; a message sized for Latin script
  silently becomes three times as expensive or gets truncated by the carrier.
- **Voice scripts are written separately, never the SMS text read aloud.** A
  listener cannot re-read a sentence, so the scripts lead with the action and
  repeat the key instruction at the end. "108" is spelled out as words so it
  is unambiguous over a phone line.
- **Every replayed or test message must be labelled as a drill**, in the
  recipient's language, at the top. `dispatch.py` enforces this rather than
  leaving it to discipline — a realistic emergency warning that isn't real is
  something people act on.
- **`dry_run` defaults to True.** Forgetting the flag gives a preview, not a
  message.
- **The Twilio Sandbox join code is a sandbox limitation, not a product
  step.** A real WhatsApp Business sender needs no join phrase; the number
  given at signup is enough. `dispatch.opt_in_instructions()` returns `None`
  when no join code is configured, so the UI can drop the step automatically.

## What was never built

- SMS and voice delivery. Both payloads are produced by `render.py`; only the
  transport is missing. SMS in India needs DLT registration under the
  deploying organisation's own entity — not something a prototype can
  shortcut. Fast2SMS's ILDO route works without it if you need a demo.
- The 36 voice recordings (12 scripts × 3 languages). Recording them with a
  native speaker beats text-to-speech, and Gujarati TTS is not supported by
  the voices behind Twilio at all.
- A dispatch/delivery log. `engine.alert_fingerprint()` and
  `suppress_already_sent()` exist for deduplication but nothing persists what
  actually went out.
