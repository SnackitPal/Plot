"""
Geospatial & Cartographic Subsystem for PLOT.
Provides H3 discrete global grid tessellation and equal-area coordinate transforms.
"""

from .hexgrid import AtlasHexGrid, HexCell

__all__ = ["AtlasHexGrid", "HexCell"]
