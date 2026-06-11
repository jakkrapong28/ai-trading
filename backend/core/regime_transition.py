from typing import Optional

REGIME_CONFIRMATION_BARS = 3

class RegimeManager:
    def __init__(self, initial_regime: str = "SIDEWAYS"):
        self.current_regime: str = initial_regime
        self._candidate: Optional[str] = None
        self._confirmation_count: int = 0

    def update(self, detected_regime: str) -> Optional[str]:
        """
        Updates the regime state with the latest detected regime.
        If a new regime candidate is confirmed over REGIME_CONFIRMATION_BARS updates,
        triggers transition and returns the old regime name.
        Otherwise returns None.
        """
        if detected_regime == self._candidate:
            self._confirmation_count += 1
        else:
            self._candidate = detected_regime
            self._confirmation_count = 1

        if self._confirmation_count >= REGIME_CONFIRMATION_BARS and self._candidate != self.current_regime:
            old = self.current_regime
            self.current_regime = self._candidate
            self._confirmation_count = 0
            return old  # Return old regime to indicate a transition occurred
        return None
