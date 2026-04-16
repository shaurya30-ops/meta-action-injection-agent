# Production State-Flow Redesign For आकृति

## Why The Current Machine Feels Robotic

The current state machine is solid for strict sequencing, but it is still mostly a
`form flow`.

Current files:

- [app/backend/state_machine/states.py](/Q:/Meta-Action-Injection/app/backend/state_machine/states.py)
- [app/backend/state_machine/transitions.py](/Q:/Meta-Action-Injection/app/backend/state_machine/transitions.py)
- [app/backend/state_machine/resolver.py](/Q:/Meta-Action-Injection/app/backend/state_machine/resolver.py)
- [app/backend/state_machine/actions.py](/Q:/Meta-Action-Injection/app/backend/state_machine/actions.py)
- [app/backend/state_machine/session.py](/Q:/Meta-Action-Injection/app/backend/state_machine/session.py)

The main gaps are structural:

1. The machine models `what question comes next`, but not `how to respond like a human` before asking it.
2. It uses one flat `State` enum for everything, so empathy, clarification, user questions, hurry, complaint, and resume logic are not first-class concepts.
3. Many verification steps map `DENY / INFORM / ELABORATE` directly to the next state, which is too lossy for real conversations.
4. Query handling is not modeled as a resumable subroutine.
5. Emotional adaptation is not represented in session state at all.
6. The intent taxonomy is too generic to drive production dialogue by itself.

The result is that the agent can be correct about sequence while still sounding
transactional.

## Design Goal

Keep the deterministic business flow, but make the agent feel human by introducing
three control layers instead of one:

1. `Workflow State`
   This tracks the business step we are currently trying to complete.
2. `Dialog Mode`
   This tracks whether we are in normal flow, handling a query, calming frustration,
   clarifying confusion, repairing input, or closing.
3. `Affect State`
   This tracks the customer's current emotional tone so the next response is phrased
   appropriately.

This avoids a giant brittle flat enum like
`VERIFY_PINCODE_WHILE_USER_IS_FRUSTRATED_AND_BUSY`.

## Recommended Controller Shape

Use a hierarchical state machine with this shape:

```text
ConversationController
├─ workflow_state
├─ dialog_mode
├─ affect_state
├─ resume_stack
├─ expected_slot
└─ pending_actions
```

Recommended runtime logic per turn:

1. Parse the user turn into a structured `TurnFrame`.
2. Run global interrupts first.
3. Update emotional stance.
4. If a side-quest is active, resolve it.
5. Otherwise resolve the current workflow step.
6. Build the next response as:
   `acknowledgement + empathy/repair line + one business question`

## TurnFrame Instead Of Raw Intent Only

The current 15-intent setup is still useful, but it should no longer be the only
decision signal.

Recommended parsed turn schema:

```python
TurnFrame(
    speech_act,          # AFFIRM / DENY / ASK / INFORM / COMPLAIN / DEFER ...
    workflow_answer,     # billing_started / billing_not_started / same_whatsapp / other_whatsapp ...
    query_type,          # technical_support / pricing / clarification / dealer_setup / general
    affect,              # neutral / positive / frustrated / confused / hurried / disengaged
    entities,            # digits, email, business_type, business_trade, referral_name, amount
    callback_request,    # bool
    wants_resume,        # bool
    wants_closure,       # bool
)
```

This is the key production difference:

- `speech_act` says how the user spoke
- `workflow_answer` says what they meant for this exact step
- `affect` says how the next line should feel

## Recommended Workflow States

These are the business states that should exist as durable workflow steps.

### Opening And Qualification

- `OPENING_GREETING`
- `CONFIRM_IDENTITY`
- `INTRODUCE_CALL`
- `CHECK_TALK_WINDOW`
- `ASK_BILLING_STATUS`
- `EXPLORE_BILLING_BLOCKER`
- `OFFER_BILLING_HELP`

### Contact Verification

- `VERIFY_WHATSAPP_AVAILABILITY`
- `COLLECT_WHATSAPP_NUMBER`
- `CONFIRM_WHATSAPP_NUMBER`
- `OFFER_ALTERNATE_NUMBER`
- `COLLECT_ALTERNATE_NUMBER`
- `CONFIRM_ALTERNATE_NUMBER`

### Detail Verification

- `VERIFY_PINCODE`
- `COLLECT_PINCODE`
- `CONFIRM_PINCODE`
- `VERIFY_BUSINESS_DETAILS`
- `CONFIRM_BUSINESS_CORRECTION`
- `VERIFY_EMAIL`
- `COLLECT_EMAIL_CORRECTION`
- `CONFIRM_EMAIL_CORRECTION`

### Usage And Value

- `ASK_PURCHASE_AMOUNT`
- `DELIVER_SUPPORT_AND_REFERRAL`

### Referral

- `COLLECT_REFERRAL_NAME`
- `COLLECT_REFERRAL_NUMBER`
- `CONFIRM_REFERRAL_NUMBER`
- `REFERRAL_DECLINE_NUDGE`

### Closing

- `PRE_CLOSING`
- `CALLBACK_CLOSING`
- `INVALID_REGISTRATION`
- `FIXED_CLOSING`
- `END`

