import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from state_machine.session import CallSession

logger = logging.getLogger(__name__)
LOG_FILE = Path(__file__).resolve().parents[3] / "call_logs.jsonl"


async def log_call(session: CallSession):
    record = {
        "call_id": session.call_id,
        "customer_name": session.customer_name,
        "company_name": session.company_name,
        "firm_name": session.firm_name,
        "primary_phone": session.primary_phone,
        "main_disposition": session.main_disposition,
        "sub_disposition": session.sub_disposition,
        "billing_started": session.billing_started,
        "callback_requested": session.callback_requested,
        "callback_time_phrase": session.callback_time_phrase,
        "states_visited": [state.value if hasattr(state, "value") else str(state) for state in session.states_visited],
        "crm_snapshot": {
            "crm_email": session.crm_email,
            "crm_pincode": session.crm_pincode,
            "crm_business_type": session.crm_business_type,
            "crm_business_trade": session.crm_business_trade,
        },
        "verified_updates": {
            "whatsapp_number": session.whatsapp_number,
            "alternate_number": session.alternate_number,
            "pincode": session.pincode,
            "business_type": session.business_type,
            "business_trade": session.business_trade,
            "email": session.email,
            "purchase_amount": session.purchase_amount,
            "referral_name": session.referral_name,
            "referral_number": session.referral_number,
        },
        "transcript_turns": len(session.transcript),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "DISPOSITION: %s / %s | Customer: %s",
        record["main_disposition"],
        record["sub_disposition"],
        record["customer_name"] or record["company_name"] or "Unknown",
    )

    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("Failed to write call log: %s", exc)

    return record
