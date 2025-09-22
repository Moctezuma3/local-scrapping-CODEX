# local.ch Sitemap Scraper

This project provides a lightweight command-line scraper dedicated to the
public sitemap structure exposed by [local.ch](https://www.local.ch/). It
lets you supply a list of Swiss postal codes together with a search keyword
and exports all matching business listings to a CSV file.

The scraper relies exclusively on the official sitemap index published at
`https://www.local.ch/sitemaps/sitemap_index.xml` and therefore does not
simulate browser activity or require Playwright.

## Features

- Discovers search and business detail pages directly from the sitemap XML
  files.
- Filters results by keyword and postal codes loaded from a text file.
- Extracts company name, address, postcode, city, phone, email and website
  when available.
- Exports the consolidated dataset to a CSV file, creating the destination
  directory automatically.
- Provides clear logging and safety checks for empty or missing input files.

## Requirements

- Python 3.10 or newer (tested on Python 3.12)
- System packages required by `beautifulsoup4`

Install the Python dependencies with:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

1. Create a text file containing one Swiss postal code per line. By default
   the scraper looks for `input.txt` located at the project root, but a
   custom path can be provided with `--input` / `-i`.
2. Run the scraper with your keyword and optional output path. Example:

   ```bash
   python sitemap_scraper.py --keyword "plombier" --input input.txt --output output/plombiers_geneve.csv
   ```

   If the `--output` argument points to a directory, the scraper will write a
   file named `local_ch_results.csv` inside it.

3. After the run completes, inspect the generated CSV for the following
   columns:

   - `source_url`
   - `name`
   - `address`
   - `zipcode`
   - `city`
   - `phone`
   - `email`
   - `website`

### Command Reference

```
usage: sitemap_scraper.py [-h] --keyword KEYWORD [--input INPUT]
                          [--output OUTPUT] [--language LANGUAGE]
                          [--max-search-pages MAX_SEARCH_PAGES]
                          [--max-detail-pages MAX_DETAIL_PAGES]
                          [--verbose]
```

| Argument | Description |
| --- | --- |
| `--keyword` / `-k` | Mandatory search term used to filter sitemap entries and detail pages. |
| `--input` / `-i` | Path to the text file containing postal codes (default: `input.txt`). |
| `--output` / `-o` | CSV file path or directory for the export (default: `output/local_ch_results.csv`). |
| `--language` / `-l` | Language parameter propagated to local.ch URLs (default: `fr`). |
| `--max-search-pages` | Safety limit for sitemap search entries to crawl (default: 200). |
| `--max-detail-pages` | Safety limit for sitemap detail pages to visit (default: 2000). |
| `--verbose` | Enables debug-level logging to troubleshoot sitemap traversal. |

## Troubleshooting

- **Empty CSV output** – Ensure that your keyword and postal codes actually
  yield results on local.ch. Try reducing filters or checking the log output
  with `--verbose` to confirm sitemap URLs are discovered.
- **Network errors** – The scraper retries requests a few times, but a
  persistent failure may indicate temporary network issues or blocking.
  Re-run the command later or with a reduced `--max-detail-pages` value.
- **Input validation errors** – The tool refuses to start if the postal code
  file is missing or empty. Double-check the path passed via `--input` and
  ensure at least one line is present.

## Repository Layout

```
.
├── input.txt             # Example postal codes for Geneva (1201, 1202)
├── requirements.txt      # Minimal dependency list: BeautifulSoup
├── sitemap_scraper.py    # Main CLI entry point
└── README.md             # This documentation
```

Temporary artifacts such as compiled Python files, log files or CSV exports
are ignored by Git via `.gitignore` so you can run tests locally without
polluting commits.

## Development

Run static compilation checks and CLI help to confirm the script is ready:

```bash
python -m compileall sitemap_scraper.py
python sitemap_scraper.py --help
```

Feel free to contribute improvements through pull requests, keeping the
repository lean and focused on the sitemap-based workflow.
