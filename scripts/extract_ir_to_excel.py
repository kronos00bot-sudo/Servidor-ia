#!/usr/bin/env python3
"""Extrae datos de PDFs de IR y genera un Excel consolidado.

Entrada:
- /home/mloco/Documentos/IR/IR <anio>/<Persona>/.../*.pdf

Salida:
- /home/mloco/Documentos/resultado_nuevo.xlsx
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from openpyxl import Workbook


BASE_DIR = Path("/home/mloco/Documentos/IR")
OUTPUT_XLSX = Path("/home/mloco/Documentos/resultado_nuevo.xlsx")

HEADERS = [
    "Año",
    "Nombre",
    "Patrimonio",
    "Renta Ahorro",
    "Renta General",
    "Impuesto Patrimonio",
    "Impuesto de la Renta",
]


@dataclass
class TaxRow:
    year: int
    name: str
    patrimonio: float
    renta_ahorro: float
    renta_general: float
    impuesto_patrimonio: float
    impuesto_renta: float


def normalize(text: str) -> str:
    """Normaliza para comparaciones robustas (min, sin tildes)."""
    text = text.lower().strip()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text


def sanitize_amount(value: str) -> str:
    """Limpia separadores anormales preservando formato 1.234,56."""
    value = value.replace(" ", "").replace("\xa0", "")
    return value


def parse_spanish_number(value: str) -> float:
    """Convierte 1.234,56 a float 1234.56."""
    cleaned = sanitize_amount(value).replace(".", "").replace(",", ".")
    return float(cleaned)


def pdf_to_text(pdf_path: Path) -> str:
    """Devuelve el texto de un PDF usando pdftotext -layout."""
    proc = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext fallo en {pdf_path}: {proc.stderr.strip()}")
    return proc.stdout


def find_first(paths: Iterable[Path], year: int) -> Optional[Path]:
    """Prioriza el archivo que incluya el año en el nombre."""
    sorted_paths = sorted(paths)
    if not sorted_paths:
        return None

    year_token = str(year)
    with_year = [p for p in sorted_paths if year_token in p.name]
    if with_year:
        return with_year[0]
    return sorted_paths[0]


def extract_before_code(text: str, code: str) -> str:
    """Extrae importe situado a la izquierda del rótulo numérico (ej. 0505)."""
    pattern = re.compile(rf"(-?[\d\.\s]+,\d{{2}})\s+{re.escape(code)}\b")
    match = pattern.search(text)
    if not match:
        raise ValueError(f"No se encontro importe antes del rotulo {code}")
    return sanitize_amount(match.group(1))


def extract_after_code_near(text: str, code: str, keywords: list[str]) -> str:
    """Busca un importe tras el código en una ventana posterior a keywords."""
    code_pattern = re.compile(rf"\b{re.escape(code)}\s+(-?[\d\.\s]+,\d{{2}})\b")

    lowered = normalize(text)
    for kw in keywords:
        kw_norm = normalize(kw)
        idx = lowered.find(kw_norm)
        if idx == -1:
            continue
        window = text[idx : idx + 3500]
        match = code_pattern.search(window)
        if match:
            return sanitize_amount(match.group(1))

    match = code_pattern.search(text)
    if not match:
        raise ValueError(f"No se encontro importe despues del rotulo {code}")
    return sanitize_amount(match.group(1))


def classify_pdf(pdf_path: Path) -> str:
    """Clasifica PDF objetivo: renta, patrimonio u otro."""
    name = normalize(pdf_path.name)
    if "just." in name and "presentacion" in name and "renta" in name:
        return "renta"
    if "just." in name and "presentacion" in name and "patrimonio" in name:
        return "patrimonio"
    return "other"


def collect_rows(base_dir: Path) -> list[TaxRow]:
    rows: list[TaxRow] = []

    year_dirs = sorted([p for p in base_dir.iterdir() if p.is_dir() and re.match(r"^IR\s+\d{4}$", p.name)])
    for year_dir in year_dirs:
        year = int(year_dir.name.split()[-1])

        for person_dir in sorted([p for p in year_dir.iterdir() if p.is_dir()]):
            pdfs = [p for p in person_dir.rglob("*.pdf")]
            renta_candidates = [p for p in pdfs if classify_pdf(p) == "renta"]
            patrimonio_candidates = [p for p in pdfs if classify_pdf(p) == "patrimonio"]

            if not renta_candidates and not patrimonio_candidates:
                continue

            renta_pdf = find_first(renta_candidates, year)
            patrimonio_pdf = find_first(patrimonio_candidates, year)

            if not renta_pdf or not patrimonio_pdf:
                continue

            renta_text = pdf_to_text(renta_pdf)
            patrimonio_text = pdf_to_text(patrimonio_pdf)

            renta_general = extract_before_code(renta_text, "0505")
            renta_ahorro = extract_before_code(renta_text, "0510")
            impuesto_renta = extract_before_code(renta_text, "0670")

            patrimonio = extract_after_code_near(
                patrimonio_text,
                "23",
                [
                    "Total de bienes y derechos no exentos",
                    "Total bienes y derechos no exentos",
                    "Resumen de la declaración",
                ],
            )
            impuesto_patrimonio = extract_after_code_near(
                patrimonio_text,
                "55",
                [
                    "Cuota a ingresar",
                    "Resumen de la declaración",
                ],
            )

            rows.append(
                TaxRow(
                    year=year,
                    name=person_dir.name,
                    patrimonio=parse_spanish_number(patrimonio),
                    renta_ahorro=parse_spanish_number(renta_ahorro),
                    renta_general=parse_spanish_number(renta_general),
                    impuesto_patrimonio=parse_spanish_number(impuesto_patrimonio),
                    impuesto_renta=parse_spanish_number(impuesto_renta),
                )
            )

    rows.sort(key=lambda r: (r.year, normalize(r.name)))
    return rows


def write_excel(rows: list[TaxRow], output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "resultado"

    ws.append(HEADERS)
    for row in rows:
        ws.append(
            [
                row.year,
                row.name,
                row.patrimonio,
                row.renta_ahorro,
                row.renta_general,
                row.impuesto_patrimonio,
                row.impuesto_renta,
            ]
        )

    # Columnas de importes como numero con 2 decimales.
    for excel_row in ws.iter_rows(min_row=2, min_col=3, max_col=7):
        for cell in excel_row:
            cell.number_format = "#,##0.00"

    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            val = "" if cell.value is None else str(cell.value)
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


def main() -> None:
    if not BASE_DIR.exists():
        raise SystemExit(f"No existe la carpeta base: {BASE_DIR}")

    rows = collect_rows(BASE_DIR)
    if not rows:
        raise SystemExit("No se encontraron pares de PDFs de Renta y Patrimonio para procesar.")

    write_excel(rows, OUTPUT_XLSX)
    print(f"OK: {len(rows)} filas guardadas en {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
