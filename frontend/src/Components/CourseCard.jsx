import { Link } from "react-router-dom";
import { Clock, Users, Star } from "lucide-react";

export default function CourseCard({ course }) {
  return (
    <Link to={`/courses/${course.course_id}`} data-testid={`course-card-${course.course_id}`} className="block h-full">
      <div className="brutal-card overflow-hidden h-full flex flex-col">
        <div className="aspect-[16/9] w-full overflow-hidden border-b-2 border-black bg-neutral-100 shrink-0">
          {course.cover_url && (
            <img
              src={course.cover_url}
              alt={course.title}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          )}
        </div>
        <div className="p-4 sm:p-5 flex flex-col flex-1">
          <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
            <span className="section-tag">{course.category}</span>
            <span className="font-mono text-xs uppercase tracking-widest text-neutral-500 shrink-0">{course.level}</span>
          </div>
          <h3 className="font-display text-lg sm:text-xl font-bold tracking-tight leading-tight mb-2">{course.title}</h3>
          <p className="text-sm text-neutral-600 line-clamp-2">{course.description}</p>
          <div className="mt-4 pt-1 flex items-center flex-wrap gap-x-4 gap-y-1 text-xs font-mono uppercase tracking-widest text-neutral-700 mt-auto">
            <span className="flex items-center gap-1"><Users size={14} /> {course.enrolled_count}</span>
            <span className="flex items-center gap-1"><Clock size={14} /> {course.lessons.length} lessons</span>
            <span className="flex items-center gap-1"><Star size={14} className="fill-[#FF2E00] text-[#FF2E00]" /> {course.rating}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}