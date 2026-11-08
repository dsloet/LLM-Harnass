# Lesson 5: Observability and a tamper-evident audit log

**Idea:** traces show what happened; the audit log lets you prove it.
**Report:** risks 3 and 4.

## Traces in Jaeger

Run any demo, then open http://localhost:16686, pick service `llm-harness` and open the latest trace. You see one `agent session` span, with `model call`, `tool ...` and `policy check` spans inside it. Click a policy span: its attributes hold the decision and the rule.

Questions to answer from the trace:

- Which step took the longest? (With the real model it is always the model call.)
- Which tool calls were refused? (`outcome = refused`)

## The audit log

```bash
make verify
```

Each line in `var/audit/audit.jsonl` holds the hash of the line before it. Look at two lines:

```bash
sed -n '1,2p' var/audit/audit.jsonl | python3 -m json.tool --json-lines
```

`prev_hash` of line 2 equals `hash` of line 1.

## Tamper with it

1. Open `var/audit/audit.jsonl`, find a `policy_decision` with `"decision": "deny"`, and change it to `"allow"`.
2. Run `make verify`. It reports the exact line that was changed.
3. Undo your edit (or delete `var/` and run a demo again).

## Read the code

- `harness/audit/log.py`: `append` and `verify_chain`, about 40 lines in total.
- `harness/telemetry.py`: tracing is optional and never breaks a run.

## Discuss

- Someone with write access could recompute every hash and rewrite the whole chain. How would you detect that? (Hint: copy the latest hash somewhere the writer cannot reach, at regular intervals.)
- Why keep traces and an audit log apart? Think about retention, access, and who reads each.
- The log stores full tool arguments and prompts. Which personal data ends up there, and how long should you keep it? (Report risk 23.)
