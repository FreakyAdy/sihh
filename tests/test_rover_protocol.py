import sys
import unittest
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from rover.protocol import RoverTelemetry, decode_json_line, decode_stream, encode_json_line


class RoverProtocolTests(unittest.TestCase):
    def test_json_line_round_trip_and_crc(self) -> None:
        sample = RoverTelemetry(100, 1.0, 0.0, 9.8, 0.1, 1, 2, 3, 4, 10, 11)
        self.assertEqual(decode_json_line(encode_json_line(sample)), sample)
        self.assertEqual(decode_stream(StringIO(encode_json_line(sample))), [sample])

    def test_crc_failure_is_explicit(self) -> None:
        sample = RoverTelemetry(100, 1.0, 0.0, 9.8, 0.1, 1, 2, 3, 4, 10, 11)
        line = encode_json_line(sample).replace('"crc32":', '"crc32":0, "ignored":')
        with self.assertRaises(ValueError):
            decode_json_line(line)


if __name__ == "__main__":
    unittest.main()
