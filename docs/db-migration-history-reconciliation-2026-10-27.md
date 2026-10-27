# Reconciliation of environmental Supabase migration history — 2026-10-27

**Target:** `monterrey-respira-db` (`xjekikweaiddfwjjaqbd`).  
**Scope:** Align version-controlled migration filenames and SQL with **already-applied** migrations. **No remote SQL, migration table, data or runtime change** is part of this PR.

## Root cause

The repository's two historical SQL files were named with *draft/promotion* timestamps. Their equivalent migrations were later applied to Supabase under different versions. Additionally, two later history RPC migrations were applied remotely but never copied into `supabase/migrations/`. Consequently, naive `supabase db push` from the repository would regard existing changes as pending.

We retrieved `supabase_migrations.schema_migrations` in **read-only** mode, including each stored `statements[1]`, and compared its contents with the repository. The local weather-context DDL was *exactly* the remote body after removing its initial draft comment; the local latest-per-city RPC DDL was identical after trimming the final newline.

## Applied migrations now mirrored byte-for-byte

| Remote version | Migration | MD5 of stored SQL |
| --- | --- | --- |
| `20260525013516` | `add_weather_context_columns` | `c2b72fd68c1a175c8f8555dae9d6b493` |
| `20260525125515` | `update_latest_air_quality_rpc_weather_context` | `f14831e4684911daefb87a6b1f00b99e` |
| `20260530200307` | `recreate_historical_weather_rpc_canonical_fields` | `879dd9cdda890ff6d529ae0ea7720b18` |
| `20260530200420` | `recreate_daily_weather_rpc_canonical_fields` | `174fd37df904c4648a08b80e03b283be` |

The first two migration files now use the exact remote versions. Their earlier unapplied aliases `20260525011000` and `20260525045500` were removed from the *executable* migrations directory, preventing accidental replay. Git history retains their original content. Historical project notes may mention these old filenames as accurate records of their authoring/promotion stages.

The last two files were recovered from the remote's original applied SQL, not reconstructed from current function definitions. All four represent past execution and are protected from accidental changes by `tests/test_migration_history_alignment.py`.

## Future deployment guard

- The PR #35 optimization migration `20261025001630_optimize_latest_air_quality_rpc.sql` stays **pending** in `supabase/migrations/`; this reconciliation **does not** apply it.
- Before live deploy: run `supabase migration list` against the *confirmed* environmental project. The four historical versions should appear in **LOCAL and REMOTE**. Only `20261025001630` should be local-only. Stop for any new drift.
- Apply **only the approved forward migration** after separate PO GO, with DDL/ACL snapshot, PostgREST smoke and `CREATE OR REPLACE` rollback from the verified runbook `docs/rpc-optimization-qa.md`.
- Do not use `migration repair` on the production migration table merely to make version numbers match. Remote history is authoritative; this change reconciles the repository instead.

### Evidence and limits

- Read-only Supabase migration history: four rows; `statements[1]` checksums above; historical and daily functions present.
- Current runtime latest RPC retains its original `row_number()` body. Product optimization was **not** deployed.
- This reconciliation fixes the migration *history file* mismatch, not freshness Issue #33 or performance Issue #34.
- References: [Supabase migration list](https://supabase.com/docs/reference/cli/supabase-migration-list), [Supabase migration repair](https://supabase.com/docs/reference/cli/supabase-migration-repair).
