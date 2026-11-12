"""Run an isolated moving-camera day/night performance check. Saves stay in memory."""
import argparse
import statistics
import time
import tkinter as tk

import tycoon
from lisbon_scene import WORLD_WIDTH
from tycoon import DAYLIGHT_SECONDS, Game, configure_display_dpi


class SilentMusic:
    enabled = False

    def stop(self):
        pass

    def set_enabled(self, enabled):
        self.enabled = enabled


class MemorySave:
    def save(self, player, revision, snapshot):
        return revision+1


def frame_statistics(frames, duration, elapsed):
    """Count completed frames; empty full one-second windows count as zero."""
    intervals = sorted((b-a)*1000 for a, b in zip(frames, frames[1:]))
    counts = [0]*int(min(duration, elapsed))
    for stamp in frames:
        bucket = int(stamp)
        if 0 <= bucket < len(counts):
            counts[bucket] += 1
    def percentile(fraction):
        return intervals[round((len(intervals)-1)*fraction)] if intervals else None
    return {
        "average_fps": len(frames)/elapsed if elapsed else 0,
        "lowest_one_second_fps": min(counts) if counts else None,
        "one_second_counts": counts,
        "median_frame_ms": statistics.median(intervals) if intervals else None,
        "p95_frame_ms": percentile(.95), "p99_frame_ms": percentile(.99),
    }


def run(seconds=6, zoom=1.25, target_fps=None):
    previous = tycoon.TARGET_FPS, tycoon.FRAME_SECONDS
    if target_fps is not None:
        if not 30 <= target_fps <= 240:
            raise ValueError("Benchmark target must be between 30 and 240 FPS")
        tycoon.TARGET_FPS, tycoon.FRAME_SECONDS = target_fps, 1/target_fps
    try:
        return _run(seconds, zoom)
    finally:
        tycoon.TARGET_FPS, tycoon.FRAME_SECONDS = previous


def _run(seconds, zoom):
    configure_display_dpi()
    root = tk.Tk()
    root.withdraw()
    root.foundry_music = SilentMusic()
    game = Game(root, (MemorySave(), "render-benchmark", 0, None))
    game.world_view.set_zoom(zoom)
    game.town.message = "Temporary world benchmark · moving camera, traffic, pedestrians and boats · closes automatically."
    half_width = game.world_view.camera.visible_width/2
    left, right = half_width+24, WORLD_WIDTH-half_width-24
    if right-left < 100:
        left, right = 140, WORLD_WIDTH-140
    game.town.x, game.town.y = left, 321
    game.world_view.camera.follow(left, 321, snap=True)
    root.deiconify()
    root.lift()
    root.focus_force()
    root.update_idletasks()
    original = game.draw_live
    started = None
    frames, draw_times = [], []
    changed_night = False
    direction = 1
    camera_samples = []
    result = {}

    def render():
        nonlocal changed_night, direction
        if started is None:
            original()
            return
        now = time.perf_counter()
        age = now-started
        game.town.elapsed = age
        if (direction > 0 and game.town.x >= right) or (direction < 0 and game.town.x <= left):
            direction *= -1
            game.keys.discard("d" if direction < 0 else "a")
            game.keys.add("a" if direction < 0 else "d")
        if age >= seconds/2 and not changed_night:
            game.town.market_elapsed = DAYLIGHT_SECONDS+10
            game.market_started_at = time.time()-game.town.market_elapsed
            changed_night = True
        original()
        completed = time.perf_counter()
        draw_times.append(completed-now)
        frames.append(completed-started)
        camera_samples.append(game.world_view.camera.x)

    game.draw_live = render

    def finish():
        elapsed = time.perf_counter()-started
        stats = frame_statistics(frames, seconds, elapsed)
        day = sum(t < seconds/2 for t in frames)/(seconds/2)
        night = sum(t >= seconds/2 for t in frames)/max(.1, elapsed-seconds/2)
        print(f"{game.viewport_width}x{game.viewport_height} | zoom {zoom} | target {tycoon.TARGET_FPS} FPS | {len(game.world_view.actors)} ambient actors")
        print("Renderer: Windows bitmap cache" if getattr(game.world_view.canvas, "native_world", False) else "Renderer: Tk canvas")
        print(f"Average {stats['average_fps']:.1f} FPS | day {day:.1f} FPS | night {night:.1f} FPS")
        if stats["lowest_one_second_fps"] is not None:
            print(f"Lowest complete one-second window: {stats['lowest_one_second_fps']} FPS")
        print(f"Median Python render: {statistics.median(draw_times)*1000:.2f} ms")
        if stats["median_frame_ms"] is not None:
            print(f"Frame time: median {stats['median_frame_ms']:.2f} ms | p95 {stats['p95_frame_ms']:.2f} ms | p99 {stats['p99_frame_ms']:.2f} ms")
        moved = sum(abs(b-a) > .01 for a, b in zip(camera_samples, camera_samples[1:]))
        travel = sum(abs(b-a) for a, b in zip(camera_samples, camera_samples[1:]))
        print(f"Camera moving on {moved/max(1, len(camera_samples)-1)*100:.1f}% of frames | travelled {travel:.0f} world units")
        print(f"Player x={game.town.x:.0f}, camera x={game.world_view.camera.x:.0f}")
        result.update(stats, day_fps=day, night_fps=night, target_fps=tycoon.TARGET_FPS,
                      width=game.viewport_width, height=game.viewport_height,
                      camera_motion_fraction=moved/max(1, len(camera_samples)-1))
        game.save_and_close()

    def start():
        nonlocal started
        started = time.perf_counter()
        game.town.x, game.town.y = left, 321
        game.world_view.camera.follow(left, 321, snap=True)
        game.keys.add("d")
        game.last_tick = game.next_frame_time = time.perf_counter()
        print("Steady-state measurement after a 1-second window warmup", flush=True)
        print(f"Walking route: x={left:.0f} to {right:.0f} | visible world width {game.world_view.camera.visible_width:.0f}", flush=True)
        root.after(round(seconds*1000), finish)

    root.after(1000, start)
    root.mainloop()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--zoom", type=float, choices=(1.0, 1.25, 1.5), default=1.25)
    parser.add_argument("--target-fps", type=int, choices=range(30, 241), metavar="30..240")
    args = parser.parse_args()
    run(max(2, min(30, args.seconds)), args.zoom, args.target_fps)
