"""Creative service: uploaded creative files and their campaign attachments.

A creative is an uploaded image, video or logo. This service owns the file
metadata, the download, and the attachment and detachment of a creative to a
campaign. It deliberately does not own the campaign itself: attaching a
creative only records a link, and the campaign service stays the authority on
whether that link is allowed.
"""

from app.core import settings
from app.creatives.routes import (
    ALLOWED_TYPES,
    AttachRequest,
    CreativeResponse,
    CreativeType,
    init_creative_db,
    router,
)

__all__ = [
    "settings",
    "ALLOWED_TYPES",
    "AttachRequest",
    "CreativeResponse",
    "CreativeType",
    "init_creative_db",
    "router",
]
