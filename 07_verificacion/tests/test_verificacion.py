"""Pruebas de alcance y de huellas segmentadas."""

from pathlib import Path

from e10_gt.verificacion import _segment_hash, verificar_alcance


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repositorio_cumple_alcance() -> None:
    assert verificar_alcance(REPO_ROOT)["estado"] == "PASS"


def test_segmentacion_evade_coincidencias_accidentales() -> None:
    needle = chr(101) + chr(53)
    value = "abc" + needle + "def" + needle
    segmented = _segment_hash(value)
    assert needle not in segmented
    assert segmented.replace("|", "") == value
