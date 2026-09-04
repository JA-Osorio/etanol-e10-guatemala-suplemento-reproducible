"""Pruebas del comparador semántico de salidas versionadas."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from e10_gt.verificacion_salidas import (
    _segment_hash,
    comparar_csv,
    comparar_json,
    validar_manifiesto,
)


def test_csv_admite_ruido_de_ultimo_bit() -> None:
    reference = b"id,valor,texto\nA,0.046468788876285,estable\n"
    actual = b"id,valor,texto\nA,0.04646878887628501,estable\n"
    assert comparar_csv(reference, actual, "resultado.csv") == []


def test_csv_rechaza_cambio_material_o_textual() -> None:
    reference = b"id,valor,texto\nA,0.046468788876285,estable\n"
    numeric = b"id,valor,texto\nA,0.0465,estable\n"
    textual = b"id,valor,texto\nA,0.046468788876285,alterado\n"
    assert comparar_csv(reference, numeric, "resultado.csv")
    assert comparar_csv(reference, textual, "resultado.csv")


def test_csv_rechaza_valores_no_finitos() -> None:
    assert comparar_csv(b"valor\nNaN\n", b"valor\nNaN\n", "resultado.csv")
    assert comparar_csv(b"valor\ninf\n", b"valor\ninf\n", "resultado.csv")


def test_csv_control_e5_e10_compara_solo_los_dos_numeros() -> None:
    path = "07_verificacion/controles_economia_articulo.csv"
    reference = (
        b"control,valor_observado\n"
        b"manuscrito_no_reproducido_total,E5=3.166771669703373; "
        b"E10=6.333543339406746\n"
    )
    close = (
        b"control,valor_observado\n"
        b"manuscrito_no_reproducido_total,E5=3.166771669703374; "
        b"E10=6.333543339406745\n"
    )
    wrong_label = close.replace(b"E10=", b"E20=")
    assert comparar_csv(reference, close, path) == []
    assert comparar_csv(reference, wrong_label, path)


def test_json_conserva_estructura_y_admite_ruido_numerico() -> None:
    reference = b'{"serie": [1.0, 0.046468788876285], "estado": "PASS"}'
    close = b'{"serie": [1.0, 0.04646878887628501], "estado": "PASS"}'
    changed = b'{"serie": [1.0, 0.05], "estado": "PASS"}'
    changed_type = b'{"serie": [1, 0.046468788876285], "estado": "PASS"}'
    assert comparar_json(reference, close, "resultado.json") == []
    assert comparar_json(reference, changed, "resultado.json")
    assert comparar_json(reference, changed_type, "resultado.json")
    assert comparar_json(b'{"valor": NaN}', b'{"valor": NaN}', "resultado.json")


def test_json_control_e5_e10_conserva_formato_y_compara_numeros() -> None:
    path = "06_resultados/economia_articulo/resumen_economia_articulo.json"
    reference = (
        b'{"controles": [{"control": "manuscrito_no_reproducido_total", '
        b'"valor_observado": "E5=3.166771669703373; E10=6.333543339406746"}]}'
    )
    close = (
        b'{"controles": [{"control": "manuscrito_no_reproducido_total", '
        b'"valor_observado": "E5=3.166771669703374; E10=6.333543339406745"}]}'
    )
    changed_label = close.replace(b"E10=", b"E20=")
    assert comparar_json(reference, close, path) == []
    assert comparar_json(reference, changed_label, path)


def _manifest_bytes(path: str, payload: bytes) -> bytes:
    digest = hashlib.sha256(payload).hexdigest()
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ruta",
            "bytes",
            "sha256_segmentado",
            "reconstruccion_huella",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerow(
        {
            "ruta": path,
            "bytes": len(payload),
            "sha256_segmentado": _segment_hash(digest),
            "reconstruccion_huella": "eliminar_barras_verticales",
        }
    )
    return output.getvalue().encode("utf-8")


def test_manifiesto_valida_archivo_tamano_y_huella(tmp_path: Path) -> None:
    relative = "06_resultados/economia/ejemplo.csv"
    candidate = tmp_path / relative
    candidate.parent.mkdir(parents=True)
    payload = b"a,b\n1,2\n"
    candidate.write_bytes(payload)
    manifest = _manifest_bytes(relative, payload)
    assert validar_manifiesto(tmp_path, manifest, manifest) == []

    candidate.write_bytes(payload + b"3,4\n")
    errors = validar_manifiesto(tmp_path, manifest, manifest)
    assert any("bytes" in error for error in errors)
    assert any("SHA-256" in error for error in errors)


def test_manifiesto_rechaza_archivo_omitido(tmp_path: Path) -> None:
    relative = "06_resultados/economia/ejemplo.csv"
    candidate = tmp_path / relative
    candidate.parent.mkdir(parents=True)
    payload = b"a,b\n1,2\n"
    candidate.write_bytes(payload)
    manifest = _manifest_bytes(relative, payload)
    (candidate.parent / "omitido.csv").write_bytes(b"x\n1\n")
    errors = validar_manifiesto(tmp_path, manifest, manifest)
    assert any("inventario actual" in error for error in errors)
