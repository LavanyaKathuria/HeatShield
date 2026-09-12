# WhatsApp alerts

The running implementation is in `src/alerts/`. The original `handover/` is an
archive. English, Hindi and Gujarati messages reuse its complete advisory catalogue.

## Behaviour

- Positive EHF and the existing per-group risk thresholds gate all alerts.
- Watch appears on the dashboard only, following slide 5. WhatsApp starts at Warning.
- Targeting uses the citizen's age, outdoor work and family members. Dependents with
  another ward receive that ward's advice at the account owner's WhatsApp number.
- Each contiguous heat event produces the highest forecast level per group. A more
  specific household advisory replaces a redundant general advisory.
- A durable SQLite ledger suppresses repeats per recipient, phone, ward, group and
  event. It permits escalation, retries after confirmed failure, and new events.
- Forecast revisions with overlapping or adjacent event dates share an event ID.
  A quiet day separating two windows starts a new event. Missing event data is an
  error, never an implicit all-clear.
- Alert language is saved separately from the dashboard language switcher.
- The scheduler skips people who have not explicitly enabled WhatsApp. Disabling
  and saving preferences opts out of future scheduler runs.

The slide deck also proposes voice, SMS, gap alerts and automatic institutional
actions. Those transports/actions are outside this WhatsApp implementation. The
current risk model reaches Danger; it does not invent a new Extreme threshold.
The renderer supports Extreme if the risk model introduces it later. No zone-level
death counts or hospitalisation predictions were added.

## Setup

1. Install backend dependencies: `pip install -r requirements.txt`.
2. Apply `frontend/supabase/alerts.sql` in your existing Supabase SQL editor. New
   projects must apply `frontend/supabase/schema.sql` first. This migration adds
   opt-in and its timestamp; existing users start opted out.
3. Copy `.env.example` to `.env` in the repository root. Supply backend Supabase
   URL/anon key and Twilio credentials. The worker also requires a Supabase
   service-role key to read enrolled profiles and dependents. Keep that key in
   backend secret storage only, never any `VITE_` variable or tracked file.
4. Start the backend and frontend normally. Save the account's WhatsApp number,
   language and explicit consent. Corporate signup collects consent. Individual
   consent can be saved using authenticated `POST /alerts/preferences`; the alerts
   panel does not contain duplicate preference inputs. Existing accounts remain
   opted out until consent is saved.
5. For sandbox testing, configure the join phrase from the Twilio console and send
   it from the enrolled number to the sandbox sender. Sandbox free-form messages require
   a user-initiated 24-hour messaging window. Consent alone does not open it.

All commands below run from the repository root. They load root `.env`; existing
shell environment values take precedence.

## Preview

No account or provider configuration is needed for historical previews:

```bash
python scripts/dispatch_alerts.py --scenario may_2024 --language gu
python scripts/dispatch_alerts.py --scenario may_2010 --language hi
python scripts/dispatch_alerts.py --scenario may_2016 --language en
```

These run recorded heatwaves through the real model and prefix messages with a
localized historical replay label. `--scenario` cannot be combined with `--send`.

Preview the current forecast for opted-in accounts:

```bash
python scripts/dispatch_alerts.py
```

Previews do not contact Twilio or reserve delivery records. They print message
bodies, which can include saved profile and dependent names; keep preview output
private. Phone numbers are not printed. `GET /alerts/me` is a read-only preview
for the signed-in user's household, using their Supabase access token and RLS.
`POST /alerts/preferences` updates only that user's profile. The authenticated
`POST /alerts/demo` previews by default and can send only to the user's own
opted-in phone in sandbox mode. There is no unauthenticated send
route. Both account types can send their own sandbox demonstration; neither can
choose another account's recipient. The client-side role switcher grants no privileges.

## Delivery and scheduling

### Built-in automation and dashboard demonstration

Set `ALERTS_AUTOMATION_ENABLED=true` and start the normal FastAPI server. HeatShield
checks on startup (unless a persisted next-run time is still pending), then every
minute. Profile and family changes are picked up on the next check; weather uses
the existing three-hour cache and is recomputed when stale. It refreshes stale forecasts, evaluates opted-in households and
dispatches only qualifying alerts. The dashboard shows the last check and outcome.
A database lease avoids duplicate scheduler runs across API processes. No external
cron job is needed. The computer and backend must stay running; this does not
install an OS-startup service.

