"""FastAPI app: the advisor, checkout, Smart KYC, the order tracker and the back office.

Run:  python app.py      (or: python -m uvicorn app:app --reload)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartParser

from advisor.config import settings
from advisor.dialogue import Advisor, SessionStore
from advisor.engine import ENGINE_VERSION, Engine
from advisor.i18n import STRINGS
from advisor.llm import LLM
from advisor.narrate import explain
from advisor.profile import BusinessProfile
from advisor.resources import get_resources
from journey.checks import KycChecker, UdyamRegistry
from journey.crm import LeadBook, Propensity, Router, canonical_source, clean_referral
from journey.extract import find_udyam
from journey.ocr import OcrProvider, available_engines
from journey.notify import Notifier
from journey.orders import JourneyError, OrderService, normalize_mobile
from journey.otp import OtpService
from journey.store import Store

logging.basicConfig(level=(os.getenv("LOG_LEVEL") or "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")
ROOT = Path(__file__).resolve().parent

resources = get_resources()
engine = Engine(resources)
llm = LLM(settings)
advisor = Advisor(engine, llm)
sessions = SessionStore()
leads = LeadBook(settings.data_dir / "smb_leads.csv")
model = Propensity(leads.rows)
router = Router(leads.rows)                      # which channel a lead deserves (signal "routing")
routing_card = router.card(model, leads.rows)
reengage_list = model.reengage(leads, limit=25, router=router)
udyam = UdyamRegistry(settings.data_dir / "mock_udyam_registry.csv")
ocr = OcrProvider(settings.ocr_engine, settings.tesseract_cmd)
store = Store(settings.db_path)
orders = OrderService(store, engine, KycChecker(resources, udyam, leads, engine), ocr, leads, model, settings,
                      max_upload_bytes=int(settings.max_upload_mb * 1024 * 1024), router=router,
                      notifier=Notifier(store))
otp = OtpService(show_code=bool(settings.demo_otp))
SAMPLE_RE = re.compile(r"^(K\d{2})_(gst_certificate|udyam_certificate|signatory_id|address_proof)\.png$")
SAMPLES_DIR = settings.data_dir / "kyc_documents"
SIGNALS_JSON = ROOT / "reports" / "signals.json"


def load_signals(path: Path = SIGNALS_JSON) -> dict | None:
    """The signal -> insight -> feature table written by scripts/signals.py, for the back office. Optional: the app runs
    without it (rerun the script after regenerating the data)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    keep = ("id", "signal", "insight", "feature", "where", "status", "supported", "note")
    return {"generated": data.get("generated"), "leads": data.get("leads"), "activations": data.get("activations"),
            "version": data.get("version"), "signals": [{k: s.get(k) for k in keep} for s in data.get("signals", [])]}


signals_report = load_signals()
if settings.backoffice_key_generated:
    log.warning("No BACKOFFICE_KEY set: this run uses a random back-office key: %s  (set BACKOFFICE_KEY in .env "
                "to keep one between runs)", settings.backoffice_key)
elif settings.demo_mode and settings.backoffice_key == "accel-demo":
    log.warning("DEMO_MODE is on and the back office uses the demo key. Do not expose this server.")

MULTIPART_SLACK = 256 * 1024         # form fields and boundaries around the file in an upload request
API_BODY_MAX = 256 * 1024            # every other API body is a small JSON document
# F-25: keep an upload in memory however big it is (Starlette's default moves anything over 1 MiB to a temp file
# on disk before our code runs, which contradicts "never written to disk" in PRIVACY.md).
MultiPartParser.spool_max_size = orders.max_upload_bytes + MULTIPART_SLACK


