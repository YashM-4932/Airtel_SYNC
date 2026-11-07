# Audit fixes: what changed, how it was checked, what is left

This file answers two audits of the code in this folder:

* **Round 1**, `AUDIT_REPORT.md`: 45 findings, F-01 to F-45.
* **Round 2**, *Project Udyam Digital: Engineering, Logic & Security Audit* (42 pages): 39 findings (7 High, 15 Medium,
  10 Low and 7 more from its judge-style stress test), plus its notes on potential vulnerabilities.

The order of work is in `ROADMAP.md` and a log of each work package is in `FIX_LOG.md` (both in this folder).

## At a glance

| | Round 1 | Round 2 |
| --- | --- | --- |
| Findings | 45 | 39 |
| **Fixed** (a test or a browser check shows it) | **42** | **38**: 15 had already been fixed in round 1 and are now pinned with the second audit's own reproduction; 23 were fixed in round 2 |
| **Mitigated** (remainder stated below) | **2**: F-10, F-32 | **1**: ADV-05 (regional languages without an LLM key) |
| **Documentation, decision left to you** | **1**: F-45 (the real "airtel" name) | none |
| Tests | 192 in `tests/test_audit_fixes.py` | 117 in `tests/test_audit2_fixes.py` |

The whole suite: **382 tests pass** (the original 73, 192 for round 1, 117 for round 2). The failures the second audit
reported in its 15 judge-style scenarios (11 of them failed with the language model off) no longer occur; each scenario
has a test.

```
python3 -m pytest -q                 # whole suite, about 30 s, 382 passed
python3 -m pytest -q -k f23          # the tests for round-1 finding F-23
python3 -m pytest -q -k kyc01        # the tests for round-2 finding KYC-01 (ids lower-case, without the dash)
```

Status legend: **Fixed**, **Mitigated**, **Docs**.

## Round 1: the code audit (F-01 to F-45)

### Critical

| ID | What was wrong | What changed | Files | Status |
| --- | --- | --- | --- | --- |
| F-01 | `12 staff` also set 12 locations | Number spans already used (people, sites, money, units) are skipped; a bare number fills only the slot still empty | `advisor/extract.py` | Fixed |

### High

| ID | What was wrong | What changed | Files | Status |
| --- | --- | --- | --- | --- |
| F-02 | "I do not have GST" read as "I have GST" | Clause-based yes/no reader: negation beats affirmation, "not sure" is no answer, `do not`, `don't`, `no GST` all work | `advisor/extract.py` | Fixed |
| F-03 | A customer who claimed GST was stuck at KYC | New "I don't have a GST registration" step. The server answers 409 `confirm_requote` with what would come out (GST-only products, swaps for link products, old and new total); only after `{"confirm": true}` is the order re-priced. Refuses if nothing would be left | `journey/orders.py`, `app.py`, `static/journey.js` | Fixed |
| F-04 | Nothing tied the person ordering to the documents | New check `id.orderer`: the ID holder must be the person ordering (or the proprietor), else the order goes to a person and the customer sees only "a team member will confirm". A mobile check (code by SMS, mocked) is needed before an order is placed | `journey/checks.py`, `journey/otp.py` (new), `journey/orders.py`, `app.py`, `static/journey.js` | Fixed |
| F-05 | Hindi "yes" ignored in default mode | Unicode-aware tokenising (Devanagari) in the same reader as F-02; Hindi cases are in the F-02 test | `advisor/extract.py` | Fixed |
| F-06 | A cheaper plan inside the budget was hidden and the warning said the opposite | The essentials plan is offered if it saves 15% or more, or is the only one inside the budget. The "floor" warning appears only when nothing fits | `advisor/engine.py` | Fixed |
| F-07 | Staff "cancel" did not delete KYC data | One `_purge()` used by staff cancel and by consent withdrawal | `journey/orders.py` | Fixed |
| F-08 | The server log held the customer's chat text | The per-turn log line carries intent, source, length and the *kinds* of identifier found; never text | `advisor/dialogue.py` | Fixed |
| F-09 | Raw chat could reach the LLM; redaction missed normal Indian formats | `redact()` rewritten: spaces, hyphens, dots, `+91`/`0` prefix, NFKC. `Extraction.redacted` is the only text allowed to leave the server; the Q&A fallback never sends the raw message | `advisor/privacy.py`, `dialogue.py`, `profile.py`, `extract.py` | Fixed |

