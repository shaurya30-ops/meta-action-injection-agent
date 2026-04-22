import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from conversation_engine.hot_path.parser import match_state_grammar
from state_machine.intents import Intent
from state_machine.resolver import execute_auto_chain, post_transition, resolve_next_state
from state_machine.session import CallSession
from state_machine.states import State
from state_machine.turn_parser import parse_turn


def test_fixture_backed_grammar_matches_real_transcript_cases():
    fixture_path = (
        BACKEND_ROOT
        / "conversation_engine"
        / "evaluation"
        / "fixtures"
        / "real_convo_2.hot_path.json"
    )
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

    for fixture in fixtures:
        match = match_state_grammar(fixture["state"], fixture["utterance"])
        assert match.rule is not None, fixture["id"]
        emitted = set(match.emitted)
        assert set(fixture["expected_events"]).issubset(emitted), fixture["id"]


def test_availability_batao_is_promoted_to_affirm_without_classifier_help():
    session = CallSession(current_state=State.CHECK_AVAILABILITY)

    turn = parse_turn(session, Intent.ASK, "बताओ")

    assert turn.speech_act == Intent.AFFIRM


def test_billing_started_with_training_pending_is_deterministic():
    session = CallSession(current_state=State.ASK_BILLING_STATUS)

    turn = parse_turn(session, Intent.COMPLAIN, "Billing तो start हो गई है पर training नहीं हुई है.")

    assert turn.workflow_answer == "billing_started_training_pending"
    assert turn.speech_act == Intent.AFFIRM


def test_verify_whatsapp_training_interrupt_routes_to_five_turn_training_flow():
    session = CallSession(current_state=State.VERIFY_WHATSAPP, primary_phone="8529152168")
    transcript = "हाँ जी मैम WhatsApp पे available है but मैम मेरे को ना training की requirement है"
    turn = parse_turn(session, Intent.UNCLEAR, transcript)

    next_state = resolve_next_state(session, turn, transcript)
    post_transition(session, turn, transcript, next_state)

    assert turn.workflow_answer == "training_pending_interrupt"
    assert next_state == State.TRAINING_PENDING_ACK
    assert session.current_state == State.TRAINING_PENDING_ACK
    assert session.billing_resume_state == State.VERIFY_WHATSAPP
    assert session.billing_blocker_reason == "training_pending"

    chain = execute_auto_chain(session, next_state)
    assert chain == [State.TRAINING_PENDING_ACK, State.ASK_TRAINING_PENDING_DURATION]
    assert session.current_state == State.ASK_TRAINING_PENDING_DURATION
