from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageSequence

import render_orca_gifs as renderer


class OrcaGifLoopTests(unittest.TestCase):
    def test_light_animation_returns_to_the_exact_start_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        particles = renderer.build_particles(root / "orca" / "orca-source.png")

        first = renderer.render_frame(particles, 0, dark=False)
        wrapped = renderer.render_frame(particles, renderer.FRAMES, dark=False)

        self.assertEqual(first.tobytes(), wrapped.tobytes())

    def test_light_animation_background_is_transparent_in_every_encoded_frame(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "light.gif"
            renderer.render(root / "orca" / "orca-source.png", output, dark=False)

            with Image.open(output) as animation:
                corner_alphas = [
                    frame.convert("RGBA").getpixel((0, 0))[3]
                    for frame in ImageSequence.Iterator(animation)
                ]

        self.assertEqual(len(corner_alphas), renderer.FRAMES)
        self.assertEqual(corner_alphas, [0] * renderer.FRAMES)

    def test_visible_light_particles_never_use_the_transparency_palette_index(self) -> None:
        root = Path(__file__).resolve().parents[1]
        particles = renderer.build_particles(root / "orca" / "orca-source.png")
        frames = [
            renderer.render_frame(particles, index, dark=False)
            for index in range(renderer.FRAMES)
        ]
        encoded = renderer.encode_frames(frames)

        erased_by_frame = [
            sum(
                alpha >= 12 and palette_index == 0
                for alpha, palette_index in zip(
                    frame.getchannel("A").tobytes(),
                    indexed.tobytes(),
                )
            )
            for frame, indexed in zip(frames, encoded)
        ]

        self.assertEqual(erased_by_frame, [0] * renderer.FRAMES)


if __name__ == "__main__":
    unittest.main()