### Medium

| ID | What was wrong | What changed | Files | Status |
| --- | --- | --- | --- | --- |
| F-10 | 8 regional languages got English and nothing was understood without an LLM key | One-time notice in the chat when the language has no templates and no LLM is set; the language list marks those languages (from `/api/config`); README feature row corrected. Regional replies still need an LLM key (see limits) | `advisor/dialogue.py`, `narrate.py`, `i18n.py`, `app.py`, `static/app.js`, `README.md` | Mitigated |
| F-11 | Negation removed needs the customer asked for | Word boundary on negation words; "cannot work without X" and "no downtime" read as requirements | `advisor/extract.py` | Fixed |
| F-12 | Ordinary words became the monthly budget | A money cue is required (₹, Rs, budget, per month, lakh, k); Mbps, metres, sq ft, days are rejected; current spend is kept apart | `advisor/extract.py` | Fixed |
| F-13 | The longest city name anywhere won | A city after in/at/near (or Hindi में) wins, else the last one named; a longer name beats a name inside it | `advisor/extract.py` | Fixed |
| F-14 | Any short non-answer became the city or business type | Non-answer lists plus a check against known places | `advisor/extract.py`, `taxonomy.py` | Fixed |
| F-15 | "clinic" not recognised | Generic Clinic type | `advisor/taxonomy.py` | Fixed |
| F-16 | Unknown towns quoted as tier 2; metro suburbs lost tier-1 products | Metro suburbs (Thane, Howrah, Secunderabad and others) count as tier 1. An unknown town is marked `tier_assumed`, the wording says "we may not serve", staff see a flag, and such an order is never auto-verified | `advisor/taxonomy.py`, `engine.py`, `journey/orders.py` | Fixed |
| F-17 | Budget compared with the price before GST | Compared with the GST-inclusive monthly amount; the UI says "GST included" | `advisor/engine.py`, `static/app.js` | Fixed |
| F-18 | A late `/api/quote` answer overwrote the bill | Sequence guard drops stale answers; add-on switches move at once; the total is dimmed and "Continue" is disabled while a quote is in flight | `static/app.js`, `styles.css` | Fixed |
| F-19 | `POST /api/orders` not idempotent; Browser Back made a second order | Server: same cart and contact in one session returns the same order and token; earlier never-started orders are superseded. UI: checkout is replaced in the history after ordering | `journey/orders.py`, `app.py`, `static/journey.js` | Fixed |
| F-20 | An expired advisor session could still place an order | `peek()` honours the 3-hour limit; periodic, size-capped prune | `advisor/dialogue.py` | Fixed |
| F-21 | "Withdraw consent" left personal data behind | Same `_purge()` as F-07: document data, "not registered" declarations, full Udyam number, GSTIN on the order, lead link, contact name. Kept: order, plan, status history, mobile number, consent record | `journey/orders.py` | Fixed |
| F-22 | A GSTIN typed in chat linked someone else's lead | A lead is linked only from registry-confirmed identifiers on uploaded documents; the propensity score is recomputed then | `journey/orders.py`, `crm.py` | Fixed |
| F-23 | `names_match` treated different people as the same | Word-by-word comparison, OCR look-alikes (0/o, 1/l/i, 5/s, 8/b, rn/m) and word order accepted. An initial, a missing middle initial or one slip in a word of 8+ letters is "near" and goes to a person. Titles (Dr, Shri, Smt, M/s) ignored. The six pairs the audit showed passing (Ramesh/Rakesh, Kavita/Savita, …) are now different | `journey/extract.py`, `checks.py` | Fixed |
| F-24 | Weak bomb and PDF guard; no upload rate limit | Pixel count checked before any decoding (25 MP). PDF page size read first (over 50 in refused) and render scale lowered to stay under 12 MP. All decoder errors become "unreadable", never a 500. New customer code `image_too_large`. Uploads limited per address (`UPLOAD_RATE`) | `journey/ocr.py`, `orders.py`, `app.py`, `advisor/config.py` | Fixed |
| F-25 | Uploads over 1 MiB were written to disk | The multipart parser keeps files up to the upload cap in memory (checked with a spy: a 3 MiB photo causes no disk event). New `BodyLimit` middleware stops a request before it is read, by `Content-Length` and by counting bytes of chunked bodies; other API bodies are capped at 256 KiB | `app.py` | Fixed |
| F-26 | Event times were a fixed demo date plus wall-clock time | Real UTC. `APP_TODAY` is used only for document-date rules | `journey/orders.py` | Fixed |
| F-27 | The plan-explanation guard let invented promises, SLAs and non-plan products through | `ungrounded()` checks summary, item reasons, excluded reasons and messages: contact details, numbers not in the facts, promise words (English and Hindi), products never sold, products outside the plan | `advisor/narrate.py` | Fixed |
| F-28 | The price guard checked "a number somewhere in the catalogue" | `_money_ok` checks amounts against the product(s) asked about; understands "99 rupees", "12k", "1.2 lakh", amounts in words. No matched product means no amounts. Q&A also gets the number, promise and contact guard | `advisor/narrate.py` | Fixed |