class RateLimit:
    """At most `limit` hits per key in `window` seconds (in memory)."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, record: bool = True) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise JourneyError(429, "rate_limited", "Too many attempts. Please wait a few minutes.")
            if record:
                q.append(now)
            elif not q:
                del self._hits[key]           # a key that never failed leaves nothing behind

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())


track_limit, order_limit = RateLimit(10, 600), RateLimit(30, 600)
handoff_limit, lookup_limit = RateLimit(10, 600), RateLimit(120, 600)
otp_limit = RateLimit(30, 600)
upload_limit = RateLimit(settings.upload_rate, 600)     # document uploads per address


UPLOAD_PATH = re.compile(r"^/api/orders/[^/]+/documents$")


class BodyLimit:
    """Pure-ASGI guard that runs before any request body is parsed (F-24, F-25).

    * Uploads (POST /api/orders/{id}/documents): the per-address upload rate limit is checked first. The body is then
      capped at MAX_UPLOAD_MB plus a little for the form fields: by the declared Content-Length, and, for chunked
      bodies that declare none, by counting bytes as they arrive. An oversized upload is cut off, not read to the end.
    * Every other API request: bodies are small JSON documents, capped at API_BODY_MAX.
    """

    def __init__(self, app):
        self.app = app

    @staticmethod
    def _declared(scope) -> int | None:
        for key, value in scope["headers"]:
            if key == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH") or not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        upload = scope["method"] == "POST" and UPLOAD_PATH.match(path) is not None
        limit = orders.max_upload_bytes + MULTIPART_SLACK if upload else API_BODY_MAX
        too_large = {"code": "too_large", "message": "The file is too large." if upload else "The request is too large."}
        if upload:
            try:
                upload_limit.check((scope.get("client") or ("unknown", 0))[0])
            except JourneyError as exc:
                return await JSONResponse(status_code=exc.status, content={
                    "detail": {"code": exc.code, "message": exc.message}})(scope, receive, send)
        declared = self._declared(scope)
        if declared is not None and declared > limit:
            return await JSONResponse(status_code=413, content={"detail": too_large})(scope, receive, send)
        received, tripped = 0, False

        async def limited_receive():
            nonlocal received, tripped
            if tripped:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    tripped = True
                    raise StarletteHTTPException(413, detail=too_large)   # FastAPI re-raises HTTPException as it is
            return message

        await self.app(scope, limited_receive, send)


app = FastAPI(title="Udyam Digital", version=ENGINE_VERSION)
app.add_middleware(BodyLimit)         # innermost: CORS and the security headers still wrap its rejections
if settings.cors_origins:        # same-origin only unless origins are listed explicitly (F-39)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Content-Type", "X-Order-Token", "X-Backoffice-Key"])

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
       "media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h.setdefault("Content-Security-Policy", CSP)
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=(), payment=()")
    if request.url.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"      # API answers can contain personal data
    return response


@app.exception_handler(JourneyError)
async def journey_error(_: Request, exc: JourneyError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": {"code": exc.code, "message": exc.message,
                                                                    **exc.extra}})


def client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def require_staff(key: Optional[str]) -> None:
    if not key or not hmac.compare_digest(key.encode(), settings.backoffice_key.encode()):
        raise JourneyError(401, "unauthorized", "Back-office key required.")


# =============================================================================== advisor (part 1)
class ChatIn(BaseModel):
    session_id: Optional[str] = None
    message: str = Field("", max_length=1000)
    language: Optional[str] = None          # None or "auto" = detect from the message
    needs: Optional[list[str]] = None       # need tags picked from chips
    source: Optional[str] = Field(None, max_length=40)   # ?src= of the link the visitor came from
    ref: Optional[str] = Field(None, max_length=24)      # ?ref= referral code from another customer


class RecommendIn(BaseModel):
    profile: BusinessProfile
    language: str = "en"
    explain: bool = False


class QuoteItem(BaseModel):
    product_id: str = Field(..., max_length=10)
    qty: int = Field(1, ge=1, le=1000)


class QuoteIn(BaseModel):
    session_id: Optional[str] = None
    profile: Optional[BusinessProfile] = None
    items: list[QuoteItem] = Field(..., max_length=30)
    language: str = "en"


@app.get("/api/health")
def health() -> dict:
    """Public liveness probe. Detail (provider, counters, data sizes) is behind the back-office key."""
    return {"status": "ok"}


@app.get("/api/config")
def public_config() -> dict:
    """Non-sensitive switches the browser needs to draw itself."""
    return {"engine_version": ENGINE_VERSION, "llm_available": bool(llm.available),
            "offline_languages": sorted(STRINGS), "demo_samples": bool(settings.demo_samples),
            "otp": {"required": settings.otp_required, "demo": bool(settings.demo_otp)}}


@app.get("/api/backoffice/health")
def backoffice_health(x_backoffice_key: Optional[str] = Header(None)) -> dict:
    require_staff(x_backoffice_key)
    return {"status": "ok", "engine_version": ENGINE_VERSION, "llm": llm.describe(),
            "data": {"products": len(resources.catalogue), "gstin_records": len(resources.gstin),
                     "udyam_records": len(udyam), "activated_peers": resources.peers.activated_total,
                     "leads": len(leads.rows)},
            "kyc": {"ocr_engine": ocr.expected(), "ocr_installed": available_engines(settings.tesseract_cmd),
                    "demo_samples": settings.demo_samples},
            "today": settings.today.isoformat()}


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    session = sessions.get(body.session_id)
    # The first channel a visit names wins; anything that is not one of the known sources is ignored.
    if session.source is None and body.source:
        session.source = canonical_source(body.source)
    if session.referral is None and body.ref:
        session.referral = clean_referral(body.ref)
        if session.referral and session.source is None:
            session.source = "Referral"
    res = advisor.handle(session, body.message, body.language, body.needs)
    if res.get("recommendation"):       # one anonymous row per session; survives restarts
        store.record_plan("s:" + hashlib.sha256(res["session_id"].encode()).hexdigest()[:24], orders.now())
    return res


@app.post("/api/recommend")
def recommend(body: RecommendIn) -> dict:
    """Structured entry point (forms, tests, other services): profile in, plan out."""
    rec = engine.recommend(body.profile, body.language)
    store.record_plan("a:" + secrets.token_hex(8), orders.now())
    if body.explain:
        rec["explanation"] = explain(rec, body.language, "native", llm, advisor.names)
    return rec


@app.post("/api/quote")
def quote(body: QuoteIn) -> dict:
    """Re-price any item list and report every rule it breaks (add-on toggles and checkout)."""
    profile = body.profile
    if profile is None:
        session = sessions.peek(body.session_id)
        if session is None:
            raise JourneyError(404, "session_expired", "Your advisor session has expired. Please start again.")
        profile = session.profile
    return engine.quote(profile, [i.model_dump() for i in body.items], body.language)


@app.get("/api/catalogue")
def catalogue() -> list[dict]:
    return [{"product_id": p.id, "name": p.name, "category": p.category, "description": p.description,
             "unit": p.unit, "list_price": p.list_price(settings.price_position), "price_range": [p.price_min, p.price_max],
             "setup_fee": p.setup_fee, "min_contract_months": p.min_contract_months, "install_days": p.install_days,
             "requires_gstin": p.requires_gstin, "requires_one_of": list(p.requires_one_of)}
            for p in resources.catalogue.values()]


@app.delete("/api/session/{session_id}")
def end_session(session_id: str) -> dict:
    sessions.drop(session_id)  # the advisor keeps nothing else about the customer
    return {"deleted": True}


# =============================================================================== checkout (part 2)
class ContactIn(BaseModel):
    name: str = Field("", max_length=120)
    mobile: str = Field("", max_length=20)


class OrderIn(BaseModel):
    session_id: str = Field(..., max_length=64)
    items: list[QuoteItem] = Field(..., min_length=1, max_length=30)
    contact: ContactIn
    language: str = "en"
    variant: Optional[str] = Field(None, max_length=20)
    otp_token: Optional[str] = Field(None, max_length=64)       # proof from /api/otp/verify (F-04)


class OtpSendIn(BaseModel):
    mobile: str = Field(..., max_length=20)


class OtpVerifyIn(BaseModel):
    mobile: str = Field(..., max_length=20)
    code: str = Field(..., max_length=12)


def _mobile_or_422(raw: str) -> str:
    m = normalize_mobile(raw)
    if not m:
        raise JourneyError(422, "invalid_contact", "Check your mobile number.", fields=["mobile"])
    return m


@app.post("/api/otp/send")
def otp_send(body: OtpSendIn, request: Request) -> dict:
    """Send a verification code to the customer's mobile (mock SMS; the code is returned only with DEMO_OTP)."""
    otp_limit.check(client(request))
    return otp.send(_mobile_or_422(body.mobile))


