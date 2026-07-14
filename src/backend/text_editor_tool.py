"""
Text editor tool — client-side Anthropic builtin tool, locked to one file.

Unlike web_search (server-side, resolved by Anthropic), the text editor tool
sends Claude's view/create/str_replace/insert requests back to *this* process
to execute. This implementation only ever touches knowledge_base/project_notes.md —
any other path is rejected before the filesystem is touched, regardless of
what path string Claude sends.
"""
from pathlib import Path
from shutil import copyfile

from anthropic.lib.tools import BetaAsyncBuiltinFunctionTool, ToolError

DOCS_DIR = (Path(__file__).parent.parent.parent / "knowledge_base").resolve()
ALLOWED_PATH = (DOCS_DIR / "project_notes.md").resolve()


class ProjectNotesEditorTool(BetaAsyncBuiltinFunctionTool):
    """Anthropic's str_replace_based_edit_tool, hardcoded to project_notes.md only."""

    def to_dict(self):
        return {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}

    def _check_path(self, path_str: str) -> Path:
        try:
            raw = Path(path_str)
            candidate = raw.resolve() if raw.is_absolute() else (DOCS_DIR / raw).resolve()
        except Exception:
            raise ToolError(f"Invalid path: {path_str!r}")
        if candidate != ALLOWED_PATH:
            raise ToolError(
                "Access denied: this tool may only view or edit 'project_notes.md'. "
                f"'{path_str}' is not allowed."
            )
        return candidate

    async def call(self, input: dict) -> str:
        command = input.get("command")
        path = self._check_path(input.get("path", ""))

        if command == "view":
            if not path.exists():
                raise ToolError("project_notes.md does not exist yet. Use 'create' to make it.")
            lines = path.read_text(encoding="utf-8").splitlines()
            view_range = input.get("view_range")
            start = 1
            if view_range:
                start, end = view_range
                end = len(lines) if end == -1 else end
                lines = lines[start - 1:end]
            return "\n".join(f"{i + start}\t{line}" for i, line in enumerate(lines))

        if command == "create":
            file_text = input.get("file_text", "")
            if path.exists():
                copyfile(path, path.with_name(path.name + ".bak"))
            path.write_text(file_text, encoding="utf-8")
            return f"Created {path.name} ({len(file_text)} chars)."

        if command == "str_replace":
            if not path.exists():
                raise ToolError("project_notes.md does not exist yet.")
            old_str = input.get("old_str", "")
            new_str = input.get("new_str", "")
            text = path.read_text(encoding="utf-8")
            count = text.count(old_str)
            if count == 0:
                raise ToolError("No match found for old_str — no changes made.")
            if count > 1:
                raise ToolError(f"old_str matches {count} times — must match exactly once. Add more surrounding context.")
            path.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
            return "Replacement applied."

        if command == "insert":
            if not path.exists():
                raise ToolError("project_notes.md does not exist yet.")
            insert_line = input.get("insert_line", 0)
            insert_text = input.get("insert_text", "")
            lines = path.read_text(encoding="utf-8").splitlines()
            lines.insert(insert_line, insert_text)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return f"Inserted text after line {insert_line}."

        raise ToolError(f"Unknown command: {command!r}. Expected view, create, str_replace, or insert.")
