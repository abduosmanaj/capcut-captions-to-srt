#!/usr/bin/env python3
"""واجهة رسومية بسيطة: اختر مشروع CapCut واحصل على ملف SRT فوراً."""

import json
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capcut_captions_to_srt import (
    DEFAULT_PROJECTS_DIR,
    entries_to_srt,
    extract_caption_entries,
)


class CapCutCaptionsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("مستخرج كابشنز CapCut")
        self.root.geometry("640x480")
        self.root.minsize(520, 400)

        self.projects_dir = DEFAULT_PROJECTS_DIR
        self.projects: list[dict] = []  # {"name", "path", "caption_count"}

        self._build_ui()
        self.refresh_projects()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="مجلد المشاريع:").pack(side="right", padx=(6, 0))
        self.dir_var = tk.StringVar(value=str(self.projects_dir))
        dir_entry = ttk.Entry(top, textvariable=self.dir_var, justify="left")
        dir_entry.pack(side="right", fill="x", expand=True, padx=6)
        ttk.Button(top, text="تغيير...", command=self.choose_projects_dir).pack(side="right")

        mid = ttk.Frame(self.root, padding=(10, 0))
        mid.pack(fill="both", expand=True)

        ttk.Label(mid, text="اختر مشروعاً (المشاريع التي فيها كابشنز فقط):").pack(
            anchor="e", pady=(0, 4)
        )

        list_frame = ttk.Frame(mid)
        list_frame.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 11),
            activestyle="dotbox",
        )
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.pack(side="right", fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self.export_selected())

        btns = ttk.Frame(self.root, padding=10)
        btns.pack(fill="x")

        ttk.Button(btns, text="تحديث القائمة", command=self.refresh_projects).pack(
            side="right", padx=4
        )
        ttk.Button(
            btns, text="تصدير المشروع المختار", command=self.export_selected
        ).pack(side="right", padx=4)
        ttk.Button(
            btns, text="تصدير الكل إلى مجلد...", command=self.export_all
        ).pack(side="right", padx=4)

        self.status_var = tk.StringVar(value="جاري الفحص...")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, anchor="e", padding=(10, 4)
        )
        status_bar.pack(fill="x")

    def choose_projects_dir(self):
        chosen = filedialog.askdirectory(
            title="اختر مجلد مشاريع CapCut (com.lveditor.draft)",
            initialdir=self.dir_var.get(),
        )
        if chosen:
            self.dir_var.set(chosen)
            self.projects_dir = Path(chosen)
            self.refresh_projects()

    def refresh_projects(self):
        self.status_var.set("جاري الفحص...")
        self.listbox.delete(0, tk.END)
        self.root.update_idletasks()
        threading.Thread(target=self._scan_projects, daemon=True).start()

    def _scan_projects(self):
        projects_dir = Path(self.dir_var.get())
        found = []
        if projects_dir.is_dir():
            for p in sorted(projects_dir.iterdir()):
                if not p.is_dir():
                    continue
                draft_path = p / "draft_content.json"
                if not draft_path.is_file():
                    continue
                try:
                    draft = json.loads(draft_path.read_text(encoding="utf-8"))
                    entries = extract_caption_entries(draft)
                except Exception:
                    entries = []
                if entries:
                    found.append(
                        {"name": p.name, "path": p, "caption_count": len(entries)}
                    )
        self.root.after(0, self._populate_projects, found)

    def _populate_projects(self, found: list):
        self.projects = found
        self.listbox.delete(0, tk.END)
        for proj in self.projects:
            self.listbox.insert(
                tk.END, f"{proj['name']}   ({proj['caption_count']} كابشن)"
            )
        if not self.projects:
            self.status_var.set("لم يتم العثور على أي مشروع فيه كابشنز.")
        else:
            self.status_var.set(f"تم العثور على {len(self.projects)} مشروع فيه كابشنز.")

    def _get_selected_project(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("تنبيه", "اختر مشروعاً من القائمة أولاً.")
            return None
        return self.projects[sel[0]]

    def export_selected(self):
        proj = self._get_selected_project()
        if not proj:
            return

        draft_path = proj["path"] / "draft_content.json"
        try:
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            entries = extract_caption_entries(draft)
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذّرت قراءة المشروع:\n{e}")
            return

        if not entries:
            messagebox.showinfo("لا توجد كابشنز", "هذا المشروع لا يحتوي على كابشنز.")
            return

        srt_content = entries_to_srt(entries)
        save_path = filedialog.asksaveasfilename(
            title="حفظ ملف SRT",
            initialfile=f"{proj['name']}.srt",
            defaultextension=".srt",
            filetypes=[("SubRip Subtitle", "*.srt"), ("كل الملفات", "*.*")],
        )
        if not save_path:
            return

        Path(save_path).write_text(srt_content, encoding="utf-8")
        self.status_var.set(f"تم الحفظ: {save_path}")
        messagebox.showinfo("تم", f"تم حفظ الملف بنجاح:\n{save_path}")

    def export_all(self):
        if not self.projects:
            messagebox.showinfo("تنبيه", "لا توجد مشاريع فيها كابشنز.")
            return

        out_dir = filedialog.askdirectory(title="اختر مجلد حفظ كل ملفات SRT")
        if not out_dir:
            return
        out_dir_path = Path(out_dir)

        exported = 0
        errors = []
        for proj in self.projects:
            draft_path = proj["path"] / "draft_content.json"
            try:
                draft = json.loads(draft_path.read_text(encoding="utf-8"))
                entries = extract_caption_entries(draft)
                if not entries:
                    continue
                srt_content = entries_to_srt(entries)
                srt_path = out_dir_path / f"{proj['name']}.srt"
                srt_path.write_text(srt_content, encoding="utf-8")
                exported += 1
            except Exception as e:
                errors.append(f"{proj['name']}: {e}")

        msg = f"تم تصدير {exported} ملف SRT إلى:\n{out_dir}"
        if errors:
            msg += "\n\nأخطاء:\n" + "\n".join(errors)
        self.status_var.set(f"تم تصدير {exported} ملف إلى {out_dir}")
        messagebox.showinfo("تم", msg)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        available = style.theme_names()
        for preferred in ("vista", "aqua", "clam"):
            if preferred in available:
                style.theme_use(preferred)
                break
    except Exception:
        pass
    CapCutCaptionsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
