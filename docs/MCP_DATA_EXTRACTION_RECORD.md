# iFinD MCP Data Extraction Record

Date: 2026-06-30

## Configuration

The provided iFinD MCP configuration was parsed from the attachment and converted into the local CLI format:

- Config path: `~/.config/ifind/mcp_config.json`
- File permission: `600`
- Servers configured in the pasted config: 7
- Token content is not stored in project source files.

The bundled iFinD CLI successfully listed the `fund` MCP service tools after network approval.

## Extracted Data

Official ETF share-flow data was extracted through:

- MCP service: `fund`
- MCP tool: `get_fund_ownership`
- Query pattern: exact ETF security code, date window, daily share-flow table
- Script: `scripts/extract_mcp_share_data.py`

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/extract_mcp_share_data.py --start 2026-06-22 --end 2026-06-30
```

Output:

- Parquet: `data/raw/etf_mcp_share_changes_recent.parquet`
- Raw MCP responses: `data/raw/mcp_share_raw/*.json`
- Rows: 156
- Symbols: 19
- Missing symbols: none

Fields:

- `symbol`
- `name`
- `date`
- `exchange_share_change`
- `listed_trading_shares`
- `source`

Important interpretation:

- `exchange_share_change` is the useful official daily flow field.
- `listed_trading_shares` appears to be a static listed-trading-share field in many responses and should not be treated as current ETF total shares without further verification.

## Coverage Summary

Most ETFs returned daily rows from 2026-06-22 to 2026-06-30. Two ETFs (`159995.SZ`, `510300.SH`) returned a single dated row for 2026-06-22; the parser now reads that date from the MCP indicator parameter block when the table itself has no date column.

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

Result:

- Unit tests: 12 passed

Overlap sanity check against HTTP-derived share changes:

- Overlap rows: 130
- Valid comparison rows: 114
- Symbols compared: 18
- Correlation between MCP `exchange_share_change` and HTTP-derived share change: 1.0

This confirms that, at least over the overlapping sample, the HTTP-derived `shares_outstanding` changes match the official MCP share-change field exactly. The full-period HTTP-derived fund-flow factor is therefore much more credible than initially assumed, though longer MCP spot checks are still recommended.

## Next Step

Extend the MCP share-flow validation over more historical windows, then either:

- extend MCP extraction by rolling date windows, or
- identify an exact iFinD HTTP/date-sequence indicator for long official ETF share-flow history.

## Annual June Window Extension

The validation was extended to five annual June windows:

- 2022-06-22 to 2022-06-30
- 2023-06-21 to 2023-06-30
- 2024-06-21 to 2024-06-28
- 2025-06-23 to 2025-06-30
- 2026-06-22 to 2026-06-30

Output files:

- `data/raw/etf_mcp_share_changes_annual_june.parquet`
- `data/raw/mcp_share_raw_annual_june/*.json`
- `data/processed/mcp_share_validation/annual_june_overlap_details.parquet`
- `data/processed/mcp_share_validation/annual_june_summary.json`

Summary:

- MCP rows: 782
- MCP symbols: 19
- HTTP/MCP overlap rows: 624
- Valid comparison rows: 554
- Valid comparison symbols: 19
- Overall correlation between MCP official share change and HTTP-derived share change: 0.9994
- Mean absolute difference: about 0.90 million shares

By window:

| Window | Rows | Symbols | Correlation | Max Absolute Difference |
|---|---:|---:|---:|---:|
| 2022-06 | 127 | 19 | 1.0000 | ~0 |
| 2023-06 | 94 | 19 | 1.0000 | ~0 |
| 2024-06 | 114 | 19 | 0.9962 | 122.0 million |
| 2025-06 | 93 | 18 | 1.0000 | ~0 |
| 2026-06 | 126 | 18 | 1.0000 | ~0 |

The only material discrepancy is concentrated around 2024-06-24 and 2024-06-25, where the MCP "current period share change" and the HTTP-derived daily change appear to have a one-trading-day attribution difference for several ETFs. Outside that local date issue, the two data sources match essentially exactly.
