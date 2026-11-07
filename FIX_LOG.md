# FIX LOG (append after each work package)

## WP1 DONE: advisor parser (advisor/extract.py, advisor/taxonomy.py)
- F-01: size fallback now skips number spans already used (people/sites/money/units) and fills only the pending slots (`_free_numbers`).
- F-02/F-05: `_gst_answer()` = clause-based, negation before affirmation, "not sure" is no answer, Unicode-safe `_tokens()` (Devanagari), NFC input.
- F-11: left word boundary on `_NEG`; "cannot work without X" and "no downtime" are requirements.
- F-12: `_money()` needs a money cue, rejects Mbps/metres/sq ft/days/etc., current spend goes to `current_monthly_spend`, lakh/k/per-year handled.
- F-13: `find_city()` prefers 'in/at/near/...' (or Hindi 'में'), else the LAST name; longer names beat the names inside them.
- F-14: `_NON_ANSWER`/`_NOT_A_PLACE` reject non-answers for city and business type; Hindi 'do'=2 only in Hindi/Hinglish text.
- F-15: generic Clinic type (segment hint prof). F-16(part): metro-suburb aliases (Thane, Howrah, Secunderabad, ...).
- F-30: `(?!\w)` after people/site words.
- Tests: tests/test_audit_fixes.py (68 cases). Repro r01: 33 BUG -> 6 (rest are WP2: redaction + gstin merge).

## WP2 DONE: privacy, sessions, profile (advisor/privacy.py, dialogue.py, profile.py, narrate.py, extract.py)
- F-09: `redact()` rewritten: separator-tolerant (space/-/.), NFKC, upper-case compact values for GSTIN/UDYAM/PAN; phone = 10 digits starting 6-9 with optional +91/0; spaced GSTIN typed in chat is now a usable `gstin`.
- F-09(a): `Extraction.redacted` is the only text that may leave the server; Q&A uses `ex.question or ex.redacted` (never the raw message).
- F-08: per-turn log line carries intent/source/length/identifier KINDS only, never chat text.
- F-20: `SessionStore.peek()` returns None for an expired session; periodic + size-capped `_prune()`.
- F-31 (part): `merge()` clears a stored GSTIN when the customer says "no GST" (engine-side guard follows in WP3).
- F-43: `ack_text()` keeps acronyms ("CA firm").
- Tests: +18 (86 in tests/test_audit_fixes.py). Full suite 159 passed. Repro r01: 0 BUG, r17: no text in logs, r22 L-4: no raw text sent.
- Note: a spaced GSTIN inside a question now counts as a fact (profile updated), so Q&A is skipped for that turn (correct behaviour).

## WP3 DONE: engine, catalogue, narrate guards (advisor/engine.py, catalogue.py, narrate.py, i18n.py, dialogue.py)
- F-06: cheaper plan offered if it saves >=15% OR it is the only one inside the budget; floor warning only when nothing fits (floor taken from the lowest-cost bundle).
- F-17: budget compared with GST-inclusive amount (`budget_status`, warnings, texts say "GST included"). Updated 2 existing tests that encoded the old ex-GST rule (test_budget_moves_default..., fuzz invariant).
- F-16: `Resolved.tier_assumed` + `profile_view.tier_assumed`; wording "we may not serve {city}"; (orders/staff view follow in WP4).
- F-31: engine ignores a stored GSTIN when `has_gstin == "no"`.
- F-32: documented design kept; new note "X need a valid GSTIN, verified at KYC and removed if it cannot be" shown next to the plan when GST is only claimed.
- F-33: duplicate lines in `quote()` add up; non-numeric qty no longer raises; total per line capped at MAX_QTY=1000 with an error.
- F-44: `unusual_quantities()` (> max(10, 4 x recommended qty)) -> `quote()["unusual"]` + `warnings` (staff flag wired in WP4).
- F-34: `validate_catalogue()` + `CatalogueError` (duplicate ids, min>max, negatives, tiers, segments, dangling/self dependencies, unreadable rows); utf-8-sig.
- F-27: `ungrounded()` guard for summary / item_reasons / excluded_reasons / messages: contact details, numbers not in facts, promise words (EN+HI), never-sold products, products outside the plan (PRODUCT_WORDS, families P07/P08, P05/P06).
- F-28: `_money_ok(text, catalogue, matched)` checks prices of the asked-about products only, understands "99 rupees", "12k", "1.2 lakh", worded amounts; no matched product = no amounts; Q&A also gets the number/promise/contact guard; guard rejections counted.
- F-10: one-time `notice` in the chat reply for languages without templates when no LLM is configured (UI work in WP6).
- Tests: +21 (test_audit_fixes.py now 107). Full suite 194 passed. Repros r04/r04b/r21b/r22/r22b: fixed behaviour confirmed.

