import os
from datetime import datetime, timezone
from auth import hash_password
from models import gen_id


SAMPLE_MENTORS = [
    {
        "mentor_id": "mentor_coach_rohan",
        "name": "Coach Rohan",
        "persona": "Cricket Captain",
        "tagline": "Treat learning like a match. One ball, one concept at a time.",
        "style_prompt": (
            "You are Coach Rohan, a fictional Indian cricket captain turned teacher. "
            "Explain in punchy sports metaphors (overs, boundaries, fielding), keep it confident, "
            "high-energy, encouraging. Use 2-3 short paragraphs."
        ),
        "avatar_url": "https://static.prod-images.emergentagent.com/jobs/1bb0b3f7-2fe1-41c1-a7d6-df7fb9557549/images/e55e399f9ee0be45a67446e94b4d0adb31428b83047cdc714576fdaecf400496.png",
        "accent": "#FF2E00",
    },
    {
        "mentor_id": "mentor_pm_vikram",
        "name": "PM Vikram",
        "persona": "Statesman",
        "tagline": "Vision. Discipline. Daily 1% — that's how nations and minds are built.",
        "style_prompt": (
            "You are PM Vikram, a fictional wise Indian statesman teacher. "
            "Explain with calm authority, civic metaphors (nation building, discipline, vision), "
            "use a memorable closing line. Keep it warm and motivational. 2-3 short paragraphs."
        ),
        "avatar_url": "https://static.prod-images.emergentagent.com/jobs/1bb0b3f7-2fe1-41c1-a7d6-df7fb9557549/images/e2804c46c5138497f0191e2177917e13fafc3a1e4a74205764f197a1e920a9c8.png",
        "accent": "#0047FF",
    },
    {
        "mentor_id": "mentor_dr_neha",
        "name": "Dr. Neha",
        "persona": "Scientist",
        "tagline": "Curiosity is the cheat code. Question everything, prove the basics first.",
        "style_prompt": (
            "You are Dr. Neha, a fictional warm Indian research scientist. "
            "Explain via everyday analogies, first-principles thinking, and a 'try this experiment' suggestion. "
            "Keep it precise and friendly. 2-3 short paragraphs."
        ),
        "avatar_url": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=600&q=80&auto=format&fit=crop",
        "accent": "#00B86B",
    },
]


SAMPLE_SLANGS = [
    {"title": "Rizz", "body": "Charisma; smooth talking, especially while flirting. 'He's got serious rizz.'", "tags": ["genz", "social"]},
    {"title": "Mid", "body": "Average, unimpressive. The worst thing you can call something. 'That movie was so mid.'", "tags": ["genz", "opinion"]},
    {"title": "Delulu", "body": "Delusional, in a fun/affectionate way. 'Delulu is the solulu.'", "tags": ["genz", "vibe"]},
    {"title": "No cap", "body": "No lie; for real. 'That lecture was fire, no cap.'", "tags": ["genz", "honesty"]},
    {"title": "Slay", "body": "To do something extremely well; absolutely crush it. 'You slayed that exam.'", "tags": ["genz", "praise"]},
    {"title": "Bet", "body": "Agreement / 'okay, sure'. Also a confident yes. 'Wanna study at 9?' 'Bet.'", "tags": ["genz", "agree"]},
]


SAMPLE_COURSES = [
    {
        "title": "Python for Absolute Beginners",
        "description": "Start from zero. Variables, loops, functions, real mini-projects. Learn like you're playing your first cricket match.",
        "category": "Programming",
        "level": "Beginner",
        "cover_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&q=80&auto=format&fit=crop",
        "mentor_id": "mentor_coach_rohan",
        "lessons": [
            {"title": "What even is Python?", "content": "Python is a high-level, readable language. Today you'll install it and print your first line.", "duration_min": 8},
            {"title": "Variables & Data Types", "content": "Boxes that hold values: int, float, str, bool. Naming rules and reassignment.", "duration_min": 12},
            {"title": "Control Flow: if/else", "content": "Branching logic. Boolean checks. Indentation matters.", "duration_min": 15},
            {"title": "Loops", "content": "for and while loops. range(). Breaking and continuing.", "duration_min": 14},
            {"title": "Functions", "content": "Define reusable blocks with def. Arguments and return values.", "duration_min": 18},
        ],
    },
    {
        "title": "Data Analytics with Pandas",
        "description": "Inspired by Analytics Vidhya. Real CSVs, real analysis. Series, DataFrame, groupby, merge, plot.",
        "category": "Data Science",
        "level": "Intermediate",
        "cover_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80&auto=format&fit=crop",
        "mentor_id": "mentor_dr_neha",
        "lessons": [
            {"title": "Series & DataFrame", "content": "Core data structures. Reading CSV, head, info, describe.", "duration_min": 15},
            {"title": "Selection & Filtering", "content": "loc, iloc, boolean masks. Cleaning nulls.", "duration_min": 18},
            {"title": "GroupBy & Aggregation", "content": "Split-apply-combine. Common aggs and pivot_table.", "duration_min": 20},
            {"title": "Merging DataFrames", "content": "merge, concat, join. SQL-style joins.", "duration_min": 16},
        ],
    },
    {
        "title": "Public Speaking & Leadership",
        "description": "Speak with vision. Structure ideas, command the room, lead change in your community.",
        "category": "Soft Skills",
        "level": "Beginner",
        "cover_url": "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?w=800&q=80&auto=format&fit=crop",
        "mentor_id": "mentor_pm_vikram",
        "lessons": [
            {"title": "The 3-Beat Speech", "content": "Hook. Story. Call to action. The simplest structure that works.", "duration_min": 12},
            {"title": "Stage Presence", "content": "Posture, pace, pauses. The power of silence.", "duration_min": 14},
            {"title": "Building a Vision", "content": "Big idea, daily 1% action, narrative arc.", "duration_min": 16},
        ],
    },
    {
        "title": "Intro to Machine Learning",
        "description": "Supervised learning, classification vs regression, evaluation metrics, your first scikit-learn model.",
        "category": "Data Science",
        "level": "Intermediate",
        "cover_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80&auto=format&fit=crop",
        "mentor_id": "mentor_dr_neha",
        "lessons": [
            {"title": "What is ML?", "content": "Patterns from data. Supervised vs unsupervised.", "duration_min": 10},
            {"title": "Train/Test Split", "content": "Why we split. sklearn.model_selection.", "duration_min": 12},
            {"title": "Your First Classifier", "content": "Logistic regression on the iris dataset.", "duration_min": 20},
        ],
    },
]


