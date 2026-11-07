# Fix roadmap: 45 audit findings, token-efficient order

**Baseline:** the attached zip was byte-identical to the audited one (same SHA-256), so every finding applies as written.

## How tokens are saved
1. **One pass per file.** Read only the functions a finding touches (`grep -n` then a line range), apply every edit for that file in one batch, and never re-read an edited file.
2. **Dependency order.** Parser (no dependencies) → privacy/sessions → engine/guards → orders/API → matching/OCR/CRM → front end/docs. Later work packages build on earlier ones, so nothing is revisited.
3. **Tests grow with the fixes.** Each fix adds its regression case to one file, `tests/test_audit_fixes.py`, at the moment it is written. There is no separate "write tests" pass.
4. **Cheap checks.** The existing suite (73 tests, ~20 s) runs after each package. The audit's repro scripts are re-run once at the end against the fixed tree.
5. **Nothing is lost on a cut-off.** `FIX_LOG.md` is appended after every package.
6. **No sub-agents and no re-auditing.** The report already has the evidence.

## Work packages (finding → approach)
| WP | Files | Findings | Approach |
|---|---|---|---|
| 1 | `advisor/extract.py`, `taxonomy.py` | F-01 02 05 11 12 13 14 15 16(aliases) 30 | Consume number spans; single pending slot gets the bare number. `do not`→`don't`, negation before yes, drop `sure`. Unicode-aware tokenising (Devanagari). `\b` on negation and people words. Budget needs a currency or "per month" cue. City after `in/at/near`. Non-answer list plus city-list validation. Clinic alias and metro-suburb aliases |
| 2 | `advisor/privacy.py`, `dialogue.py`, `profile.py`, `narrate.py` (ack) | F-08 09 20 31 43 | Normalising `redact()` (spaces/hyphens, digits-based phone). Redact once in `handle()` and use only that string everywhere. Log no text. `peek()` honours the TTL. `has_gstin=no` clears `gstin`. Acronym-safe ack |
| 3 | `advisor/engine.py`, `catalogue.py`, `narrate.py`, `i18n` | F-06 10 16 17 27 28 32 33 34 44 | `show_ess` also when it fits the budget; budget vs GST-inclusive. `tier_assumed` flag. Sum duplicate lines; unusual-qty warning. Catalogue validation. Strict LLM guards (digits, promise words, plan-only product mentions, per-product price check). Language notice when no LLM |
| 4 | `journey/orders.py`, `checks.py`, `texts.py`, `store.py`, `app.py`, `.env.example`, `run.*` | F-03 04 07 19 21 22 26 35 39 40 41 42 | "No GST" at KYC drops the GST-only lines and re-quotes. Checkout-name↔ID binding (mismatch → review) plus mock mobile OTP gate. One purge routine for cancel and withdraw. Idempotent create. Lead link only after a verified GSTIN. Real UTC timestamps. Store the real language. Minimal public `/health`; registry lookups return less and don't "repair". Persisted plan events. Random back-office key, security headers |
| 5 | `journey/extract.py`, `ocr.py`, `crm.py`, `app.py` (uploads) | F-23 24 25 29 36 37 38 40(mask) | Token-wise name match, OCR-lookalike aware, no substitutions in short tokens. Unit numbers must match. Phrase-aware noise filter. Pixel check before decode, PDF page cap, upload rate limit, in-memory spool plus body cap. Extra re-engage reasons. CV-based AUC and out-of-fold scores |
| 6 | `static/*.js`, `index.html`, `backoffice.*`, `PRIVACY.md`, `README.md` | F-18 19 10 45 07 | Quote sequence guard, optimistic toggle, `location.replace` after order, language notice, OTP card, accurate privacy and README text |
| 7 | tests, repros | all | Full suite, re-run of the audit repro scripts (expect no BUG lines), headless-browser smoke test |

## Decisions made up front
- **Left as design choices, documented not coded:** the real "airtel" branding in a fictional case (F-45b). Your team restyled it deliberately. A "claimed" GSTIN still unlocks GST-only lines (F-32), now correctable at KYC via F-03.
- **Mock OTP** (F-04): the real SMS gateway is out of scope for a prototype. The code is shown in the API response only when `DEMO_OTP=1`; otherwise it is only handed to a `send_sms()` stub.
- **Google Fonts** (F-45a): cannot be self-hosted offline here, so it is disclosed in `PRIVACY.md` and CSP-allowed instead.

---

# Round 2: second audit (Project Udyam Digital — Engineering, Logic & Security Audit, 42 pages)

**First step, cheap:** one probe script (`audit/probe_audit2.py`) re-ran the second audit's reproductions on the already-fixed
tree. Items the first round had already fixed are only locked in with regression tests; the rest are fixed below.

| Already fixed in round 1 (regression test only) | Still open, fixed in round 2 |
| --- | --- |
| ADV-01, ADV-02, ADV-04, ADV-06 (F-01, F-02, F-14), LLM-01 basic path (F-09), PRV-01 (F-07), PRV-02, PRV-03 (F-08, F-09), SES-01 (F-20), KYC-02 (F-23), SEC-01 (F-24), SEC-02 (F-41), PRV-04 (F-25), FE-01 (F-18), ENG-03 (F-33), ORD-02 (F-19), CORS and default key (F-39) | KYC-01 (beyond the contact check), ORD-01, ORD-03, ORD-04, KYC-03, ENG-01, ENG-02, ENG-04, ENG-05, LLM-01 (redaction inside the client), LLM-02, LLM-03 (think tags, price answers), LLM-04, LLM-05, MDL-01 (calibration, serving features), TRK-01, ADV-03, ADV-05, ADV-07, ADV-08, ADV-09, DLG-01, DLG-02, REQ-01, unbounded lock map, staff attribution |

| WP | Files | Findings |
| --- | --- | --- |
| 8 | `advisor/llm.py`, `narrate.py` | LLM-01 (redact every request), LLM-03 (strip think tags, price questions answered from the catalogue only, promise words matched as whole words, dates), LLM-04 (parse failures count), LLM-05 (one deadline per turn, pause on the first timeout) |
| 9 | `advisor/extract.py`, `taxonomy.py` | ADV-03, ADV-05, ADV-07, ADV-08, ADV-09, DLG-02 (rules and LLM schema), REQ-01 answers |
| 10 | `advisor/engine.py`, `profile.py` | ENG-01, ENG-02, ENG-04, ENG-05, ADV-09 sizing |
| 11 | `advisor/dialogue.py`, `narrate.py`, `i18n.py` | DLG-01, DLG-02 reply, LLM-02 (provenance and confirmation), REQ-01 question, ENG-05 "make it cheaper", ADV-09 "2 more" |
| 12 | `journey/orders.py`, `store.py`, `checks.py`, `ocr.py`, `app.py` | ORD-01 (expected status, named actions), ORD-03 (one transaction), ORD-04, KYC-01 (contradictions go to a team check; verified business copied to the order), KYC-03 (multi-page PDF), TRK-01, bounded locks, staff name on actions |
| 13 | `journey/crm.py` | MDL-01 (calibrated bands, no "Unknown" category at serving time) |
| 14 | `static/*.js`, README, PRIVACY, AUDIT_FIXES | Back office (expected status, buttons disabled while pending, staff name), tracker language switch, chat chips; documents |
| 15 | tests, probe, browser | Full suite, `audit/probe_audit2.py` must print no STILL line, the 15 judge-style scenarios, headless browser |

Same token rules as round 1: read only the functions a finding touches, one batch of edits per file, tests in one new
file (`tests/test_audit2_fixes.py`), log after each package (`FIX_LOG.md`).
