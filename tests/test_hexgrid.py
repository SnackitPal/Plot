"""
Unit tests for Uber H3 Hexgrid engine.
"""

import pytest
from atlas.geo.hexgrid import AtlasHexGrid, HexCell


def test_h3_latlng_to_cell():
    grid = AtlasHexGrid(resolution=3)
    # San Francisco (37.7749, -122.4194)
    sf_cell = grid.latlng_to_cell(37.7749, -122.4194)
    assert isinstance(sf_cell, str)
    assert len(sf_cell) > 10

    # London (51.5074, -0.1278)
    london_cell = grid.latlng_to_cell(51.5074, -0.1278)
    assert sf_cell != london_cell


def test_h3_cell_geometry_and_neighbors():
    grid = AtlasHexGrid(resolution=3)
    tokyo_cell = grid.latlng_to_cell(35.6762, 139.6503)

    hex_obj = grid.get_hex_cell(tokyo_cell)
    assert isinstance(hex_obj, HexCell)
    assert hex_obj.resolution == 3
    # Center should be close to Tokyo
    assert 34.0 < hex_obj.center_lat < 37.0
    assert 138.0 < hex_obj.center_lng < 141.0

    # Boundary should have 6 or 7 vertices (closed polygon)
    assert len(hex_obj.boundary) >= 6

    # Neighbors should have exactly 6 equidistant cells in k=1 ring
    assert len(hex_obj.neighbors_k1) == 6
    for neighbor in hex_obj.neighbors_k1:
        assert neighbor != tokyo_cell
        assert grid.grid_distance(tokyo_cell, neighbor) == 1
