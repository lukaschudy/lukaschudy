#!/usr/bin/env python3
"""Render the theme-aware particle-orca profile GIFs.

The travelling current follows the underside of the orca from its body toward
the tail. Rendering is deterministic so both GitHub theme variants stay in
sync.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

WIDTH = 960
HEIGHT = 414
FRAMES = 40
DURATION_MS = 140
SUPERSAMPLE = 2
SOURCE_BACKGROUND = (242, 239, 232)
LIGHT_BACKGROUND = (240, 237, 231)
TRANSPARENT_KEY = (1, 0, 2)


@dataclass(frozen=True)
class Particle:
    x: float
    y: float
    color: tuple[int, int, int]
    radius: float
    phase_x: float
    phase_y: float
    phase_alpha: float
    curve_t: float
    curve_distance: float
    tangent_x: float
    tangent_y: float
    normal_x: float
    normal_y: float


def cubic_bezier(t: float) -> tuple[float, float]:
    # Matches the user-directed route: under the body, rising through the
    # belly particles, then falling into the tail tip.
    p0 = (0.40 * WIDTH, 0.90 * HEIGHT)
    p1 = (0.52 * WIDTH, 0.68 * HEIGHT)
    p2 = (0.76 * WIDTH, 0.67 * HEIGHT)
    p3 = (0.91 * WIDTH, 0.97 * HEIGHT)
    u = 1.0 - t
    x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
    return x, y


def cubic_tangent(t: float) -> tuple[float, float]:
    p0 = (0.40 * WIDTH, 0.90 * HEIGHT)
    p1 = (0.52 * WIDTH, 0.68 * HEIGHT)
    p2 = (0.76 * WIDTH, 0.67 * HEIGHT)
    p3 = (0.91 * WIDTH, 0.97 * HEIGHT)
    u = 1.0 - t
    dx = 3 * u * u * (p1[0] - p0[0]) + 6 * u * t * (p2[0] - p1[0]) + 3 * t * t * (p3[0] - p2[0])
    dy = 3 * u * u * (p1[1] - p0[1]) + 6 * u * t * (p2[1] - p1[1]) + 3 * t * t * (p3[1] - p2[1])
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def smoothstep(low: float, high: float, value: float) -> float:
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    x = (value - low) / (high - low)
    return x * x * (3.0 - 2.0 * x)


def mix_color(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.0, min(1.0, amount))
    return tuple(round(left + (right - left) * amount) for left, right in zip(a, b))


def build_particles(source_path: Path) -> list[Particle]:
    source = Image.open(source_path).convert("RGB")
    scale_x = WIDTH / source.width
    scale_y = HEIGHT / source.height
    pixels = source.load()
    curve = [(step / 240.0, *cubic_bezier(step / 240.0)) for step in range(241)]
    rng = random.Random(20260828)
    particles: list[Particle] = []

    for source_y in range(0, source.height, 4):
        for source_x in range(0, source.width, 4):
            color = pixels[source_x, source_y]
            delta = sum(abs(color[channel] - SOURCE_BACKGROUND[channel]) for channel in range(3))
            if delta < 58:
                continue

            x = source_x * scale_x
            y = source_y * scale_y
            curve_t, curve_x, curve_y = min(
                curve,
                key=lambda sample: (sample[1] - x) ** 2 + (sample[2] - y) ** 2,
            )
            tangent_x, tangent_y = cubic_tangent(curve_t)
            particles.append(
                Particle(
                    x=x,
                    y=y,
                    color=color,
                    radius=0.55 + rng.random() * 0.72,
                    phase_x=rng.random() * math.tau,
                    phase_y=rng.random() * math.tau,
                    phase_alpha=rng.random() * math.tau,
                    curve_t=curve_t,
                    curve_distance=math.hypot(curve_x - x, curve_y - y),
                    tangent_x=tangent_x,
                    tangent_y=tangent_y,
                    normal_x=-tangent_y,
                    normal_y=tangent_x,
                )
            )
    return particles


def theme_color(source: tuple[int, int, int], dark: bool) -> tuple[int, int, int]:
    if not dark:
        return tuple(max(35, round(channel * 0.78)) for channel in source)
    luminance = sum(source) / (3 * 255)
    return (
        round(86 + 92 * luminance),
        round(126 + 96 * luminance),
        round(159 + 92 * luminance),
    )


def render_frame(particles: list[Particle], frame_index: int, dark: bool) -> Image.Image:
    width = WIDTH * SUPERSAMPLE
    height = HEIGHT * SUPERSAMPLE
    background = (0, 0, 0, 0) if dark else (*LIGHT_BACKGROUND, 255)
    frame = Image.new("RGBA", (width, height), background)
    draw = ImageDraw.Draw(frame, "RGBA")
    loop_phase = frame_index / FRAMES * math.tau

    # The head and tail ends are idle, making frame 39 -> frame 0 seamless.
    loop_fraction = frame_index / FRAMES
    current_center = -0.15 + 1.30 * loop_fraction
    edge_strength = smoothstep(-0.01, 0.09, current_center) * (
        1.0 - smoothstep(0.91, 1.01, current_center)
    )
    accent = (215, 241, 255) if dark else (39, 91, 128)

    for particle in particles:
        ambient_x = math.sin(loop_phase + particle.phase_x) * 0.62
        ambient_y = math.cos(loop_phase + particle.phase_y) * 0.48

        along = particle.curve_t - current_center
        longitudinal = math.exp(-0.5 * (along / 0.085) ** 2)
        cross_section = math.exp(-0.5 * (particle.curve_distance / 34.0) ** 2)
        current = longitudinal * cross_section * edge_strength

        # Carry the selected particles downstream and give the wave a small
        # organic curl. They settle back onto the silhouette after it passes.
        carry = 22.0 * current
        curl = math.sin(particle.phase_y + loop_phase * 1.35) * 5.2 * current
        x = particle.x + ambient_x + particle.tangent_x * carry + particle.normal_x * curl
        y = particle.y + ambient_y + particle.tangent_y * carry + particle.normal_y * curl

        base = theme_color(particle.color, dark)
        color = mix_color(base, accent, current * 0.90)
        shimmer = 0.82 + 0.18 * math.sin(loop_phase + particle.phase_alpha)
        alpha = round((188 if dark else 212) * shimmer + current * (58 if dark else 34))
        radius = particle.radius * (1.0 + current * 0.58) * SUPERSAMPLE
        center_x = x * SUPERSAMPLE
        center_y = y * SUPERSAMPLE
        draw.ellipse(
            (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
            fill=(*color, max(0, min(255, alpha))),
        )

    return frame.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def shared_palette(frames: list[Image.Image], dark: bool) -> Image.Image:
    samples = frames[::4]
    strip = Image.new("RGB", (WIDTH, HEIGHT * len(samples)), TRANSPARENT_KEY if dark else LIGHT_BACKGROUND)
    for index, frame in enumerate(samples):
        if dark:
            rgb = Image.new("RGB", frame.size, TRANSPARENT_KEY)
            rgb.paste(frame.convert("RGB"), mask=frame.getchannel("A"))
        else:
            rgb = frame.convert("RGB")
        strip.paste(rgb, (0, index * HEIGHT))

    colors = 255 if dark else 256
    quantized = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()[: colors * 3]
    if dark:
        palette = [*TRANSPARENT_KEY, *palette]
    palette = palette[:768] + [0] * max(0, 768 - len(palette))
    palette_image = Image.new("P", (1, 1))
    palette_image.putpalette(palette)
    return palette_image


def encode_frames(frames: list[Image.Image], dark: bool) -> list[Image.Image]:
    palette = shared_palette(frames, dark)
    encoded: list[Image.Image] = []
    for frame in frames:
        if dark:
            rgb = Image.new("RGB", frame.size, TRANSPARENT_KEY)
            rgb.paste(frame.convert("RGB"), mask=frame.getchannel("A"))
        else:
            rgb = frame.convert("RGB")
        indexed = rgb.quantize(palette=palette, dither=Image.Dither.NONE)
        if dark:
            transparent = frame.getchannel("A").point(lambda alpha: 255 if alpha < 12 else 0)
            indexed.paste(0, mask=transparent)
            indexed.info["transparency"] = 0
        encoded.append(indexed)
    return encoded


def render(source: Path, output: Path, *, dark: bool) -> tuple[int, int]:
    particles = build_particles(source)
    frames = [render_frame(particles, index, dark) for index in range(FRAMES)]
    encoded = encode_frames(frames, dark)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded[0].save(
        output,
        save_all=True,
        append_images=encoded[1:],
        duration=DURATION_MS,
        loop=0,
        disposal=2,
        optimize=True,
        transparency=0 if dark else None,
    )
    influenced = sum(1 for particle in particles if particle.curve_distance <= 34)
    return len(particles), influenced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source = args.root / "orca" / "orca-source.png"
    light = args.root / "assets" / "orca-particles.gif"
    dark = args.root / "assets" / "orca-particles-dark.gif"
    particle_count, influenced = render(source, light, dark=False)
    render(source, dark, dark=True)
    print(f"rendered particles={particle_count} current_band={influenced} frames={FRAMES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
