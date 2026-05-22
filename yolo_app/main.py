from __future__ import annotations

import os
import sys

# Some conda-packaged OpenCV builds use the Qt backend but do not bundle fonts.
# Point Qt to a common system font directory before importing cv2 to suppress warnings.
os.environ.setdefault("QT_QPA_FONTDIR", "/usr/share/fonts/truetype/dejavu")

import cv2

try:
    from annotator import Annotator
    from command_receiver import CommandReceiver
    from config import load_config
    from frame_hub import FrameHub
    from mjpeg_server import MjpegServer
    from target_manager import TargetManager, build_scene_detections
    from tracker_runner import TrackerRunner
    from udp_publisher import UdpPublisher
    from utils import ensure_parent_dir
    from video_source import VideoSource
except ImportError:
    from yolo_app.annotator import Annotator
    from yolo_app.command_receiver import CommandReceiver
    from yolo_app.config import load_config
    from yolo_app.frame_hub import FrameHub
    from yolo_app.mjpeg_server import MjpegServer
    from yolo_app.target_manager import TargetManager, build_scene_detections
    from yolo_app.tracker_runner import TrackerRunner
    from yolo_app.udp_publisher import UdpPublisher
    from yolo_app.utils import ensure_parent_dir
    from yolo_app.video_source import VideoSource


def build_video_writer(save_path: str, fps: float, width: int, height: int) -> cv2.VideoWriter:
    ensure_parent_dir(save_path)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    return cv2.VideoWriter(save_path, fourcc, fps if fps > 0 else 30.0, (width, height))


def main() -> int:
    cfg = load_config()
    frame_hub = FrameHub(
        quality=cfg.mjpeg_quality,
        max_fps=cfg.mjpeg_max_fps,
        max_width=cfg.mjpeg_max_width,
    )
    mjpeg_server = MjpegServer(
        frame_hub,
        host=cfg.mjpeg_host,
        port=cfg.mjpeg_port,
        path=cfg.mjpeg_path,
    ) if cfg.mjpeg_enabled else None
    if mjpeg_server is not None:
        mjpeg_server.start()

    video_source = None
    udp_publisher = None
    command_receiver = None
    writer = None

    try:
        video_source = VideoSource(cfg.source)
        tracker = TrackerRunner(cfg)
        target_manager = TargetManager(cfg)
        udp_publisher = UdpPublisher(cfg.udp_ip, cfg.udp_port)
        command_receiver = CommandReceiver(cfg.command_ip, cfg.command_port, enabled=cfg.command_enabled)
        annotator = Annotator(cfg)
        while True:
            packet = video_source.read()
            if packet is None:
                break

            frame = packet.frame
            image_height, image_width = frame.shape[:2]

            tracks = tracker.run(frame)
            commands = command_receiver.poll()
            for command in commands:
                target_manager.apply_command(command, tracks)

            current_target = target_manager.update(
                tracks=tracks,
                image_width=image_width,
                image_height=image_height,
                frame_id=packet.frame_id,
                timestamp=packet.timestamp,
            )
            scene = build_scene_detections(
                tracks=tracks,
                image_width=image_width,
                image_height=image_height,
                frame_id=packet.frame_id,
                timestamp=packet.timestamp,
            )
            udp_publisher.publish(current_target, scene)

            if cfg.show or cfg.save_video or cfg.mjpeg_enabled:
                annotated = annotator.annotate(
                    frame=frame,
                    tracks=tracks,
                    current_target=current_target,
                    locked_track_id=target_manager.locked_track_id,
                )
                if cfg.mjpeg_enabled:
                    frame_hub.update_bgr(
                        annotated,
                        frame_id=packet.frame_id,
                        timestamp=packet.timestamp,
                    )
                if cfg.show:
                    cv2.imshow(cfg.window_name, annotated)
                    key = cv2.waitKey(1) & 0xFF
                    if key in {27, ord("q")}:
                        break
                if cfg.save_video:
                    if writer is None:
                        fps = video_source.cap.get(cv2.CAP_PROP_FPS)
                        writer = build_video_writer(cfg.save_path, fps, image_width, image_height)
                    writer.write(annotated)
    finally:
        if video_source is not None:
            video_source.release()
        if udp_publisher is not None:
            udp_publisher.close()
        if command_receiver is not None:
            command_receiver.close()
        if mjpeg_server is not None:
            mjpeg_server.stop()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
