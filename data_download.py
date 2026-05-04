"""
Download BLS OEWS National industry-specific and by ownership files.

Source:
https://www.bls.gov/oes/tables.htm

This script scrapes the OEWS tables page and downloads the annual
"National industry-specific and by ownership" XLSX/XLS files.

Usage:
    python scripts/download_bls_oes.py

Optional:
    python scripts/download_bls_oes.py --start-year 2013 --end-year 2024
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BLS_TABLES_URL = "https://www.bls.gov/oes/tables.htm"


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=1997)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/bls_oes"),
        help="Directory where downloaded files will be saved.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to wait between downloads.",
    )
    return parser.parse_args()


def extract_year_from_heading(text: str) -> int | None:
    """
    Extract year from headings like:
    'May 2024'
    'May 2013'
    '2002'
    """
    match = re.search(r"(19|20)\d{2}", text)
    if match:
        return int(match.group(0))
    return None


def find_oes_links(html: str, base_url: str) -> list[dict]:
    """
    Finds annual BLS OEWS zip download links for the National data only.

    Returns:
        [
            {
                "year": 2024,
                "category": "national",
                "url": "...zip",
                "extension": ".zip"
            },
            ...
        ]
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    current_year = None

    # The BLS page is structured with year headings followed by list items.
    for element in soup.find_all(["h2", "li"]):
        if element.name == "h2":
            current_year = extract_year_from_heading(element.get_text(" ", strip=True))
            continue

        if element.name != "li" or current_year is None:
            continue

        li_text = element.get_text(" ", strip=True).lower()

        if not li_text.startswith("national"):
            continue

        candidate_links = []
        for a in element.find_all("a", href=True):
            href = a["href"].lower()
            full_url = urljoin(base_url, href)

            if href.endswith(".zip"):
                candidate_links.append(full_url)

        if not candidate_links:
            continue

        selected_url = candidate_links[0]
        extension = Path(selected_url).suffix.lower()

        results.append(
            {
                "year": current_year,
                "category": "national",
                "url": selected_url,
                "extension": extension,
            }
        )

    return results


def download_file(url: str, destination: Path) -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; student-research-downloader/1.0; "
            "+https://www.bls.gov/oes/tables.htm)"
        )
    }

    with requests.get(url, headers=headers, stream=True, timeout=60) as response:
        response.raise_for_status()

        with destination.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def extract_and_process_zip(zip_path: Path, output_dir: Path, year: int) -> None:
    """
    Extract zip file, find the national_*_dl data file, move it to output_dir,
    and clean up the temporary extraction folder and zip file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Extract the zip
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        # Find the national_*_dl file (either .xls or .xlsx)
        data_files = list(tmpdir_path.glob("**/national_*_dl.*"))
        
        if not data_files:
            data_files = list(tmpdir_path.glob("**/national_dl.*"))
            print(f"          warning: no national_*_dl file found in {zip_path.name}")
            return
        
        if len(data_files) > 1:
            print(f"          warning: multiple national_*_dl files found, using first one")
        
        data_file = data_files[0]
        
        # Move it to output_dir with a clean name
        extension = data_file.suffix.lower()
        final_filename = f"national_{year}{extension}"
        final_path = output_dir / final_filename
        
        shutil.move(str(data_file), str(final_path))
        print(f"          extracted: {final_path.name}")
    
    # Delete the zip file after successful extraction
    zip_path.unlink()
    print(f"          removed: {zip_path.name}")


def main() -> None:
    args = get_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading BLS table page: {BLS_TABLES_URL}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; student-research-downloader/1.0; "
            "+https://www.bls.gov/oes/tables.htm)"
        )
    }

    response = requests.get(
        BLS_TABLES_URL,
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()

    links = find_oes_links(response.text, BLS_TABLES_URL)

    links = [
        item
        for item in links
        if item["category"] == "national"
        and item["extension"] == ".zip"
        and args.start_year <= item["year"] <= args.end_year
    ]

    links = sorted(links, key=lambda x: x["year"])

    if not links:
        raise RuntimeError("No matching BLS OEWS zip files found for National.")

    print(f"Found {len(links)} files.")

    for item in links:
        year = item["year"]
        category = item["category"]
        url = item["url"]
        extension = item["extension"]

        label = "nat" if category == "national" else "nat_industry_ownership"
        filename = f"oes_{label}_{year}{extension}"
        destination = args.output_dir / filename

        extracted_files = [
            args.output_dir / f"national_{year}.xls",
            args.output_dir / f"national_{year}.xlsx",
        ]
        if any(path.exists() and path.stat().st_size > 0 for path in extracted_files):
            print(f"[skip] {year}: already extracted national data file")
            continue

        print(f"[download] {year}: {url}")
        download_file(url, destination)
        print(f"          saved to {destination}")
        
        # Extract the zip and process the data file
        if extension == ".zip":
            extract_and_process_zip(destination, args.output_dir, year)

        time.sleep(args.sleep)

    print("Done.")


if __name__ == "__main__":
    main()