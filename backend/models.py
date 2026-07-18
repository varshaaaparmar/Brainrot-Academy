from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
import uuid


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------- Users ----------
class UserPublic(BaseModel):
    user_id: str
    email: str
    name: str
    role: str  # student | instructor | admin
    bio: Optional[str] = ""
    avatar_url: Optional[str] = ""
    created_at: datetime


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str
    role: str = "student"  # student or instructor


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ---------- Mentors (AI Heroes) ----------
class Mentor(BaseModel):
    mentor_id: str
    name: str
    persona: str  # short tag e.g., "Cricket Coach"
    tagline: str
    style_prompt: str  # system prompt
    avatar_url: str
    accent: str  # color hex


# ---------- Courses & Lessons ----------
class LessonIn(BaseModel):
    title: str
    content: str
    duration_min: int = 10


class Lesson(BaseModel):
    lesson_id: str
    title: str
    content: str
    duration_min: int
    order: int


class CourseIn(BaseModel):
    title: str
    description: str
    category: str
    level: str = "Beginner"  # Beginner | Intermediate | Advanced
    cover_url: Optional[str] = ""
    mentor_id: Optional[str] = ""
    lessons: List[LessonIn] = Field(default_factory=list)


class Course(BaseModel):
    course_id: str
    title: str
    description: str
    category: str
    level: str
    cover_url: str
    mentor_id: str
    instructor_id: str
    instructor_name: str
    lessons: List[Lesson] = Field(default_factory=list)
    enrolled_count: int = 0
    rating: float = 4.7
    created_at: datetime


class Enrollment(BaseModel):
    enrollment_id: str
    user_id: str
    course_id: str
    progress: float = 0.0  # 0..1
    completed_lessons: List[str] = Field(default_factory=list)
    enrolled_at: datetime


# ---------- Certificates ----------
class Certificate(BaseModel):
    certificate_id: str
    user_id: str
    course_id: str
    course_title: str
    student_name: str
    instructor_name: str
    issued_at: datetime


# ---------- Explore (slangs + memes) ----------
class ExplorePostIn(BaseModel):
    kind: str  # \"slang\" | \"meme\"
    title: str
    body: Optional[str] = ""  # slang definition or meme caption
    image_data_url: Optional[str] = ""  # base64 data URL for memes
    tags: List[str] = Field(default_factory=list)


class ExplorePost(BaseModel):
    post_id: str
    kind: str
    title: str
    body: str
    image_data_url: str
    tags: List[str] = Field(default_factory=list)
    author_id: str
    author_name: str
    likes: List[str] = Field(default_factory=list)  # user_ids
    comments: List[dict] = Field(default_factory=list)
    created_at: datetime


class CommentIn(BaseModel):
    text: str


# ---------- Mentor chat ----------
class MentorAskIn(BaseModel):
    mentor_id: str
    course_id: Optional[str] = ""
    lesson_id: Optional[str] = ""
    question: str