### Low

| ID | What was wrong | What changed | Files | Status |
| --- | --- | --- | --- | --- |
| F-29 | A different unit number on the same street and PIN matched | House and unit numbers must match exactly (3B is not 3C; 199 is not 191, 99, 19 or 299); the rest of the address stays fuzzy | `journey/extract.py` | Fixed |
| F-30 | `5 logistics partners` set the head-count | `(?!\w)` after people and site words | `advisor/extract.py` | Fixed |
| F-31 | A stored GSTIN overrode an explicit "no" | "No GST" clears the stored GSTIN, and the engine ignores a stored one when the answer is "no" | `advisor/profile.py`, `engine.py` | Fixed |
| F-32 | A claimed GSTIN (yes, no number) unlocks GST-only products | Kept as a design choice. The chain the report described is closed by F-02 (it no longer comes from "I do not have GST") and F-03 (it can be corrected at KYC). The plan now says "X need a valid GSTIN, verified at KYC and removed if it cannot be" | `advisor/engine.py`, `i18n.py` | Mitigated |
| F-33 | Duplicate product lines overwrote each other | They add up; a non-numeric quantity no longer raises; a line is capped at 1,000 with an error | `advisor/engine.py` | Fixed |
| F-34 | The catalogue loader validated nothing | `validate_catalogue()` and `CatalogueError`: duplicate ids, min above max, negatives, bad tiers or segments, dangling or self dependencies, unreadable rows | `advisor/catalogue.py` | Fixed |
| F-35 | Order and call-back language collapsed to English for 8 of 10 languages | The real language code is stored on the order, the consent record and the call-back | `journey/orders.py`, `app.py` | Fixed |
| F-36 | The OCR noise filter could drop a real firm name | Phrase-based filter; "Synthetic Fibres Pvt Ltd" is kept | `journey/extract.py` | Fixed |
| F-37 | The re-engage list ignored the drop reasons Smart KYC exists to fix | Three more addressable reasons (details did not match, cancelled before install, install delayed beyond 21 days), each with a pitch | `journey/crm.py` | Fixed |
| F-38 | The reported AUC (0.635) was one pessimistic split | The model card reports 5-fold cross-validated AUC **0.705 ± 0.039**, keeps the 80/20 split (0.635) and the "has a GSTIN" rule alone (0.614), labels the model "weak to moderate", and the call list uses out-of-fold scores | `journey/crm.py`, `static/backoffice.js` | Fixed (calibrated in round 2, MDL-01) |
| F-39 | Shipped defaults were not safe to expose | Random back-office key unless `DEMO_MODE=1`; `make_env.py` (called by `run.sh` and `run.bat`) saves one in `.env` on first run. Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy; `Cache-Control: no-store` on `/api`; CORS off unless `CORS_ORIGINS` lists origins; specimen documents and on-screen codes only on a local server or in demo mode | `app.py`, `advisor/config.py`, `make_env.py` (new), `run.sh`, `run.bat`, `.env.example` | Fixed |
| F-40 | Registry lookups were open, "repaired" typed numbers, and the Udyam mask was cosmetic | GST lookup returns trade name, constitution, state, city and status only. Udyam lookup needs the exact format (no O-to-0 repair) and returns 6 business fields. The mask shows only the last 2 characters: it identifies **0** of 2,723 records (it was 2,652). The lookups were already rate-limited and still are, but they remain unauthenticated mock endpoints (see limits) | `app.py`, `journey/extract.py` | Fixed |
| F-41 | `/api/health` exposed provider, model, counters and URL | `/api/health` returns `{"status":"ok"}`. Public switches are in `/api/config`; the detail is in `/api/backoffice/health`, behind the key | `app.py`, `static/*.js` | Fixed |
| F-42 | The funnel's "plans shown" lived in process memory | Plan events are stored (table `plans`, hashed session key); "submitted" and "verified" count orders that ever got there | `journey/store.py`, `app.py` | Fixed |
| F-43 | "Got it: **cA** firm" | Acronym-safe acknowledgement | `advisor/narrate.py` | Fixed |
| F-44 | Any quantity up to 1,000 per line was accepted | A line above max(10, 4 × the recommended quantity) is flagged in the quote, shown to staff, and the order is never auto-verified; the 1,000 hard cap stays | `advisor/engine.py`, `journey/orders.py` | Fixed |
| F-45 | The privacy note omitted Google Fonts and speech input; a real brand in a fictional case | (a) `PRIVACY.md` rewritten to match what the code does: fonts, browser speech recognition, LLM, SMS stub, upload handling, headers, what is deleted and what is kept, known limits. The CSP allows the fonts. (b) The "airtel" name and logo are **unchanged** (see limits) | `PRIVACY.md`, `README.md`, `app.py` | Docs |

