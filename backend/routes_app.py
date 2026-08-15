import os
import logging
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional
from auth import get_current_user
from routes_certificates import _ensure_certificate
from models import (
    CourseIn,
    gen_id,
    ExplorePostIn,
    CommentIn,
    MentorAskIn,
    MentorNarrateIn,
)

router = APIRouter(prefix="/api", tags=["app"])


# ---------- Mentors ----------
@router.get("/mentors")
async def list_mentors(request: Request):
    db = request.app.state.db
    items = await db.mentors.find({}, {"_id": 0}).to_list(100)
    return items


# ---------- Courses ----------
@router.get("/courses")
async def list_courses(request: Request, category: Optional[str] = None, q: Optional[str] = None):
    db = request.app.state.db
    flt = {}
    if category and category != "All":
        flt["category"] = category
    if q:
        flt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    items = await db.courses.find(flt, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@router.get("/courses/{course_id}")
async def get_course(course_id: str, request: Request):
    db = request.app.state.db
    course = await db.courses.find_one({"course_id": course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    return course


@router.post("/courses")
async def create_course(payload: CourseIn, request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(403, "Only instructors can create courses")
    db = request.app.state.db
    lessons = []
    for idx, l in enumerate(payload.lessons):
        lessons.append({
            "lesson_id": gen_id("lesson"),
            "title": l.title,
            "content": l.content,
            "duration_min": l.duration_min,
            "video_url": l.video_url or "",
            "order": idx,
        })
    doc = {
        "course_id": gen_id("course"),
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "level": payload.level,
        "cover_url": payload.cover_url or "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=800&q=80",
        "mentor_id": payload.mentor_id or "mentor_coach_rohan",
        "instructor_id": user["user_id"],
        "instructor_name": user["name"],
        "lessons": lessons,
        "enrolled_count": 0,
        "rating": 4.7,
        "created_at": datetime.now(timezone.utc),
    }
    await db.courses.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/courses/{course_id}")
async def update_course(course_id: str, payload: CourseIn, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(404, "Course not found")
    if user["role"] != "admin" and course["instructor_id"] != user["user_id"]:
        raise HTTPException(403, "Not your course")
    lessons = []
    for idx, l in enumerate(payload.lessons):
        lessons.append({
            "lesson_id": l.lesson_id or gen_id("lesson"),
            "title": l.title,
            "content": l.content,
            "duration_min": l.duration_min,
            "video_url": l.video_url or "",
            "order": idx,
        })
    update = {
        "title": payload.title,
        "description": payload.description,
        "category": payload.category,
        "level": payload.level,
        "cover_url": payload.cover_url or course.get("cover_url", ""),
        "mentor_id": payload.mentor_id or course.get("mentor_id", ""),
        "lessons": lessons,
    }
    await db.courses.update_one({"course_id": course_id}, {"$set": update})
    updated = await db.courses.find_one({"course_id": course_id}, {"_id": 0})
    return updated


@router.delete("/courses/{course_id}")
async def delete_course(course_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(404, "Course not found")
    if user["role"] != "admin" and course["instructor_id"] != user["user_id"]:
        raise HTTPException(403, "Not your course")
    await db.courses.delete_one({"course_id": course_id})
    await db.enrollments.delete_many({"course_id": course_id})
    return {"ok": True}


@router.get("/instructor/courses")
async def instructor_courses(request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(403, "Instructors only")
    db = request.app.state.db
    items = await db.courses.find({"instructor_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


# ---------- Enrollment ----------
@router.post("/enroll/{course_id}")
async def enroll(course_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(404, "Course not found")
    existing = await db.enrollments.find_one({"user_id": user["user_id"], "course_id": course_id})
    if existing:
        existing.pop("_id", None)
        return existing
    doc = {
        "enrollment_id": gen_id("enr"),
        "user_id": user["user_id"],
        "course_id": course_id,
        "progress": 0.0,
        "completed_lessons": [],
        "enrolled_at": datetime.now(timezone.utc),
    }
    await db.enrollments.insert_one(doc)
    await db.courses.update_one({"course_id": course_id}, {"$inc": {"enrolled_count": 1}})
    await db.notifications.insert_one({
        "id": gen_id("notif"),
        "user_id": user["user_id"],
        "type": "enrollment",
        "message": f"You enrolled in {course.get('title', 'a course')}.",
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })
    doc.pop("_id", None)
    return doc


@router.post("/enroll/{course_id}/lesson/{lesson_id}/complete")
async def complete_lesson(course_id: str, lesson_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    enr = await db.enrollments.find_one({"user_id": user["user_id"], "course_id": course_id})
    if not enr:
        raise HTTPException(400, "Not enrolled")
    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(404, "Course not found")
    completed = set(enr.get("completed_lessons", []))
    completed.add(lesson_id)
    total = max(1, len(course.get("lessons", [])))
    progress = round(len(completed) / total, 3)
    await db.enrollments.update_one(
        {"enrollment_id": enr["enrollment_id"]},
        {"$set": {"completed_lessons": list(completed), "progress": progress}},
    )
    await db.notifications.insert_one({
        "id": gen_id("notif"),
        "user_id": user["user_id"],
        "type": "completion",
        "message": "Lesson completed. Keep going!",
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })

    certificate = None
    if progress >= 1.0:
        certificate = await _ensure_certificate(db, user, course)

    return {"progress": progress, "completed_lessons": list(completed), "certificate": certificate}


@router.get("/my/enrollments")
async def my_enrollments(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    enrs = await db.enrollments.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    course_ids = [e["course_id"] for e in enrs]
    courses = await db.courses.find({"course_id": {"$in": course_ids}}, {"_id": 0}).to_list(200)
    cmap = {c["course_id"]: c for c in courses}
    out = []
    for e in enrs:
        c = cmap.get(e["course_id"])
        if c:
            out.append({"enrollment": e, "course": c})
    return out


# ---------- Analytics ----------
@router.get("/analytics/student")
async def student_analytics(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    enrs = await db.enrollments.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(200)
    total = len(enrs)
    in_progress = sum(1 for e in enrs if 0 < e.get("progress", 0) < 1)
    completed = sum(1 for e in enrs if e.get("progress", 0) >= 1)
    total_lessons = sum(len(e.get("completed_lessons", [])) for e in enrs)
    avg_progress = round(sum(e.get("progress", 0) for e in enrs) / total, 2) if total else 0
    # By category
    course_ids = [e["course_id"] for e in enrs]
    courses = await db.courses.find({"course_id": {"$in": course_ids}}, {"_id": 0}).to_list(200)
    by_cat = {}
    for c in courses:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    return {
        "total_courses": total,
        "in_progress": in_progress,
        "completed": completed,
        "lessons_completed": total_lessons,
        "avg_progress": avg_progress,
        "by_category": [{"category": k, "count": v} for k, v in by_cat.items()],
    }


@router.get("/analytics/instructor")
async def instructor_analytics(request: Request, user: dict = Depends(get_current_user)):
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(403, "Instructors only")
    db = request.app.state.db
    courses = await db.courses.find({"instructor_id": user["user_id"]}, {"_id": 0}).to_list(200)
    total_courses = len(courses)
    total_enrolled = sum(c.get("enrolled_count", 0) for c in courses)
    avg_rating = round(sum(c.get("rating", 0) for c in courses) / total_courses, 2) if total_courses else 0
    by_course = [{"title": c["title"], "enrolled": c.get("enrolled_count", 0)} for c in courses]
    return {
        "total_courses": total_courses,
        "total_enrolled": total_enrolled,
        "avg_rating": avg_rating,
        "by_course": by_course,
    }


# ---------- Explore ----------
@router.get("/explore")
async def list_posts(request: Request, kind: Optional[str] = None):
    db = request.app.state.db
    flt = {}
    if kind in ("slang", "meme"):
        flt["kind"] = kind
    items = await db.explore_posts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(200)
    return items


@router.post("/explore")
async def create_post(payload: ExplorePostIn, request: Request, user: dict = Depends(get_current_user)):
    if payload.kind not in ("slang", "meme"):
        raise HTTPException(400, "kind must be slang or meme")
    db = request.app.state.db
    doc = {
        "post_id": gen_id("post"),
        "kind": payload.kind,
        "title": payload.title.strip(),
        "body": (payload.body or "").strip(),
        "image_data_url": payload.image_data_url or "",
        "tags": payload.tags,
        "author_id": user["user_id"],
        "author_name": user["name"],
        "likes": [],
        "comments": [],
        "created_at": datetime.now(timezone.utc),
    }
    await db.explore_posts.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/explore/{post_id}/like")
async def like_post(post_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    post = await db.explore_posts.find_one({"post_id": post_id})
    if not post:
        raise HTTPException(404, "Post not found")
    likes = set(post.get("likes", []))
    if user["user_id"] in likes:
        likes.remove(user["user_id"])
    else:
        likes.add(user["user_id"])
    await db.explore_posts.update_one({"post_id": post_id}, {"$set": {"likes": list(likes)}})
    return {"likes": list(likes), "liked": user["user_id"] in likes}


@router.post("/explore/{post_id}/comment")
async def comment_post(post_id: str, payload: CommentIn, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    post = await db.explore_posts.find_one({"post_id": post_id})
    if not post:
        raise HTTPException(404, "Post not found")
    comment = {
        "comment_id": gen_id("c"),
        "author_id": user["user_id"],
        "author_name": user["name"],
        "text": payload.text.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.explore_posts.update_one({"post_id": post_id}, {"$push": {"comments": comment}})
    return comment


# ---------- Notifications ----------
@router.get("/notifications")
async def list_notifications(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    items = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return items


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


@router.patch("/notifications/read-all")
async def mark_all_notifications_read(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    await db.notifications.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    result = await db.notifications.delete_one({"id": notification_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


@router.post("/mentor/ask")
async def mentor_ask(payload: MentorAskIn, request: Request, user: dict = Depends(get_current_user)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(503, "Mentor chat is not configured. Set GEMINI_API_KEY to enable this feature.")

    db = request.app.state.db
    mentor = await db.mentors.find_one({"mentor_id": payload.mentor_id}, {"_id": 0})
    if not mentor:
        raise HTTPException(404, "Mentor not found")

    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty")
    if len(question) > 1000:
        raise HTTPException(400, "Question is too long (max 1000 characters)")

    # Pull in lesson context if the student asked from within a specific lesson
    context = ""
    if payload.course_id and payload.lesson_id:
        course = await db.courses.find_one({"course_id": payload.course_id}, {"_id": 0})
        if course:
            lesson = next((l for l in course.get("lessons", []) if l["lesson_id"] == payload.lesson_id), None)
            if lesson:
                context = (
                    f"\n\nThe student is currently on the lesson \"{lesson['title']}\" "
                    f"in the course \"{course['title']}\". Lesson content for context:\n{lesson['content'][:1500]}"
                )

    model = os.environ.get("MENTOR_MODEL", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                params={"key": api_key},
                json={
                    "system_instruction": {"parts": [{"text": mentor["style_prompt"] + context}]},
                    "contents": [{"role": "user", "parts": [{"text": question}]}],
                    "generationConfig": {
                        "maxOutputTokens": 800,
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                },
            )
        if resp.status_code != 200:
            logging.getLogger("learnhero").error(f"Gemini API error in mentor_ask: {resp.status_code} {resp.text}")
            raise HTTPException(502, "Mentor is temporarily unavailable. Try again in a moment.")

        data = resp.json()
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"] if candidates else []
        reply_text = "".join(p.get("text", "") for p in parts).strip()
        finish_reason = candidates[0].get("finishReason") if candidates else None
        if finish_reason == "MAX_TOKENS":
            logging.getLogger("learnhero").warning("mentor_ask reply hit MAX_TOKENS and may be truncated")
        if not reply_text:
            raise HTTPException(502, "Mentor didn't return a response. Try again.")
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("learnhero").error(f"Unexpected error in mentor_ask: {e}")
        raise HTTPException(500, "Something went wrong while asking the mentor.")

    return {"reply": reply_text}


@router.post("/mentor/narrate")
async def mentor_narrate(payload: MentorNarrateIn, request: Request, user: dict = Depends(get_current_user)):
    """Generates a spoken-style teaching script for a lesson, fully in the
    mentor's persona. The frontend reads this aloud with the browser's
    built-in text-to-speech, so it's written for the ear, not the eye:
    no markdown, no bullet points, conversational sentences only."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(503, "Narration is not configured. Set GEMINI_API_KEY to enable this feature.")

    db = request.app.state.db
    mentor = await db.mentors.find_one({"mentor_id": payload.mentor_id}, {"_id": 0})
    if not mentor:
        raise HTTPException(404, "Mentor not found")

    course = await db.courses.find_one({"course_id": payload.course_id}, {"_id": 0})
    if not course:
        raise HTTPException(404, "Course not found")
    lesson = next((l for l in course.get("lessons", []) if l["lesson_id"] == payload.lesson_id), None)
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    lesson_title = lesson.get("title") or "This lesson"
    lesson_content = (lesson.get("content") or "").strip()
    if not lesson_content:
        raise HTTPException(400, "This lesson doesn't have any content yet, so there's nothing for the mentor to teach. Add some lesson content first.")

    prompt = (
        "You are recording a short spoken lesson for a student, fully in character. "
        "Write ONLY the exact words you would say out loud — nothing else. "
        "Do not mention formatting, word count, or instructions. Do not write notes to yourself. "
        "Just speak: start with a brief greeting, then teach the concept below in a warm, "
        "conversational way, in about 150-220 words.\n\n"
        f"Lesson title: {lesson_title}\n"
        f"Lesson content:\n{lesson_content[:2000]}"
    )

    model = os.environ.get("MENTOR_MODEL", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                params={"key": api_key},
                json={
                    "system_instruction": {"parts": [{"text": mentor.get("style_prompt") or "You are a friendly, encouraging tutor."}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 900,
                        "thinkingConfig": {"thinkingBudget": 0},
                    },
                },
            )
        if resp.status_code != 200:
            logging.getLogger("learnhero").error(f"Gemini API error in mentor_narrate: {resp.status_code} {resp.text}")
            raise HTTPException(502, "Mentor is temporarily unavailable. Try again in a moment.")

        data = resp.json()
        candidates = data.get("candidates") or []
        parts = candidates[0]["content"]["parts"] if candidates else []
        script_text = "".join(p.get("text", "") for p in parts).strip()
        finish_reason = candidates[0].get("finishReason") if candidates else None
        if finish_reason == "MAX_TOKENS":
            logging.getLogger("learnhero").warning("mentor_narrate script hit MAX_TOKENS and may be truncated")
        if not script_text:
            raise HTTPException(502, "Mentor didn't return a script. Try again.")
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("learnhero").error(
            f"Unexpected error in mentor_narrate: {type(e).__name__}: {e}", exc_info=True
        )
        raise HTTPException(500, "Something went wrong while preparing the narration.")

    return {"script": script_text}