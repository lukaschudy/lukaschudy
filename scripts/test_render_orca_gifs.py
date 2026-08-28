from __future__ import annotations

import unittest
from pathlib import Path

import render_orca_gifs as renderer


class OrcaGifLoopTests(unittest.TestCase):
    def test_light_animation_returns_to_the_exact_start_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        particles = renderer.build_particles(root / "orca" / "orca-source.png")

        first = renderer.render_frame(particles, 0, dark=False)
        wrapped = renderer.render_frame(particles, renderer.FRAMES, dark=False)

        self.assertEqual(first.tobytes(), wrapped.tobytes())


if __name__ == "__main__":
    unittest.main()
