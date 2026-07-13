"""
Temporal frame restoration using prev/current/next frames.
Designed for film dust/scratch cleanup with optional alignment and inpainting.
"""

from dataclasses import dataclass
from typing import Optional, Callable, List, Tuple
import os
import re
import cv2
import numpy as np


@dataclass
class RestorerConfig:
    # scene cut detection
    scene_cut_threshold: float = 0.22

    # alignment (ECC)
    use_alignment: bool = True
    ecc_motion: int = cv2.MOTION_TRANSLATION
    ecc_iters: int = 18

    # auto-mask
    automask_mode: str = "normal"  # "normal" | "aggressive"
    automask_tophat_kernel: Tuple[int, int] = (1, 11)
    automask_thresh: int = 18
    automask_dilate: int = 1

    # inpaint
    strong_thresh: int = 35
    inpaint_radius: int = 3

    # deflicker
    deflicker_enabled: bool = True
    deflicker_strength: float = 0.5

    # local deflicker
    deflicker_local_enabled: bool = False
    deflicker_local_strength: float = 0.4

    # dewarp and channel registration
    dewarp_strength: float = 0.0  # -1.0 .. 1.0
    register_channels: bool = False
    fieldsplit_enabled: bool = False

    # simple post adjustments
    auto_color_balance: bool = False
    auto_contrast: bool = False
    degrain_strength: float = 0.0