## Round 2: the second audit

A probe script (`audit/probe_audit2.py`) re-ran the second audit's reproductions on the round-1 code first. Fifteen of its findings were already
fixed there; they are marked "round 1" below and now have tests written from this audit's own reproduction steps.

### High

| ID | What the audit found | Status | What changed | Tests (`-k`) |
| --- | --- | --- | --- | --- |
| KYC-01 | Documents never reconciled with the order (a salon in Jaipur verified with a Nagpur furniture workshop's documents) | Fixed | Round 1 bound the ID holder to the person ordering (F-04). Now the business is checked too: the Udyam activity (or the lead's type) against the order's business type, the documents' city against the order's city, and "no GST" against an uploaded GST certificate. Any contradiction is a warning, so a person checks before anything is verified; staff see both values. On verification the order takes the business the documents prove (name, type, city, state, GSTIN). Staff cannot approve KYC that needs attention | `kyc01` (incl. the audit's run with real uploads) |
| ADV-06 | "4 people" set 4 staff and 4 sites | Fixed (round 1, F-01) | Pinned: "4 people", "just one outlet", "एक दुकान", and the two-turn salon at ₹1,848 | `adv06` |
| ADV-01 | "I do not have GST" read as yes | Fixed (round 1, F-02) | 15 negative phrasings (English, Hinglish, Hindi, Tamil, Marathi) and 6 positive ones | `adv01` |
| LLM-01 | Raw text sent on product questions | Fixed | Round 1 fixed the path (F-09). The client now also redacts every request body itself, so no prompt kind can carry a phone, email or GSTIN | `llm01` |
| LLM-03 | Wrong prices and invented offers shown | Fixed | Price questions are answered from the price list; the model is not asked. Reasoning blocks (`<think>`) are removed before anything reads the text. "Free", "% off", "discount" and dates ("today", "by Friday") are refused unless the facts contain the same whole word ("toll-free" no longer backs "free") | `llm03` |
| ORD-01 | Two "Next stage" clicks skipped a stage | Fixed | Named actions (Schedule the visit, Mark installed, Mark active), each valid from one status; every action carries the status the screen showed and gets 409 `stale` if it moved; buttons are disabled while a request is in flight. The old "advance" needs that status | `ord01`, `audit/ui_check_round2.py` |
| PRV-01 | Staff cancel kept KYC data | Fixed (round 1, F-07) | Cancel runs the same deletion as withdrawal; the label and dialog say so | `f07` |

### Medium

