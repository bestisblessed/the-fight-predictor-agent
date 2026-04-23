## Architecture Decision Snapshot

| Essential dimension | Current (Drive `.docx` bridge) | Simplified (Direct X + SQLite) | Why it matters |
|---|---|---|---|
| Flow complexity | Multi-hop ingest and parse path before reply generation | Direct mentions fetch into one processing loop | Fewer hops means fewer breakpoints |
| Dependency surface | X write API + Google Drive + OpenAI + glue scripts | X read/write API + OpenAI + SQLite | Fewer external systems to coordinate |
| State integrity | File-based dedupe tracking | Transactional state machine in DB | Safer retries and idempotency |
| Failure risk | More integration-specific failure modes | Narrower failure surface | Lower incident frequency and easier recovery |
| Response latency | Added ingest overhead each cycle | Shorter end-to-end path | Faster time from mention to reply |
| Operational effort | Higher maintenance and troubleshooting overhead | Lower ongoing maintenance overhead | Lower total cost of ownership in practice |

## Decision

- Choose **Simplified** if your goal is reliability, speed, and maintainability.
- Keep **Current** only if you must preserve the existing upstream feed short-term.
- Recommended rollout: run both paths in parallel, validate parity, then cut over.