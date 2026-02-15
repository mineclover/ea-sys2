"""Re-export from ea_profile for backward compatibility.

ProfileBuilder is extended with build_with_corpus() which depends on
ea_kernel.rule_corpus and ea_kernel.types (kernel-specific).
"""

from ea_profile.builder import ProfileBuilder as _BaseProfileBuilder
from ea_profile.builder import *  # noqa: F401, F403
from ea_profile.types import SchemaPort


class ProfileBuilder(_BaseProfileBuilder):
    """Kernel-aware ProfileBuilder with build_with_corpus support."""

    def build_with_corpus(
        self,
        kernel: SchemaPort | None = None,
        *,
        auto_fallback: bool = True,
        validate: bool = True,
    ) -> tuple:
        """Build the KernelProfile and return corpus entries for its rules.

        Returns (profile, corpus_entries) where corpus_entries contains
        one RuleCorpusEntry per rule, with explicit metadata where provided
        and inferred metadata otherwise.
        """
        from ea_kernel.rule_corpus import RuleCorpus
        from ea_kernel.types import RuleCorpusEntry as _RCE

        profile = self.build(kernel, auto_fallback=auto_fallback, validate=validate)

        entries: list[_RCE] = []
        for rule in profile.validity_rules:
            meta = self._rule_metadata.get(rule.id)
            if meta is None:
                meta = RuleCorpus.infer_metadata(rule)
            entries.append(_RCE(rule=rule, metadata=meta))

        return profile, tuple(entries)
