"""文件读写工具。"""
import os


def list_files(args: dict) -> dict:
    path = args.get("path", ".")
    if not os.path.isdir(path):
        return {"error": f"目录不存在: {path}"}
    files = []
    for root, _dirs, names in os.walk(path):
        for n in names:
            files.append(os.path.join(root, n))
    return {"files": files}


def read_file(args: dict) -> dict:
    path = args.get("path", "")
    if not os.path.isfile(path):
        return {"error": f"文件不存在: {path}"}
    with open(path, "r", encoding="utf-8") as f:
        return {"path": path, "content": f.read()}


def write_file(args: dict) -> dict:
    path = args.get("path", "")
    content = args.get("content", "")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}