| ID | What the audit found | Status | What changed | Tests (`-k`) |
| --- | --- | --- | --- | --- |
| ADV-02 | "what do you mean?" gave 2 staff | Fixed (round 1, F-14) | Pinned | `adv02` |
| ADV-03 | Single words created needs ("dedicated staff", "fast food", "UPI", "2 units of AC"); spend read as budget | Fixed | Needs come from phrases ("fast internet", "dedicated line", "card machine"); "units of" is not a site count; spend stays apart from the budget (F-12) | `adv03` |
| ADV-04 | "no idea" became the type and the city | Fixed (round 1, F-14) | Pinned for type, city and GST | `adv04` |
| ENG-01 | One cafe, gym or hotel priced as a chain (₹3,046 against ₹1,797) | Fixed | One or two outlets of a chain type are a small business (micro, or professional office); shown as "Restaurant", not "Restaurant chain" | `eng01` |
| ENG-02 | Leased line and SD-WAN quoted on an assumed size | Fixed | Products with a minimum size are never unlocked on an assumed size; they are listed with "tell me your team size and I can add it" | `eng02` |
| LLM-02 | A later model reply overwrote "20 staff" with 3 | Fixed | A model may fill an empty field; changing a stated one needs support in that message ("we are 25 now"). Otherwise the old value stays and the customer is asked "Earlier you told me 20 people. Should I change it to 3?" | `llm02` |
| LLM-04 | Unusable model output never counted as a failure | Fixed | Empty, non-JSON, array and reasoning-only replies count, so three in a row pause the model | `llm04` |
| LLM-05 | A slow provider stalled a turn for up to 30 s | Fixed | All calls of a turn share one budget (`LLM_TURN_BUDGET_S`, 18 s); one timeout pauses the model at once | `llm05` |
| ORD-02 | Duplicate orders | Fixed (round 1, F-19) | Per-session lock and idempotency; checkout also forgets the plan after ordering | `f19`, `audit/ui_check_round1.py` |
| SES-01 | Expired sessions still quoted and ordered | Fixed (round 1, F-20) | Pinned by the round-1 tests | `f20` |
| PRV-02 | Spaced phone numbers not redacted | Fixed (round 1, F-09) | Pinned | `f09` |
| PRV-03 | Chat text in the logs | Fixed (round 1, F-08) | Pinned | `f08` |
| KYC-02 | "Sneha Rao" matched "Sneha Ram" | Fixed (round 1, F-23) | Word-by-word matching; "Ram Traders" and "Sam Traders" differ too | `f23` |
| SEC-01 | A 544-byte PDF drove memory to 565 MB | Fixed (round 1, F-24) | Page size checked before rendering; render capped | `f24` |
| MDL-01 | Top band promised 18.4%, delivered 11.5%; serving features differed from training | Fixed | Platt scaling on out-of-fold scores (top fifth now 15.4% predicted, 14.2% actual); a calibration table on the model card; an unknown answer (current internet, Udyam) scores as the average lead, not as a category no lead has; Udyam becomes known at KYC and the score is recomputed; the call list uses out-of-fold scores (F-38) | `mdl01`, `f38` |

### Low

| ID | What the audit found | Status | What changed | Tests (`-k`) |
| --- | --- | --- | --- | --- |
| KYC-03 | Only page 1 of a PDF was read | Fixed | Up to 5 pages are read, one at a time, until the page with the slot's document; the page used is stored | `kyc03` |
| ORD-03 | Status and history written separately | Fixed | One SQLite transaction for the order and its history entry (rolled back together) | `ord03` |
| ORD-04 | Withdrawal after cancel logged "cancelled" twice | Fixed | Wipes again, no second status entry | `ord04` |
| ENG-03 | Duplicate quote lines collapsed | Fixed (round 1, F-33) | They add up | `f33` |
| ENG-04 | Mumbai with a Kochi GSTIN was quoted 1 Gbps | Fixed | When the registered city has fewer products, the quote uses its tier and says why, so KYC cannot block it later | `eng04` |
| TRK-01 | Tracker limited after 10 successful lookups; language switch showed the form again | Fixed | Only failed lookups count; switching language redraws the order in place | `trk01`, `audit/ui_check_round2.py` |
| ADV-05 | Regional languages need the LLM | Mitigated | Digits of every Indian script, GST yes/no, the main city names and staff/shop words in the 8 regional scripts are understood. Replies stay in English or Hindi without an LLM key, with the one-time notice (F-10) | `adv05` |
| SEC-02 | Health endpoint showed the provider and last error | Fixed (round 1, F-41) | `{"status":"ok"}` only | `test_health` |
| PRV-04 | Uploads over 1 MB spooled to disk | Fixed (round 1, F-25) | Kept in memory, cut off while arriving | `f25` |
| FE-01 | A stale quote could overwrite the add-on total | Fixed (round 1, F-18) | Sequence guard | `audit/ui_check_round1.py` |

