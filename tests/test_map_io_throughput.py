import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "shared"))
sys.path.insert(0, str(Path(__file__).parents[1] / "edge-engine"))

from idr.throughput import measure_throughput
from idr_engine import load_road_segments


class MapAndThroughputTests(unittest.TestCase):
    def test_loads_json_way_into_segments(self) -> None:
        segments = load_road_segments(io.StringIO('{"ways":[{"id":"a","points":[[0,0],[10,0],[10,5]]}]}'))
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[1].road_id, "a:1")

    def test_loads_osm_xml_into_local_segments(self) -> None:
        source = io.StringIO(
            '<osm><node id="1" lon="77" lat="28"/>'
            '<node id="2" lon="77.0001" lat="28"/>'
            '<way id="w"><nd ref="1"/><nd ref="2"/></way></osm>'
        )
        segments = load_road_segments(source)
        self.assertEqual(len(segments), 1)
        self.assertGreater(segments[0].end_x_m, 0.0)

    def test_reports_update_rate_and_target(self) -> None:
        report = measure_throughput(range(5), lambda _: None, target_rate_hz=1.0)
        self.assertEqual(report.sample_count, 5)
        self.assertTrue(report.meets_target)


if __name__ == "__main__":
    unittest.main()
