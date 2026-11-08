# Lesson 6: Context provenance

**Idea:** for every model call, record exactly what the model saw, where it came from and how far it can be trusted. Then narrow down what it used.
**Report:** section 6, risks 17 to 25.

## Run it

```bash
make demo-provenance
```

The scripted model searches the records and answers with two citations. One is real (`records:rec-001`), one is invented (`records:rec-999`). The citation check reports the invented one.

## What the model saw

Find the call IDs of your session:

```bash
grep model_call var/audit/audit.jsonl | tail -2 | python3 -c "import sys,json; [print(json.loads(l)['data']['call_id']) for l in sys.stdin]"
docker compose run --rm harness show-call <call_id>
```

```
source                           trust      version                    sha256
system-rules                     owner      1794122682                 e97975d6fdd8
request                          user                                  3b353e6424f8
records:rec-001                  verified   v3 (2026-09-01)            82321f85f61c
```

This is the **context manifest**: every item, its trust level, its version and a hash of its content. The full prompt is in `var/audit/calls/<call_id>.json`.

## Access is filtered before the model sees anything

```bash
docker compose run --rm harness run --role analyst --scenario /app/scenarios/04_injection.yaml "x"
docker compose run --rm harness run --role manager --scenario /app/scenarios/04_injection.yaml "x"
```

Compare the `access_filter` events. Filtering after the model has read a record is too late: it can repeat it.

## Read the code

- `harness/context/ledger.py`: `ContextItem` and the manifest.
- `harness/context/sources.py`: the access filter.
- `harness/context/citations.py`: what the citation check can and cannot prove.

## "What did it use?": leave-one-out

The manifest proves what the model saw, not what it used. A practical test for a decision that matters:

1. Run the real model on a question and note the answer.
2. Remove one source (for example, move `data/records/rec-001.json` out of the folder) and run again.
3. If the answer changes, that source drove it. If it does not, the citation to it was decoration.

## Exercises

1. Set `context.require_citations: false`. Which failure does the check no longer catch?
2. Extend `check_citations` so it also checks that quoted text appears in the cited source.
3. A record changes after the model read it. Which field in the manifest lets you prove which version the model saw?

## Discuss

- Context compression (summarising old turns) saves tokens but loses provenance. How would you keep the link from a summary back to its sources?
- Why is the model's own explanation of its reasoning not an audit trail?
