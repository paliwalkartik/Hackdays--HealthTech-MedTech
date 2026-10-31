import numpy as np
import pytest
import vitals_engine
from vitals_engine import VitalsEngine


@pytest.mark.parametrize("target_bpm", [55, 72, 90, 110, 140])
def test_vitals_engine_accuracy(monkeypatch, target_bpm):
    """Feed synthetic RGB trace at 30 fps and assert measured BPM is within +-3."""
    engine = VitalsEngine(fps=30, window_seconds=10)
    current_time = 0.0

    def mock_time():
        return current_time

    monkeypatch.setattr(vitals_engine.time, "time", mock_time)

    f = target_bpm / 60.0
    baseline = np.array([150.0, 110.0, 90.0])
    pulse_weights = np.array([-0.2, 0.6, -0.1])

    rng = np.random.default_rng(seed=42)

    measured_bpm = 0.0
    for i in range(20 * 30):
        t = i / 30.0
        current_time = t
        noise = rng.normal(0, 0.0004, size=3)
        rgb = baseline * (1.0 + pulse_weights * np.sin(2 * np.pi * f * t) * 0.003 + noise)
        _, measured_bpm = engine.process_rgb(rgb[0], rgb[1], rgb[2])

    assert abs(measured_bpm - target_bpm) <= 3.0, (
        f"Target BPM {target_bpm} expected within +-3, got {measured_bpm:.2f}"
    )


@pytest.mark.xfail(reason="160 BPM is currently wrong due to upper bandpass cutoff at 2.5 Hz (150 BPM); SIG-1 will fix it")
def test_vitals_engine_160_bpm_xfail(monkeypatch):
    """Document that 160 BPM is currently not supported by the 150 BPM filter limit."""
    engine = VitalsEngine(fps=30, window_seconds=10)
    current_time = 0.0

    def mock_time():
        return current_time

    monkeypatch.setattr(vitals_engine.time, "time", mock_time)

    target_bpm = 160
    f = target_bpm / 60.0
    baseline = np.array([150.0, 110.0, 90.0])
    pulse_weights = np.array([-0.2, 0.6, -0.1])

    rng = np.random.default_rng(seed=42)

    measured_bpm = 0.0
    for i in range(20 * 30):
        t = i / 30.0
        current_time = t
        noise = rng.normal(0, 0.0004, size=3)
        rgb = baseline * (1.0 + pulse_weights * np.sin(2 * np.pi * f * t) * 0.003 + noise)
        _, measured_bpm = engine.process_rgb(rgb[0], rgb[1], rgb[2])

    assert abs(measured_bpm - target_bpm) <= 3.0, (
        f"Target BPM {target_bpm} expected within +-3, got {measured_bpm:.2f}"
    )

