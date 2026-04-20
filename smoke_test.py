import py_compile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    targets = [ROOT / "dynaclip.py", ROOT / "DynaClip.spec"]
    for target in targets:
        if target.suffix == ".py":
            py_compile.compile(str(target), doraise=True)
            print(f"OK: {target.name}")
        else:
            compile(target.read_text(encoding="utf-8"), str(target), "exec")
            print(f"OK: {target.name}")

    expected = [ROOT / "README.md", ROOT / "version_info.txt"]
    for target in expected:
        if not target.exists():
            raise FileNotFoundError(target)
        print(f"PRESENT: {target.name}")


if __name__ == "__main__":
    main()
