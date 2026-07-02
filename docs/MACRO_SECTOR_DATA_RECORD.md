# Macro and Sector Data Record

Date: 2026-07-02

## Objective

Continue the original ETF rotation plan by filling the data gaps needed for valuation, prosperity, and macro-resonance factors.

This step focuses on:

- Macro indicators from iFinD EDB
- Sector/index daily market data
- Sector valuation and consensus/prosperity data probe

## Implemented Components

New code and configuration:

- `src/etf_rotation/data/ifind_mcp.py`
- `scripts/collect_ifind_research_data.py`
- `config/macro_indicators.json`
- `config/sector_indices.json`
- `tests/test_ifind_mcp_parser.py`

The collector supports:

- iFinD MCP raw response archival
- Standard EDB table parsing
- Markdown table parsing
- Chinese numeric units such as `万`, `亿`, `万亿`
- 3-month sector-index windows to avoid MCP long-range truncation
- Raw-response reuse for resumable collection

## Macro EDB Data

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets macro
```

Output:

- `data/raw/macro_indicators.parquet`
- Raw responses under `data/raw/ifind_research_raw/macro/`

Coverage:

| Indicator | Rows | Start | End | Notes |
|---|---:|---|---|---|
| Manufacturing PMI | 66 | 2021-01-31 | 2026-06-30 | Monthly |
| CPI YoY | 65 | 2021-01-31 | 2026-05-31 | Monthly |
| PPI YoY | 65 | 2021-01-31 | 2026-05-31 | Monthly |
| M2 YoY | 65 | 2021-01-31 | 2026-05-31 | Monthly |
| Social financing stock YoY | 65 | 2021-01-31 | 2026-05-31 | Monthly |
| China 10Y government bond yield | 1369 | 2021-01-04 | 2026-06-30 | Daily |

Result:

- Macro data is usable for the macro-resonance factor and future HMM/regime classifier work.

## Sector Index Data

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets sector_index --sector-window-months 3
```

Output:

- `data/raw/sector_index_daily.parquet`
- Raw responses under `data/raw/ifind_research_raw/sector_index/`

Coverage:

| Theme | Index Code | Rows | Start | End | Limitation |
|---|---|---:|---|---|---|
| brokerage | `399975.SZ` | 1328 | 2021-01-04 | 2026-06-30 | Complete |
| consumer | `000932.SH` | 1328 | 2021-01-04 | 2026-06-30 | 60 close values missing |
| defense | `399967.SZ` | 1328 | 2021-01-04 | 2026-06-30 | Complete |
| financial | `000914.SH` | 1328 | 2021-01-04 | 2026-06-30 | Complete |
| infrastructure | `399995.SZ` | 1328 | 2021-01-04 | 2026-06-30 | Complete |
| nonferrous metals | `930708.CSI` | 1328 | 2021-01-04 | 2026-06-30 | Complete |
| pharmaceutical | `000933.SH` | 1328 | 2021-01-04 | 2026-06-30 | Uses CSI 800 health care proxy |
| semiconductor | `931865.CSI` | 1235 | 2021-01-04 | 2026-06-30 | Starts with fewer early records |
| coal | `H30596.CSI` | 1328 | 2021-01-04 | 2026-06-30 | Amount missing |
| real estate | `000006.SH` | 120 | 2021-01-29 | 2026-06-30 | Monthly/sparse only |
| technology | `931186.CSI` | 180 | 2021-01-29 | 2026-06-30 | Monthly/sparse only |

Result:

- Most sector index close-price series are usable.
- Real estate and technology index mappings need a better daily index code or should temporarily fall back to ETF daily prices.
- Coal can be used for price momentum but not amount-based crowding from the sector-index source.

## Sector Valuation and Consensus Probe

Command:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/collect_ifind_research_data.py --datasets sector_fundamental
```

Output:

- `data/raw/sector_fundamentals.parquet`
- Raw responses under `data/raw/ifind_research_raw/sector_fundamental/`

Result:

- Parsed rows: 0
- The MCP `sector_data` tool recognizes requested fields such as PE, PB, ROE, forecast net profit, and forecast EPS, but returned empty tables for the current sector/index queries.

Current interpretation:

- This is likely a sector-identifier issue rather than proof that the data is unavailable.
- The next attempt should use exact iFinD板块代码 if available, or derive sector valuation/prosperity from index constituents or representative ETF holdings.

## Data Issues Requiring Decision

1. **iFinD HTTP refresh token is not configured in the current shell**

   HTTP `cmd_history_quotation` could be a faster and more exact channel for index daily data, but the current environment has no `IFIND_REFRESH_TOKEN`.

2. **Sector valuation/consensus needs an exact identifier strategy**

   Options:

   - Ask iFinD/terminal for exact sector codes for the target industries.
   - Use ETF holdings/constituents and aggregate stock-level PE/PB/ROE/consensus.
   - Temporarily postpone valuation/prosperity and proceed with macro-resonance first.

3. **Real estate and technology sector proxies need review**

   The current exact codes return sparse series. These two themes should use either better index codes or ETF daily price series until the sector-index mapping is improved.

## Validation

Commands run:

```bash
/Users/sweethome/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest -q
```

Result:

- Unit tests: 31 passed
