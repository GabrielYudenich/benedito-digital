"""
Dirt Mask Generator for Video Restoration
Advanced temporal analysis for detecting dirt and scratches in video frames
"""

import cv2
import numpy as np
import os
from typing import Tuple, Optional

# Add path for logger
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'lib', 'utils'))

try:
    from logger import get_logger
    logger = get_logger()
except ImportError:
    # Fallback if logger not available
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def debug(self, msg): pass
        def log_ffmpeg_command(self, *args): pass
        def log_video_processing(self, *args): pass
        def log_frame_operation(self, *args): pass

    logger = MockLogger()

class MaskGenerator:
    """Advanced dirt and scratch mask generator"""

    def __init__(self):
        self.logger = logger

    def to_gray(self, img: np.ndarray) -> np.ndarray:
        """Convert image to grayscale if needed"""
        if img.ndim == 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def align_to(self, ref_gray: np.ndarray, mov_gray: np.ndarray) -> np.ndarray:
        """
        Align mov_gray to ref_gray using optical flow (Farneback) and warping.
        Good for small movements/camera shake.
        """
        try:
            flow = cv2.calcOpticalFlowFarneback(
                mov_gray, ref_gray, None,
                pyr_scale=0.5, levels=3, winsize=21,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0
            )
            h, w = ref_gray.shape
            grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
            map_x = (grid_x + flow[..., 0]).astype(np.float32)
            map_y = (grid_y + flow[..., 1]).astype(np.float32)
            warped = cv2.remap(mov_gray, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            return warped
        except Exception as e:
            self.logger.error(f"Error in alignment: {e}")
            return mov_gray

    def detect_dirt_mask(self, prev_g: np.ndarray, curr_g: np.ndarray, next_g: np.ndarray,
                        diff_thresh: int = 25,
                        thin_line_boost: bool = True,
                        protect_edges: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create dirt/scratches mask for curr using temporal discrepancy.
        """
        try:
            # Temporal median is a robust guess of what is real content
            median = np.median(np.stack([prev_g, curr_g, next_g], axis=0), axis=0).astype(np.uint8)

            # Difference of current frame from "real content"
            diff = cv2.absdiff(curr_g, median)

            # Initial mask by threshold
            _, mask = cv2.threshold(diff, diff_thresh, 255, cv2.THRESH_BINARY)

            # Optional: reinforce thin lines (scratches)
            if thin_line_boost:
                # Enhance thin linear structures
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9))
                tophat = cv2.morphologyEx(curr_g, cv2.MORPH_TOPHAT, kernel)
                _, m2 = cv2.threshold(tophat, 18, 255, cv2.THRESH_BINARY)
                mask = cv2.bitwise_or(mask, m2)

            # Cleanup: remove small noise and close holes
            mask = cv2.medianBlur(mask, 3)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
            mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, np.ones((3, 3), np.uint8), iterations=1)

            # Extra protection: don't touch strong edges (lots of detail) to avoid erasing face/text
            if protect_edges:
                edges = cv2.Canny(curr_g, 80, 160)
                # Dilate edges to create a protection zone
                edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
                # Remove these regions from dirt mask
                mask = cv2.bitwise_and(mask, cv2.bitwise_not(edges))

            return mask, median

        except Exception as e:
            self.logger.error(f"Error detecting dirt mask: {e}")
            # Return empty mask on error
            return np.zeros_like(curr_g), curr_g

    def temporal_repair(self, prev: np.ndarray, curr: np.ndarray, next: np.ndarray,
                       diff_thresh: int = 25,
                       use_alignment: bool = True,
                       inpaint_if_needed: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        Repair curr using prev/next and temporal mask.
        - First tries temporal replacement (median).
        - If large scratch remains, does inpainting only on what's left.
        """
        try:
            # Preserve color if it exists
            is_color = (curr.ndim == 3)
            prev_g, curr_g, next_g = map(self.to_gray, (prev, curr, next))

            if use_alignment:
                # Align prev/next to curr (for movement)
                prev_al = self.align_to(curr_g, prev_g)
                next_al = self.align_to(curr_g, next_g)
            else:
                prev_al, next_al = prev_g, next_g

            mask, median = self.detect_dirt_mask(prev_al, curr_g, next_al, diff_thresh=diff_thresh)

            # 1) Direct temporal repair: replace masked pixels with temporal median
            repaired_g = curr_g.copy()
            repaired_g[mask > 0] = median[mask > 0]

            if not inpaint_if_needed:
                if is_color:
                    # Apply same mask for each channel (repair via median in each channel)
                    prev_c = prev.copy()
                    next_c = next.copy()
                    if use_alignment:
                        # Align in each channel using gray warp would be better,
                        # but to simplify, we just apply repair via median without alignment in color.
                        pass
                    median_c = np.median(np.stack([prev_c, curr, next_c], axis=0), axis=0).astype(np.uint8)
                    out = curr.copy()
                    out[mask > 0] = median_c[mask > 0]
                    return out, mask
                return repaired_g, mask

            # 2) If mask caught large lines, there might still be "scar".
            # Inpainting only where was touched (very conservative).
            inpaint_radius = 3
            repaired2_g = cv2.inpaint(repaired_g, mask, inpaint_radius, cv2.INPAINT_TELEA)

            if not is_color:
                return repaired2_g, mask

            # For color: do repair by channel using same mask + inpaint by channel
            out = curr.copy()
            for ch in range(3):
                ch_img = out[..., ch]
                # Temporal replacement by channel
                median_c = np.median(np.stack([prev[..., ch], curr[..., ch], next[..., ch]], axis=0), axis=0).astype(np.uint8)
                ch_img2 = ch_img.copy()
                ch_img2[mask > 0] = median_c[mask > 0]
                # Inpaint by channel (soft)
                ch_img2 = cv2.inpaint(ch_img2, mask, inpaint_radius, cv2.INPAINT_TELEA)
                out[..., ch] = ch_img2

            return out, mask

        except Exception as e:
            self.logger.error(f"Error in temporal repair: {e}")
            return curr, np.zeros_like(curr[:, :, 0] if curr.ndim == 3 else curr)

    def generate_mask_for_frame(self, frame_path: str, prev_frame_path: str, next_frame_path: str,
                               output_mask_path: str,
                               diff_thresh: int = 25,
                               thin_line_boost: bool = True,
                               protect_edges: bool = True) -> bool:
        """
        Generate dirt mask for a specific frame
        """
        try:
            # Load frames
            curr = cv2.imread(frame_path)
            prev = cv2.imread(prev_frame_path)
            next_frame = cv2.imread(next_frame_path)

            if curr is None:
                self.logger.error(f"Could not load current frame: {frame_path}")
                return False

            # Use current frame for missing neighbors
            if prev is None:
                prev = curr.copy()
            if next_frame is None:
                next_frame = curr.copy()

            # Generate mask
            mask, _ = self.detect_dirt_mask(
                self.to_gray(prev),
                self.to_gray(curr),
                self.to_gray(next_frame),
                diff_thresh=diff_thresh,
                thin_line_boost=thin_line_boost,
                protect_edges=protect_edges
            )

            # Save mask
            cv2.imwrite(output_mask_path, mask)

            self.logger.info(f"Mask generated for {os.path.basename(frame_path)} -> {os.path.basename(output_mask_path)}")
            return True

        except Exception as e:
            self.logger.error(f"Error generating mask for {frame_path}: {e}")
            return False

    def generate_mask_for_project(self, project_path: str, frames_dir: str = "frames",
                                 diff_thresh: int = 25,
                                 thin_line_boost: bool = True,
                                 protect_edges: bool = True,
                                 masks_dir: str = "masks") -> bool:
        """
        Generate masks for all frames in a project
        """
        try:
            frames_path = frames_dir if os.path.isabs(frames_dir) else os.path.join(project_path, frames_dir)
            masks_path = masks_dir if os.path.isabs(masks_dir) else os.path.join(project_path, masks_dir)

            # Create masks directory
            os.makedirs(masks_path, exist_ok=True)

            # Get all frame files
            frame_files = sorted([f for f in os.listdir(frames_path) if f.endswith(('.jpg', '.jpeg', '.png'))])

            if len(frame_files) < 3:
                self.logger.warning(f"Not enough frames for mask generation (found {len(frame_files)})")
                return False

            self.logger.info(f"Generating masks for {len(frame_files)} frames...")

            success_count = 0
            for i, frame_file in enumerate(frame_files):
                # Get neighboring frames
                prev_frame = frame_files[max(0, i-1)]
                curr_frame = frame_file
                next_frame = frame_files[min(len(frame_files)-1, i+1)]

                # Paths
                prev_path = os.path.join(frames_path, prev_frame)
                curr_path = os.path.join(frames_path, curr_frame)
                next_path = os.path.join(frames_path, next_frame)

                # Output mask path
                mask_name = f"mask_{curr_frame}"
                mask_path = os.path.join(masks_path, mask_name)

                # Generate mask
                if self.generate_mask_for_frame(
                    curr_path, prev_path, next_path, mask_path,
                    diff_thresh, thin_line_boost, protect_edges
                ):
                    success_count += 1

            self.logger.info(f"Generated {success_count}/{len(frame_files)} masks successfully")
            return success_count > 0

        except Exception as e:
            self.logger.error(f"Error generating masks for project: {e}")
            return False

    def apply_mask_to_frame(self, frame_path: str, mask_path: str, output_path: str,
                          overlay_color: Tuple[int, int, int] = (255, 0, 0),
                          alpha: float = 0.3) -> bool:
        """
        Apply mask overlay to frame for visualization
        """
        try:
            # Load frame and mask
            frame = cv2.imread(frame_path)
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

            if frame is None or mask is None:
                self.logger.error(f"Could not load frame or mask: {frame_path}, {mask_path}")
                return False

            # Create colored overlay
            overlay = np.zeros_like(frame)
            overlay[mask > 0] = overlay_color

            # Blend with original frame
            result = cv2.addWeighted(frame, 1.0, overlay, alpha, 0)

            # Save result
            cv2.imwrite(output_path, result)

            self.logger.info(f"Mask applied to {os.path.basename(frame_path)} -> {os.path.basename(output_path)}")
            return True

        except Exception as e:
            self.logger.error(f"Error applying mask to frame: {e}")
            return False
