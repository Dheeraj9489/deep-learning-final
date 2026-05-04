from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd  # pyright: ignore[reportMissingImports]


EXCEL_EXTENSIONS = {".xls", ".xlsx"}


def sheet_output_path(excel_path: Path, sheet_name: str, output_root: Path, input_root: Path) -> Path:
    relative_parent = excel_path.parent.relative_to(input_root)
    safe_sheet_name = "".join(
        character if character.isalnum() or character in ("-", "_") else "_"
        for character in sheet_name.strip()
    )
    return output_root / relative_parent / f"{excel_path.stem}__{safe_sheet_name}.csv"


def convert_excel_file(
    excel_path: Path, output_root: Path, input_root: Path
) -> tuple[list[Path], list[Path]]:
    engine = "xlrd" if excel_path.suffix.lower() == ".xls" else "openpyxl"
    workbook = pd.ExcelFile(excel_path, engine=engine)

    written_files: list[Path] = []
    skipped_files: list[Path] = []
    for sheet_name in workbook.sheet_names:
        output_path = sheet_output_path(excel_path, str(sheet_name), output_root, input_root)
        if output_path.exists():
            skipped_files.append(output_path)
            continue

        data_frame = workbook.parse(sheet_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data_frame.to_csv(output_path, index=False)
        written_files.append(output_path)

    return written_files, skipped_files


def convert_all_excel_files(input_root: Path, output_root: Path) -> tuple[list[Path], list[Path]]:
    excel_files = sorted(
        path
        for path in input_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in EXCEL_EXTENSIONS
        and not path.name.startswith("~$")
        and output_root not in path.parents
    )

    written_files: list[Path] = []
    skipped_files: list[Path] = []
    for excel_file in excel_files:
        written, skipped = convert_excel_file(excel_file, output_root, input_root)
        written_files.extend(written)
        skipped_files.extend(skipped)

    return written_files, skipped_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert all .xls and .xlsx files below a folder into CSV files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("."),
        help="Folder to search recursively for Excel files. Defaults to the current folder.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("converted_csv"),
        help="Folder where CSV files will be written. Defaults to converted_csv/.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_root = args.input_dir.resolve()
    output_root = args.output_dir.resolve()

    written_files, skipped_files = convert_all_excel_files(input_root, output_root)
    if not written_files and not skipped_files:
        print(f"No .xls or .xlsx files found under {input_root}")
        return

    print(f"Converted {len(written_files)} new sheet(s) to CSV.")
    for path in written_files:
        print(path)

    print(f"Skipped {len(skipped_files)} already converted sheet(s).")


if __name__ == "__main__":
    main()