## WP4 DONE: orders, KYC, privacy, hardening (journey/orders.py, checks.py, otp.py, store.py, texts.py, extract.mask_udyam; app.py; advisor/config.py; run scripts)
- F-03: "I don't have GST" at KYC: `declare_not_registered` for gst_certificate -> 409 `confirm_requote` (removed products, swaps, old/new totals) then, with `{"confirm": true}`, re-quotes without GST-only products (link products swapped via ALTERNATIVES), profile -> has_gstin=no, doc state "declared"; refuses if nothing is left / rules break.
- F-04: new check `id.orderer` (ID holder vs checkout name, or proprietor) -> warn = review, staff see both names, customer never sees the other name. Mock OTP (`journey/otp.py`, /api/otp/send + /verify; proof token single-use, bound to the mobile; 5 tries, 30 s gap, 5/hour; code returned only with DEMO_OTP). `/api/orders` needs `otp_token` when OTP_REQUIRED.
- F-07/F-21: one `_purge()` for staff cancel and consent withdrawal: docs, declared, full Udyam, profile.gstin, lead, contact name. Kept: order/plan/status, mobile, consent record.
- F-16/F-44: `flags` on the order (tier assumed, unusual qty) shown to staff; flagged orders never auto-verify (go to kyc_review).
- F-19: idempotent create via session memo (same cart+contact = same order and token); earlier never-started orders of the session are superseded; cancelled orders are not reused.
- F-20: (WP2) peek() TTL.
- F-22: no lead from chat GSTIN; lead only from registry-confirmed identifiers on uploaded documents; propensity score recomputed when the lead is found.
- F-26: audit timestamps are real UTC; APP_TODAY only for document-date rules.
- F-35: real language code stored (order, consent, call-back).
- F-39: random back-office key unless DEMO_MODE (shipped key never accepted outside demo mode); make_env.py writes a random key on first run (run.sh/run.bat); CSP/X-Frame-Options/nosniff/Referrer-Policy/Permissions-Policy headers; `Cache-Control: no-store` on /api; CORS off unless CORS_ORIGINS lists origins; demo samples/OTP codes default to on only for loopback or DEMO_MODE.
- F-40: GST lookup returns trade name/constitution/state/city/status only; Udyam lookup is exact-format (no O->0 repair) and returns 6 business fields; `mask_udyam` shows only the last 2 characters (records uniquely identified by the mask: 2652 -> 0 of 2723).
- F-41: /api/health = {"status":"ok"}; /api/config (public flags), /api/backoffice/health (key).
- F-42: plan events persisted (`plans` table, hashed session key); funnel "ever submitted/verified" from the events table.
- Existing tests updated because they encoded the old behaviour: test_health, test_clean_applicant (order placed by the ID holder), conftest OTP_REQUIRED=0.
- Tests: +18 (test_audit_fixes.py now 125 + 2 in other files). Full suite 212 passed.

