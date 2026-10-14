"""
Nexora API - Course Catalog Pydantic Schemas
Strictly validated request and response models for Stage 8 Course Catalog operations.
Adheres strictly to the authoritative live database columns in Supabase.
"""

from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict, Field


class CourseListItem(BaseModel):
    """
    Public course representation for catalog listing cards.
    Contains verified live database columns.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    description: str
    instructor: str
    category: str = "General"
    level: str = "Beginner"
    duration: str = "4 weeks"
    thumbnail: Optional[str] = "📚"
    total_lessons: int = 10
    rating: float = 4.5
    price: int = 0
    points_price: int = 0
    created_at: Optional[Union[str, datetime]] = None


class CourseDetailResponse(BaseModel):
    """
    Public course detail representation.
    Contains verified live database columns.
    Never exposes passwords, tokens, or private credentials.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    description: str
    instructor: str
    category: str = "General"
    level: str = "Beginner"
    duration: str = "4 weeks"
    thumbnail: Optional[str] = "📚"
    total_lessons: int = 10
    rating: float = 4.5
    price: int = 0
    points_price: int = 0
    created_by: Optional[int] = None
    created_at: Optional[Union[str, datetime]] = None


class CourseListResponse(BaseModel):
    """
    Standard deterministic envelope for listing courses.
    """
    model_config = ConfigDict(extra="ignore")

    courses: List[CourseListItem]
    total: int