async def seed_database(db):
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token", unique=True)
    await db.courses.create_index("course_id", unique=True)
    await db.mentors.create_index("mentor_id", unique=True)
    await db.enrollments.create_index([("user_id", 1), ("course_id", 1)], unique=True)
    await db.explore_posts.create_index("post_id", unique=True)

    now = datetime.now(timezone.utc)

    # Admin
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    existing_admin = await db.users.find_one({"email": admin_email})
    if not existing_admin:
        await db.users.insert_one({
            "user_id": gen_id("user"),
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "LearnHero Admin",
            "role": "admin",
            "bio": "Platform admin",
            "avatar_url": "",
            "created_at": now,
        })

    # Optional sample instructor
    inst_email = os.environ.get("DEMO_INSTRUCTOR_EMAIL", "instructor@example.com")
    inst_password = os.environ.get("DEMO_INSTRUCTOR_PASSWORD")
    existing_inst = await db.users.find_one({"email": inst_email})
    if not existing_inst and inst_password:
        await db.users.insert_one({
            "user_id": gen_id("user"),
            "email": inst_email,
            "password_hash": hash_password(inst_password),
            "name": "Instructor",
            "role": "instructor",
            "bio": "Senior software engineer & educator",
            "avatar_url": "",
            "created_at": now,
        })
    instructor = await db.users.find_one({"email": inst_email}, {"_id": 0})
    if not instructor:
        instructor = await db.users.find_one({"email": admin_email}, {"_id": 0})

    # Optional sample student
    stu_email = os.environ.get("DEMO_STUDENT_EMAIL", "student@example.com")
    stu_password = os.environ.get("DEMO_STUDENT_PASSWORD")
    if stu_password and not await db.users.find_one({"email": stu_email}):
        await db.users.insert_one({
            "user_id": gen_id("user"),
            "email": stu_email,
            "password_hash": hash_password(stu_password),
            "name": "Varsha Ghanchi",
            "role": "student",
            "bio": "Curious learner",
            "avatar_url": "",
            "created_at": now,
        })

    # Mentors
    for m in SAMPLE_MENTORS:
        await db.mentors.update_one({"mentor_id": m["mentor_id"]}, {"$set": m}, upsert=True)

    # Courses (only insert if no courses exist yet)
    if await db.courses.count_documents({}) == 0:
        for c in SAMPLE_COURSES:
            lessons = []
            for idx, l in enumerate(c["lessons"]):
                lessons.append({
                    "lesson_id": gen_id("lesson"),
                    "title": l["title"],
                    "content": l["content"],
                    "duration_min": l["duration_min"],
                    "order": idx,
                })
            await db.courses.insert_one({
                "course_id": gen_id("course"),
                "title": c["title"],
                "description": c["description"],
                "category": c["category"],
                "level": c["level"],
                "cover_url": c["cover_url"],
                "mentor_id": c["mentor_id"],
                "instructor_id": instructor["user_id"],
                "instructor_name": instructor["name"],
                "lessons": lessons,
                "enrolled_count": 0,
                "rating": 4.7,
                "created_at": now,
            })

    # Slangs
    if await db.explore_posts.count_documents({"kind": "slang"}) == 0:
        admin = await db.users.find_one({"email": admin_email}, {"_id": 0})
        for s in SAMPLE_SLANGS:
            await db.explore_posts.insert_one({
                "post_id": gen_id("post"),
                "kind": "slang",
                "title": s["title"],
                "body": s["body"],
                "image_data_url": "",
                "tags": s["tags"],
                "author_id": admin["user_id"],
                "author_name": admin["name"],
                "likes": [],
                "comments": [],
                "created_at": now,
            })
