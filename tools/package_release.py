import argparse
import re
import shutil
import tarfile
import zipfile
from pathlib import Path


def _validate_version(version):
    if not re.fullmatch(r"v[0-9A-Za-z][0-9A-Za-z._-]*", version) or version.endswith("."):
        raise ValueError(f"Invalid release tag for asset filenames: {version}")


def _release_files(build, platform):
    libraries = sorted((build / "core/libs/libs").glob("*.prx"))
    expected = {f"{directory.name}.prx" for directory in Path("core/libs/prx").iterdir() if directory.is_dir()}
    expected.add("libcohtml.Prospero.prx")
    missing = expected - {library.name for library in libraries}
    if missing:
        raise RuntimeError(f"Missing patched libraries: {', '.join(sorted(missing))}")

    executable = "relinker.exe" if platform == "windows" else "relinker"
    files = list(libraries)
    if platform == "windows":
        runtime = Path("C:/winlibs/mingw64/bin")
        files.extend(runtime / name for name in ("libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll"))

    binary = build / "core/relinker" / executable
    for file in [*files, binary]:
        if not file.is_file() or file.stat().st_size == 0:
            raise RuntimeError(f"Missing or empty release file: {file}")
    return files, binary


def package(platform, build, output, version, gui):
    _validate_version(version)
    files, binary = _release_files(build, platform)

    if not gui.is_file() or gui.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty portable GUI: {gui}")

    output.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(
        output / f"prx-{platform}-{version}.zip",
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for file in files:
            archive.write(file, arcname=f"libs/{file.name}")

    with tarfile.open(output / f"prx-{platform}-{version}.tar.gz", "w:gz", compresslevel=9) as archive:
        for file in files:
            archive.add(file, arcname=f"libs/{file.name}")

    asset = f"relinker-{version}.exe" if platform == "windows" else f"relinker-{version}"
    shutil.copy2(binary, output / asset)

    package_root = output / f"AnyPS5-{version}-{platform}"
    if package_root.exists():
        shutil.rmtree(package_root)
    (package_root / "libs").mkdir(parents=True)
    (package_root / "tools").mkdir(parents=True)

    bundled_relinker = package_root / ("relinker.exe" if platform == "windows" else "relinker")
    shutil.copy2(binary, bundled_relinker)
    if platform != "windows":
        bundled_relinker.chmod(bundled_relinker.stat().st_mode | 0o111)

    for file in files:
        shutil.copy2(file, package_root / "libs" / file.name)

    bundled_gui = package_root / ("AnyPS5-GUI.exe" if platform == "windows" else "AnyPS5-GUI")
    shutil.copy2(gui, bundled_gui)
    if platform != "windows":
        bundled_gui.chmod(bundled_gui.stat().st_mode | 0o111)

    source_tools = (
        "anyps5_gui.py",
        "AnyPS5-GUI.bat",
        "AnyPS5-GUI.sh",
        "RunAnyPS5_GUI.bat",
        "run_anyps5_gui.sh",
    )
    for name in source_tools:
        source = Path("tools") / name
        if source.is_file():
            shutil.copy2(source, package_root / "tools" / name)

    for name in ("README.md", "LICENSE"):
        source = Path(name)
        if source.is_file():
            shutil.copy2(source, package_root / name)

    readme = f"""# AnyPS5 {version} - Portable package ({platform})

## Start here

1. Run AnyPS5-GUI (Windows: AnyPS5-GUI.exe).
2. Select the PS5 ELF you want to convert.
3. Choose Windows or Linux as the target.
4. Choose an output path and click Convert.
5. Use Convert & Run only when the runtime folders required by the converted game are already present.

The bundled GUI and relinker are intended to work from this folder without a project build tree.

## Runtime files

The package includes the patched libs/*.prx files required by the relinker/runtime.

A converted game still needs its own compatible game data/runtime layout, including the required libs/ and app0/ contents beside the converted executable. This project does not distribute proprietary game data, firmware, keys, or other copyrighted game files.

## Fallback

The tools/ directory contains the Python GUI source and launcher scripts. The packaged GUI executable is the recommended entry point.
"""
    (package_root / "README-PORTABLE.md").write_text(readme, encoding="utf-8")

    portable_zip = output / f"anyps5-portable-{platform}-{version}.zip"
    with zipfile.ZipFile(
        portable_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for file in sorted(package_root.rglob("*")):
            if file.is_file():
                archive.write(file, arcname=file.relative_to(output))

    portable_tar = output / f"anyps5-portable-{platform}-{version}.tar.gz"
    with tarfile.open(portable_tar, "w:gz", compresslevel=9) as archive:
        archive.add(package_root, arcname=package_root.name)

    shutil.rmtree(package_root)


def collect_docs(source, output):
    documents = sorted(source.rglob("*.md"))
    if not documents:
        raise RuntimeError(f"No Markdown documents found in {source}")
    names = set()
    for document in documents:
        if document.name in names or (output / document.name).exists():
            raise RuntimeError(f"Duplicate release asset name: {document.name}")
        names.add(document.name)
    output.mkdir(parents=True, exist_ok=True)
    for document in documents:
        shutil.copy2(document, output / document.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("linux", "windows"))
    parser.add_argument("--build", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--gui", type=Path)
    parser.add_argument("--docs", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.docs is not None:
        if any(value is not None for value in (args.platform, args.build, args.version, args.gui)):
            parser.error("--docs cannot be combined with package options")
        collect_docs(args.docs, args.output)
    else:
        if any(value is None for value in (args.platform, args.build, args.version, args.gui)):
            parser.error("--platform, --build, --version and --gui are required when packaging a platform release")
        package(args.platform, args.build, args.output, args.version, args.gui)


if __name__ == "__main__":
    main()