### Found by the judge-style stress test

| ID | What the audit found | Status | What changed | Tests (`-k`) |
| --- | --- | --- | --- | --- |
| ADV-07 (High) | "6 teachers", "me and one helper", "4 pharmacy outlets", "3 होटल" missed | Fixed | Job titles count as staff (summed), "me and N helpers" = N+1, "just me" = 1; describing words may sit between a number and a place word; hotels, gyms, cafes, salons and Hindi/regional shop words are place words. Never across a quantity or a time ("4 cameras per outlet", "a 10 year old shop", "5 star hotel"), and "5 logistics partners" still sets nothing (F-30) | `adv07`, `t07`, `t09`, `t14`, `t15` |
| DLG-01 (High) | A question that also gives a fact was never answered | Fixed | It is answered, then the conversation continues | `dlg01` |
| ADV-08 (Medium) | किराने, उदयपुर, वाई-फाई, कैमरे, "customers ke liye alag wifi", "Banglore" missed | Fixed | Hindi inflections and the Hindi names of every listed city; spellings with or without nukta; guest Wi-Fi in Hindi and Hinglish; misspelt cities matched (6+ letters, same first letter, close match) | `adv08`, `t01`, `t02`, `t04` |
| ADV-09 (Medium) | "4 cameras per outlet", "email for everyone", "add 2 more SIMs" misread | Fixed | Per-site and per-person counts are kept and multiplied by sites or staff; "N more" and "N fewer" change the plan on screen | `adv09`, `t04` |
| ENG-05 (Medium) | No option under ₹1,348 for a ₹1,000 internet-only ask; "make it cheaper" got silence | Fixed | The lower-cost plan has only what was asked for (the connection alone, ₹999); over budget, the cheapest plan is shown first; "make it cheaper" with nothing cheaper says so and names the item to drop | `eng05`, `t14` |
| DLG-02 (Medium) | Swiggy, Zomato and Google-reviews asks vanished | Fixed | Off-catalogue asks are named back once ("We don't offer ..."), from rules and from the model's `unsupported` list | `dlg02` |
| REQ-01 (Low) | The advisor never asked about current tools | Fixed | "What do you use for internet today?" is asked once, together with another question (never a turn of its own); the answer feeds the plan and the score | `req01` |

The 15 scenarios (language model off): T01, T02, T04, T05, T06, T07, T09, T12, T13, T14 and T15 are tests of their own
(`-k t01` ...); T03, T08, T10 and T11 are covered by `adv09`, `eng05`, `dlg02` and `dlg01`.

### Potential vulnerabilities and production controls from the second audit

| Item | Status |
| --- | --- |
| A lock entry for every order ID, before the token check | Fixed: a fixed pool of 64 order locks and 64 session locks; memory cannot grow (`lock_map`) |
| Upload stored in a temp file before the size check | Fixed in round 1 (F-25) |
| `CORS_ORIGINS=*`; shared key falling back to `accel-demo` | Fixed in round 1 (F-39) |
| Every staff action logged as "backoffice" | Each action now records the name typed at sign-in (`backoffice:<name>`). It is a label, not a login |
| Product answers following injected instructions | Fixed by LLM-03: prices only from the price list; numbers, promises, dates and contact details are refused |
| Order token in the URL fragment | Documented, unchanged: the fragment is never sent to a server or in a Referer (the pages send no referrer), the token is stored only as a hash and opens one order. On a shared computer the read-only tracker (order ID + mobile) is the safer way back. See PRIVACY.md |
| Several server workers would split sessions, limits and locks | Unchanged: run one process (as `run.sh` and `run.bat` do) or move this state to Redis or a database |
| Sign-in with roles, HTTPS, a managed encrypted database, a secrets vault, a scheduled retention purge, shared rate limits, DigiLocker and real GST/Udyam APIs | Not built: the audit lists these as production hardening, "not needed for the MVP" |