## Recommended Dialog Modes

These should not replace workflow states. They should wrap them.

- `NORMAL`
- `HANDLE_QUERY`
- `HANDLE_COMPLAINT`
- `HANDLE_CONFUSION`
- `HANDLE_FRUSTRATION`
- `HANDLE_HURRY`
- `REPAIR_INPUT`
- `CLOSE_ONLY`

Behavior:

- `workflow_state` answers: what business step is pending?
- `dialog_mode` answers: what kind of conversation are we in right now?

Example:

- workflow state: `VERIFY_PINCODE`
- dialog mode: `HANDLE_QUERY`
- affect state: `FRUSTRATED`

That means:

- answer the user's query first
- do it softly
- then resume pincode verification

## Recommended Affect States

These should be stored in session and updated every turn.

- `NEUTRAL`
- `POSITIVE`
- `FRUSTRATED`
- `CONFUSED`
- `HURRIED`
- `DISENGAGED`
- `COMPLAINT`

Important:

Do not create separate workflow states for every affect.
Instead, use affect to pick acknowledgement style and pacing.

## Session Fields That Should Be Added

Recommended additions to `CallSession`:

```python
dialog_mode: str = "NORMAL"
affect_state: str = "NEUTRAL"
resume_state: State | None = None
resume_reason: str = ""
expected_slot: str = ""
last_user_query_type: str = ""
last_blocker_reason: str = ""
billing_blocker_reason: str = ""
busy_but_continuing: bool = False
user_disengagement_count: int = 0
query_resolution_pending: bool = False
business_correction_pending: bool = False
email_correction_pending: bool = False
referral_declined_once: bool = False
hard_stop_after_closing: bool = False
```

## Where The Current Flow Needs Stronger Mapping

### 1. Opening After `OPENING_GREETING`

Current machine mostly routes all non-denial replies to `CHECK_AVAILABILITY`.
That is too shallow.

Recommended mapping:

- identity confirmed -> `INTRODUCE_CALL`
- identity denied -> `INVALID_REGISTRATION`
- confusion / who are you / what is this call -> `HANDLE_QUERY`, then resume `INTRODUCE_CALL`
- complaint at opening -> `HANDLE_FRUSTRATION`, then retry `INTRODUCE_CALL`
- busy / callback -> `CALLBACK_CLOSING`

### 2. Talk-Time Check

`CHECK_AVAILABILITY` should become `CHECK_TALK_WINDOW`.

Outcomes:

- can talk -> `ASK_BILLING_STATUS`
- busy, call later -> `CALLBACK_CLOSING`
- rushed but willing -> set `affect_state = HURRIED`, continue with compressed acknowledgements
- objection or irritation -> `HANDLE_FRUSTRATION`, then retry `CHECK_TALK_WINDOW`

### 3. Billing Status

Current machine loops on `ASK_BILLING_STATUS` without modeling why billing has not started.

Recommended mapping:

- billing started -> `VERIFY_WHATSAPP_AVAILABILITY`
- billing not started -> `EXPLORE_BILLING_BLOCKER`
- user says "everything fine" but vague -> nudge once, stay in billing cluster
- technical issue -> `HANDLE_QUERY`, then return to billing cluster

### 4. Billing Not Started Path

Your reference prompt clearly requires a soft nudge here.

Add:

- `EXPLORE_BILLING_BLOCKER`
- `OFFER_BILLING_HELP`

Possible blocker labels:

- `NO_TIME`
- `TECHNICAL_ISSUE`
- `DEALER_PENDING`
- `TRAINING_GAP`
- `NO_CLEAR_REASON`

Then continue to detail verification.

### 5. WhatsApp Flow

Current machine is better now, but it still lacks explicit confirmation states.

Recommended mapping:

- same WhatsApp -> `OFFER_ALTERNATE_NUMBER`
- different WhatsApp -> `COLLECT_WHATSAPP_NUMBER`
- 10 digits complete -> `CONFIRM_WHATSAPP_NUMBER`
- confirmation yes -> `OFFER_ALTERNATE_NUMBER`
- confirmation no -> stay in WhatsApp collection cluster

### 6. Alternate Number Flow

This should mirror WhatsApp exactly:

- offer
- collect if yes
- confirm
- proceed only after explicit user reply

Also keep one soft branch for:

- "no alternate number" -> `VERIFY_PINCODE`

### 7. Pincode Flow

This should be a 3-step cluster, not a single verify state plus a collection state.

- `VERIFY_PINCODE`
- `COLLECT_PINCODE`
- `CONFIRM_PINCODE`

That produces clean behavior for:

- correct as-is
- corrected in same turn
- corrected over multiple turns
- overflow reset and re-ask

### 8. Business Details

Current code moves to email even when the user corrects business details.
That is too abrupt for real calls.

Recommended mapping:

- confirm both as read
- if corrected, extract correction
- echo correction back in `CONFIRM_BUSINESS_CORRECTION`
- only then continue

This is where "realness" improves a lot.

### 9. Email Flow

Current machine also jumps too fast here.

Recommended mapping:

