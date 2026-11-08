# Short commands for the lessons. Everything runs in Docker.
DC := docker compose
RUN := $(DC) run --rm harness
# Lint and tests use the source on your disk, mounted read-only: no rebuild needed after edits.
DEV := $(DC) run --rm --no-deps -v "$(CURDIR):/src:ro" -w /src -e PYTHONPATH=/src

.PHONY: help up down build test lint check run demo-hello demo-policy demo-destructive demo-injection demo-provenance demo-runaway verify policy-check traces diagrams clean

help:            ## Show this list
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

build:           ## Build the harness image
	$(DC) build harness

up:              ## Start Ollama and Jaeger, download the model
	mkdir -p var/audit var/outbox
	$(DC) up -d ollama jaeger
	$(DC) run --rm model-pull

down:            ## Stop all containers
	$(DC) down

test:            ## Run the unit and scenario tests (no model needed)
	$(DEV) --entrypoint python harness -m pytest

lint:            ## Check style and Google-style docstrings with flake8
	$(DEV) --entrypoint flake8 harness harness tests scripts

check: lint test ## Lint, then test

diagrams:        ## Export the report's figures to docs/diagrams/ (run after editing the report)
	$(DC) run --rm --no-deps -v "$(CURDIR):/src" -w /src --user "$$(id -u):$$(id -g)" --entrypoint python harness scripts/export_diagrams.py

run:             ## Run a task against the real model: make run TASK="..." ROLE=analyst
	$(RUN) run --role $(or $(ROLE),analyst) "$(TASK)"

demo-hello:      ## Lesson 1: the loop with a scripted model
	$(RUN) run --scenario /app/scenarios/01_hello.yaml "List the workspace and read the notes."

demo-policy:     ## Lesson 2: probe the policy gate
	$(RUN) run --scenario /app/scenarios/02_policy.yaml "Probe the policy."

demo-destructive: ## Lesson 3: delete and overwrite attempts
	$(RUN) run --scenario /app/scenarios/03_destructive.yaml "Clean up the workspace."

demo-injection:  ## Lesson 4: a hijacked model tries to exfiltrate data
	$(RUN) run --approval deny --scenario /app/scenarios/04_injection.yaml "Summarise the latest email in the inbox."

demo-provenance: ## Lesson 6: manifests, access filter and citation check
	$(RUN) run --scenario /app/scenarios/06_provenance.yaml "What is our pricing policy?"

demo-runaway:    ## Lesson 7: a model that never stops
	$(RUN) run --scenario /app/scenarios/07_runaway.yaml "Keep checking the workspace."

verify:          ## Lesson 5: check that the audit log has not been changed
	$(RUN) verify-audit

policy-check:    ## Lesson 2: dry-run a tool call: make policy-check TOOL=run_command ARGS='{"argv":["rm","-rf","x"]}'
	$(RUN) policy-check $(TOOL) '$(ARGS)'

traces:          ## Where to look at traces
	@echo "Open http://localhost:16686 and pick service 'llm-harness'"

clean:           ## Delete audit logs, outbox and workspace changes (asks first)
	@read -p "Delete var/audit, var/outbox and reset workspace? [y/N] " a; [ "$$a" = "y" ] && rm -rf var/audit/* var/outbox/* && git checkout -- workspace || echo "Nothing deleted."