## What you will notice when you run it

1. **Mobile check before an order.** Checkout has "Send code / Verify". On a local server the code is shown on screen and
   pre-filled; elsewhere it is not. `OTP_REQUIRED=0` turns the step off. The SMS gateway is a stub: put a real one into
   `send_sms()` in `journey/otp.py`.
2. **Documents must match the order (round 2).** An order is verified automatically only when the documents describe the
   same business, city and GST status, and the ID holder placed it. In the demo, use the example **Sample KYC applicant
   (K03)** (a furniture workshop in Nagpur) and the name "Joseph Singh". The salon example with K03 goes to a team check.
3. **Back office (round 2).** Sign in with the key and your name. Stage buttons are named (Schedule the visit, Mark
   installed, Mark active) and disabled while a request runs. Order rows show the verified business; the model card shows
   predicted against actual conversion by fifth.
4. **Back-office key.** Random for each run unless `BACKOFFICE_KEY` is set. `run.sh` and `run.bat` create one on first run,
   print it and save it in `.env`. `accel-demo` works only with `DEMO_MODE=1`.
5. **Public endpoints say less.** `/api/health` is `{"status":"ok"}`.
6. **Budget is compared with the GST-inclusive price**, and over budget the cheapest plan is shown first.
7. **Cancel and withdraw delete the KYC details** (see F-21 for exactly what stays).
8. **"I don't have a GST registration" asks for confirmation** and shows the new price first.
9. **The advisor (round 2)** answers a question even when the message also gives facts, names things it does not sell,
   asks once what you use for internet today, asks before a model reading changes something you said, and treats a
   single cafe or gym as a small business.
10. **New error codes** the UI handles: `otp_*`, `image_too_large`, an early `413 too_large`, upload `rate_limited`, and
    `stale` for a back-office action on an order that has moved on.

New settings (all in `.env.example`): `DEMO_MODE` (0), `OTP_REQUIRED` (1), `DEMO_OTP` (on only for a local server),
`DEMO_SAMPLES` (same rule), `UPLOAD_RATE` (40 uploads per address per 10 min), `CORS_ORIGINS` (empty = same origin),
`BACKOFFICE_KEY` (random if empty), `LLM_TURN_BUDGET_S` (18 s for all model calls of one chat turn).

API changes in round 2: back-office actions take an optional JSON body `{"expected_status": "..."}` and an
`X-Staff-Name` header; the actions are `approve`, `send_back`, `schedule`, `install`, `activate`, `cancel` (plus the old
`advance`, which now needs `expected_status`). KYC views have new order checks `order.type`, `order.city` (now a warning
when it differs) and `order.gst`; uploaded PDFs record `page` and `pages`; the model card has `calibration`.

## Existing tests that had to change

They checked the old, wrong behaviour. Nothing was deleted.

| Test | Why |
| --- | --- |
| `test_engine.py::test_budget_moves_default_to_the_cheaper_option` and the budget invariant in the fuzz test | Budget is now compared with the GST-inclusive price (F-17) |
| `test_api.py::test_health` | Public health is `{"status":"ok"}` (F-41) |
| `test_api.py::test_step_by_step_flow_and_changes` | The needs question also asks about current internet (REQ-01) |
| `test_journey.py::test_clean_applicant_uploads_and_is_verified_automatically` | Placed by the ID holder (F-04) for K03's own business, a furniture workshop in Nagpur (KYC-01) |
| `test_journey.py::test_typed_details_go_to_review_and_the_team_approves` | Named stage actions; "advance" without the status is refused (ORD-01) |
| `test_kyc.py::test_answer_key` | Clean documents on an unrelated order now go to a person; the same documents on the applicant's own order are ready (KYC-01) |
| `test_audit_fixes.py::test_f28_end_to_end...`, `::test_f38_...` | Price questions never reach the model (LLM-03); the call list shows calibrated scores (MDL-01) |
| `conftest.py` | `OTP_REQUIRED=0` and a high `UPLOAD_RATE` for the suite; the OTP and rate-limit tests turn them on themselves |
| `pytest.ini` | Ignores Pillow's own warning for 25 to 50 MP images in the F-24 tests |

