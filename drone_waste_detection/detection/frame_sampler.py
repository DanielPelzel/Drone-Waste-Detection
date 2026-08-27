"""Temporal frame sampling independent of drone movement."""


class TimeFrameSampler:
    """Select frames at a fixed target rate using video timestamps.

    This replaces the earlier distance-based scan trigger. Consequently, waste
    can still be detected while the drone is stationary or moving only slowly.
    """

    def __init__(self, target_fps: float) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive.")
        self.period_seconds = 1.0 / float(target_fps)
        self.next_time_seconds = 0.0

    def should_process(self, video_seconds: float) -> bool:
        """Return True when the current video time reaches the next sample."""
        if video_seconds + 1e-9 < self.next_time_seconds:
            return False

        # Advance until the next requested sample lies strictly in the future.
        # This remains stable if input FPS is not an integer multiple of target FPS.
        while self.next_time_seconds <= video_seconds + 1e-9:
            self.next_time_seconds += self.period_seconds
        return True
