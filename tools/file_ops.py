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
    # 硬保护：禁止覆盖演示源文件（data/demo_project 下已存在的文件），迁移产物应写到 output/
    norm = os.path.normpath(path).replace("\\", "/")
    if os.path.exists(path) and "data/demo_project" in norm:
        return {"error": f"禁止覆盖原始源文件 {path}。请把迁移结果写到 output/ 目录，"
                         f"例如 output/{os.path.basename(path).replace('.sql', '_migrated.sql')}"}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}
