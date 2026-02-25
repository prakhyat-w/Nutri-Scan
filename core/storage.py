"""
Supabase Storage helper.

Uploads a meal photo (bytes) to the configured Supabase bucket and
returns the public URL.  Falls back gracefully when Supabase env vars
are not configured (e.g. local dev without a Supabase project).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Return an initialised Supabase client or None if not configured."""
    url = getattr(settings, "SUPABASE_URL", "")
    key = getattr(settings, "SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    from supabase import create_client  # type: ignore

    return create_client(url, key)


def upload_meal_photo(file_bytes: bytes, original_filename: str, user_id: int) -> Optional[str]:
    """Upload image bytes to Supabase Storage.

    File is stored at ``<user_id>/<uuid>.<ext>`` so each user's photos
    are in their own "folder" and filenames never collide.

    Returns:
        Public URL string on success, or ``None`` if Supabase is not
        configured / the upload fails.
    """
    client = _get_client()
    if client is None:
        logger.warning(
            "Supabase not configured — meal photo will not be stored remotely."
        )
        return None

    bucket = getattr(settings, "SUPABASE_BUCKET", "meal-photos")

    # Build a collision-free storage path
    ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "jpg"
    storage_path = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    try:
        client.storage.from_(bucket).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": f"image/{ext}", "upsert": "false"},
        )
        public_url: str = client.storage.from_(bucket).get_public_url(storage_path)
        logger.info("Uploaded meal photo to Supabase: %s", public_url)
        return public_url
    except Exception as exc:  # noqa: BLE001
        logger.error("Supabase upload failed: %s", exc)
        return None
