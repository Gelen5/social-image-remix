"""Package only skill source files; never include customer outputs or credentials."""
import argparse
from pathlib import Path
import zipfile


def package(output):
    root = Path(__file__).resolve().parent.parent
    files = [root / name for name in ("SKILL.md", "README.md", "requirements.txt", "LICENSE", "VALIDATION.md")]
    for directory in ("scripts", "references", "agents", "tests"):
        files.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and p.suffix in (".py", ".md", ".yaml", ".html", ".json") and "__pycache__" not in p.parts)
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(root).as_posix())
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    package(parser.parse_args().output)
