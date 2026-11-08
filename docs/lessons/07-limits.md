# Lesson 7: Limits and runaway loops

**Idea:** an agent that never stops costs money and can repeat a harmful action. Hard limits live outside the model.
**Report:** risk 14.

## Run it

```bash
make demo-runaway
```

The scripted model lists the workspace forever. The loop stops after `limits.max_steps` model calls (12) and logs `limit_reached`.

## Settings

In `config/harness.yaml`:

| Setting | Stops |
|---|---|
| `limits.max_steps` | too many model calls in one session |
| `limits.max_seconds` | a session that runs too long |
| `limits.max_output_chars` | huge tool output flooding the context (the full hash is still logged) |
| `tools.run_command.timeout_seconds` | a single command that hangs |

## Exercises

1. Set `max_steps: 3` and run `make demo-hello`. Does it still finish?
2. Make a scenario that runs `["cat", "big.txt"]` on a large file. Find the `truncated` flag in the audit log. Why log the hash of the full output?
3. Add a limit on the number of `ask` decisions per session. Where in the code does it belong?

## Discuss

- Which limit protects your budget, and which protects your systems?
- What should happen to work in progress when a limit is hit?