## WP5 DONE: matching, uploads, call list (journey/extract.py, checks.py, ocr.py, crm.py, app.py, advisor/config.py)
- F-23: names compared word by word (`name_level`): OCR look-alikes (0/o, 1/l/i, 5/s, 8/b, rn/m, vv/w) and word order are "exact"; an initial, a missing middle initial or one slip in a >=8-letter word is "near" (-> warn, goes to a person, never auto-verified); anything else is different. Leading titles (Dr, Shri/Sri, Smt, Mr, M/s...) are ignored. The six pairs the audit showed passing (Ramesh/Rakesh, Kavita/Savita, Vijay/Vinay, Rahul Verma/Varma, Amit Shah/Shaw, Suresh/Sunesh) and Neha/Sneha are now different people; the registry's 23 conflated pairs -> 0.
- F-29: house/unit numbers must match exactly (3B is not 3C, 199 is not 191/99/19/299); the rest of the address stays fuzzy.
- F-36: watermark filter (`NOISE`) is phrase based; business names such as "Synthetic Fibres Pvt Ltd" are kept.
- F-24: images are refused when width x height > 25 MP *before* any pixel is decoded (Pillow only warned up to 50 MP); PDF page size is read first: pages over 50 inches are refused and the render scale is lowered so the bitmap stays under 12 MP; all decoder errors map to "unreadable", never a 500; new customer-facing code `image_too_large` (EN + HI strings). Measured: 49 MP / 79 MP blank PNG and a 14,400 pt PDF page are now refused (peak RSS 82-111 MiB instead of 320-456 MiB); a 3000 pt PDF page 149 MiB instead of 337 MiB. Per-address upload rate limit (UPLOAD_RATE, default 40 per 10 min).
- F-25: Starlette's multipart parser no longer spools files over 1 MiB to a temp file (`MultiPartParser.spool_max_size` = upload cap + 256 KiB); measured with a SpooledTemporaryFile spy: 3 MiB phone-sized photo -> no disk event. New pure-ASGI `BodyLimit` middleware cuts a request off before it is read: by Content-Length, and by counting bytes for chunked bodies; uploads capped at MAX_UPLOAD_MB (+256 KiB of form fields), every other API body at 256 KiB. Rejections still carry the security headers.
- F-37: three more addressable drop reasons (Document details did not match, Customer cancelled before install, Installation delayed beyond 21 days) with pitches.
- F-38: model card reports 5-fold cross-validated AUC 0.705 +/- 0.039 (the single 80/20 split 0.635 is kept and labelled, plus the "has a GSTIN" rule alone 0.614) and says "weak to moderate"; the call list is ranked and shown with out-of-fold probabilities (no in-sample scores kept). Back-office text updated.
- Tests: +52 (full suite 264 passed).

