from pathlib import Path
class FileReader:
    def read(self, path, workspace):
        root=Path(workspace).resolve(); target=(root/path).resolve()
        if root not in target.parents and target != root: raise PermissionError("Path escapes workspace.")
        return target.read_text(encoding="utf-8")
