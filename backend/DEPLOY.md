# Rollback Plan

If any anomalous behavior is detected during trading or execution operations, operators can adjust feature flags in `backend/config.py` to restore the system to rule-based defaults instantly.

## Rollback Scenarios

| Scenario | Symptoms | Action |
|----------|----------|--------|
| **Partial TP Failure** | Positions remain open or partially locked | Set `"partial_tp": False` in `FEATURE_FLAGS` to close entire order at targets |
| **Circuit Breaker Issues** | System fails to reset daily or weekly metrics | Set `"circuit_breaker_v2": False` to fall back to global boolean |
| **SMC Strategy Anomalies** | Incorrect structure shift detections | Set `"smc_strategy": False` to rely on RSI-based signals |
| **Kelly Lot Discontinuities** | Over-leveraged or too small lots | Set `"kelly_sizing": False` to revert to standard 0.01 lot size |
| **Alerting Overhead** | Alerting spam or API rate limit issues | Set `"alerting": False` to disable webhook message dispatching |
| **Correlation Cap Issue** | False rejections of non-correlated trades | Set `"correlation_cap": False` to bypass basic category caps |