## WP6 DONE: front end and documents (static/app.js, journey.js, backoffice.js, styles.css; PRIVACY.md, README.md, .env.example)
- F-10 (UI): the chat shows the one-time `notice`; the language list marks languages that need the AI assistant (from /api/config `offline_languages`); the AI chip no longer shows provider/model (F-41).
- F-17 (UI): the budget row says "(GST included)".
- F-18: `requote()` has a sequence guard (a stale answer is ignored), add-on switches move at once, the total is dimmed and "Continue" is disabled while a quote is in flight. Verified in headless Chromium by holding the first /api/quote request: total and switch correct after the stale answer arrives.
- F-19 (UI): after placing an order `location.replace()` leaves checkout out of the history; Back goes to the advisor; one order exists (server idempotency as a second layer).
- F-04 (UI): checkout has the mobile-check block (send code, enter code, verified); Place order stays disabled until verified; the code is single-use (state reset after the order); editing the number drops a code or proof issued for the old one; demo code shown and pre-filled only when the server says so.
- F-03 (UI): the GST step has "I don't have a GST registration"; a confirm panel lists what comes out, swaps, and the old and new price (GST included); nothing changes until "Remove them and continue". Error strings for otp_*, image_too_large, nothing_left, cannot_requote in English and Hindi.
- F-07 (UI): the back-office cancel dialog says the KYC details are deleted; funnel tiles say "(ever)" / "now"; model card text shows cross-validated AUC with the caveats.
- F-45: PRIVACY.md rewritten to match the code (what is deleted and kept; Google Fonts; browser speech recognition; LLM; SMS stub; upload handling; headers; key behaviour; known limits). README updated (languages, mobile check, key and DEMO_MODE, new endpoints and settings, AUC wording, demo script uses the ID holder's name, test counts).
- Real "airtel" branding left unchanged on purpose (the case study is about that company); noted in AUDIT_FIXES.md.
- Browser check (repro_fixed/r26_ui_fixed.py): desktop 1280 + phone 375: no horizontal overflow, no page errors; the only 409 in the log is the designed GST confirm handshake.

## WP7 DONE: verification and packaging
- Full suite: 265 passed (73 original + 192 in tests/test_audit_fixes.py), no warnings (pytest.ini ignores Pillow's 25-50 MP warning in the F-24 tests).
- Audit repro scripts re-run on the fixed tree (repro_fixed/, outputs in the scratch area): r01 now "0 behaviours reproduced as BUG" (33 before); the rest print the fixed behaviour. r22 adapted for F-41 (public health has no llm block).
- Headless Chromium (r26_ui_fixed.py) at 1280 px and 375 px: no overflow, no script errors; F-18 stale-quote race, F-19 Back button, F-04 mobile check, F-03 GST-drop panel, F-10 notice, back-office text all verified.
- Extra hardening (audit L-6): model output is stripped of control and bidirectional-override characters and angle brackets (`_text()` in advisor/extract.py); test added.
- run.bat: only the `make_env.py` line changed; CRLF line endings restored after an edit had turned them into LF.
- README test counts updated (265 / 277 with both OCR engines). AUDIT_FIXES.md written (finding-by-finding table, behaviour changes, limits).
- Zip built from the clean tree (no __pycache__, .pytest_cache, .env, var/); extracted into a fresh folder, the suite and a server boot were run again there.

# Round 2: second audit (42-page PDF)

## WP8 DONE: LLM client and guards (advisor/llm.py, narrate.py, dialogue.py, config.py)
- LLM-01: `LLM.complete` redacts every request body itself (phone, email, GSTIN, PAN, Aadhaar, Udyam), whatever the caller built.
- LLM-03: `strip_reasoning()` removes <think>/<thinking>/<reasoning> blocks before parsing or showing; an unclosed block = no answer. Price questions are answered from the price list only (the model is not asked). Promise words must appear as the same whole word in the facts ("toll-free" no longer backs "free"); dates ("today", "by Friday", "this week") count as commitments; Q&A facts are the asked-about rows only.
- LLM-04: empty, non-JSON, array and reasoning-only replies count as failures (stats `bad_output`), so 3 in a row pause the model.
- LLM-05: one timeout pauses the model at once; all calls of one chat turn share `LLM_TURN_BUDGET_S` (default 18 s).
- Tests: tests/test_audit2_fixes.py (22). test_f28_end_to_end updated: the answer prompt is never sent for a price question.

## WP9-11 DONE: understanding, engine, dialogue (advisor/extract.py, taxonomy.py, profile.py, engine.py, dialogue.py, narrate.py, i18n.py)
- ADV-03: needs from phrases, not single words ("fast internet" not "fast food"; "dedicated line" not "dedicated staff"; "internet for UPI" is not a POS); "2 units of AC" is no site count; current spend stays apart from budget (F-12).
- ADV-05: digits of every Indian script; GST yes/no words and "GST" in the 8 regional scripts; main city names in those scripts; people and shop words. Replies stay English/Hindi (notice from F-10).
- ADV-07: job titles count as staff (teachers, helpers, doctors... summed), "me and one helper" = 2, "just me" = 1; "4 pharmacy outlets", "3 होटल", hotels/gyms/cafes/salons as site words; never across a quantity or time ("4 cameras per outlet", "a 10 year old shop", "5 star hotel"). F-30 still holds.
- ADV-08: Hindi inflections (किराने), Hindi names of all listed cities, Hindi spellings without nukta (वाई-फाई), plural कैमरे, guest Wi-Fi in Hindi/Hinglish, misspelt cities matched fuzzily (6+ letters, same first letter, ratio 0.84).
- ADV-09: "4 cameras per outlet" (per-site counts), "email for everyone" (per-person), "add 2 more SIMs" / "one camera less" (relative to the plan on screen); profile keeps per-site/per-person counts and the engine multiplies by sites/employees.
- DLG-01: a question that also gives facts is answered, then the conversation continues; questions in the middle of a message are detected.
- DLG-02: off-catalogue asks (Swiggy/Zomato, Google reviews, marketing, accounting, loans, power backup, custom apps) are named back once; the LLM schema has an `unsupported` list too.
- REQ-01: "what do you use for internet today?" is asked once, together with another question (never its own turn); answers like "mobile hotspot", "jio fiber", "nothing yet" are stored.
- LLM-02: a model reading may fill an empty field, but changing a stated one needs support in that message; otherwise the old value stays and the customer is asked "Earlier you told me 20 people. Should I change it to 3?" (yes/no).
- ENG-01: one or two outlets of a chain type (cafe, restaurant, gym, hotel...) are micro/prof, not multi-site; shown as "Restaurant", not "Restaurant chain".
- ENG-02: products with a minimum size are never unlocked on an assumed size; they are listed as "tell me your team size and I can add it".
- ENG-04: when the GSTIN's registered city has fewer products than the stated city, the quote uses the registered city's tier (with a warning), so KYC cannot block it later.
- ENG-05: the lower-cost plan contains only what was asked for (internet only = the connection alone); over budget, the cheapest plan is shown first; "make it cheaper" with nothing cheaper says so and names the item to drop.
- Tests: tests/test_audit2_fixes.py now 100 (incl. T01, T02, T04, T07, T09, T12, T14, T15 judge scenarios). test_api step-by-step flow updated for REQ-01. Full suite 365 passed.

## WP12-13 DONE: orders, KYC, tracker, model (journey/orders.py, store.py, checks.py, texts.py, ocr.py, crm.py, app.py)
- ORD-01: named stage actions (schedule, install, activate) valid from one status each; every action takes `expected_status` and answers 409 `stale` if the order moved; the old "advance" needs it. Staff name (X-Staff-Name) recorded as `backoffice:<name>`.
- ORD-03: order and history entry written in one SQLite transaction (rollback on failure); tested with a simulated event-write failure.
- ORD-04: withdrawing consent on a cancelled order wipes again but logs no second "cancelled".
- Locks: a fixed pool of 64 order locks and 64 session locks (by CRC32), so unknown order IDs no longer grow memory; session -> order lock order only.
- KYC-01: documents are reconciled with the order: Udyam activity (or the lead's type) vs the business type, documents' city vs the order city, "no GST" vs an uploaded GST certificate; any contradiction is a warning, so the order goes to a person (never auto-verified). Staff see both values. On verification the order takes the proven business (name, type, city, state, GSTIN). Staff approve refuses an order whose KYC needs attention.
- KYC-03: PDFs are read page by page (up to 5) until the page that holds the slot's document is found; the page used is stored.
- TRK-01: only failed tracker lookups count toward the limit.
- MDL-01: Platt scaling on out-of-fold scores (top fifth now predicts 15.4% vs 14.2% actual; was 18.4% vs 11.5%); calibration table on the model card; unknown answers (current internet, Udyam) score as the average lead instead of a category no lead has; Udyam becomes known at KYC and the score is recomputed.
- Existing tests updated: test_kyc answer key (clean documents on an unrelated order now go to review; the same documents on the applicant's own order are ready), test_journey clean applicant (order for K03's own business) and staff flow (named actions), test_f38 (calibrated scores).
- Tests: tests/test_audit2_fixes.py 114. Full suite 379 passed.

## WP14-15 DONE: front end, documents, verification
- Back office: sign-in takes the staff name (sent as X-Staff-Name); named stage buttons; each action sends the status on screen; buttons disabled while a request runs; verified business in the order detail; calibration table on the model card.
- Customer app: language switch on the read-only tracker redraws the order in place (TRK-01); checkout forgets the plan after an order (ORD-02); new example "Sample KYC applicant (K03)" for the demo.
- README demo script (K03 on its own business; Schedule the visit), test counts (382 / 394), layout; PRIVACY (client-side redaction, documents checked against the order, failed-lookup limit, token in the fragment, staff name, PDF pages); AUDIT_FIXES.md covers both audits.
- Shipped in audit/: probe_audit2.py (43 checks, none fails), ui_check_round1.py and ui_check_round2.py (headless Chromium; both clean).
- Full suite: 382 passed.

# Round 3: signals from the leads data

## WP16 DONE: audit of the signals (scripts/signals.py v1 -> v2, reports/)
- Reran v1 on the data pack: byte-identical to the signals.json handed over, so every finding below applies to it.
- friction: v1 called it supported if (visit share at Contacted) + (quote share at Needs assessed) > 25%, adding shares
  of two different stages; and its insight said leads are lost "more to the visit and the PDF quote than to the product"
  while price is the largest reason at the steepest step (56%). v2: one denominator (2,545 drops before a quote: 48%
  visit or quote, 24% price), price named, and where it bites (micro 38% vs manufacturers 16%).
- reach: "72% of their first-stage drops are unreachable or wrong numbers" holds for every source (about 70%). v2
  compares leads never reached: 35% for WhatsApp/website vs 18% (Fisher test), and reports the same reason mix.
- chases: churn half untested in v1. v2: churn logit (odds x1.40 per chase, p = 0.015), Fisher 1 vs 5+ (p = 0.017), and
  r = 0.01 between chases and days to activate (chases are not slow installs in disguise).
- install: "NPS falls 0.10 per day of waiting" uses days from lead to activation, not installation; v2 says so, and
  measures the tier gap on the same bundle: +1.75 days in tier 2 (OLS on catalogue install days, p < 0.001).
- routing: the insight "field visits pay off only on high-propensity leads" was never tested (v1's test was top-fifth
  lift > 1.2). v2 tests it (field leads in the Low band: 3.2% activate, Rs 51,445 per activation, vs 12.2% and Rs 15,774;
  p < 0.001) and finds value matters as much: ranking by score x segment bundle puts 70% of activated revenue in the top
  fifth vs 48% (69% vs 55% on later leads only). WhatsApp's low cost per activation rests on 10 activations.
- misfit: the GSTIN rule trusted has_gstin; a cancelled or suspended GSTIN passed. v2 uses the registry: 56 rule-breaking
  bundles (as scripts/backtest.py), not 48. Still not supported.
- band(): num_sites collapsed into one band of 5,000 leads; log-spaced bands when quantiles tie.
- New in v2: per-step models (where each factor acts), Udyam at KYC (odds x1.6), referral (2x, every step), segment
  economics (micro: 8 months to recover acquisition cost), commission on activation (partners: 1.5 months of bundle).

## WP17 DONE: features from the signals
- install: `PeerStats.install_allowance` measures extra install days per tier from the data (tier 2: 1.75 -> 2 days,
  only when clearly above zero); `Engine.install_days` adds it to products that need an installation (not same-day
  items); plan, checkout, order and tracker agree and say why. AirFiber offer: staff action `airfiber` (kyc_verified,
  needs a fibre line) swaps fibre for P04, removes fibre-only products, re-prices through the engine; scheduling is
  blocked until the customer accepts or declines in the tracker (`POST /api/orders/{id}/proposal`, private link only)
  or staff record a phone answer (`accept-airfiber`, `drop-proposal`). Dates then count from the acceptance.
- chases: `journey/notify.py` texts the customer at every status change (EN/HI, no names or document details; stub
  gateway in `journey/sms.py`, shared with the OTP); only kind and time are stored. Tracker views are counted (once per
  30 minutes). `OrderService._risk` flags orders being chased (3 visits since the last update), past their promised
  date, or without documents after 2 days; the back office lists them after team checks, with an "At risk now" tile.
- routing: `journey/crm.Router` reads channel costs (needs-assessment step: field Rs 1,850, call Rs 320) and segment
  bundles from the leads; each call-back and dropped lead gets a channel; a call-back never gets less than a call. The
  back office shows last quarter routed this way (visit band: 15% of leads, 58% of activated revenue).
- reach and referral: `?src=` and `?ref=` from the link reach the session (`canonical_source`, `clean_referral`); the
  order keeps its source, is scored with it, and gets a random referral code shown once active; an order through the
  link is credited to the referring order (self-referrals and unknown codes ignored).
- Back office: "What the leads data says" table from reports/signals.json; routing card; risk badges; order detail
  shows texts sent, tracker visits, promised date and allowance, the open offer.
- Tests: tests/test_signals.py (22). Existing suite unchanged; 404 in all. Browser check at 1280 px and 375 px: no overflow, no
  script errors (only Google Fonts blocked in the sandbox).
