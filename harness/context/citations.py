"""Check the citations in a final answer against the context ledger.

A model can invent a citation as easily as a fact. This check is done in
code: every [source:ID] must refer to an item the model actually saw in this
session. It cannot prove the model USED that source correctly; for that, see
the leave-one-out exercise in docs/lessons/06-context-provenance.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from harness.context.ledger import ContextLedger

_CITATION = re.compile(r"\[source:([A-Za-z0-9_.:\-]+)\]")


@dataclass(frozen=True)
class CitationReport:
    cited: tuple[str, ...]
    unknown: tuple[str, ...]        # cited, but never in the context: invented
    missing: bool                   # citations required but none given

    @property
    def ok(self) -> bool:
        return not self.unknown and not self.missing


def check_citations(answer: str, ledger: ContextLedger, required: bool) -> CitationReport:
    cited = tuple(dict.fromkeys(_CITATION.findall(answer)))
    unknown = tuple(source_id for source_id in cited if not ledger.has(source_id))
    return CitationReport(cited=cited, unknown=unknown, missing=required and not cited)
