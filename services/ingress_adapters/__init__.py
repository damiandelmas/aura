"""Per-source ingress adapters for the Aura HTTP in-jack.

Each adapter is a module exposing two pure functions:

    verify(raw_body: bytes, headers: Mapping[str, str], secret: str) -> bool
        True iff this delivery is authentically from the source.

    normalize(payload: dict, headers: Mapping[str, str]) -> dict | None
        Translate the source's payload into a native envelope, or None to ignore.
        Returns {"target", "kind", "body", "dedupe", "meta"}.

An adapter exists ONLY because a foreign source imposes its own signature scheme
and JSON shape. Source text is untrusted task content: it must land in body/meta
and never choose target, route, or auth.
"""
