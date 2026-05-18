"""Compatibility processors package."""

from .image_processor import process_images
from .video_processor import process_videos
from .pdf_processor import process_documents

__all__ = ["process_images", "process_videos", "process_documents"]
