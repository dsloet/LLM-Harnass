# Lesson 3: Destructive actions

**Idea:** irreversible actions need a person, and changes must be undoable.
**Report:** risk 2.

## Run it

```bash
make demo-destructive
```

The scripted model tries to "clean up":

1. `rm -rf .` is **denied** outright (rule `no-delete-commands`); no approval can unlock it.
2. Overwriting `report_draft.md` is **ask**: you get a prompt. Answer `y` this time.
3. `python -c "import shutil; shutil.rmtree('.')"` is **ask** because Python can do anything. Answer `n`.

## Undo the overwrite

Every `write_file` keeps a snapshot of the old content in `var/audit/snapshots/<session>/`, outside the workspace, so the agent cannot change it.

```bash
grep session_start var/audit/audit.jsonl | tail -1     # find your session ID
docker compose run --rm harness revert <session_id>
cat workspace/report_draft.md                          # the original is back
```

## Read the code

- `harness/tools/files.py`: `_snapshot` and `revert_session`.
- `harness/policy/approval.py`: why there is no terminal means the answer is **no**.

## Exercises

1. Run `make demo-destructive` with `HARNESS_APPROVAL=deny make demo-destructive`. What does an unattended run do with "ask"?
2. The snapshot only covers `write_file`. If you approved the Python command, would `revert` help? What would? (Think about version control and backups outside the agent's reach.)

## Discuss

- Which actions in your organisation are truly irreversible? Sent emails, payments, deleted records, published posts.
- What should an approval prompt show so a person can decide well? Look at what ours shows.
