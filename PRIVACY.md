# Data privacy and security note: Project Udyam Digital

Principle: each step collects only what it needs, keeps it only as long as needed, and tells the
owner exactly what happens. Designed against the DPDP Act, 2023: consent, purpose limitation and
data minimisation. This note describes what the code does today; the last section lists what a
production launch still needs.

## What each step collects

| Step | Collected | Not collected |
| --- | --- | --- |
| Advisor | Business type, city, staff, sites, GST status or GSTIN, needs, budget. Held in memory only, for at most 3 hours. | Name, phone, address |
| Checkout | Contact name and mobile (for the verification code, order updates and the visit) | Email, payment details |
| KYC | GSTIN, legal and trade name, business address, Udyam number, signatory name and ID validity, bill name, address and date | Document images, ID number (kept masked: `SYN-ID-••6190`), bill amount, consumer number, units |
| Call back | Name, mobile, reason, with a tick giving permission to call | Anything else |
| Funnel counts | One anonymous row per advisor session (a hash of the session ID, and a time) | Anything about the person |
| Order updates | For each text sent: the order ID, the kind of update ("scheduled") and the time | The text itself, the number it went to (already on the order) |
| Tracker visits | For each look at an order's status: the order ID and the time (looks within 30 minutes count once) | IP address, device, browser |
| Arrival link | The channel named in the link (`?src=whatsapp`: one of the six sources in the data, nothing else) and a referral code if there was one | Campaign IDs, referrer pages, any other link parameter |

## Consent

- A plain notice in English or Hindi comes before any upload: what we keep, why, how long, and how to withdraw.
- The server refuses documents until consent is given; this is not only hidden in the UI.
- Offers are a separate, optional tick, off by default. Consent is versioned and time-stamped.
- Withdrawing takes one click. It deletes the KYC details at once and cancels the order. After
  installation, closure goes through support, because telecom records must be kept.

## What is deleted, and what is kept

Withdrawing consent, and a back-office cancel, run the same deletion. It removes the document data
(every field read or typed), the "not registered" declarations, the full Udyam number, the GSTIN
saved on the order, the link to a lead record and the contact name. The **order, the plan and its
price, the status history, the mobile number and the consent record** (proof that consent was given
and later withdrawn) are kept. A scheduled purge for those, after the period telecom record rules
require, is part of the production list below.

## Purpose limitation

