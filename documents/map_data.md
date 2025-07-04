# Data-to-Chart Mappings for Ondo Research Report

| Chart Type | Visualizer | Data Source | ResearchState Key | Expected Structure | Fallback Cache Path | Max Data Age |
|------------|------------|-------------|-------------------|-------------------|---------------------|--------------|
| TVL Chart | LineChartVisualizer | DeFiLlama | data.defillama.tvl_history | List of `[timestamp, tvl]` or `[{"date": timestamp, "tvl": value}]` | reports/ondo/cache/defillama/tvl_ondo.json | 24h |
| Price Chart (30-day) | CandlestickChartVisualizer | CoinMarketCap | data.coinmarketcap.ohlcv | List of `[{"date": timestamp, "open": float, "high": float, "low": float, "close": float, "volume": float}]` | reports/ondo/cache/coinmarketcap/ohlcv_ondo_30.json | 1h |
| Volume Chart | LineChartVisualizer | CoinMarketCap | data.coinmarketcap.volume_history | List of `[{"date": timestamp, "volume": float}]` | reports/ondo/cache/coinmarketcap/historical_ondo_days_30.json | 4h |
| Tokenomics Pie Chart | PieChartVisualizer | Tokenomics | data.tokenomics.token_distribution | Nested object with `token_allocation` field containing Dict of `{category: percentage}` | reports/ondo/cache/tokenomics/distribution_ondo.json | 168h |
| Chain Distribution Pie Chart | PieChartVisualizer | DeFiLlama | data.defillama.currentChainTvls | Dict of `{chain: tvl}` or `[{"chain": str, "tvl": float}]` | reports/ondo/cache/defillama/protocol_protocol_ondo.json | 24h |
| Comparison Chart | ComparisonChartVisualizer | Multiple | data.competitors | Dict of `{project: {metric1: value1, metric2: value2}}` | Multiple source cache files | 24h |
| Metrics Table | TableVisualizer | Multiple | data.metrics_table | DataFrame or list of dicts | Multiple source cache files | 12h |

## Data Handling Guidelines

### Validation & Error Handling
- Validate data structure before visualization - log errors via `logging_config.py`
- For missing data fields (like null values in token_allocation): display "N/A" instead of zeros or synthetic values
- For malformed data: fall back to cache or display error message in visualization
- For time series with gaps: show discontinuities with dotted lines rather than interpolating

### Nested Data Extraction
- Cache files follow pattern: `{"data": {...}, "metadata": {...}}`
- Deeply nested data (e.g., tokenomics) requires multi-level extraction:
  - Example: `data.data.data.token_allocation` for tokenomics distribution
- Visualizers should use `_extract_*_data()` methods to handle the appropriate nesting

### Cache Structure
- Cache files are organized by source and endpoint: `reports/ondo/cache/{source}/{endpoint}_{query}.json`
- Metadata includes source, endpoint, query, timestamps, and TTL
- Some files have query-specific suffixes (e.g., `_30` for 30-day data)

### Data Normalization
- **Time Series**: Normalize timestamps to consistent format before visualization
- **Missing Values**: Handle null values appropriately by rendering as "N/A" 
- **ComparisonChart**: Normalize metrics across projects for fair comparison (e.g., marketcap-weighted TVL)
- **Multi-source Tables**: Ensure consistent units and formatting across data sources

## Notes
- Always check `ResearchState.data` first, using the specified key.
- Fallback to `CacheManager.load_from_cache` if data is missing or unavailable.
- Update `ResearchState` with cache data to ensure consistency.
- Validate data structure in each visualizer and log errors.
- All visualizers should handle null/undefined values gracefully.