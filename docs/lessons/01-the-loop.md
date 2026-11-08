# Lesson 1: The loop

**Idea:** the model proposes, the harness decides and records.
**Report:** section 2 (What a harness is), risks 1 and 3.

## Run it

```bash
make demo-hello
```

This uses a **scripted model** (`scenarios/01_hello.yaml`): it replays fixed steps, whatever the tool results are. That way every run is identical and you can study the harness instead of the model.

## What you see

```
[1] model proposes list_files {"path": "."}
    policy: ALLOW (rule read-workspace) Reading inside the workspace is safe.
    result: ... chars from tool:list_files:1
[2] model proposes read_file {"path": "notes.txt"}
    policy: ALLOW (rule read-workspace) ...
Answer: The notes say ... [source:tool:read_file:2]
Citation check passed
```

Every step has three parts: what the model **proposed**, what the **policy** decided, and what came **back** (with a source ID).

## Read the code

1. `harness/loop.py`, function `_run`: the whole loop is about 20 lines.
2. `harness/dispatch.py`, function `handle_tool_call`: the fixed order every call goes through.
3. `harness/model/scripted.py`: how the fake model works.

Notice that `loop.py` contains no `if dangerous:` logic. Safety lives in the gate, the tools, the hooks and the container.

## Look at the evidence

```bash
cat var/audit/audit.jsonl | python3 -m json.tool --json-lines | less
```

Find the `session_start`, `model_call`, `policy_decision` and `final_answer` events of your session.

## Exercises

1. Write your own scenario in `scenarios/` that reads `report_draft.md` and answers. Run it with
   `docker compose run --rm harness run --scenario /app/scenarios/<yours>.yaml "task"`.
2. Make the scenario call a tool that does not exist (`tool: delete_everything`). What does the harness do, and which audit event records it?

## Discuss

- Why should the loop itself contain no safety decisions?
- What would change if the model could call Python functions directly instead of going through `dispatch.py`?
