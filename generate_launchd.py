"""Generate a project-local launchd plist preview without loading it."""

import argparse
import os
import plistlib
import sys
import tempfile
from pathlib import Path


LABEL = "com.things3githubsync.agent"


def render_plist(project_dir: Path, python_path: Path) -> str:
    project = project_dir.expanduser().resolve()
    python = python_path.expanduser().resolve()
    logs = project / "logs"
    payload = {"Label": LABEL, "ProgramArguments": [str(python), str(project / "main.py")], "WorkingDirectory": str(project), "RunAtLoad": True, "KeepAlive": True, "StandardOutPath": str(logs / "launchd.out.log"), "StandardErrorPath": str(logs / "launchd.err.log")}
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML, sort_keys=False).decode("utf-8")


def write_plist(output: Path, project_dir: Path, python_path: Path) -> Path:
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    project_dir.expanduser().resolve().joinpath("logs").mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        handle.write(render_plist(project_dir, python_path))
        temporary = Path(handle.name)
    try:
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    parser.add_argument("--python", dest="python_path", default=sys.executable)
    args = parser.parse_args(argv)
    project = Path(__file__).resolve().parent
    output = Path(args.output) if args.output else project / "build" / f"{LABEL}.plist"
    print(write_plist(output, project, Path(args.python_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
