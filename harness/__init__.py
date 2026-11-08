"""LLM-Harnass: a teaching harness around a language model.

Read docs/architecture.md first. Each sub-package is one control layer:

    model/     talks to the model (Ollama, or a scripted fake for lessons)
    policy/    decides allow / deny / ask for every proposed tool call
    tools/     the only way the model can touch anything
    context/   builds what the model sees, with sources and trust labels
    audit/     tamper-evident log of everything that happened
    hooks/     checks that run before and after each tool call
    loop.py    the agent loop that ties it together
"""
