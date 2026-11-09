# Fix for "ORL Orchestrator Phani": pass the two results to the combined JSON

Problem: steps 3 and 4 have no output mapping, so `_subworkflow_outputs_step_3` and
`_subworkflow_outputs_step_4` are never filled, and step 5 returns
`{"call_audit": [], "lead_score": []}`.

In the Auto editor, open each step's subworkflow settings and paste the code below
into **Output mapping** (steps 3 and 4), then replace the code of step 5.

## Step 3 (Run Call Audit Subworkflow): output mapping

```python
import json

def _parse(v):
    if isinstance(v, (dict, list)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in '{[':
            try:
                return json.loads(s)
            except Exception:
                return None
    return None

def _find_block(o, agent, depth=0):
    if depth > 8:
        return None
    if isinstance(o, str):
        o = _parse(o)
    if isinstance(o, dict):
        if o.get('agent') == agent and isinstance(o.get('result'), dict):
            return o
        for v in o.values():
            b = _find_block(v, agent, depth + 1)
            if b:
                return b
    elif isinstance(o, list):
        for v in reversed(o):
            b = _find_block(v, agent, depth + 1)
            if b:
                return b
    return None

_raw_step_3 = globals().get('_subworkflow_outputs_step_3') or {}
step_step3_block = _find_block(_raw_step_3, 'call_audit')
print(json.dumps(step_step3_block, indent=2, ensure_ascii=False, default=str))
```

## Step 4 (Run Lead Score Subworkflow): output mapping

Same code as step 3, with these two lines changed:

```python
_raw_step_4 = globals().get('_subworkflow_outputs_step_4') or {}
step_step4_block = _find_block(_raw_step_4, 'lead_score')
print(json.dumps(step_step4_block, indent=2, ensure_ascii=False, default=str))
```

## Step 5 (Combine Subworkflow Outputs): code

```python
import json

info = globals().get('step_step1_call_info', {}) or {}
combined = {
    'task_id': info.get('task_id'),
    'transcript': globals().get('transcript'),
    'call_audit': globals().get('step_step3_block'),
    'lead_score': globals().get('step_step4_block'),
}
print(json.dumps(combined, indent=2, ensure_ascii=False, default=str))
```

Result shape the Command Center reads:

```json
{
  "task_id": "call_...",
  "transcript": "[Agent] ...",
  "call_audit": {"agent": "call_audit", "task_id": "call_...", "result": {"checks": [...], "score_percent": 100, "summary": "..."}},
  "lead_score": {"agent": "lead_score", "task_id": "call_...", "result": {"band": 1, "label": "...", "reason": "...", "evidence": ["..."]}}
}
```