- KYC fields are used only to verify the business and to re-check the order's eligibility.
- The lead record (CRM) is linked only when a document identifier (GSTIN or Udyam number) is
  confirmed by the registry. A number typed in chat links nothing. The record is used to credit the
  lead's source, to check that the signatory is the contact on record, and to check that the business type
  on the order matches (as the Udyam registration's activity is).
- Documents are checked against the order they verify: business type, city and declared GST status. When they
  contradict it, a person looks before anything is installed, and the customer is told what differs.
- When the ID is in a different name from the contact on record or from the person ordering, the
  customer sees "a team member will confirm" and never the other name. Only the back office sees it.

- **Signals work (reports/signals.json).** Tracker visits are counted only so staff can call a customer who keeps
  checking an order before that customer has to call; the texts exist so nobody has to chase. Both are about the
  order the customer placed, on the number they verified for "updates and the installation visit" (the checkout
  says so); they are not marketing, which stays behind the separate offers tick. A referral code is random (not
  the order ID): the referred order records which order referred it, and the referring customer learns nothing about
  the business they referred. A code used from the referring customer's own number is ignored.

## Minimisation and masking

- **Documents stay in memory.** An upload is read from the network into memory and processed there.
  The server is set up so that a large phone photo is not spooled to a temporary file either, and
  only the extracted fields are stored. OCR runs on our server; no document is sent to a third party.
- Only the fields the checks need are stored. GSTIN, Udyam number (only its last two characters are
  shown), ID number and mobile are masked in every customer response.
- **Logs carry order IDs, document types and results.** For chat they record only the length of the
  message, the intent, and the *names* of identifier types found, never the text or the identifiers.
- The optional LLM (off by default) receives only redacted chat text: GSTIN, Udyam, PAN, Aadhaar,
  phone and email are replaced before sending, even when written with spaces or dashes. The LLM client
  redacts every request body itself as well, whichever part of the app built it. It never
  sees documents and never decides prices or KYC results. Its wording is checked against the facts
  and the price list, and thrown away if it adds numbers, promises or contact details of its own.
- Advisor sessions hold no name or phone, expire after 3 hours (also for the tracker and order
  link), and "Start over" deletes them.

## What reaches other services

| Service | When | What it receives |
| --- | --- | --- |
| Google Fonts | Every page load (the Poppins typeface) | The visitor's IP address and browser details. Self-host the font files to remove this. |
| Browser speech recognition | Only if the visitor taps the microphone, and only in browsers that offer it | Audio, handled by the browser vendor (in Chrome, Google), not by this server. The transcript is then used like typed text. |
| LLM provider | Only if `LLM_PROVIDER` is set | The redacted chat text and the checked facts of the plan. Never documents. |
| SMS gateway | The verification code before an order, and a short update at each change of an order's status | The mobile number and the text. Update texts hold the order ID, the status, dates and the price, never names, GSTIN or document details. In this build the gateway is a stub: no SMS is sent, the log says "queued" without the text, and on a local demo the verification code is shown on screen. |
| GST and Udyam registries | KYC checks | Mock registries, read from local files. Nothing leaves the server. |

## Retention

- KYC details are kept while the order and service are active.
- They are deleted immediately on withdrawal, or if the order is cancelled before installation
  (see "What is deleted, and what is kept").
- Order, plan, mobile and consent records stay until a production purge job removes them; the period
  must be configurable, not hard-coded.

## Security

- **Mobile check.** An order can be placed only with a proof that a code sent to that number was
  entered. Codes expire after 5 minutes, allow 5 tries, are stored only as a hash and are limited
  per number and per address. The proof works once and only for that number.
- **Order links.** Each order has a random 144-bit token, shown once and stored only as a SHA-256 hash.
  Placing the same order twice returns the same order.
- **Read-only tracking.** Needs the order ID and the mobile number, compared in constant time and
  rate-limited (10 failed tries per 10 minutes; an owner checking their own order is never blocked).
- **The link in the address bar.** The private link carries its token after `#`, which browsers never send to a server or in a
  Referer header (and the pages send no referrer at all). It stays in the browser's history: on a shared computer,
  use "Track order" with the order ID and mobile instead, which cannot change anything.
- **Server-side decisions.** Prices, eligibility and KYC results are computed on the server; tampered
  prices from the browser are ignored (tested).
- **Names are compared word by word.** A different person with a similar name (Ramesh and Rakesh) is
  not accepted; an initial or a slip in a long word sends the order to a person instead of verifying it.
- **Uploads.** At most 8 MB, cut off while arriving rather than after, images or PDF only (up to 5 PDF pages are
  read, one at a time, in memory, to find the page that holds the document). The size in
  pixels is checked before decoding (25 megapixels; PDF pages up to 50 inches, rendered at a lower
  resolution when large), so a tiny file that expands into a huge image is refused. Unreadable files
  get a clear error, never a crash. Uploads are rate-limited per address.
- **Back office.** Behind a key compared in constant time. Every action records the name the staff member typed at
  sign-in (a label, not a login: production needs single sign-on) and the status the screen showed, so a double
  click or a stale screen cannot move an order twice. If no `BACKOFFICE_KEY` is set, a random key
  is generated for that run and shown once in the server log. The shipped demo key works only when
  `DEMO_MODE=1`, and the server warns while it is in use.
- **Browser protections.** A Content-Security-Policy, `X-Frame-Options: DENY`, `nosniff`, no referrer,
  and `Cache-Control: no-store` on every API answer. Cross-origin calls are refused unless
  `CORS_ORIGINS` lists the origin.
- **Public endpoints say little.** The liveness probe returns only `ok`. The browser config lists
  switches, not providers or models. Registry lookups return a few business fields and do not
  correct mistyped numbers. Specimen documents and on-screen codes are on only for a local demo
  (`DEMO_MODE=1` or a loopback host) unless switched on explicitly.
- **Abuse limits.** Rate limits on order creation, codes, uploads, call-backs and registry lookups.
  All input is validated with Pydantic, and request bodies have size caps.

## Known limits of this build

- Sessions, codes and rate limits live in the memory of one server process.
- A GSTIN typed in the chat is a claim: it decides which products are shown, and is checked against
  the registry and the documents at KYC; products that need a valid GSTIN are removed if it fails.
- SQLite is not encrypted, and the retention purge is not implemented.

## Before production

- HTTPS everywhere, and a managed database encrypted at rest instead of SQLite.
- Secrets in a vault.
- Single sign-on with roles: KYC team, field sales, and partners who see only their own city's leads.
- An exportable audit log of consent and KYC decisions.
- A real SMS gateway, shared storage for sessions, codes and rate limits, and a scheduled retention purge.
- Self-hosted fonts.
- DigiLocker pull instead of uploads where the owner agrees, and Aadhaar e-sign for the customer
  agreement.
- Real GST and Udyam APIs in place of the mock registries.
- A grievance officer contact on the consent screen, and a data-protection impact assessment before
  launch.