@app.post("/api/otp/verify")
def otp_verify(body: OtpVerifyIn, request: Request) -> dict:
    otp_limit.check(client(request))
    return otp.verify(_mobile_or_422(body.mobile), body.code)


@app.post("/api/orders")
def create_order(body: OrderIn, request: Request) -> dict:
    """Place an order. Prices are recomputed here; the browser sends only product IDs and quantities."""
    order_limit.check(client(request))
    verify = (lambda mobile: otp.consume(body.otp_token, mobile)) if settings.otp_required else None
    order, token = orders.create(sessions.peek(body.session_id), [i.model_dump() for i in body.items],
                                 body.contact.model_dump(), body.language, body.variant, verify_mobile=verify)
    return {"order_id": order["id"], "token": token, "order": orders.view(order, body.language)}


# =============================================================================== tracker (part 4)
@app.get("/api/orders/{order_id}")
def get_order(order_id: str, lang: str = "en", x_order_token: Optional[str] = Header(None)) -> dict:
    order = orders.load(order_id, x_order_token)
    orders.record_view(order)            # a look at the tracker (signal "chases")
    return orders.view(order, lang)


class ProposalIn(BaseModel):
    accept: bool
    language: str = "en"


@app.post("/api/orders/{order_id}/proposal")
def answer_proposal(order_id: str, body: ProposalIn, x_order_token: Optional[str] = Header(None)) -> dict:
    """Accept or decline the 5G AirFiber offer made when the site survey found no fibre (private link only)."""
    return orders.view(orders.answer_proposal(order_id, x_order_token, body.accept), body.language)