class TemporalRestorer:
    def __init__(self, config: Optional[RestorerConfig] = None):
        self.cfg = config or RestorerConfig()

    @staticmethod
    def _imread(path: str) -> np.ndarray:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Could not read image: {path}")
        return img

    @staticmethod
    def _to_gray(bgr: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _norm_diff(a_gray: np.ndarray, b_gray: np.ndarray) -> float:
        return float(np.mean(cv2.absdiff(a_gray, b_gray))) / 255.0

    def _is_scene_cut(self, prev_bgr: np.ndarray, curr_bgr: np.ndarray, next_bgr: np.ndarray) -> Tuple[bool, float, float]:
        pg, cg, ng = self._to_gray(prev_bgr), self._to_gray(curr_bgr), self._to_gray(next_bgr)
        d1 = self._norm_diff(pg, cg)
        d2 = self._norm_diff(ng, cg)
        return (d1 > self.cfg.scene_cut_threshold) and (d2 > self.cfg.scene_cut_threshold), d1, d2

    def _ecc_warp(self, mov_gray: np.ndarray, ref_gray: np.ndarray) -> Optional[np.ndarray]:
        try:
            motion = self.cfg.ecc_motion
            warp = np.eye(3, 3, dtype=np.float32) if motion == cv2.MOTION_HOMOGRAPHY else np.eye(2, 3, dtype=np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, self.cfg.ecc_iters, 1e-5)
            cv2.findTransformECC(ref_gray, mov_gray, warp, motion, criteria, None, 1)
            return warp
        except Exception:
            return None

    def _apply_warp(self, img: np.ndarray, warp: Optional[np.ndarray]) -> np.ndarray:
        if warp is None:
            return img
        h, w = img.shape[:2]
        if self.cfg.ecc_motion == cv2.MOTION_HOMOGRAPHY:
            return cv2.warpPerspective(
                img, warp, (w, h),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_REFLECT
            )
        return cv2.warpAffine(
            img, warp, (w, h),
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT
        )

    def build_automask(self, curr_bgr: np.ndarray) -> np.ndarray:
        g = self._to_gray(curr_bgr)
        kx, ky = self.cfg.automask_tophat_kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kx, ky))
        tophat = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, kernel)

        thr = self.cfg.automask_thresh
        if self.cfg.automask_mode == "aggressive":
            thr = max(10, thr - 6)

        _, m = cv2.threshold(tophat, thr, 255, cv2.THRESH_BINARY)
        m = cv2.medianBlur(m, 3)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

        dil = self.cfg.automask_dilate + (1 if self.cfg.automask_mode == "aggressive" else 0)
        if dil > 0:
            m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=dil)

        return m

    def restore_triplet(
        self,
        prev_bgr: np.ndarray,
        curr_bgr: np.ndarray,
        next_bgr: np.ndarray,
        mask: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, dict]:
        # Pre-processing (fieldsplit, dewarp, channel registration)
        prev_bgr = self.preprocess_frame(prev_bgr)
        curr_bgr = self.preprocess_frame(curr_bgr)
        next_bgr = self.preprocess_frame(next_bgr)

        cut, d1, d2 = self._is_scene_cut(prev_bgr, curr_bgr, next_bgr)
        use_temporal = not cut

        aligned_prev, aligned_next = prev_bgr, next_bgr
        if use_temporal and self.cfg.use_alignment:
            curr_g = self._to_gray(curr_bgr)
            wp = self._ecc_warp(self._to_gray(prev_bgr), curr_g)
            wn = self._ecc_warp(self._to_gray(next_bgr), curr_g)
            aligned_prev = self._apply_warp(prev_bgr, wp)
            aligned_next = self._apply_warp(next_bgr, wn)

        if mask is None:
            mask = self.build_automask(curr_bgr)

        out = curr_bgr.copy()
        m = mask > 0

        if use_temporal:
            stack = np.stack([aligned_prev, curr_bgr, aligned_next], axis=0)
            med = np.median(stack, axis=0).astype(np.uint8)
            out[m] = med[m]

        # inpaint strong residuals inside mask
        curr_g = self._to_gray(curr_bgr)
        out_g = self._to_gray(out)
        diff = cv2.absdiff(out_g, curr_g)
        strong = (diff > self.cfg.strong_thresh).astype(np.uint8) * 255
        strong = cv2.bitwise_and(strong, mask)
        strong = cv2.dilate(strong, np.ones((3, 3), np.uint8), iterations=1)

        for ch in range(3):
            out[..., ch] = cv2.inpaint(out[..., ch], strong, self.cfg.inpaint_radius, cv2.INPAINT_TELEA)

        info = {"scene_cut": cut, "d_prev": d1, "d_next": d2}
        # Local deflicker
        if self.cfg.deflicker_local_enabled:
            try:
                out = self.deflicker_local(prev_bgr, out, self.cfg.deflicker_local_strength)
            except Exception:
                pass

        # Post-processing (color balance, contrast, degrain)
        out = self.postprocess_frame(out)
        return out, info

    def restore_frame_paths(
        self,
        prev_path: str,
        curr_path: str,
        next_path: str,
        output_path: str,
        mask_path: Optional[str] = None
    ) -> dict:
        prev = self._imread(prev_path)
        curr = self._imread(curr_path)
        nxt = self._imread(next_path)

        # Ensure same size
        h, w = curr.shape[:2]
        prev = cv2.resize(prev, (w, h), interpolation=cv2.INTER_AREA)
        nxt = cv2.resize(nxt, (w, h), interpolation=cv2.INTER_AREA)

        mask = None
        if mask_path and os.path.exists(mask_path):
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

        restored, info = self.restore_triplet(prev, curr, nxt, mask=mask)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, restored)
        return info

    def restore_sequence(
        self,
        frames_dir: str,
        output_dir: str,
        start_index: int = 0,
        end_index: Optional[int] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> int:
        os.makedirs(output_dir, exist_ok=True)
        frames = self._list_frames(frames_dir)
        if not frames:
            return 0

        end_index = len(frames) - 1 if end_index is None else min(end_index, len(frames) - 1)
        start_index = max(0, start_index)
        if start_index > end_index:
            return 0

        total = end_index - start_index + 1
        done = 0
        prev_restored = None
        for i in range(start_index, end_index + 1):
            prev_i = max(0, i - 1)
            next_i = min(len(frames) - 1, i + 1)

            prev_path = os.path.join(frames_dir, frames[prev_i])
            curr_path = os.path.join(frames_dir, frames[i])
            next_path = os.path.join(frames_dir, frames[next_i])
            out_path = os.path.join(output_dir, frames[i])

            info = self.restore_frame_paths(prev_path, curr_path, next_path, out_path)
            if self.cfg.deflicker_enabled:
                try:
                    restored = cv2.imread(out_path, cv2.IMREAD_COLOR)
                    if restored is not None:
                        if prev_restored is not None:
                            restored = self.deflicker_match(prev_restored, restored, self.cfg.deflicker_strength)
                            cv2.imwrite(out_path, restored)
                        prev_restored = restored
                except Exception:
                    pass
            done += 1
            if progress_callback:
                progress_callback((done / total) * 100.0)

        return done

    @staticmethod
    def deflicker_match(prev_bgr: np.ndarray, curr_bgr: np.ndarray, strength: float = 0.5) -> np.ndarray:
        """Match luminance between frames to reduce flicker."""
        if prev_bgr is None or curr_bgr is None:
            return curr_bgr
        strength = max(0.0, min(1.0, float(strength)))
        prev_g = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        curr_g = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        prev_mean = float(np.mean(prev_g))
        curr_mean = float(np.mean(curr_g))
        if curr_mean < 1e-3:
            return curr_bgr
        gain = prev_mean / curr_mean
        gain = 1.0 + (gain - 1.0) * strength
        out = np.clip(curr_bgr.astype(np.float32) * gain, 0, 255).astype(np.uint8)
        return out

    @staticmethod
    def deflicker_local(prev_bgr: np.ndarray, curr_bgr: np.ndarray, strength: float = 0.4) -> np.ndarray:
        """Local deflicker using a smoothed gain map."""
        strength = max(0.0, min(1.0, float(strength)))
        prev_y = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        curr_y = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        eps = 1e-3
        gain = prev_y / (curr_y + eps)
        gain = cv2.GaussianBlur(gain, (0, 0), sigmaX=7, sigmaY=7)
        gain = 1.0 + (gain - 1.0) * strength
        out = np.clip(curr_bgr.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)
        return out

    def preprocess_frame(self, bgr: np.ndarray) -> np.ndarray:
        out = bgr
        if self.cfg.fieldsplit_enabled:
            out = self.fieldsplit_deinterlace(out)
        if abs(self.cfg.dewarp_strength) > 1e-6:
            out = self.dewarp(out, self.cfg.dewarp_strength)
        if self.cfg.register_channels:
            out = self.register_color_channels(out)
        return out

    def postprocess_frame(self, bgr: np.ndarray) -> np.ndarray:
        out = bgr
        if self.cfg.auto_color_balance:
            out = self.auto_white_balance(out)
        if self.cfg.auto_contrast:
            out = self.auto_contrast_stretch(out)
        if self.cfg.degrain_strength > 0:
            out = self.degrain(out, self.cfg.degrain_strength)
        return out

    @staticmethod
    def fieldsplit_deinterlace(bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        even = bgr[0::2, :, :]
        odd = bgr[1::2, :, :]
        even_up = cv2.resize(even, (w, h), interpolation=cv2.INTER_LINEAR)
        odd_up = cv2.resize(odd, (w, h), interpolation=cv2.INTER_LINEAR)
        out = ((even_up.astype(np.float32) + odd_up.astype(np.float32)) * 0.5).astype(np.uint8)
        return out

    @staticmethod
    def dewarp(bgr: np.ndarray, strength: float) -> np.ndarray:
        strength = max(-1.0, min(1.0, float(strength)))
        h, w = bgr.shape[:2]
        fx = fy = max(w, h)
        cx = w / 2.0
        cy = h / 2.0
        k1 = strength * 0.0008
        camera = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)
        dist = np.array([k1, 0, 0, 0, 0], dtype=np.float32)
        return cv2.undistort(bgr, camera, dist)

    def register_color_channels(self, bgr: np.ndarray) -> np.ndarray:
        try:
            b, g, r = cv2.split(bgr)
            r_al = self._align_channel(r, g)
            b_al = self._align_channel(b, g)
            return cv2.merge([b_al, g, r_al])
        except Exception:
            return bgr

    @staticmethod
    def _align_channel(channel: np.ndarray, ref: np.ndarray) -> np.ndarray:
        try:
            warp = np.eye(2, 3, dtype=np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 1e-5)
            cv2.findTransformECC(ref, channel, warp, cv2.MOTION_TRANSLATION, criteria, None, 1)
            h, w = channel.shape[:2]
            return cv2.warpAffine(channel, warp, (w, h),
                                  flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                                  borderMode=cv2.BORDER_REFLECT)
        except Exception:
            return channel

    @staticmethod
    def auto_white_balance(bgr: np.ndarray) -> np.ndarray:
        try:
            b, g, r = cv2.split(bgr.astype(np.float32))
            mean_b, mean_g, mean_r = np.mean(b), np.mean(g), np.mean(r)
            mean_gray = (mean_b + mean_g + mean_r) / 3.0
            b = b * (mean_gray / max(mean_b, 1e-3))
            g = g * (mean_gray / max(mean_g, 1e-3))
            r = r * (mean_gray / max(mean_r, 1e-3))
            out = cv2.merge([b, g, r])
            return np.clip(out, 0, 255).astype(np.uint8)
        except Exception:
            return bgr

    @staticmethod
    def auto_contrast_stretch(bgr: np.ndarray) -> np.ndarray:
        try:
            yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
            y = yuv[:, :, 0]
            y = cv2.equalizeHist(y)
            yuv[:, :, 0] = y
            return cv2.cvtColor(yuv, cv2.COLOR_YCrCb2BGR)
        except Exception:
            return bgr

    @staticmethod
    def degrain(bgr: np.ndarray, strength: float = 0.4) -> np.ndarray:
        strength = max(0.0, min(1.0, float(strength)))
        if strength <= 0:
            return bgr
        blur = cv2.GaussianBlur(bgr, (0, 0), sigmaX=1.5 + strength * 2.0)
        out = cv2.addWeighted(bgr, 1.0 - strength, blur, strength, 0)
        return out

    @staticmethod
    def _list_frames(frames_dir: str) -> List[str]:
        if not os.path.exists(frames_dir):
            return []
        files = [f for f in os.listdir(frames_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        return sorted(files, key=TemporalRestorer._extract_frame_number)

    @staticmethod
    def _extract_frame_number(filename: str) -> int:
        match = re.search(r"(\\d+)", filename)
        if match:
            return int(match.group(1))
        return 0
