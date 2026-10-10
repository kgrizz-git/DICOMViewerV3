"""
MPR session/view admission-limit configuration mixin.

Persists the configurable caps that bound constructed MPR sessions and total
MPR views (see ``core.mpr_session_types`` for the in-memory enforcement).
Plain display/storage settings: no patient data passes through here, so these
keys live in the regular config document, never in privacy storage.

Validation is strict with safe fallbacks: stored values must be exact ``int``
(``bool`` counts as invalid — ``True`` must never silently become a cap of
one), at least one, and satisfy ``view_cap >= session_cap``. Anything else
falls back to the compiled defaults on read; setters reject invalid input and
report ``False`` without mutating.

Expects ``self.config`` and ``self.save_config()`` from ConfigManager.
"""

from collections.abc import Callable
from typing import Any, cast

#: Default caps, mirroring ``core.mpr_session_types``.
MPR_SESSION_CAP_DEFAULT = 8
MPR_VIEW_CAP_DEFAULT = 16


class MprSessionConfigMixin:
    """Config mixin: MPR session and view admission caps."""

    def _config(self) -> dict[str, Any]:
        return cast(dict[str, Any], getattr(self, "config"))

    def _save_mpr_session_config(self) -> bool:
        # Uniquely named: several older mixins define ``_save_config`` with
        # differing return types, and MRO would resolve to the first base.
        save_func = cast(Callable[[], bool], getattr(self, "save_config"))
        return save_func()

    def get_mpr_session_cap(self) -> int:
        """Validated session cap (default 8).

        Falls back to the default for missing values, non-``int`` types
        (including ``bool``), or values below one.
        """
        raw = self._config().get("mpr_session_cap", MPR_SESSION_CAP_DEFAULT)
        if type(raw) is not int or raw < 1:
            return MPR_SESSION_CAP_DEFAULT
        return raw

    def get_mpr_view_cap(self) -> int:
        """Validated view cap (default 16).

        Falls back for missing values, non-``int`` types (including
        ``bool``), values below one, or values below the validated session
        cap. The fallback is ``max(16, session_cap)`` so getters always
        return a usable ``view >= session`` pair even when the stored
        session cap exceeds 16.
        """
        raw = self._config().get("mpr_view_cap", MPR_VIEW_CAP_DEFAULT)
        session_cap = self.get_mpr_session_cap()
        if type(raw) is not int or raw < 1 or raw < session_cap:
            return max(MPR_VIEW_CAP_DEFAULT, session_cap)
        return raw

    def get_mpr_caps(self) -> tuple[int, int]:
        """Validated ``(session_cap, view_cap)`` pair with ``view >= session >= 1``.

        The view getter already falls back to ``max(16, session_cap)``, so the
        pair invariant holds by construction.
        """
        return self.get_mpr_session_cap(), self.get_mpr_view_cap()

    def set_mpr_session_cap(self, cap: int) -> bool:
        """Persist the session cap.

        Requires an exact ``int`` of at least one that does not exceed the
        current validated view cap (lowering never evicts; growth just
        blocks). Returns ``False`` and mutates nothing on invalid input or
        when saving fails.
        """
        if type(cap) is not int or cap < 1 or cap > self.get_mpr_view_cap():
            return False
        return self._store_mpr_cap("mpr_session_cap", cap)

    def set_mpr_view_cap(self, cap: int) -> bool:
        """Persist the view cap.

        Requires an exact ``int`` of at least the current validated session
        cap. Returns ``False`` and mutates nothing on invalid input or when
        saving fails.
        """
        if type(cap) is not int or cap < self.get_mpr_session_cap():
            return False
        return self._store_mpr_cap("mpr_view_cap", cap)

    def set_mpr_caps(self, session_cap: int, view_cap: int) -> bool:
        """Persist both caps as one atomic pair.

        Requires exact ``int`` values with ``view_cap >= session_cap >= 1``
        (``bool`` is rejected). Unlike the single-cap setters, raising the
        session cap above the old view cap is fine when the new pair is valid.
        Both keys are written, then saved once; a failed save restores both
        keys exactly as they were (including their absence). Returns ``False``
        and mutates nothing on invalid input or a failed save. Lowering never
        evicts: it only blocks new MPR growth at runtime.
        """
        if type(session_cap) is not int or type(view_cap) is not int:
            return False
        if session_cap < 1 or view_cap < session_cap:
            return False
        config = self._config()
        missing = object()
        previous = {key: config.get(key, missing) for key in ("mpr_session_cap", "mpr_view_cap")}
        config["mpr_session_cap"] = session_cap
        config["mpr_view_cap"] = view_cap
        if self._save_mpr_session_config():
            return True
        for key, value in previous.items():
            if value is missing:
                config.pop(key, None)
            else:
                config[key] = value
        return False

    def _store_mpr_cap(self, key: str, cap: int) -> bool:
        config = self._config()
        missing = object()
        previous = config.get(key, missing)
        config[key] = cap
        if self._save_mpr_session_config():
            return True
        if previous is missing:
            config.pop(key, None)
        else:
            config[key] = previous
        return False
