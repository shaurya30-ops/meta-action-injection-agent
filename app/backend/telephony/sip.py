"""
telephony/sip.py
Utilities for LiveKit SIP integration with Twilio Programmable Voice.

Responsibilities:
  1. Extract SIP call attributes from a LiveKit participant.
  2. Look up CRM data from MongoDB by caller phone number (inbound-only).
"""

import logging
import os
import re
from typing import Any

logger = logging.getLogger("आकृति.telephony")

# ── SIP Participant Attribute Keys (injected by LiveKit SIP) ──────────────────
SIP_CALL_ID        = "sip.callID"        # unique SIP call identifier
SIP_CALL_FROM      = "sip.callFrom"      # caller's E.164 phone number
SIP_CALL_TO        = "sip.callTo"        # dialled number (== your Twilio number)
SIP_TRUNK_NUMBER   = "sip.trunkPhoneNumber"  # number on the inbound trunk
SIP_PARTICIPANT_ID = "sip.sipParticipantId"

# ── CRM collection / field config ────────────────────────────────────────────
# Set MONGO_CRM_COLLECTION in .env to override; defaults to "customers".
CRM_COLLECTION = os.getenv("MONGO_CRM_COLLECTION", "customers")

# How customer documents store the phone number.  We try all of these in order.
PHONE_FIELDS = ["primary_phone", "phone_number", "mobile", "contact_number", "phone"]


def extract_sip_attrs(participant: Any) -> dict:
    """
    Pull SIP attributes from a LiveKit participant object.

    Returns a dict with keys:
      call_id, call_from, call_to, trunk_num, is_sip
    """
    attrs: dict = getattr(participant, "attributes", None) or {}
    call_id  = attrs.get(SIP_CALL_ID, "") or ""
    call_from = attrs.get(SIP_CALL_FROM, "") or ""
    call_to   = attrs.get(SIP_CALL_TO, "") or ""
    trunk_num = attrs.get(SIP_TRUNK_NUMBER, "") or ""

    return {
        "call_id":   call_id,
        "call_from": call_from,
        "call_to":   call_to,
        "trunk_num": trunk_num,
        "is_sip":    bool(call_id or call_from),
    }


def _normalize_phone(phone: str) -> list[str]:
    """
    Return a list of candidate phone strings to match in the DB.

    Twilio sends E.164 (+919876543210).  Our DB may store:
      - +919876543210  (E.164)
      - 9876543210     (10-digit, no country code)
      - 09876543210    (with leading 0)
    """
    phone = (phone or "").strip()
    digits = re.sub(r"\D", "", phone)

    candidates = [phone]              # original E.164
    if digits:
        candidates.append(digits)     # all-digits
        if digits.startswith("91") and len(digits) == 12:
            candidates.append(digits[2:])   # strip country code  → 10 digits
        if len(digits) == 10:
            candidates.append("91" + digits)   # prepend country code
            candidates.append("+91" + digits)  # E.164

    # deduplicate while preserving order
    seen, result = set(), []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


async def lookup_crm_by_phone(phone: str) -> dict[str, Any]:
    """
    Asynchronously look up a customer CRM record from MongoDB by phone number.

    Uses the MONGO_URL and DB_NAME env vars already present in .env.
    Returns a dict compatible with CallSession field names, or {} on miss.
    """
    import motor.motor_asyncio  # lazy import — only needed for SIP calls

    raw_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("DB_NAME", "marg_crm")

    # Strip surrounding escaped / literal quotes that may be in the .env file
    mongo_url = raw_url.strip('"').strip("'")
    db_name   = db_name.strip('"').strip("'")

    candidates = _normalize_phone(phone)
    if not candidates:
        logger.warning("[SIP_CRM] Empty phone — skipping MongoDB lookup")
        return {}

    logger.info("[SIP_CRM] Looking up phone=%s in %s.%s", phone, db_name, CRM_COLLECTION)

    try:
        client  = motor.motor_asyncio.AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
        db      = client[db_name]
        collection = db[CRM_COLLECTION]

        # Build OR query across all phone field names × all candidate formats
        or_clauses = [
            {field: candidate}
            for field in PHONE_FIELDS
            for candidate in candidates
        ]

        doc = await collection.find_one({"$or": or_clauses})
        client.close()

        if not doc:
            logger.warning("[SIP_CRM] No CRM record found for phone=%s", phone)
            return {}

        logger.info("[SIP_CRM] Found CRM record for phone=%s id=%s", phone, doc.get("_id"))
        return _map_doc_to_crm(doc)

    except Exception as exc:
        logger.error("[SIP_CRM] MongoDB lookup failed: %s", exc, exc_info=True)
        return {}


# Field mapping: MongoDB document keys → CallSession field names
_DOC_FIELD_MAP: dict[str, str] = {
    # Phone
    "primary_phone":    "primary_phone",
    "phone_number":     "primary_phone",
    "mobile":           "primary_phone",
    "contact_number":   "primary_phone",
    "phone":            "primary_phone",
    # Name
    "customer_name":    "customer_name",
    "name":             "customer_name",
    "full_name":        "customer_name",
    "contact_name":     "customer_name",
    # Company
    "company_name":     "company_name",
    "company":          "company_name",
    "business_name":    "company_name",
    "firm_name":        "firm_name",
    "firm":             "firm_name",
    # Contact details
    "crm_email":        "crm_email",
    "email":            "crm_email",
    "email_id":         "crm_email",
    "crm_pincode":      "crm_pincode",
    "pin_code":         "crm_pincode",
    "pincode":          "crm_pincode",
    "zip_code":         "crm_pincode",
    # Business
    "crm_business_type":  "crm_business_type",
    "business_type":      "crm_business_type",
    "crm_business_trade": "crm_business_trade",
    "business_trade":     "crm_business_trade",
    "trade":              "crm_business_trade",
}


def _map_doc_to_crm(doc: dict) -> dict[str, Any]:
    """Map a raw MongoDB document to CallSession-compatible field names."""
    mapped: dict[str, Any] = {}
    for doc_key, value in doc.items():
        if doc_key == "_id":
            continue
        session_key = _DOC_FIELD_MAP.get(doc_key)
        if session_key and value is not None:
            mapped[session_key] = str(value) if not isinstance(value, str) else value

    return mapped
