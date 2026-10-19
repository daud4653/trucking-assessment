"""Weather corridor grid.

The corridor is the set of regular lat/lon cells touched by any route, plus
their immediate neighbours, so the heatmap covers roughly one cell either
side of every route. Weather is sampled at each cell centre; cells are drawn
as squares, so no value is interpolated or smoothed between samples.

Cell size starts at the finest candidate and coarsens until the cell count
fits MAX_CELLS, bounding provider requests for long trips.
"""

import itertools
import math
from dataclasses import dataclass

from .geometry import Coordinate

CELL_SIZE_CANDIDATES = (0.2, 0.3, 0.5, 0.75, 1.0, 1.5)
MAX_CELLS = 320
SAMPLE_STEP_DEGREES = 0.05


@dataclass(frozen=True)
class CorridorCell:
    row: int
    col: int
    size: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        south, west = self.row * self.size, self.col * self.size
        return (west, south, west + self.size, south + self.size)

    @property
    def center(self) -> Coordinate:
        west, south, east, north = self.bounds
        return Coordinate((south + north) / 2, (west + east) / 2)


@dataclass(frozen=True)
class CorridorGrid:
    cell_size: float
    cells: tuple[CorridorCell, ...]


def build_corridor(routes: list[list[Coordinate]]) -> CorridorGrid:
    samples = [point for route in routes for point in _densify(route)]
    if not samples:
        raise ValueError("Corridor requires at least one route.")
    for size in CELL_SIZE_CANDIDATES:
        cells = _cells_for(samples, size)
        if len(cells) <= MAX_CELLS or size == CELL_SIZE_CANDIDATES[-1]:
            ordered = sorted(cells)
            return CorridorGrid(size, tuple(CorridorCell(r, c, size) for r, c in ordered))
    raise AssertionError("unreachable")


def _cells_for(samples: list[Coordinate], size: float) -> set[tuple[int, int]]:
    touched = {(math.floor(p.lat / size), math.floor(p.lon / size)) for p in samples}
    return {
        (row + dr, col + dc)
        for row, col in touched
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        if -90 <= (row + dr) * size < 90
    }


def _densify(route: list[Coordinate]) -> list[Coordinate]:
    if len(route) < 2:
        return list(route)
    dense = [route[0]]
    for a, b in itertools.pairwise(route):
        steps = max(1, math.ceil(max(abs(b.lat - a.lat), abs(b.lon - a.lon)) / SAMPLE_STEP_DEGREES))
        dense.extend(
            Coordinate(a.lat + (b.lat - a.lat) * i / steps, a.lon + (b.lon - a.lon) * i / steps)
            for i in range(1, steps + 1)
        )
    return dense
