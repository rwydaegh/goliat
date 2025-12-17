"""Tests for dispersion model fitting."""

import pytest

from goliat.dispersion.fitter import (
    DispersionParams,
    PoleFit,
    fit_dispersion,
    validate_fit,
)


class TestFitDispersion:
    """Tests for the fit_dispersion function."""

    def test_basic_two_frequency_fit(self):
        """Test fitting to two frequency points with known values."""
        frequencies_hz = [700e6, 2450e6]
        eps_r_targets = [53.0, 48.9]
        sigma_targets = [0.92, 1.81]

        params = fit_dispersion(frequencies_hz, eps_r_targets, sigma_targets)

        assert isinstance(params, DispersionParams)
        assert params.eps_inf > 0
        assert params.sigma_dc >= 0
        assert len(params.poles) == 2
        assert all(isinstance(p, PoleFit) for p in params.poles)
        # For 2-frequency exact solve, error should be near zero
        assert params.fit_error < 1e-10

    def test_exact_match_at_target_frequencies(self):
        """Test that fitted model exactly matches target values."""
        frequencies_hz = [700e6, 2450e6]
        eps_r_targets = [53.90, 48.91]
        sigma_targets = [0.86, 1.81]

        params = fit_dispersion(frequencies_hz, eps_r_targets, sigma_targets)

        is_valid, errors = validate_fit(params, frequencies_hz, eps_r_targets, sigma_targets, tolerance_pct=0.1)

        # Should be exact match (< 0.1% error)
        assert is_valid, f"Expected exact match, got errors: {errors}"

    def test_three_frequency_fit(self):
        """Test fitting to three frequency points (uses optimization)."""
        frequencies_hz = [450e6, 700e6, 2450e6]
        eps_r_targets = [56.0, 53.0, 48.9]
        sigma_targets = [0.72, 0.92, 1.81]

        params = fit_dispersion(frequencies_hz, eps_r_targets, sigma_targets)

        assert isinstance(params, DispersionParams)
        assert len(params.poles) == 2
        # For 3 frequencies, some error is expected
        assert params.fit_error >= 0

    def test_fit_speed(self):
        """Test that 2-frequency fit is fast (< 10ms)."""
        import time

        frequencies_hz = [700e6, 2450e6]
        eps_r_targets = [53.0, 48.9]
        sigma_targets = [0.92, 1.81]

        start = time.perf_counter()
        for _ in range(10):
            fit_dispersion(frequencies_hz, eps_r_targets, sigma_targets)
        elapsed = (time.perf_counter() - start) / 10

        # Should complete in < 10ms (typically ~0.2ms)
        assert elapsed < 0.01, f"Fit took {elapsed * 1000:.1f}ms, expected < 10ms"

    def test_invalid_input_length_mismatch(self):
        """Test that mismatched input lengths raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            fit_dispersion([700e6, 2450e6], [53.0], [0.92, 1.81])

    def test_various_tissue_values(self):
        """Test fitting works for various tissue types."""
        test_cases = [
            # (name, freqs, eps_targets, sigma_targets)
            ("Muscle", [700e6, 2450e6], [55.6, 52.7], [0.88, 1.74]),
            ("Fat", [700e6, 2450e6], [11.4, 10.8], [0.10, 0.27]),
            ("Bone", [700e6, 2450e6], [12.5, 11.4], [0.13, 0.39]),
        ]

        for name, freqs, eps_t, sig_t in test_cases:
            params = fit_dispersion(freqs, eps_t, sig_t)
            is_valid, _ = validate_fit(params, freqs, eps_t, sig_t, tolerance_pct=1.0)
            assert is_valid, f"Fit failed for {name}"


class TestDispersionParams:
    """Tests for DispersionParams dataclass."""

    def test_dataclass_fields(self):
        """Test that DispersionParams has expected fields."""
        pole = PoleFit(delta_eps=10.0, tau_s=1e-10, damping_hz=1e8)
        params = DispersionParams(
            eps_inf=2.0,
            sigma_dc=0.1,
            poles=[pole],
            fit_error=0.001,
            start_freq_hz=350e6,
            end_freq_hz=3e9,
        )

        assert params.eps_inf == 2.0
        assert params.sigma_dc == 0.1
        assert len(params.poles) == 1
        assert params.poles[0].delta_eps == 10.0
