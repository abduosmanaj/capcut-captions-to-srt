#!/usr/bin/env python3
"""
يسحب الكابشنز (النصوص) مع توقيتاتها من مشاريع CapCut ويصدّرها كملفات SRT.

الاستخدام:
    python capcut_captions_to_srt.py
    python capcut_captions_to_srt.py --projects-dir "PATH" --output-dir "PATH"
    python capcut_captions_to_srt.py --project "0812"
"""

import argparse
import json
import platform
import sys
from pathlib import Path

if sys.stdout is not None and (sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr is not None and (sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _default_projects_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Movies" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    # Windows (وأي نظام آخر كافتراضي احتياطي)
    return (
        Path.home() / "AppData" / "Local" / "CapCut" / "User Data" / "Projects" / "com.lveditor.draft"
    )


DEFAULT_PROJECTS_DIR = _default_projects_dir()


def us_to_srt_timestamp(microseconds: int) -> str:
    total_ms = max(0, microseconds) // 1000
    hh, rem_ms = divmod(total_ms, 3600000)
    mm, rem_ms = divmod(rem_ms, 60000)
    ss, ms = divmod(rem_ms, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def _parse_text_content(raw_content: str) -> str:
    try:
        parsed = json.loads(raw_content)
        return parsed.get("text", "")
    except (json.JSONDecodeError, TypeError):
        return raw_content or ""


def extract_caption_entries(draft: dict) -> list:
    """يرجع قائمة (start_us, end_us, text) من كل مقاطع النصوص في المشروع.

    material_id في الـ segment قد يشير مباشرة لعنصر في materials.texts،
    أو (في حالة قوالب الكابشن الجاهزة) لعنصر في materials.text_templates
    الذي يحيل بدوره إلى نص فعلي عبر text_info_resources[].text_material_id.
    """
    texts_by_id = {}
    for mat in draft.get("materials", {}).get("texts", []):
        mat_id = mat.get("id")
        if mat_id:
            texts_by_id[mat_id] = _parse_text_content(mat.get("content", ""))

    templates_by_id = {}
    for tmpl in draft.get("materials", {}).get("text_templates", []):
        tmpl_id = tmpl.get("id")
        if tmpl_id:
            templates_by_id[tmpl_id] = tmpl

    entries = []
    for track in draft.get("tracks", []):
        if track.get("type") != "text":
            continue
        for seg in track.get("segments", []):
            timerange = seg.get("target_timerange") or {}
            start = timerange.get("start")
            duration = timerange.get("duration")
            if start is None or duration is None:
                continue
            material_id = seg.get("material_id")

            text = ""
            if material_id in texts_by_id:
                text = texts_by_id[material_id]
            elif material_id in templates_by_id:
                infos = templates_by_id[material_id].get("text_info_resources", [])
                parts = []
                for info in infos:
                    sub_text = texts_by_id.get(info.get("text_material_id"), "")
                    if sub_text:
                        parts.append(sub_text)
                text = "\n".join(parts)

            text = text.strip()
            if not text:
                continue
            entries.append((start, start + duration, text))

    entries.sort(key=lambda e: e[0])
    return entries


def entries_to_srt(entries: list) -> str:
    lines = []
    for idx, (start_us, end_us, text) in enumerate(entries, start=1):
        lines.append(str(idx))
        lines.append(f"{us_to_srt_timestamp(start_us)} --> {us_to_srt_timestamp(end_us)}")
        lines.append(text.replace("\r\n", "\n"))
        lines.append("")
    return "\n".join(lines)


def process_project(project_dir: Path, output_dir: Path | None) -> str | None:
    draft_path = project_dir / "draft_content.json"
    if not draft_path.is_file():
        return None

    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        print(f"  تحذير: تعذّرت قراءة {draft_path}: {e}", file=sys.stderr)
        return None

    entries = extract_caption_entries(draft)
    if not entries:
        return None

    srt_content = entries_to_srt(entries)
    target_dir = output_dir if output_dir else project_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    srt_path = target_dir / f"{project_dir.name}.srt"
    srt_path.write_text(srt_content, encoding="utf-8")
    return str(srt_path)


def main():
    parser = argparse.ArgumentParser(description="استخراج كابشنز مشاريع CapCut إلى SRT")
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=DEFAULT_PROJECTS_DIR,
        help="مجلد مشاريع CapCut (com.lveditor.draft)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="مجلد حفظ ملفات SRT (افتراضياً: بجانب كل مشروع)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="اسم مجلد مشروع واحد فقط (بدلاً من كل المشاريع)",
    )
    args = parser.parse_args()

    projects_dir: Path = args.projects_dir
    if not projects_dir.is_dir():
        print(f"خطأ: المجلد غير موجود: {projects_dir}", file=sys.stderr)
        sys.exit(1)

    if args.project:
        project_dirs = [projects_dir / args.project]
    else:
        project_dirs = sorted(p for p in projects_dir.iterdir() if p.is_dir())

    exported = 0
    skipped = 0
    for project_dir in project_dirs:
        if not project_dir.is_dir():
            print(f"تخطي: المجلد غير موجود: {project_dir}", file=sys.stderr)
            continue
        result = process_project(project_dir, args.output_dir)
        if result:
            print(f"تم: {project_dir.name} -> {result}")
            exported += 1
        else:
            skipped += 1

    print(f"\nالإجمالي: {exported} ملف SRT تم إنشاؤه، {skipped} مشروع بدون كابشنز أو بدون ملف.")


if __name__ == "__main__":
    main()
