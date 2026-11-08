# Lesson 2: The policy gate and failing closed

**Idea:** every action passes a rule check in code you control. Unknown actions are refused.
**Report:** section 4 (Weak defaults to avoid), risks 1, 5 and 8.

## Run it

```bash
make demo-policy
```

The scenario (`scenarios/02_policy.yaml`) tries four things:

| Call | Expected | Why |
|---|---|---|
| `read_file secrets/token.env` | DENY | rule `no-secret-files` |
| `run_command ["ls", "&&", "rm", "-rf", "notes.txt"]` | ALLOW, but nothing is deleted | there is no shell, so `&&` is just an argument to `ls` |
| `run_command ["tar", ...]` | DENY | no rule mentions `tar`, so the **default** applies |
| `run_command ["cat", "secrets/token.env"]` | ALLOW, but the token is redacted | a gap in the policy, caught by the `secret_redactor` hook |

## Dry-run single calls

```bash
make policy-check TOOL=run_command ARGS='{"argv":["/bin/rm","-rf","/"]}'
make policy-check TOOL=read_file ARGS='{"path":"secrets/token.env"}'
make policy-check TOOL=send_email ARGS='{"to":"x@y.example"}'
```

## Read the code

- `harness/policy/gate.py`: precedence is deny, then ask, then allow, then the default, whatever the order of the rules in the file.
- `harness/tools/shell.py`: why an argument list without a shell removes a whole class of attacks.

## Experiment 1: fail open

In `config/policy.yaml`, change `default: deny` to `default: allow` and run `make demo-policy` again. Which call now runs that did not before? Change it back.

## Experiment 2: a crashing safety hook

In `config/harness.yaml`, add `always_crashes` to `hooks.enabled` and run `make demo-hello`.

- With `fail_closed: true`, every call is blocked.
- With `fail_closed: false`, the crash is logged as `hook_error` and the calls run anyway.

The second behaviour is a common accident in home-made harnesses: the security check throws, someone catches and prints the error, and the action goes ahead. Restore the config afterwards.

## Experiment 3: close the gap

The `cat secrets/token.env` call shows the policy has a gap: the secret-file rule only covers `read_file`. Write a rule that closes it. Hint: a `run_command` rule cannot see paths inside `argv`, so think about which layer should own this check.

## Discuss

- Why is "deny when nothing matches" safer than a long list of forbidden commands?
- The secret redactor caught what the policy missed. Should you rely on that?
