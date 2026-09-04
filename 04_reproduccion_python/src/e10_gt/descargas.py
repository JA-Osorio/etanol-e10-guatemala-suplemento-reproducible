"""Resolución y verificación de la dependencia MIP fijada."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Mapping


def _load_dependency(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "03_configuracion" / "dependencia_mip.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _expected_hash(item: Mapping[str, Any]) -> str:
    if "sha256" in item:
        return str(item["sha256"])
    parts = item.get("sha256_partes")
    if not isinstance(parts, list) or not parts:
        raise ValueError(f"No hay huella declarada para {item.get('id', 'archivo')}")
    return "".join(str(part) for part in parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verificar_mip(mip_root: str | Path, dependency: Mapping[str, Any]) -> Path:
    """Comprueba existencia e integridad de todos los CSV canónicos."""

    root = Path(mip_root).resolve()
    failures: list[str] = []
    for item in dependency["archivos"]:
        path = root / item["ruta"]
        if not path.is_file():
            failures.append(f"ausente: {item['id']}")
            continue
        if _sha256(path) != _expected_hash(item):
            failures.append(f"huella inesperada: {item['id']}")
    if failures:
        raise ValueError("La dependencia MIP no pasó la verificación: " + "; ".join(failures))
    return root


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "e10-gt-suplemento/0.2.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        with tempfile.NamedTemporaryFile(
            prefix="mip-",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                handle.write(block)
    os.replace(temporary, destination)


def resolver_mip(
    repo_root: str | Path,
    mip_dir: str | Path | None = None,
) -> Path:
    """Devuelve una MIP local verificada o descarga la copia fijada al caché."""

    supplement = Path(repo_root).resolve()
    dependency = _load_dependency(supplement)
    if mip_dir is not None:
        return verificar_mip(mip_dir, dependency)

    cache_root = supplement / "01_datos" / "cache_mip"
    commit = "".join(str(part) for part in dependency["commit_fijado_partes"])
    base_url = f"{str(dependency['raiz_descarga_base']).rstrip('/')}/{commit}"
    for item in dependency["archivos"]:
        destination = cache_root / item["ruta"]
        expected = _expected_hash(item)
        if destination.is_file() and _sha256(destination) == expected:
            continue
        _download(f"{base_url}/{item['ruta']}", destination)
        if _sha256(destination) != expected:
            raise ValueError(
                f"La descarga de {item['id']} no coincide con la versión fijada"
            )
    return verificar_mip(cache_root, dependency)


__all__ = ["resolver_mip", "verificar_mip"]
