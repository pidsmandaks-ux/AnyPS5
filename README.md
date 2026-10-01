# About

Tool for automatic executables porting to Linux and Windows.

Includes a [relinker](core/relinker) that converts executable to the target system's native format and implementations of [system prx libraries](core/libs/prx) suitable for dynamic linking. No emulation or separate runtime process.



## Status

[![libraries](https://boykopovar.github.io/AnyPS5/badge-libraries.svg)](https://boykopovar.github.io/AnyPS5/) [![shaders](https://boykopovar.github.io/AnyPS5/badge-shaders.svg)](https://boykopovar.github.io/AnyPS5/)

[![progress map](https://boykopovar.github.io/AnyPS5/progress.svg)](https://boykopovar.github.io/AnyPS5/)

<sub>* System libraries: percentage of the functions known to the project so far (declared in [core/libs/prx](core/libs/prx)), not of every PS5 system function. The total grows as more functions are declared.</sub>

[List of verified games](docs/user/COMPATIBILITY.md)

Dreaming Sarah (2D platformer) runs at a stable 60 fps on a GTX 1050 Ti / i5-7500 3.4GHz.

Unsupported or unexpected states strictly throw `std::runtime_error`. `what()` is printed to stderr and the process terminates.

The [shader recompiler](core/shader/recompiler/Recompiler.cpp) successfully produces SPIR-V (validated via [Spirv-Tools](3rdparty/SPIRV-Tools) when built with `ANYPS5_ENABLE_SPIRV_TOOLS`).

[Technical debt of the project](docs/dev/TechnicalDebt.md), [code style conventions](docs/dev/CONVENTIONS.md), [contributing](CONTRIBUTING.md)

## Build

The relinker uses only the C++20 standard library and should build with any conforming compiler.

On Intel hosts, pass `--to-intel` to the relinker to lower supported AMD-only instructions in the executable and bundled `sce_module`/`sce_modules` PRX files. Unsupported instructions or stub jumps outside the x86-64 relative branch range produce an error.

[libc.prx](core/libs/prx/libc) implementations contain compiler-specific code. Linux builds work with GCC; on Windows, MinGW-w64 GCC 15.2.0 (`winlibs-gcc15`, `x86_64-ucrt-posix-seh`) is currently required.

The project targets maximum compiler portability. Support for additional compilers will be addressed after the first successful game launch.

## GUI

A simple cross-platform Tkinter GUI is available at [tools/anyps5_gui.py](tools/anyps5_gui.py). It wraps the relinker so the usual workflow is: select the PS5 ELF, choose Windows or Linux, choose an output location, then click **Convert**. The GUI can also launch the converted executable after a successful conversion.

The GUI uses only Python's standard library and automatically looks for a relinker built at `build/core/relinker/relinker` (or `relinker.exe`). It can also browse for the executable manually. Run it with:

```bash
python3 tools/anyps5_gui.py
```

On Windows, the same script can be started with `py tools\\anyps5_gui.py`. A Python installation with Tkinter is required.

The generated runtime must still contain the required `libs/` and `app0/` layout next to the converted executable; the GUI does not supply proprietary game data or system libraries.

## Compatibility

See the [game compatibility list](docs/user/COMPATIBILITY.md) for tested games and known issues.

For troubleshooting a new title, see [diagnostics](docs/user/DIAGNOSTICS.md).

## Input mapping

SDL-mapped game controllers are supported, including analog sticks and triggers. Keyboard and mouse controls can be configured with an `anyps5-input.ini` file. See [input mapping](docs/user/INPUT_MAPPING.md) for the supported devices and configuration format.

## Disclaimer

This project is intended for interoperability, research, preservation, and compatibility purposes. It does not include, distribute, or require copyrighted software, firmware, cryptographic keys, or proprietary libraries. Users are responsible for ensuring that any binaries used with this project are obtained and used in accordance with applicable laws and their respective license terms.

## License

This project is licensed under the GNU General Public License version 2 only.
