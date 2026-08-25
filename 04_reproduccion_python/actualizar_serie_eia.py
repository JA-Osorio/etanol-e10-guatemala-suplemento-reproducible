#!/usr/bin/env python3
"""Extrae la serie anual de gasolina de Guatemala desde el archivo masivo EIA."""

from __future__ import annotations

import argparse
import csv
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        type=Path,
        default=None,
        help="Copia local de INTL.zip. Si se omite, se descarga desde EIA.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help="CSV de salida; por defecto usa la ruta declarada en la configuración.",
    )
    return parser.parse_args()


def _extract_record(zip_path: Path, series_id: str) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open("INTL.txt") as handle:
            for raw_line in handle:
                record = json.loads(raw_line)
                if record.get("series_id") == series_id:
                    return record
    raise ValueError(f"No se encontró la serie {series_id}")


def _download() -> Path:
    url = "https://www.eia.gov/opendata/bulk/INTL.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "e10-gt-suplemento/0.1.0"})
    handle = tempfile.NamedTemporaryFile(prefix="eia-intl-", suffix=".zip", delete=False)
    path = Path(handle.name)
    with handle, urllib.request.urlopen(request, timeout=180) as response:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)
    return path


def main() -> int:
    args = parse_args()
    config_path = REPO_ROOT / "03_configuracion" / "emisiones_ttw.json"
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    zip_path = args.zip.resolve() if args.zip else _download()
    record = _extract_record(zip_path, config["eia_series_id"])
    start = int(config["observed_start_year"])
    rows = sorted(
        (
            {
                "year": int(year),
                "energy_tj": float(value),
                "series_id": record["series_id"],
                "series_name": record["name"],
                "units": record["units"],
                "source": record["source"],
                "last_updated": record["last_updated"],
            }
            for year, value in record["data"]
            if int(year) >= start and isinstance(value, (int, float))
        ),
        key=lambda row: row["year"],
    )
    if not rows:
        raise ValueError("La extracción no produjo observaciones")
    output = (
        args.salida.resolve()
        if args.salida
        else REPO_ROOT / config["source_csv"]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"Serie {record['series_id']} escrita en {output}: "
        f"{rows[0]['year']}-{rows[-1]['year']} ({len(rows)} observaciones)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
