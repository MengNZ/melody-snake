"""YIN fundamental-frequency estimator (self-contained, numpy only).

YIN: De Cheveigne & Kawahara (2002). Steps:
  1. difference function d(tau)
  2. cumulative-mean-normalized difference function (CMNDF)
  3. absolute threshold to find the first plausible period
  4. parabolic interpolation for sub-sample period accuracy

The difference function is evaluated exactly but in O(n log n) via an
FFT-based autocorrelation plus prefix sums (no O(n^2) loop over samples).

Known limitation: single-f0 estimators like YIN suit monophonic / near
monophonic audio. Full polyphonic melody extraction is explicitly out of
scope for v1.
"""

import numpy as np


class YinDetector:
    def __init__(self, fmin=60.0, fmax=2000.0, threshold=0.1):
        self.fmin = float(fmin)
        self.fmax = float(fmax)
        self.threshold = float(threshold)

    def _difference(self, frame, tau_max):
        n = len(frame)
        # Linear autocorrelation via FFT (zero-padded to 2n avoids wraparound).
        spec = np.fft.rfft(frame, n=2 * n)
        ac = np.fft.irfft(spec * np.conj(spec))[:n]

        x2 = frame * frame
        cum = np.cumsum(x2)
        total = cum[-1]

        d = np.empty(tau_max + 1, dtype=np.float64)
        d[0] = 0.0
        for tau in range(1, tau_max + 1):
            # Exact YIN difference: sum over j in [0, n-tau-1] of (x[j]-x[j+tau])^2
            first = cum[n - tau - 1]          # sum x[j]^2 for j in [0, n-tau-1]
            r_tail = total - cum[tau - 1]     # sum x[j]^2 for j in [tau, n-1]
            d[tau] = first + r_tail - 2.0 * ac[tau]
        return d

    def _cmndf(self, d):
        n = len(d)
        cmndf = np.zeros(n, dtype=np.float64)
        cmndf[0] = 1.0
        running = 0.0
        for tau in range(1, n):
            running += d[tau]
            cmndf[tau] = (d[tau] * tau / running) if running > 0 else 1.0
        return cmndf

    def detect(self, frame, sample_rate):
        """Estimate f0 of a mono float frame.

        Returns (f0_hz, confidence, rms, clipped):
          - f0_hz is None when unvoiced/undetected.
          - confidence in [0, 1] (1 - aperiodicity), NOT a calibrated probability.
        """
        frame = np.asarray(frame, dtype=np.float32)
        n = len(frame)

        rms = float(np.sqrt(np.mean(frame * frame))) if n else 0.0
        clipped = bool(np.max(np.abs(frame)) >= 0.99) if n else False

        tau_min = max(1, int(sample_rate / self.fmax))
        tau_max = min(n // 2, int(sample_rate / self.fmin))
        if tau_max <= tau_min or rms < 1e-4 or n == 0:
            return None, 0.0, rms, clipped

        d = self._difference(frame, tau_max)
        cmndf = self._cmndf(d)

        seg = cmndf[tau_min:tau_max + 1]
        below = np.where(seg < self.threshold)[0]
        if len(below) == 0:
            return None, 0.0, rms, clipped

        tau = int(below[0]) + tau_min

        # The first below-threshold index lands on the *approach* slope of the
        # period dip, not the dip itself. Walk forward to the local minimum so
        # parabolic interpolation happens at the true minimum.
        while tau + 1 <= tau_max and cmndf[tau + 1] < cmndf[tau]:
            tau += 1

        beta = float(cmndf[tau])

        # Parabolic interpolation around tau for sub-sample period accuracy.
        if 1 <= tau < tau_max:
            alpha = float(cmndf[tau - 1])
            gamma = float(cmndf[tau + 1])
            denom = alpha - 2.0 * beta + gamma
            if abs(denom) > 1e-12:
                peak = tau + 0.5 * (alpha - gamma) / denom
            else:
                peak = float(tau)
        else:
            peak = float(tau)

        f0 = sample_rate / peak
        if f0 < self.fmin or f0 > self.fmax:
            return None, 0.0, rms, clipped

        aperiodicity = float(np.clip(beta, 0.0, 1.0))
        confidence = 1.0 - aperiodicity
        return f0, confidence, rms, clipped
