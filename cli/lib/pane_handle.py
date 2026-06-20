"""Backend-neutral terminal pane/window identity — the single owner of the ref format.

Today the `tmux:<fleet>:%N` pane-ref and `tmux:<fleet>:<window>` window-ref formats
are hand-built and hand-parsed in ~23 files, in 7 slightly-different ways that do
not all agree. That leak is why the prior Zellij backend swap failed: no single
seam owned the format. This module is that seam.

Everything that builds or parses a pane/window ref should route through here, so a
backend change — or just fixing the format — touches one file instead of 23.

Compatibility by construction: ``from_ref`` accepts every form in circulation —
    tmux:<fleet>:%N   canonical pane_ref
    <fleet>:%N        prefix-less (some builders emit this today — a latent bug)
    %N                bare pane id
— so the system tolerates the existing inconsistency rather than depending on it.

The helper functions at the bottom (`pane_ref_parts`, `pane_key`,
`physical_fleet_from_ref`, `is_pane_ref`, `backend_ref_from`) reproduce the exact
return contracts of the current duplicate parsers, so they are drop-in
replacements (proven equivalent in tests/test_pane_handle.py).
"""

from __future__ import annotations

from typing import NamedTuple

BACKEND = "tmux"
_PREFIX = "tmux:"


def _strip_backend(value: str) -> str:
    return value[len(_PREFIX):] if value.startswith(_PREFIX) else value


class PaneHandle(NamedTuple):
    """A physical pane: backend + fleet (tmux session) + pane id (``%N``)."""

    fleet: str | None
    pane_id: str            # always starts with "%"
    backend: str = BACKEND

    def to_ref(self) -> str:
        if self.fleet:
            return f"{self.backend}:{self.fleet}:{self.pane_id}"
        return f"{self.backend}:{self.pane_id}"

    @staticmethod
    def make(fleet: str | None, pane_id: str, backend: str = BACKEND) -> "PaneHandle":
        return PaneHandle(fleet or None, str(pane_id), backend)

    @staticmethod
    def from_ref(value: str | None) -> "PaneHandle | None":
        """Parse ``tmux:<fleet>:%N`` | ``<fleet>:%N`` | ``%N``.

        Returns None when there is no ``%N`` pane id (e.g. a window ref). Splits
        on the LAST colon — the pane id is the tail — matching the rsplit family
        of current parsers (tmux_mirror, seat_status, fleets, agent_packages).
        """
        if not value:
            return None
        subject = _strip_backend(str(value))
        if ":" in subject:
            fleet, pane_id = subject.rsplit(":", 1)
            if pane_id.startswith("%"):
                return PaneHandle(fleet or None, pane_id)
            return None
        if subject.startswith("%"):
            return PaneHandle(None, subject)
        return None


class WindowHandle(NamedTuple):
    """A window target: backend + fleet (tmux session) + window name."""

    fleet: str | None
    window: str
    backend: str = BACKEND

    def to_ref(self) -> str:
        if self.fleet:
            return f"{self.backend}:{self.fleet}:{self.window}"
        return f"{self.backend}:{self.window}"

    @staticmethod
    def make(fleet: str | None, window: str, backend: str = BACKEND) -> "WindowHandle":
        return WindowHandle(fleet or None, str(window), backend)

    @staticmethod
    def from_ref(value: str | None, *, default_fleet: str | None = None) -> "WindowHandle | None":
        """Parse ``tmux:<fleet>:<window>`` | ``<fleet>:<window>`` | ``<window>``.

        Splits on the FIRST colon (the window name is the tail), mirroring the
        target splitter in tmux.py (``_split_ref``). A bare ``%N`` is a pane, not
        a window, so it returns None. A bare name uses ``default_fleet``.
        """
        if not value:
            return None
        subject = _strip_backend(str(value))
        if subject.startswith("%"):
            return None
        if ":" in subject:
            fleet, window = subject.split(":", 1)
            return WindowHandle(fleet or default_fleet, window)
        return WindowHandle(default_fleet, subject)


# --------------------------------------------------------------------------- #
# Drop-in helpers matching the current duplicate-parser return contracts.      #
# --------------------------------------------------------------------------- #


def pane_ref_parts(value: str | None) -> tuple[str | None, str | None]:
    """``(fleet, pane_id)`` with ``pane_id`` None when there is no ``%N``.

    Drop-in for the (tuple-always) family: tmux_mirror._pane_ref_parts and
    fleets._pane_ref_key. A window ref returns ``(fleet, None)``.
    """
    handle = PaneHandle.from_ref(value)
    if handle is not None:
        return handle.fleet, handle.pane_id
    if value:
        subject = _strip_backend(str(value))
        if ":" in subject:
            fleet, _ = subject.rsplit(":", 1)
            return (fleet or None), None
    return None, None


def pane_key(value: str | None) -> tuple[str | None, str] | None:
    """``(fleet, pane_id)`` or None when there is no ``%N`` pane id.

    Drop-in for the (None-when-not-a-pane) family: seat_status._extract_pane_key
    and agent_packages._pane_ref_key.
    """
    handle = PaneHandle.from_ref(value)
    return (handle.fleet, handle.pane_id) if handle is not None else None


def physical_fleet_from_ref(value: str | None) -> str | None:
    """Fleet from any pane/window/backend ref (splits on the FIRST colon).

    Drop-in for registry._physical_fleet_from_ref and
    tmux_mirror._physical_fleet_from_ref.
    """
    if not value:
        return None
    subject = _strip_backend(str(value))
    if ":" in subject:
        fleet, _ = subject.split(":", 1)
        return fleet or None
    return None


def is_pane_ref(value: str | None) -> bool:
    """True when the ref carries a ``%N`` pane id."""
    return PaneHandle.from_ref(value) is not None


def backend_ref_from(value: str | None) -> str | None:
    """The ``tmux:``-stripped form (``<fleet>:<subject>``).

    Drop-in for the scattered ``.removeprefix("tmux:")`` derivations of
    backend_ref.
    """
    if not value:
        return None
    return _strip_backend(str(value))