- `VERIFY_EMAIL`
- if corrected -> `COLLECT_EMAIL_CORRECTION`
- `CONFIRM_EMAIL_CORRECTION`
- then move to purchase amount

### 10. Purchase Amount

This can stay simple, but it still needs better outcome handling:

- provided amount -> continue
- does not remember -> continue, store `unknown`
- asks why needed -> `HANDLE_QUERY`, then resume `ASK_PURCHASE_AMOUNT`

### 11. Support Pitch And Referral

This one should remain a single deterministic scripted turn.
That part of your prompt is correct and should not be loosened.

But afterward the outcomes should branch better:

- yes referral -> `COLLECT_REFERRAL_NAME`
- no referral -> `REFERRAL_DECLINE_NUDGE`
- question about support -> `HANDLE_QUERY`, then return to referral ask

### 12. Referral Collection

Current machine only models number collection.
That is incomplete.

Recommended flow:

- `COLLECT_REFERRAL_NAME`
- `COLLECT_REFERRAL_NUMBER`
- `CONFIRM_REFERRAL_NUMBER`
- `PRE_CLOSING`

### 13. Closing

The closing contract should stay strict:

- `PRE_CLOSING`
- `FIXED_CLOSING`
- `END`

The fixed closing line should remain deterministic and isolated.

## Query Handling Should Be A Subroutine

This is the biggest missing production feature after empathy.

Recommended query flow:

1. Save `resume_state = current workflow_state`
2. Switch `dialog_mode = HANDLE_QUERY`
3. Classify query type
4. Answer query
5. Ask one resolution-check question
6. Resume from `resume_state`

Suggested query categories:

- `TECHNICAL_SUPPORT`
- `PRICING`
- `RENEWAL`
- `SETUP_PENDING`
- `TICKET_PROCESS`
- `MARG_HELP_PROCESS`
- `GENERAL_CLARIFICATION`

This should be implemented as subroutines, not duplicate copies of every main state.

## Empathy Should Be Deterministic, Not Freeform

The machine should not hope the model "sounds empathetic."
It should choose empathy deliberately.

Recommended response builder:

```text
response = acknowledgement(affect_state, speech_act, workflow_state)
         + optional_empathy_line(dialog_mode, affect_state)
         + business_prompt(workflow_state)
```

Examples:

- positive:
  `बहुत अच्छा, ये सुनकर अच्छा लगा.`
- frustrated:
  `जी, मैं समझ सकती हूँ — ये frustrating लगता है.`
- confused:
  `जी, मैं थोड़ा आसान तरीके से बताती हूँ.`
- hurried:
  `बिल्कुल, मैं short में रखती हूँ.`

This makes the agent feel human without giving up control.

## Which Turns Should Stay Fully Deterministic

These should stay exact and direct-rendered:

- fixed opening
- introduction line
- billing question
- WhatsApp verification question
- alternate number offer
- pincode verification prompt
- support pitch + referral ask
- fixed closing

These can be semi-deterministic templates:

- acknowledgements
- empathy lines
- blocker exploration
- query answers
- clarification repairs
- decline nudges

## Recommended Transition Policy

Use this order every turn:

1. `hard stop after closing`
2. `callback intent`
3. `goodbye / disconnect intent`
4. `user query / clarification`
5. `frustration / complaint / hurry / confusion`
6. `step-specific slot resolution`
7. `fallback repair`

This ordering matters. It keeps the agent human and safe.

## Real-Production Rules The Current Machine Still Needs

### Resume Safety

The agent must always know:

- what step was paused
- why it was paused
- whether the user query is already resolved

### Explicit Confirmation States

Never jump to the next business step right after a correction that matters.

### Short Acknowledgement Before Every Next Question

This should be enforced by the response builder, not left to chance.

### Refusal Handling Versus Objection Handling

`No alternate number` is not the same as
`Why are you asking so many questions?`

### Busy Versus Uninterested

These should not map to the same close path.

- busy -> callback
- uninterested but polite -> warm close
- angry escalation -> complaint path first

### Compressed Flow For Hurried Users

Do not skip mandatory steps, but reduce acknowledgement length and avoid unnecessary probes.

### Soft Nudge Limits

Nudge exactly once in dead-end scenarios.
Do not repeatedly push.

## Recommended Implementation Strategy

Do this in phases.

### Phase 1

Refactor the session model and add controller fields:

- `dialog_mode`
- `affect_state`
- `resume_state`
- `expected_slot`

### Phase 2

Split the current workflow into better verification clusters:

- confirm WhatsApp
- confirm alternate
- confirm pincode
- confirm business correction
- confirm email correction
- collect referral name

### Phase 3

Add query-handling subroutines with resume.

### Phase 4

Add affect detection plus deterministic acknowledgement selection.

### Phase 5

Improve NLU from flat intent to `TurnFrame`.

## Final Recommendation

Do not try to solve this by adding dozens of flat states only.
That will make the machine harder to maintain and still not feel human.

The right production design is:

- a deterministic workflow state
- a transient dialog mode
- a persistent affect state
- a resume pointer
- a structured turn parser

That is the cleanest path to a natural, elegant, and controllable support-calling agent.
