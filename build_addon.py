"""Build clean faceanim_exporter.zip for Blender add-on installation."""
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
ADDON_DIR = ROOT / "faceanim_exporter"
ZIP_OUT = ROOT / "faceanim_exporter.zip"

def main():
    print(f"Packaging {ADDON_DIR.name} into {ZIP_OUT.name}...")
    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for file_path in ADDON_DIR.rglob("*"):
            if "__pycache__" in file_path.parts or file_path.suffix == ".pyc":
                continue
            arcname = file_path.relative_to(ROOT)
            z.write(file_path, arcname)
    print(f"Successfully created {ZIP_OUT.name}")

if __name__ == "__main__":
    main()
