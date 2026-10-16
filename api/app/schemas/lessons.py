"""
Nexora API - Lesson Pydantic Schemas
Strictly validated request and response models for Stage 10 Learning Foundation.
Conforms strictly to the verified live database boundary with no fabricated fields.
"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class LessonItem(BaseModel):
    """
    Safe public lesson representation for course curriculum lists.
    Contains only safe verified fields.
    """
    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Unique positive lesson ID")
    course_id: int = Field(..., description="Course ID this lesson belongs to")
    title: str = Field(..., min_length=1, max_length=255, description="Lesson title")
    description: Optional[str] = Field(default=None, max_length=2000, description="Optional lesson description")


class LessonDetail(BaseModel):
    """
    Detailed lesson representation for lesson viewing.
    Contains only safe verified fields.
    """
    model_config = ConfigDict(extra="ignore")

    id: int = Field(..., description="Unique positive lesson ID")
    course_id: int = Field(..., description="Course ID this lesson belongs to")
    title: str = Field(..., min_length=1, max_length=255, description="Lesson title")
    description: Optional[str] = Field(default=None, max_length=5000, description="Optional lesson description")


class CourseLessonsResponse(BaseModel):
    """
    Response envelope for course lessons list.
    """
    model_config = ConfigDict(extra="ignore")

    course_id: int = Field(..., description="Target course ID")
    lessons: List[LessonItem] = Field(default_factory=list, description="List of available course lessons")
    total: int = Field(default=0, ge=0, description="Total number of lessons")
