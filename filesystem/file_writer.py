from pathlib import Path
class FileWriter:
    def write(self,path,content,workspace):
        root=Path(workspace).resolve(); target=(root/path).resolve()
        if root not in target.parents: raise PermissionError("Path escapes workspace.")
        target.parent.mkdir(parents=True,exist_ok=True); target.write_text(content,encoding="utf-8"); return str(target)
