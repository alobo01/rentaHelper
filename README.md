# FinCLI

**FinCLI** is a minimal yet extensible command-line tool that transforms broker CSV exports into a consolidated, visually appealing HTML report. It uses a plug-in architecture with Pydantic models for strict typing, allowing you to integrate new data sources, metrics, and outputs with ease.

---

## 🚀 Features

* **Modular architecture**: Separate packages for parsers, processors, outputs, and domain models.
* **Strongly typed**: Pydantic v2 models validate all inputs and outputs.
* **Built-in support**:

  * TradeRepublic CSV exports (`TradeRepublicParser`).
  * Dividend & interest aggregation (`SavingPerformanceProcessor`).
  * FIFO trading P/L calculation (`TradingPerformanceProcessor`).
  * HTML report generation (`HtmlReportOutput`).
* **Official FX rates**: Uses ECB euro reference rates (daily historic).
  Source: [https://www.ecb.europa.eu/stats/policy\_and\_exchange\_rates/euro\_reference\_exchange\_rates/html/index.en.html](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
* **Community integration**: TradeRepublic data via [https://github.com/pytr-org/pytr](https://github.com/pytr-org/pytr)

---

## 📦 Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/your-org/fincli.git
   cd fincli
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Prepare data folders:

   * Place your TradeRepublic CSVs in `rawData/tradeRepublic/`.
   * Download ECB FX history to `utilsData/eurofxref-hist.csv`:

     ```bash
     wget -O utilsData/eurofxref-hist.csv \
       https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv
     ```

---

## ⚙️ Configuration

All parsers, processors, and outputs are configured via `config.yaml`. Example:

```yaml
parsers:
  - name: tr
    type: fincli.parsers.TradeRepublicParser
    params:
      data_dir: rawData/tradeRepublic

processors:
  - name: savings
    type: fincli.processors.SavingPerformanceProcessor
    params:
      year: 2025
      fx_csv: utilsData/eurofxref-hist.csv

  - name: trading
    type: fincli.processors.TradingPerformanceProcessor
    params:
      year: 2025
      fx_csv: utilsData/eurofxref-hist.csv

output:
  type: fincli.output.HtmlReportOutput
  params:
    out_file: report.html
```

Modify or extend this file to enable different parsers, processors, outputs, or model packages.

---

## 🏗️ Project Structure

```
fincli/
├── fincli/                       # Main package
│   ├── __init__.py               # Exports cli entrypoint
│   ├── cli.py                    # Entry point
│   ├── fx.py                     # ECB FX utilities
│   ├── models/                   # Domain & DTO models
│   │   └── __init__.py           # Pydantic classes
│   ├── parsers/                  # Parser modules
│   │   ├── __init__.py           # Abstract + exports
│   │   ├── abstract.py           # AbstractParser
│   │   └── trade_republic.py     # TradeRepublicParser
│   ├── processors/               # Processor modules
│   │   ├── __init__.py           # Abstract + exports
│   │   ├── abstract.py           # AbstractProcessor
│   │   ├── saving_performance.py # SavingPerformanceProcessor
│   │   └── trading_performance.py# TradingPerformanceProcessor
│   └── output/                   # Output modules
│       ├── __init__.py           # Abstract + exports
│       ├── abstract.py           # AbstractOutputPipe
│       └── html_report.py        # HtmlReportOutput
├── rawData/tradeRepublic/        # Place TradeRepublic CSVs here
├── utilsData/                    # Utilities data (FX history)
│   └── eurofxref-hist.csv
├── config.yaml                   # User configuration
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 💡 Extending FinCLI

### 1. Add a new data source (Parser)

1. Create `fincli/parsers/my_parser.py` subclassing `AbstractParser`.
2. Define a Pydantic config model under `fincli/models/` (e.g., `MyParserConfig`).
3. Implement `load()` to return a DataFrame with a `__object__` column of Pydantic models.
4. Export your parser in `fincli/parsers/__init__.py`.
5. Add to `config.yaml` under `parsers:`.

### 2. Add a new metric (Processor)

1. Create `fincli/processors/my_metric.py` subclassing `AbstractProcessor`.
2. Define `input_model` and `output_model` in `fincli/models/`.
3. Implement `process()`.
4. Export in `fincli/processors/__init__.py`.
5. Add to `config.yaml` under `processors:`.

### 3. Add a different output format (OutputPipe)

1. Create `fincli/output/my_output.py` subclassing `AbstractOutputPipe`.
2. Implement `render(*results)` to generate your deliverable (e.g., PDF).
3. Export in `fincli/output/__init__.py`.
4. Add to `config.yaml` under `output:`.

---

## 📝 License & Credits

* **ECB FX rates**: European Central Bank public data
* **TradeRepublic exports**: pytr community tool ([https://github.com/pytr-org/pytr](https://github.com/pytr-org/pytr))
* **BINGX exports**: https://bingx.com/es-es/transaction-history
Feel free to contribute new parsers, processors, models, or outputs via pull requests!