The dashboard's **Historical heatwave** navigation control runs May 2024 through
the actual model and household targeting. Activating it automatically sends eligible
historical alerts to your saved, opted-in phone in your saved language. Deliberate
repeat activations have a 60-second cooldown. Historical events have separate
identities so they cannot suppress future live warnings. **Check delivery status**
reads Twilio's actual delivery state without sending another message.

`WHATSAPP_LIMITS_ENABLED=true` enables the optional local caps. Set it to
`false` if demonstration accounts should not share a limited local
allowance. Duplicate suppression and opt-in still apply. When caps are enabled,
`WHATSAPP_DAILY_LIMIT=3` and `WHATSAPP_TOTAL_LIMIT=10` cap new provider attempts
since this guard was installed. Failed/uncertain requests count too. The total
does not reset on restart or the next day. Atomic reservations apply to scheduler,
CLI and dashboard sends. Previews and delivery-status reads use no outbound units.
These caps are **not** your Twilio free-unit balance: earlier tests, inbound traffic
and sends outside HeatShield are not counted. Check Twilio's Free units tracker
for the actual allowance: [Twilio trial WhatsApp](https://www.twilio.com/docs/usage/trials/try-out-whatsapp).

Recipients come from each user's saved profile phone; there is no single-number
allowlist. Signup saves the phone and chosen alert language (English by default).
After signing in, enable WhatsApp consent in preferences and save. Changing the
saved number or language changes subsequent delivery for that account. Each demo
request uses the verified signed-in user's profile, never a caller-supplied number.
Every recipient must join the Twilio sandbox from their own phone. The reply
window still applies: message the sandbox before presenting. The sandbox contact
will remain Twilio's sender; HeatShield is identified in the body and the visible
application preview, dispatch and delivery history. A custom sender display name
requires a registered production sender.

Set `ALERTS_AUTOMATION_ENABLED=false` and restart to disable automatic checks.
Enable limits and set either message cap to `0` to block provider sends, including demonstrations.
Do not delete the database or budget table to reset a limit.

### Optional standalone scheduler

After reviewing a preview and setting up the sender:

```bash
python scripts/dispatch_alerts.py --send
python scripts/reconcile_alerts.py
```

The first command sends actual messages. If not using built-in automation, run it every three hours with Windows
Task Scheduler or cron, with the repository root as the working directory. The
forecast cache refreshes when stale. Run reconciliation every few minutes to
update queued/sent records to provider-confirmed delivered/read/failed states.
Standalone jobs are not automatically installed. Avoid enabling both scheduling
methods: reservations prevent duplicates, but redundant workers waste API calls.

Keep `ALERTS_DB_PATH` on a persistent local volume shared by the API and worker.
Do not use separate databases per process or ephemeral containers. The SQLite
reservation transaction prevents two workers reserving the same alert at once.
For deployment across multiple hosts, migrate this ledger to PostgreSQL first.
The database contains phone numbers and advisory bodies; limit filesystem access
and define retention for your deployment.

An interrupted reservation or network timeout stays `reserved` or `unknown`.
It is deliberately not retried automatically: the provider may have accepted it.
Inspect Twilio logs, attach a confirmed message SID and status in the ledger, or
mark it failed only after confirming no message was accepted. Known provider
failure permits retry on the next run. Do not delete the ledger to resolve errors.

## Production templates

WhatsApp requires active opt-in and pre-approved templates for business-initiated
messages outside the 24-hour reply window. These requirements also apply to the
sandbox; a join phrase is not permanent permission to send arbitrary text.
See [Twilio's WhatsApp documentation](https://www.twilio.com/docs/whatsapp/api).

1. Register your production WhatsApp sender in Twilio.
2. Run `python scripts/export_whatsapp_templates.py` to get the 36 proposed text
   templates (3 languages, 4 audiences, 3 outbound levels). Submit the needed
   templates for approval in Twilio Content Template Builder. Use each language's
   text as exported; configure variable samples for ward, date and timing label.
3. Set `WHATSAPP_MODE=production`, set the production sender number, and fill
   `WHATSAPP_TEMPLATES` with the returned Content SIDs, for example:
   `{"en.elderly.warning":"HX...","hi.elderly.warning":"HX...","gu.elderly.warning":"HX..."}`.
   Add every group/level/language you intend to send. Missing mappings fail visibly.

Variables are `{{1}}` ward ID, `{{2}}` ISO forecast date, and `{{3}}` localized
"Today" or "Forecast for". Advisory actions remain static approved content,
not an arbitrary message inserted into a template variable. If advisory copy
changes, update and approve corresponding templates before deployment; provider
template content cannot be verified locally. Replays are blocked in production.

## Checks performed

`python -m pytest tests -q` covers the model plus targeting, all three advisory
catalogues, event gating, per-dependent wards, deduplication across restarts,
escalation, opt-out, previews and mocked Twilio template transport.
`npm run build` in `frontend/` checks TypeScript and production bundling.

Actual Supabase migration, live recipient delivery and template approval require
your configured external accounts. They are not simulated as completed.


## Shared sandbox phones and corporate accounts

Several profiles may intentionally save the same sandbox-connected number.
Delivery identity includes the profile ID, so those profiles never suppress each
other's warnings. Each message includes the profile/institution name; household
advice also names the affected family members. The account's saved language is
used, defaulting to English. All transport requests share a three-second send
spacing. Long institutional checklists are split at action boundaries.

Individual profiles use saved age and outdoor-work status. Age 0-14 selects child
advice; 65+ selects elderly advice. Outdoor work is an independent group. Family
members contribute their own age/work groups; their selected ward overrides the
account ward, otherwise they inherit it. Advice goes to the account phone, not a
separate family-member phone. The family form accepts newborn age zero.

Hospitals, schools, PHCs and city administration now participate in automatic
WhatsApp dispatch. The alerts tab uses the saved account preferences; it no longer
duplicates profile inputs. Corporate signup accepts language and consent.
Schools use the child threshold. Other institutions receive the appropriate
heat-action checklist at the overall event level, with due dates. A city-admin
account without a ward receives one citywide checklist (possibly split into
parts), using the highest group levels across wards; it does not receive 48 copies.

Corporate phone and organization details stay in `corporate_accounts`. Language
and WhatsApp consent use Supabase Auth user metadata so existing installations
need no additional SQL migration. The API verifies the session and corporate row;
user-editable metadata is used only for preferences, never for authorization.
Individuals continue using their existing `profiles` preference columns.

Use the account's saved WhatsApp consent, phone and language (English by default).
Use one of the 2-3 joined sandbox numbers in each account. Those phones still
need to open a 24-hour reply window. No join phrase is sent by HeatShield itself.

Failed or undelivered sends have a three-hour retry cooldown, so a closed sandbox
reply window does not cause send attempts every minute. Successful messages remain
deduplicated for the event; uncertain sends remain reserved for reconciliation.

The automatic loop uses LIVE weather only. It does not invent warning conditions
for a presentation. Quiet days send nothing; missing event data is an error.
Historical previews remain separately labelled demonstrations, never inserted
into the live forecast cache or automatic live dispatch.

### Dashboard historical replay

Both dashboards have a **Historical heatwave** navigation button (immediately
before Weather / Heat Risk on the corporate dashboard). Activation switches all
weather, map, event, mortality and advisory queries to `source=may_2024`. The
five-day window is 21–25 May 2024 and opens on 23 May, the highest stored UTCI
(52.3°C) in `data/cleaned/utci_daily_history.csv` (1995–2024). This is a UTCI-based
selection, not a claim about the highest EHF or observed deaths.

The archive contains citywide weather, which is applied uniformly across current
ward boundaries. The common live risk pipeline computes the model's citywide
excess mortality estimate (~290 over this window), with its model uncertainty
range. This is not an observed death toll and ward estimates must not be summed.
The banner discloses these limitations. Historical data stays out of the live
forecast cache; returning to live restores current queries and the first day.

Activation also posts to authenticated `POST /alerts/replay`, which loads only
the current user's saved profile, consent, number, language and family members.
It automatically sends eligible group/institution checklists using the same
historical records displayed in the dashboard. No separate send button is
required. Delivery requires sandbox mode, a joined number and an open reply
window. Messages carry a short translated historical replay label instead of the
large test-message notice. Individual WhatsApp alerts contain two priority
actions, retaining the emergency-call action where present. Full advisories and
reasoning remain available in the dashboard; institutional checklists stay full.
Dispatch deduplicates each
account/phone/language/ward/group/event separately from normal live sends, so
rapidly re-entering replay does not duplicate successful alerts. A deliberate
new activation after 60 seconds can send another historical demonstration.
Pending or uncertain deliveries stay protected until reconciled; live alerts
retain event-level duplicate suppression.
Refreshes and GET requests never send. The background scheduler continues live
monitoring; replay is a deliberate per-account activation, not a global switch.
