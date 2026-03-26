"""
Announcement endpoints for the High School Management System API
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    """Request payload for creating or updating announcements."""

    message: str = Field(min_length=1, max_length=500)
    start_date: Optional[date] = None
    expiration_date: date

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message is required")
        return cleaned

    @field_validator("expiration_date")
    @classmethod
    def validate_expiration_date(cls, value: date) -> date:
        if value is None:
            raise ValueError("Expiration date is required")
        return value


def require_signed_in_user(teacher_username: Optional[str]) -> Dict[str, Any]:
    """Validate that the requester is a signed-in teacher/admin."""
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def serialize_announcement(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document into JSON-serializable API response."""
    return {
        "id": str(document["_id"]),
        "message": document["message"],
        "start_date": document.get("start_date"),
        "expiration_date": document["expiration_date"],
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at")
    }



@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all currently active announcements ordered by expiration date."""
    today_iso = date.today().isoformat()
    announcements = announcements_collection.find().sort(
        [("expiration_date", 1), ("start_date", 1), ("created_at", -1)]
    )
    return [
        serialize_announcement(announcement)
    active_filter = {
        "$and": [
            {"expiration_date": {"$gte": today_iso}},
            {
                "$or": [
                    {"start_date": {"$exists": False}},
                    {"start_date": {"$lte": today_iso}},
                ]
            },
        ]
    }
    announcements = announcements_collection.find(active_filter).sort(
        [("expiration_date", 1), ("start_date", 1), ("created_at", -1)]
    )
    return [serialize_announcement(announcement) for announcement in announcements]
) -> List[Dict[str, Any]]:
    """Get all announcements for management by authenticated staff."""
    require_signed_in_user(teacher_username)
    announcements = announcements_collection.find().sort(
        [("expiration_date", 1), ("start_date", 1), ("created_at", -1)]
    )
    return [serialize_announcement(announcement) for announcement in announcements]


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement for authenticated staff."""
    require_signed_in_user(teacher_username)

    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date must be on or before expiration date")

    timestamp = datetime.now(timezone.utc).isoformat()
    announcement = {
        "_id": uuid4().hex,
        "message": payload.message,
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "expiration_date": payload.expiration_date.isoformat(),
        "created_at": timestamp,
        "updated_at": timestamp
    }
    announcements_collection.insert_one(announcement)
    return serialize_announcement(announcement)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement for authenticated staff."""
    require_signed_in_user(teacher_username)

    if payload.start_date and payload.start_date > payload.expiration_date:
        raise HTTPException(status_code=400, detail="Start date must be on or before expiration date")

    existing_announcement = announcements_collection.find_one({"_id": announcement_id})
    if not existing_announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated_fields = {
        "message": payload.message,
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "expiration_date": payload.expiration_date.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    announcements_collection.update_one(
        {"_id": announcement_id},
        {"$set": updated_fields}
    )

    existing_announcement.update(updated_fields)
    return serialize_announcement(existing_announcement)


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement for authenticated staff."""
    require_signed_in_user(teacher_username)

    result = announcements_collection.delete_one({"_id": announcement_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}