class TrackIn(BaseModel):
    order_id: str = Field(..., max_length=20)
    mobile: str = Field(..., max_length=20)
    language: str = "en"


@app.post("/api/track")
def track(body: TrackIn, request: Request) -> dict:
    """Read-only status with order ID + mobile (no private link needed)."""
    # Only failed lookups count (TRK-01): an owner checking their own order often is not guessing anything.
    keys = (client(request), "order:" + re.sub(r"[^A-Z0-9]", "", body.order_id.upper()))
    for key in keys:
        track_limit.check(key, record=False)
    order = orders.find_for_tracking(body.order_id, body.mobile)
    if order is None:
        for key in keys:
            track_limit.hit(key)
        raise JourneyError(404, "not_found", "No order matches that order ID and mobile number.")
    orders.record_view(order)
    view = orders.view(order, body.language)
    view["can_upload"] = False
    return view


# =============================================================================== Smart KYC (part 3)
class ConsentIn(BaseModel):
    kyc: bool
    offers: bool = False
    language: str = "en"


class ManualIn(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    language: str = "en"


@app.get("/api/orders/{order_id}/kyc")
def kyc_state(order_id: str, lang: str = "en", x_order_token: Optional[str] = Header(None)) -> dict:
    return orders.kyc_view(orders.load(order_id, x_order_token), lang)


@app.post("/api/orders/{order_id}/consent")
def give_consent(order_id: str, body: ConsentIn, x_order_token: Optional[str] = Header(None)) -> dict:
    order = orders.give_consent(order_id, x_order_token, body.kyc, body.offers, body.language)
    return orders.kyc_view(order, body.language)


@app.delete("/api/orders/{order_id}/consent")
def withdraw_consent(order_id: str, lang: str = "en", x_order_token: Optional[str] = Header(None)) -> dict:
    """Withdraw consent: deletes the KYC details and cancels the order (DPDP right to withdraw)."""
    return orders.kyc_view(orders.withdraw_consent(order_id, x_order_token), lang)


@app.post("/api/orders/{order_id}/documents")
def upload_document(order_id: str, file: UploadFile = File(...), doc_type: Optional[str] = Form(None),
                    lang: str = Form("en"), x_order_token: Optional[str] = Header(None)) -> dict:
    """One document image or PDF. doc_type is optional: without it the document type is detected."""
    data = file.file.read(orders.max_upload_bytes + 1)
    order, detected = orders.upload(order_id, x_order_token, data, file.filename, doc_type or None)
    return {"doc_type": detected, "kyc": orders.kyc_view(order, lang)}


@app.post("/api/orders/{order_id}/documents/{doc_type}/manual")
def type_document(order_id: str, doc_type: str, body: ManualIn, x_order_token: Optional[str] = Header(None)) -> dict:
    return orders.kyc_view(orders.manual(order_id, x_order_token, doc_type, body.fields), body.language)


class NotRegisteredIn(BaseModel):
    confirm: bool = False           # GST: accept the re-priced order without the products that need a GSTIN


@app.post("/api/orders/{order_id}/documents/{doc_type}/not-registered")
def not_registered(order_id: str, doc_type: str, body: Optional[NotRegisteredIn] = None, lang: str = "en",
                   x_order_token: Optional[str] = Header(None)) -> dict:
    order = orders.declare_not_registered(order_id, x_order_token, doc_type, lang, bool(body and body.confirm))
    view = orders.kyc_view(order, lang)
    view["order"] = orders.view(order, lang)         # the price may have changed (GST products removed)
    return view


@app.delete("/api/orders/{order_id}/documents/{doc_type}")
def remove_document(order_id: str, doc_type: str, lang: str = "en", x_order_token: Optional[str] = Header(None)) -> dict:
    return orders.kyc_view(orders.remove_document(order_id, x_order_token, doc_type), lang)


@app.post("/api/orders/{order_id}/kyc/submit")
def submit_kyc(order_id: str, lang: str = "en", x_order_token: Optional[str] = Header(None)) -> dict:
    order = orders.submit(order_id, x_order_token, lang)
    return {"order": orders.view(order, lang), "kyc": orders.kyc_view(order, lang)}


@app.get("/api/registry/gstin/{gstin}")
def gstin_lookup(gstin: str, request: Request) -> dict:
    """Mock GST registry API (backed by mock_gstin_registry.csv)."""
    lookup_limit.check(client(request))
    chk = resources.gstin.check(gstin)
    if chk.status == "invalid":
        raise JourneyError(422, "invalid", "Not a valid GSTIN: the format or check digit is wrong.")
    if chk.record is None:
        raise JourneyError(404, "not_found", "GSTIN not found in the registry.")
    r = chk.record       # business-level facts only: no personal (proprietor) name, street address or dates
    return {"gstin": r.gstin, "trade_name": r.trade_name, "constitution": r.constitution, "state": r.state,
            "city": r.city, "status": r.status}


@app.get("/api/registry/udyam/{number}")
def udyam_lookup(number: str, request: Request) -> dict:
    """Mock Udyam registry API (backed by mock_udyam_registry.csv)."""
    lookup_limit.check(client(request))
    n = number.strip().upper()
    if not re.fullmatch(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", n):       # exact format only: no OCR-style 'repair' here
        raise JourneyError(422, "invalid", "Not a valid Udyam number (UDYAM-XX-00-0000000).")
    rec = udyam.get(n)
    if rec is None:
        raise JourneyError(404, "not_found", "Udyam number not found in the registry.")
    return {k: rec[k] for k in ("udyam_number", "enterprise_name", "enterprise_type", "major_activity", "state", "city")}


@app.get("/api/demo/samples")
def demo_samples() -> dict:
    """The data pack's specimen KYC documents, for demos (DEMO_SAMPLES=0 turns this off)."""
    if not settings.demo_samples or not SAMPLES_DIR.is_dir():
        return {"enabled": False, "applicants": {}}
    applicants: dict[str, list[str]] = {}
    for f in sorted(SAMPLES_DIR.iterdir()):
        m = SAMPLE_RE.match(f.name)
        if m:
            applicants.setdefault(m.group(1), []).append(f.name)
    return {"enabled": True, "applicants": applicants}


@app.get("/api/demo/samples/{name}")
def demo_sample_file(name: str) -> FileResponse:
    if not settings.demo_samples or not SAMPLE_RE.match(name) or not (SAMPLES_DIR / name).is_file():
        raise JourneyError(404, "not_found", "Sample not found.")
    return FileResponse(SAMPLES_DIR / name, media_type="image/png")


# =============================================================================== call-backs
class HandoffIn(BaseModel):
    name: str = Field("", max_length=120)
    mobile: str = Field("", max_length=20)
    reason: str = Field("plan", max_length=20)
    language: str = "en"
    consent: bool = False
    session_id: Optional[str] = Field(None, max_length=64)
    order_id: Optional[str] = Field(None, max_length=20)


@app.post("/api/handoffs")
def request_callback(body: HandoffIn, request: Request, x_order_token: Optional[str] = Header(None)) -> dict:
    """'Talk to an expert': a lead the advisor couldn't close, for sales or a channel partner to call."""
    handoff_limit.check(client(request))
    if not body.consent:
        raise JourneyError(422, "consent_required", "Tick the box so we may call you about this request.")
    order = None
    if body.order_id:
        order = orders.load(body.order_id, x_order_token) if x_order_token else \
            orders.find_for_tracking(body.order_id, body.mobile)
    h = orders.create_handoff(body.name, body.mobile, body.reason, body.language,
                              session=sessions.peek(body.session_id), order=order)
    return {"ok": True, "id": h["id"]}


# =============================================================================== back office
@app.get("/api/backoffice/summary")
def backoffice_summary(x_backoffice_key: Optional[str] = Header(None)) -> dict:
    require_staff(x_backoffice_key)
    counts = store.order_counts()
    # Persisted and "ever" based: a plan shown before a restart, or an order sent back or cancelled later, still counts.
    funnel = {**store.funnel(), "active": counts.get("active", 0), "cancelled": counts.get("cancelled", 0)}
    return {"today": settings.today.isoformat(), "funnel": funnel,
            "orders": [orders.staff_view(o) for o in store.list_orders(200)],
            "handoffs": store.list_handoffs(100), "reengage": reengage_list, "model": model.card(),
            "routing": routing_card, "signals": signals_report,
            "install_allowance": resources.peers.install_allowance}


class StaffActionIn(BaseModel):
    expected_status: Optional[str] = Field(None, max_length=20)   # the status the screen showed (ORD-01)


def staff_actor(name: Optional[str]) -> str:
    """Who did it, for the history: the name typed at sign-in (one shared key still; production needs real sign-in)."""
    clean = " ".join((name or "").split())[:40]
    return f"backoffice:{clean}" if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,39}", clean) else "backoffice"


@app.post("/api/backoffice/orders/{order_id}/{action}")
def backoffice_action(order_id: str, action: str, body: Optional[StaffActionIn] = None,
                      x_backoffice_key: Optional[str] = Header(None), x_staff_name: Optional[str] = Header(None)) -> dict:
    require_staff(x_backoffice_key)
    expected = body.expected_status if body else None
    return orders.staff_view(orders.staff_action(order_id, action.replace("-", "_"), staff_actor(x_staff_name),
                                                 expected_status=expected))


@app.post("/api/backoffice/handoffs/{handoff_id}/close")
def backoffice_close_handoff(handoff_id: str, x_backoffice_key: Optional[str] = Header(None)) -> dict:
    require_staff(x_backoffice_key)
    return orders.close_handoff(handoff_id)


# =============================================================================== pages
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/backoffice", include_in_schema=False)
def backoffice_page() -> FileResponse:
    return FileResponse(ROOT / "static" / "backoffice.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=int(os.getenv("PORT") or "8000"))
