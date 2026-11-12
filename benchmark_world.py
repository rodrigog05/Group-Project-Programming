"""Run an isolated moving-camera day/night performance check. Saves stay in memory."""
import argparse
import statistics
import time
import tkinter as tk

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


def run(seconds=6, zoom=1.25):
    configure_display_dpi()
    root = tk.Tk()
    root.withdraw()
    root.foundry_music = SilentMusic()
    game = Game(root, (MemorySave(), "render-benchmark", 0, None))
    game.world_view.set_zoom(zoom)
    game.town.message = "Temporary world benchmark · moving camera, traffic, pedestrians and boats · closes automatically."
    root.deiconify()
    root.update()
    original = game.draw_live
    started = previous = time.perf_counter()
    frames, draw_times = [], []
    changed_night = False

    def render():
        nonlocal previous, changed_night
        now = time.perf_counter()
        age = now-started
        dt = min(.05, now-previous)
        previous = now
        game.town.elapsed = age
        game.town.move(1, 0, dt)
        if age >= seconds/2 and not changed_night:
            game.town.market_elapsed = DAYLIGHT_SECONDS+10
            game.market_started_at = time.time()-game.town.market_elapsed
            changed_night = True
        original()
        draw_times.append(time.perf_counter()-now)
        frames.append(age)

    game.draw_live = render

    def finish():
        elapsed = time.perf_counter()-started
        day = sum(t < seconds/2 for t in frames)/(seconds/2)
        night = sum(t >= seconds/2 for t in frames)/max(.1, elapsed-seconds/2)
        print(f"{game.viewport_width}x{game.viewport_height} | zoom {zoom} | {len(game.world_view.actors)} ambient actors")
        print(f"Average {len(frames)/elapsed:.1f} FPS | day {day:.1f} FPS | night {night:.1f} FPS")
        print(f"Median Python render: {statistics.median(draw_times)*1000:.2f} ms")
        print(f"Player x={game.town.x:.0f}, camera x={game.world_view.camera.x:.0f}")
        game.save_and_close()

    root.after(round(seconds*1000), finish)
    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--zoom", type=float, choices=(1.0, 1.25, 1.5), default=1.25)
    args = parser.parse_args()
    run(max(2, min(30, args.seconds)), args.zoom)
