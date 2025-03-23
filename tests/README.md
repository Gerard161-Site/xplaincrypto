# XplainCrypto Testing Scripts

This directory contains testing scripts for the XplainCrypto application that help debug API calls to external services (CoinGecko, CoinMarketCap, DeFiLlama) and ensure that data fields required for visualizations are properly populated.

## Test Scripts Overview

### 1. Data Module Testing

- **`test_data_modules.py`**: Tests the base data modules (CoinGecko, CoinMarketCap, DeFiLlama) to ensure they return expected fields.
- **`test_enhanced_data_modules.py`**: Extends the base data modules with enhanced functionality to fetch additional required data fields.

### 2. Visualization Testing

- **`test_visualizations.py`**: Basic visualization test using synthetic data.
- **`test_enhanced_visualizations.py`**: Enhanced visualization test that uses real API data when possible.
- **`test_publisher.py`**: Tests the report publishing functionality.
- **`test_report_generation.py`**: Tests the full report generation process.

## Setup

Before running tests, ensure you have:

1. Set up your `.env` file with API keys:
   ```
   OPENAI_API_KEY=your_openai_key
   COINGECKO_API_KEY=your_coingecko_key
   COINMARKETCAP_API_KEY=your_coinmarketcap_key
   ```

2. Installed required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Running Test Scripts

### Testing Data Modules

To test the data modules with real API calls:

```bash
python -m tests.test_data_modules
```

To test the enhanced data modules that fill in missing fields:

```bash
python -m tests.test_enhanced_data_modules
```

### Testing Visualizations

To test visualizations with synthetic data:

```bash
python -m tests.test_visualizations
```

To test visualizations with real API data:

```bash
python -m tests.test_enhanced_visualizations --project Bitcoin
```

For synthetic data only:

```bash
python -m tests.test_enhanced_visualizations --project Bitcoin --synthetic
```

## Debugging Common Issues

### Issue: Missing Data Fields Warning

If you see warnings like:

```
WARNING - Data field 'tvl_history' not found or empty for tvl_chart, using synthetic data
```

This indicates that the required data field for a visualization is not present in the API response data. The enhanced data modules will attempt to:

1. Get the data from an appropriate API endpoint if possible
2. Provide synthetic data as a fallback

### Issue: API Access Problems

If you see API error messages:

1. Verify your API keys are correctly set in `.env`
2. Check API limitations and rate limits (especially for CoinGecko)
3. Use the `--synthetic` flag with the enhanced visualization test to bypass API calls

### Issue: Visualization Quality Problems

If visualizations are created but appear to have synthetic/dummy data:

1. Run `test_enhanced_data_modules.py` first to check which data fields are available
2. Check the `.json` files generated in the `cache/` directory to inspect the data
3. Look for specific error messages about each API endpoint in the logs

## Expected Output

When tests are working correctly, you should see messages like:

```
INFO - ✅ price_history: Found with 60 data points
INFO - ✅ volume_history: Found with 30 data points
INFO - ✅ tvl_history: Found with 60 data points
INFO - ✅ token_distribution: Found with 4 categories
INFO - Successfully generated 8 visualizations for Bitcoin
```

And visualization files will be created in the `docs/[project_name]/` directory. 