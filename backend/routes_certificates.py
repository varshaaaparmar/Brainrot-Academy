from io import BytesIO
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import Response
from auth import get_current_user
from models import gen_id

router = APIRouter(prefix="/api", tags=["certificates"])


def _render_certificate_pdf(student_name: str, course_title: str, instructor_name: str, issued_at: datetime) -> bytes:
    """Render a simple, clean certificate of completion as a PDF."""
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    width, height = landscape(A4)

    ink = HexColor("#0A0A0A")
    accent = HexColor("#FF2E00")

    # Border
    c.setStrokeColor(ink)
    c.setLineWidth(3)
    c.rect(24, 24, width - 48, height - 48)
    c.setLineWidth(1)
    c.rect(34, 34, width - 68, height - 68)

    # Brand
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 80, "BRAINROT ACADEMY")

    # Title
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 140, "Certificate of Completion")

    # Body copy
    c.setFillColor(ink)
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 190, "This certifies that")

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 230, student_name)

    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 268, "has successfully completed the course")

    # wrap long course titles roughly by shrinking font if needed
    title_font_size = 20
    while c.stringWidth(course_title, "Helvetica-Bold", title_font_size) > width - 160 and title_font_size > 12:
        title_font_size -= 1
    c.setFont("Helvetica-Bold", title_font_size)
    c.drawCentredString(width / 2, height - 300, course_title)

    # Footer: date + instructor
    c.setFont("Helvetica", 11)
    c.drawString(70, 70, f"Issued on {issued_at.strftime('%B %d, %Y')}")
    c.drawRightString(width - 70, 70, f"Instructor: {instructor_name}" if instructor_name else "")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


async def _ensure_certificate(db, user: dict, course: dict) -> dict:
    """Create the certificate if it doesn't exist yet. Idempotent — safe to call every time a course is completed."""
    existing = await db.certificates.find_one(
        {"user_id": user["user_id"], "course_id": course["course_id"]}, {"_id": 0}
    )
    if existing:
        return existing

    cert = {
        "certificate_id": gen_id("cert"),
        "user_id": user["user_id"],
        "course_id": course["course_id"],
        "course_title": course["title"],
        "student_name": user["name"],
        "instructor_name": course.get("instructor_name", ""),
        "issued_at": datetime.now(timezone.utc),
    }
    try:
        await db.certificates.insert_one(cert)
    except Exception:
        # unique index on (user_id, course_id) — another request already created it
        existing = await db.certificates.find_one(
            {"user_id": user["user_id"], "course_id": course["course_id"]}, {"_id": 0}
        )
        if existing:
            return existing
        raise
    cert.pop("_id", None)

    await db.notifications.insert_one({
        "id": gen_id("notif"),
        "user_id": user["user_id"],
        "type": "certificate",
        "message": f"Your certificate for \"{course['title']}\" is ready!",
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })
    return cert


@router.post("/certificates/{course_id}/generate")
async def generate_certificate(course_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db

    enr = await db.enrollments.find_one({"user_id": user["user_id"], "course_id": course_id})
    if not enr:
        raise HTTPException(400, "You are not enrolled in this course")
    if enr.get("progress", 0) < 1.0:
        raise HTTPException(400, "Complete all lessons in this course before generating a certificate")

    course = await db.courses.find_one({"course_id": course_id})
    if not course:
        raise HTTPException(404, "Course not found")

    return await _ensure_certificate(db, user, course)


@router.get("/my/certificates")
async def my_certificates(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    items = await db.certificates.find({"user_id": user["user_id"]}, {"_id": 0}).sort("issued_at", -1).to_list(200)
    return items


@router.get("/certificates/{certificate_id}/download")
async def download_certificate(certificate_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    cert = await db.certificates.find_one({"certificate_id": certificate_id, "user_id": user["user_id"]}, {"_id": 0})
    if not cert:
        raise HTTPException(404, "Certificate not found")

    pdf_bytes = _render_certificate_pdf(
        student_name=cert["student_name"],
        course_title=cert["course_title"],
        instructor_name=cert.get("instructor_name", ""),
        issued_at=cert["issued_at"],
    )
    filename = f"certificate-{cert['course_title'].replace(' ', '-').lower()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )