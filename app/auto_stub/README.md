# Auto stub (temporary)

Stands in for Supervity Auto so the Command Centre flow can be seen end to end.
All data is fake sample text.

## How it works

1. Intake saves a call as `received` and calls `hand_off()` in `app/services/auto_gateway.py`.
2. With `AUTO_MODE=stub`, `hand_off()` calls `deliver_handoff()` here.
3. After `AUTO_STUB_DELAY_SECONDS` (default 3) it posts the scenario's results into
   `process_output()` in `app/services/call_output.py`, the same function the real
   `POST /api/webhooks/output` route uses. Nothing here has its own validation.

Scenarios (picked per call in the drop form, only when `TEST_MODE=true`):
`normal`, `band_zero`, `invalid_band` (7), `missing_reason`, `duplicate_result`,
`recording_link_fails` (the hand-off itself fails).

## Removing it

1. Delete this folder (`app/auto_stub/`).
2. In `app/services/auto_gateway.py` delete both blocks between `AUTO STUB START` and `AUTO STUB END`,
   and replace `hand_off()` with the real Auto client. Keep `AutoHandoffError` and `HandOff`.
3. In `app/routers/calls.py` delete the blocks marked `AUTO STUB` (the scenario field and the config values).
4. In the frontend, delete the block marked `AUTO STUB` in `frontend/src/app/calls/new/page.tsx`.
5. Remove `AUTO_MODE`, `TEST_MODE`, `AUTO_STUB_DELAY_SECONDS` from `.env.example`.