## How it was checked

| Check | Result |
| --- | --- |
| `python3 -I -m pytest -q` | 382 passed in about 30 s (Tesseract installed, so the OCR tests ran too) |
| Round-2 probe (`audit/probe_audit2.py`, the second audit's reproductions, no server needed) | 43 checks, none fails (26 failed on the round-1 code) |
| Round-1 repro scripts | Each prints the fixed behaviour; `r01` reports **0** behaviours reproduced as bugs (33 before) |
| Memory use (F-24, SEC-01) | 49 MP and 79 MP blank PNGs and a 14,400 pt PDF page are refused (peak 82 to 111 MiB, was 320 to 456 MiB); a 3,000 pt page renders in 149 MiB (was 337 MiB) |
| Headless Chromium, round 1 (`audit/ui_check_round1.py`), 1280 px and 375 px | No horizontal overflow, no script errors; stale-quote race, Back after ordering, mobile check, GST-drop panel and language notice all work. The only 4xx is the designed 409 of the GST confirm step |
| Headless Chromium, round 2 (`audit/ui_check_round2.py`) | A double click on "Schedule the visit" moves one stage, buttons are disabled in flight, the staff name is recorded; switching language on the read-only tracker keeps the order on screen; a question with a fact is answered; the current-internet question appears once. No script errors |

## Limits and decisions that are yours

- **F-10 / ADV-05, regional languages.** Without an LLM key the advisor understands the basics in the 8 regional scripts
  (numbers, GST yes/no, main cities, staff and shop words) but replies in English or Hindi, and says so once. Full replies
  need a key or new template sets in `advisor/i18n.py`.
- **F-32, claimed GSTIN.** Left as designed. If you would rather not show GST-only products until a number is typed or
  verified, set `gst_ok` to `False` in the `"claimed"` branch of `advisor/engine.py::resolve()` (the `elif p.has_gstin == "yes"` line).
- **F-45(b), brand.** The pages still say "airtel". The case study calls everything fictional (Accel Telecom), so check that
  you may use the real name and logo, or change the 9 mentions in `static/` (`index.html`, `backoffice.html`, `styles.css`, `journey.js`).
- **KYC-01.** The person is bound by name and mobile check, not by an OTP to the signatory's registered mobile or Aadhaar
  e-sign; the audit lists those for production.
- **LLM-02.** The confirmation covers the six facts the plan depends on most (type, city, staff, sites, GST, budget).
- **F-40.** The GST and Udyam lookups are mock registries and still open to any caller, with minimal fields, exact
  formats and a rate limit. A real registry call needs authentication and a consent step.
- **F-24.** Memory is capped; CPU time for rendering a PDF is not (KYC-03 reads at most 5 pages).
- **F-38 / MDL-01.** The scores are honest and calibrated now. The model itself is still weak to moderate (cross-validated
  AUC 0.705 on 5,000 leads).
- **Single process.** Sessions, codes, rate limits and locks are in memory; two server processes would not share them.
- **Staff name** on back-office actions is typed, not authenticated; one shared key remains until sign-in with roles exists.
- **Google Fonts** still loads from Google on each page view and browser speech recognition sends audio to the browser
  vendor. Both are disclosed in `PRIVACY.md`. Self-host the font files to remove the first.
- **Not run here:** `run.bat` on Windows (only its line endings and the one changed line were checked), a real LLM (the guards
  are tested against a stub that misbehaves on purpose), RapidOCR (results are from Tesseract), voice input.
- **The 409 in the browser console** when the customer declares "no GST" is the confirm step working as designed.

## Extra hardening found on the way

Free text that comes back from a model (`city`, `business_type`) now loses control characters, bidirectional-override
characters and angle brackets (`advisor/extract.py::_text`, test `test_l6_…`). The round-1 report listed this as a loose
end, not as a finding.
