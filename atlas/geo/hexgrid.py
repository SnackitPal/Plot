"""
Uber H3 Geospatial Hexgrid Engine for PLOT / The Cultural Atlas.
Partitions the Earth into discrete equal-area hexagonal cells.
Eliminates Modifiable Areal Unit Problem (MAUP) and arbitrary political border bias.
Supports both H3 v3 and v4 API signatures.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import h3


@dataclass
class HexCell:
    cell_id: str
    resolution: int
    center_lat: float
    center_lng: float
    boundary: List[Tuple[float, float]]  # List of (lat, lng) boundary vertices
    neighbors_k1: List[str]


class AtlasHexGrid:
    """
    Manages global and regional hexagonal indexing using Uber's H3 DGGS.
    Default resolution 3 (~11,000 km² macro-regions) and 4 (~1,570 km² metro-regions).
    """

    DEFAULT_RESOLUTION = 3

    def __init__(self, resolution: int = DEFAULT_RESOLUTION):
        self.resolution = resolution
        self._is_v4 = hasattr(h3, "latlng_to_cell")

    def latlng_to_cell(self, lat: float, lng: float, res: Optional[int] = None) -> str:
        """Convert latitude and longitude to H3 hex cell index."""
        r = res if res is not None else self.resolution
        if self._is_v4:
            return h3.latlng_to_cell(lat, lng, r)
        else:
            return h3.geo_to_h3(lat, lng, r)

    def cell_to_latlng(self, cell_id: str) -> Tuple[float, float]:
        """Get center (latitude, longitude) of an H3 cell."""
        if self._is_v4:
            lat, lng = h3.cell_to_latlng(cell_id)
            return float(lat), float(lng)
        else:
            lat, lng = h3.h3_to_geo(cell_id)
            return float(lat), float(lng)

    def cell_to_boundary(self, cell_id: str) -> List[Tuple[float, float]]:
        """Get boundary vertices of an H3 cell as list of (lat, lng)."""
        if self._is_v4:
            boundary = h3.cell_to_boundary(cell_id)
        else:
            boundary = h3.h3_to_geo_boundary(cell_id)
        return [(float(pt[0]), float(pt[1])) for pt in boundary]

    def get_neighbors(self, cell_id: str, k: int = 1) -> List[str]:
        """Return k-ring neighboring cells (all equidistant neighbors)."""
        if self._is_v4:
            neighbors = h3.grid_disk(cell_id, k)
        else:
            neighbors = h3.k_ring(cell_id, k)
        return [c for c in neighbors if c != cell_id]

    def get_hex_cell(self, cell_id: str) -> HexCell:
        """Construct a full HexCell object with geometry and neighbors."""
        lat, lng = self.cell_to_latlng(cell_id)
        boundary = self.cell_to_boundary(cell_id)
        neighbors = self.get_neighbors(cell_id, k=1)
        r = h3.get_resolution(cell_id) if hasattr(h3, "get_resolution") else self.resolution

        return HexCell(
            cell_id=cell_id,
            resolution=r,
            center_lat=round(lat, 5),
            center_lng=round(lng, 5),
            boundary=[(round(p[0], 5), round(p[1], 5)) for p in boundary],
            neighbors_k1=neighbors,
        )

    def grid_distance(self, cell_origin: str, cell_destination: str) -> int:
        """Compute topological hexagonal grid distance between two cells."""
        if self._is_v4:
            return h3.grid_distance(cell_origin, cell_destination)
        else:
            return h3.h3_distance(cell_origin, cell_destination)
