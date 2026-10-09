from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TextIO

from .constraints import RoadSegment


def load_road_segments(source: str | Path | TextIO) -> tuple[RoadSegment, ...]:
    """Load a small offline road graph from explicit JSON or OSM XML.

    JSON uses ``{"ways": [{"id": "...", "points": [[x, y], ...]}]}``.
    OSM XML way coordinates are converted from lon/lat into a local
    equirectangular metre frame using the first node as the origin.
    """
    stream, close = _open(source)
    try:
        name = getattr(stream, "name", "")
        if str(name).lower().endswith(".json"):
            return _from_json(json.load(stream))
        content = stream.read()
    finally:
        if close:
            stream.close()
    stripped = content.lstrip()
    if stripped.startswith("{"):
        return _from_json(json.loads(content))
    return _from_osm_xml(stripped)


def _from_json(payload: object) -> tuple[RoadSegment, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("ways"), list):
        raise ValueError("map JSON must contain a ways list")
    segments: list[RoadSegment] = []
    for way in payload["ways"]:
        if not isinstance(way, dict) or not isinstance(way.get("points"), list):
            raise ValueError("each map way requires a points list")
        points = way["points"]
        road_id = str(way.get("id", ""))
        for index, (start, end) in enumerate(zip(points, points[1:])):
            if len(start) != 2 or len(end) != 2:
                raise ValueError("map points must contain x and y")
            segments.append(RoadSegment(float(start[0]), float(start[1]), float(end[0]), float(end[1]), f"{road_id}:{index}"))
    if not segments:
        raise ValueError("map contains no non-zero road segments")
    return tuple(segments)


def _from_osm_xml(content: str) -> tuple[RoadSegment, ...]:
    root = ET.fromstring(content)
    nodes = {
        element.attrib["id"]: (float(element.attrib["lon"]), float(element.attrib["lat"]))
        for element in root.findall("node")
    }
    if not nodes:
        raise ValueError("OSM document contains no nodes")
    origin_lon, origin_lat = next(iter(nodes.values()))
    cos_lat = __import__("math").cos(__import__("math").radians(origin_lat))

    def project(point: tuple[float, float]) -> tuple[float, float]:
        lon, lat = point
        return (
            (lon - origin_lon) * 111_320.0 * cos_lat,
            (lat - origin_lat) * 110_540.0,
        )

    segments: list[RoadSegment] = []
    for way in root.findall("way"):
        road_id = way.attrib.get("id", "")
        refs = [node.attrib["ref"] for node in way.findall("nd")]
        points = [project(nodes[ref]) for ref in refs if ref in nodes]
        for index, (start, end) in enumerate(zip(points, points[1:])):
            segments.append(RoadSegment(*start, *end, f"{road_id}:{index}"))
    if not segments:
        raise ValueError("OSM document contains no usable road ways")
    return tuple(segments)


def _open(source: str | Path | TextIO) -> tuple[TextIO, bool]:
    if hasattr(source, "read"):
        return source, False  # type: ignore[return-value]
    return Path(source).open("r", encoding="utf-8"), True
