"""Figuras compactas derivadas únicamente de las salidas reproducibles."""

from __future__ import annotations

import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Mapping, Sequence

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "e10-gt-matplotlib")
)

import matplotlib.pyplot as plt


COLORS = {"E10": "#2f6f4e", "E15": "#5a9b72", "E20": "#93bea2"}


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "figure.dpi": 140,
        }
    )


def crear_figuras(
    raiz_repositorio: str | Path,
    emisiones: Mapping[str, Any],
    economia: Mapping[str, Any],
) -> list[Path]:
    """Crea tres PNG didácticos y devuelve sus rutas."""

    _style()
    root = Path(raiz_repositorio).resolve()
    output = root / "06_resultados" / "figuras"
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    shares = emisiones["config"]["blend_shares"]
    annual_rows: Sequence[Mapping[str, Any]] = emisiones["open_annual"]
    reduction_by_scenario = {
        scenario: next(
            float(row["ttw_reduction_fraction"])
            for row in annual_rows
            if row["scenario_id"] == scenario
        )
        for scenario in shares
    }
    labels = list(shares)
    values = [100.0 * reduction_by_scenario[label] for label in labels]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    bars = ax.bar(labels, values, color=[COLORS[label] for label in labels], width=0.62)
    ax.set_title("Reducción de CO₂ de escape por mezcla")
    ax.set_ylabel("Reducción frente a gasolina (%)")
    ax.set_xlabel("Participación volumétrica")
    ax.grid(axis="y", alpha=0.22)
    ax.bar_label(bars, labels=[f"{value:.2f}%" for value in values], padding=3)
    ax.text(
        0.0,
        -0.20,
        "Servicio energético constante; límite TTW; CO₂ biogénico fuera del total de Energía.",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.tight_layout()
    path = output / "reduccion_ttw_por_mezcla.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    grid: Sequence[Mapping[str, Any]] = economia["malla"]
    fuel_share = min(float(row["participacion_gasolina_en_p068"]) for row in grid)
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for scenario in labels:
        selected = sorted(
            (
                row
                for row in grid
                if row["escenario"] == scenario
                and float(row["participacion_gasolina_en_p068"]) == fuel_share
            ),
            key=lambda row: float(row["recargo_entrega_ilustrativo_fraccion"]),
        )
        ax.plot(
            [100 * float(row["recargo_entrega_ilustrativo_fraccion"]) for row in selected],
            [float(row["cambio_costo_servicio_pct"]) for row in selected],
            marker="o",
            linewidth=2,
            color=COLORS[scenario],
            label=scenario,
        )
    ax.axhline(0, color="#444444", linewidth=0.9)
    ax.set_title("Sensibilidad del costo por servicio energético")
    ax.set_xlabel("Recargo ilustrativo sobre la referencia FOB (%)")
    ax.set_ylabel("Cambio frente a gasolina (%)")
    ax.grid(alpha=0.22)
    ax.legend(frameon=False)
    ax.text(
        0.0,
        -0.22,
        "Los recargos no son costos entregados observados; muestran dónde cambia el signo del resultado.",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.tight_layout()
    path = output / "sensibilidad_costo_servicio.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    effects: Sequence[Mapping[str, Any]] = economia["efectos_precios"]
    selected = [
        row
        for row in effects
        if row["escenario"] == "E10"
        and float(row["recargo_entrega_ilustrativo_fraccion"]) == 0.15
        and float(row["participacion_gasolina_en_p068"]) == fuel_share
    ]
    top = sorted(
        selected,
        key=lambda row: abs(float(row["efecto_precio_propagado_pct"])),
        reverse=True,
    )[:10]
    top.reverse()
    fig, ax = plt.subplots(figsize=(8.4, 6.4))
    values = [float(row["efecto_precio_propagado_pct"]) for row in top]
    bar_colors = ["#c8755b" if value > 0 else "#4f86a6" for value in values]
    ax.barh(
        [
            f"{row['codigo']} · "
            + "\n".join(textwrap.wrap(str(row["producto"]), width=46))
            for row in top
        ],
        values,
        color=bar_colors,
    )
    ax.axvline(0, color="#444444", linewidth=0.9)
    ax.set_title("E10: mayores efectos contables de precio en la MIP")
    ax.set_xlabel("Cambio propagado (%)")
    ax.grid(axis="x", alpha=0.22)
    ax.tick_params(axis="y", labelsize=8.7)
    ax.text(
        0.0,
        -0.14,
        "Caso ilustrativo: recargo 15% y participación gasolina en P068 de 45%; MIP 2013.",
        transform=ax.transAxes,
        fontsize=8,
    )
    fig.tight_layout()
    path = output / "e10_efectos_precio_mip_caso_ilustrativo.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    return paths


__all__ = ["crear_figuras"]
