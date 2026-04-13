import json
import logging
from datetime import datetime, timezone
from state_machine.session import CallSession

logger = logging.getLogger(__name__)


async def log_call(session: CallSession):
    """Log final call disposition and collected data."""
    record = {
        "call_id": session.call_id,
        "customer_name": session.customer_name,
        "firm_name": session.firm_name,
        "main_disposition": session.main_disposition,
        "sub_disposition": session.sub_disposition,
        "billing_status": session.billing_status,
        "sentiment": session.sentiment,
        "dsat_flag": session.dsat_flag,
        "states_visited": [s.value if hasattr(s, 'value') else str(s) for s in session.states_visited],
        "crm_updates": {
            "whatsapp_number": session.whatsapp_number,
            "alternate_number": session.alternate_number,
            "pincode": session.pincode,
            "city": session.city,
            "business_trade": session.business_trade,
            "email": session.email,
            "price_confirmed": session.price_confirmed,
            "license_number": session.license_number,
        },
        "issue_description": session.issue_description,
        "callback_datetime": session.callback_datetime,
        "reference_name": session.reference_name,
        "reference_number": session.reference_number,
        "delay_subreason": session.delay_subreason,
        "will_not_use_reason": session.will_not_use_reason,
        "transcript_turns": len(session.transcript),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"DISPOSITION: {record['main_disposition']} / {record['sub_disposition']} "
                f"| Customer: {record['customer_name']} | Sentiment: {record['sentiment']}")

    # Write to JSONL file for now (replace with MongoDB in production)
    try:
        with open("call_logs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to write call log: {e}")

    return record
