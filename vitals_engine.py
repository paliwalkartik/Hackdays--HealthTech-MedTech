import numpy as np
from scipy.signal import butter, filtfilt, detrend
import time

class VitalsEngine:
    def __init__(self, fps=30, window_seconds=10):
        self.fps = fps
        self.window_size = int(fps * window_seconds)
        self.rgb_buffer = []
        self.time_buffer = []
        self.current_bpm = 0.0
        self.pulse_value = 0.0

    def reset(self):
        """Clear all signal buffers to start a fresh measurement."""
        self.rgb_buffer   = []
        self.time_buffer  = []
        self.current_bpm  = 0.0
        self.pulse_value  = 0.0


    def process_rgb(self, r, g, b):
        self.rgb_buffer.append([r, g, b])
        self.time_buffer.append(time.time())
        if len(self.rgb_buffer) > self.window_size:
            self.rgb_buffer.pop(0)
            self.time_buffer.pop(0)
            
        if len(self.time_buffer) >= 2:
            time_diff = self.time_buffer[-1] - self.time_buffer[0]
            if time_diff > 0:
                self.fps = len(self.time_buffer) / time_diff

        # Require at least 3 seconds of data to start showing something
        if len(self.rgb_buffer) >= self.fps * 3:
            self._compute_vitals()
            
        return self.pulse_value, self.current_bpm

    def _compute_vitals(self):
        C = np.array(self.rgb_buffer)
        
        # Moving Average Filter (window size 5)
        window = 5
        if len(C) >= window:
            kernel = np.ones(window) / window
            C_smooth = np.zeros_like(C)
            for i in range(3):
                C_smooth[:, i] = np.convolve(C[:, i], kernel, mode='same')
            C = C_smooth
            
        mu_c = np.mean(C, axis=0)
        # Normalize
        C_n = C / (mu_c + 1e-8)
        
        R_n = C_n[:, 0]
        G_n = C_n[:, 1]
        B_n = C_n[:, 2]
        
        # Project
        P_x = G_n - B_n
        P_y = G_n + B_n - 2 * R_n
        
        std_Px = np.std(P_x)
        std_Py = np.std(P_y)
        
        # Result S
        S = P_x + (std_Px / (std_Py + 1e-8)) * P_y
        
        # Detrend the signal
        S = detrend(S)
        
        # We need at least enough samples for the butterworth filter
        if len(S) <= 15:
            return

        try:
            # Bandpass filter for 45 to 150 BPM (0.75 Hz - 2.5 Hz)
            nyquist = self.fps / 2.0
            if nyquist <= 2.5:
                return
            b, a = butter(3, [0.75 / nyquist, 2.5 / nyquist], btype='band')
            filtered = filtfilt(b, a, S)
            self.pulse_value = filtered[-1]
            
            # Compute BPM if we have enough data (e.g., 5 seconds)
            if len(S) >= self.fps * 5:
                n = len(filtered)
                freqs = np.fft.rfftfreq(n, d=1.0/self.fps)
                fft = np.abs(np.fft.rfft(filtered))
                
                valid_idx = np.where((freqs >= 0.75) & (freqs <= 2.5))
                if len(valid_idx[0]) > 0:
                    valid_freqs = freqs[valid_idx]
                    valid_fft = fft[valid_idx]
                    peak_freq = valid_freqs[np.argmax(valid_fft)]
                    self.current_bpm = peak_freq * 60.0
        except ValueError:
            # Handle cases where array is too short for the filter or other scipy errors
            pass
