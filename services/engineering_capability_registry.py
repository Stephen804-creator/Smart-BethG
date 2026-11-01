"""Unified, language-neutral engineering capability catalog.

This catalog describes what Smart BethG understands and what integrations are
planned. It does not make a tool executable or connected. Actual execution
continues to be controlled by the separately reviewed runtime registry.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EngineeringCapability:
    id: str
    category: str
    domain: str
    name: str
    description: str
    status: str
    integration: str
    actions: tuple[str, ...] = ()
    related_ids: tuple[str, ...] = ()
    supported_formats: tuple[str, ...] = ()
    host_requirements: tuple[str, ...] = ()
    license_status: str = "review_required"

    def public_dict(self) -> dict:
        value = asdict(self)
        value["actions"] = list(self.actions)
        value["related_ids"] = list(self.related_ids)
        value["supported_formats"] = list(self.supported_formats)
        value["host_requirements"] = list(self.host_requirements)
        return value


# Status values are deliberately explicit:
# - implemented: an approved runtime is registered in Unit C.
# - catalog_only: known target, not yet integrated or executable.
# - integration_candidate: external tool identified; no connector is implied.
# - planned: roadmap item, not currently supported.
CAPABILITIES = (
    EngineeringCapability(
        "python", "language_runtime", "software", "Python",
        "General-purpose language; the only runtime enabled by the current C-D increment.",
        "implemented", "managed_sandbox",
        ("edit", "execute"), ("python-project",),
    ),
    EngineeringCapability(
        "javascript", "language", "software", "JavaScript",
        "Web and server-side application language.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("nodejs", "web-frontend"),
    ),
    EngineeringCapability(
        "typescript", "language", "software", "TypeScript",
        "Typed JavaScript commonly used for frontend and backend applications.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("nodejs", "web-frontend"),
    ),
    EngineeringCapability(
        "html-css", "web_format", "software", "HTML and CSS",
        "Web document structure and styling; not standalone server runtimes.",
        "planned", "web_preview", ("edit", "preview"),
        ("javascript", "typescript"),
    ),
    EngineeringCapability(
        "java", "language", "software", "Java",
        "JVM language and ecosystem.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("jvm", "spring-boot"),
    ),
    EngineeringCapability(
        "c-cpp", "language", "software", "C and C++",
        "Compiled systems and application languages.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("gcc-clang", "embedded-toolchains"),
    ),
    EngineeringCapability(
        "go", "language", "software", "Go",
        "Compiled language for services and systems software.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("go-toolchain",),
    ),
    EngineeringCapability(
        "rust", "language", "software", "Rust",
        "Compiled systems language with ownership-based memory safety.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("rust-toolchain",),
    ),
    EngineeringCapability(
        "php", "language", "software", "PHP",
        "Server-side web application language.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("composer", "laravel"),
    ),
    EngineeringCapability(
        "csharp", "language", "software", "C#",
        "Language commonly built with the .NET SDK.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("dotnet-sdk", "aspnet-core"),
    ),
    EngineeringCapability(
        "dart", "language", "software", "Dart",
        "Language used by Flutter and other Dart applications.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("flutter-sdk",),
    ),
    EngineeringCapability(
        "nodejs", "runtime_toolchain", "software", "Node.js",
        "JavaScript and TypeScript server-side runtime/toolchain.",
        "planned", "managed_sandbox", ("run", "build", "test"),
        ("javascript", "typescript"),
    ),
    EngineeringCapability(
        "jvm", "runtime_toolchain", "software", "Java Virtual Machine",
        "Runtime environment for approved JVM languages.",
        "planned", "managed_sandbox", ("run",),
        ("java",),
    ),
    EngineeringCapability(
        "gcc-clang", "compiler_toolchain", "software", "GCC / Clang",
        "C and C++ compiler toolchains; versions and images require review.",
        "planned", "managed_sandbox", ("build", "test"),
        ("c-cpp", "embedded-toolchains"),
    ),
    EngineeringCapability(
        "go-toolchain", "compiler_toolchain", "software", "Go toolchain",
        "Compiler, formatter and test tools for Go projects.",
        "planned", "managed_sandbox", ("build", "test"),
        ("go",),
    ),
    EngineeringCapability(
        "rust-toolchain", "compiler_toolchain", "software", "Rust toolchain",
        "Rust compiler and Cargo build/test tooling.",
        "planned", "managed_sandbox", ("build", "test"),
        ("rust",),
    ),
    EngineeringCapability(
        "dotnet-sdk", "sdk_toolchain", "software", ".NET SDK",
        "Build and test tooling for approved .NET targets.",
        "planned", "managed_sandbox", ("build", "test"),
        ("csharp",),
    ),
    EngineeringCapability(
        "flutter-sdk", "sdk_toolchain", "software", "Flutter SDK",
        "Cross-platform UI SDK; target-specific host requirements apply.",
        "planned", "capability_routed_runner", ("build", "test"),
        ("dart", "android-sdk", "apple-xcode"),
    ),
    EngineeringCapability(
        "android-sdk", "sdk_toolchain", "software", "Android SDK",
        "Android build tooling; Android emulator support is a separate capability.",
        "planned", "capability_routed_runner", ("build", "test", "package"),
        ("flutter-sdk",),
    ),
    EngineeringCapability(
        "apple-xcode", "sdk_toolchain", "software", "Apple Xcode",
        "Apple-platform toolchain requiring a compatible macOS runner.",
        "planned", "capability_routed_runner", ("build", "test", "package"),
        ("flutter-sdk",),
    ),
    EngineeringCapability(
        "react", "framework_profile", "software", "React",
        "Frontend UI library; supported versions and build profiles require separate approval.",
        "planned", "managed_sandbox", ("build", "test"),
        ("javascript", "typescript", "nodejs"),
    ),
    EngineeringCapability(
        "angular", "framework_profile", "software", "Angular",
        "TypeScript frontend framework with a versioned CLI/build profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("typescript", "nodejs"),
    ),
    EngineeringCapability(
        "vue", "framework_profile", "software", "Vue",
        "Frontend framework with an approved package/build profile to be added.",
        "planned", "managed_sandbox", ("build", "test"),
        ("javascript", "typescript", "nodejs"),
    ),
    EngineeringCapability(
        "nextjs", "framework_profile", "software", "Next.js",
        "React-based full-stack framework; server and build capabilities require review.",
        "planned", "managed_sandbox", ("build", "test"),
        ("javascript", "typescript", "nodejs", "react"),
    ),
    EngineeringCapability(
        "vite", "build_profile", "software", "Vite",
        "Frontend development and production build tool.",
        "planned", "managed_sandbox", ("build", "preview", "test"),
        ("javascript", "typescript", "nodejs"),
    ),
    EngineeringCapability(
        "express", "framework_profile", "software", "Express.js",
        "Node.js web framework; not a language or standalone runtime.",
        "planned", "managed_sandbox", ("build", "test"),
        ("javascript", "typescript", "nodejs"),
    ),
    EngineeringCapability(
        "nestjs", "framework_profile", "software", "NestJS",
        "Node.js backend framework with a TypeScript-oriented project profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("typescript", "nodejs"),
    ),
    EngineeringCapability(
        "fastapi", "framework_profile", "software", "FastAPI",
        "Python API framework; requires a reviewed dependency and project profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("python",),
    ),
    EngineeringCapability(
        "django", "framework_profile", "software", "Django",
        "Python web framework with a reviewed dependency and project profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("python",),
    ),
    EngineeringCapability(
        "flask", "framework_profile", "software", "Flask",
        "Python web framework with a reviewed dependency and project profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("python",),
    ),
    EngineeringCapability(
        "spring-boot", "framework_profile", "software", "Spring Boot",
        "Java application framework requiring a compatible JVM and build profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("java", "jvm"),
    ),
    EngineeringCapability(
        "aspnet-core", "framework_profile", "software", "ASP.NET Core",
        ".NET web framework requiring a compatible .NET SDK profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("csharp", "dotnet-sdk"),
    ),
    EngineeringCapability(
        "laravel", "framework_profile", "software", "Laravel",
        "PHP web framework requiring a reviewed PHP and Composer profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("php", "composer"),
    ),
    EngineeringCapability(
        "flutter", "framework_profile", "software", "Flutter",
        "Cross-platform UI framework; actual target support depends on compatible runner hosts.",
        "planned", "capability_routed_runner", ("build", "test"),
        ("dart", "flutter-sdk", "android-sdk", "apple-xcode"),
    ),
    EngineeringCapability(
        "react-native", "framework_profile", "software", "React Native",
        "Cross-platform mobile framework with Android/iOS host-specific requirements.",
        "planned", "capability_routed_runner", ("build", "test"),
        ("javascript", "typescript", "nodejs", "android-sdk", "apple-xcode"),
    ),
    EngineeringCapability(
        "unity", "framework_profile", "software", "Unity",
        "Game engine project profile; licensing and compatible build hosts require review.",
        "planned", "capability_routed_runner", ("build", "test", "package"),
        (),
    ),
    EngineeringCapability(
        "unreal", "framework_profile", "software", "Unreal Engine",
        "Game engine project profile; licensing, resource and host requirements require review.",
        "planned", "capability_routed_runner", ("build", "test", "package"),
        (),
    ),
    EngineeringCapability(
        "godot", "framework_profile", "software", "Godot",
        "Game engine project profile with version-pinned export templates.",
        "planned", "capability_routed_runner", ("build", "test", "package"),
        (),
    ),
    EngineeringCapability(
        "python-project", "project_build_profile", "software", "Python project profile",
        "Validated Python project profile; framework and dependency sets require separate approval.",
        "planned", "managed_sandbox", ("build", "test"),
        ("python",),
    ),
    EngineeringCapability(
        "web-frontend", "project_build_profile", "software", "Web frontend project profile",
        "Validated HTML/CSS/JavaScript/TypeScript frontend profile with a pinned package manager and build steps.",
        "planned", "managed_sandbox", ("build", "test", "preview"),
        ("html-css", "javascript", "typescript", "nodejs"),
    ),
    EngineeringCapability(
        "embedded-toolchains", "project_build_profile", "embedded", "Embedded firmware project profile",
        "Validated embedded project profile linking a selected board, toolchain, firmware format and runner capability.",
        "planned", "capability_routed_runner", ("build", "test", "export"),
        ("arduino-cli", "esp-idf", "platformio"),
    ),
    EngineeringCapability(
        "composer", "package_manager", "software", "Composer",
        "PHP dependency manager; packages and scripts require an approved dependency policy.",
        "planned", "managed_sandbox", ("install", "build", "test"),
        ("php", "laravel"),
    ),
    EngineeringCapability(
        "arduino-cli", "embedded_toolchain", "embedded", "Arduino CLI",
        "Compile and manage supported Arduino sketches and board packages.",
        "planned", "managed_sandbox", ("build", "test", "export"),
        ("c-cpp", "arduino-uno", "esp32"),
    ),
    EngineeringCapability(
        "esp-idf", "embedded_toolchain", "embedded", "ESP-IDF",
        "Espressif's embedded development framework and build tools.",
        "planned", "managed_sandbox", ("build", "test", "export"),
        ("c-cpp", "esp32"),
    ),
    EngineeringCapability(
        "platformio", "embedded_toolchain", "embedded", "PlatformIO",
        "Project-based embedded build and dependency tooling.",
        "planned", "managed_sandbox", ("build", "test", "export"),
        ("c-cpp", "esp32", "rp2040", "stm32"),
    ),
    EngineeringCapability(
        "micropython", "embedded_runtime", "embedded", "MicroPython",
        "Python implementation for supported microcontrollers.",
        "planned", "managed_sandbox", ("build", "simulate", "flash"),
        ("esp32", "rp2040"),
    ),
    EngineeringCapability(
        "circuitpython", "embedded_runtime", "embedded", "CircuitPython",
        "Python implementation for supported microcontroller boards.",
        "planned", "managed_sandbox", ("build", "simulate", "flash"),
        ("rp2040",),
    ),
    EngineeringCapability(
        "verilog", "hardware_description_language", "hardware", "Verilog",
        "Hardware description language for digital logic design.",
        "planned", "capability_routed_runner", ("edit", "simulate", "synthesize"),
        ("fpga",),
    ),
    EngineeringCapability(
        "vhdl", "hardware_description_language", "hardware", "VHDL",
        "Hardware description language for digital logic design.",
        "planned", "capability_routed_runner", ("edit", "simulate", "synthesize"),
        ("fpga",),
    ),
    EngineeringCapability(
        "systemverilog", "hardware_description_language", "hardware", "SystemVerilog",
        "Hardware design and verification language.",
        "planned", "capability_routed_runner", ("edit", "simulate", "verify", "synthesize"),
        ("fpga",),
    ),
    EngineeringCapability(
        "arduino-uno", "hardware_target", "hardware", "Arduino Uno",
        "Microcontroller board target; not a programming language or runtime.",
        "catalog_only", "local_agent_or_simulator", ("flash", "serial_monitor"),
        ("arduino-cli", "wokwi"),
    ),
    EngineeringCapability(
        "esp32", "hardware_target", "hardware", "ESP32",
        "Microcontroller family target; physical access requires a controlled local agent.",
        "catalog_only", "local_agent_or_simulator", ("flash", "serial_monitor", "debug"),
        ("esp-idf", "platformio", "micropython", "wokwi"),
    ),
    EngineeringCapability(
        "rp2040", "hardware_target", "hardware", "RP2040 / Raspberry Pi Pico",
        "Microcontroller target with board-specific toolchain requirements.",
        "catalog_only", "local_agent_or_simulator", ("flash", "serial_monitor", "debug"),
        ("platformio", "micropython", "circuitpython"),
    ),
    EngineeringCapability(
        "stm32", "hardware_target", "hardware", "STM32",
        "Microcontroller family target with vendor/toolchain-specific requirements.",
        "catalog_only", "local_agent_or_simulator", ("flash", "serial_monitor", "debug"),
        ("platformio",),
    ),
    EngineeringCapability(
        "fpga", "hardware_target", "hardware", "FPGA development boards",
        "Programmable logic target; supported board families and vendor tools require review.",
        "catalog_only", "capability_routed_runner", ("synthesize", "program", "verify"),
        ("verilog", "vhdl", "systemverilog"),
    ),
    EngineeringCapability(
        "wokwi", "engineering_tool", "hardware", "Wokwi",
        "Candidate microcontroller simulator integration; not connected by this catalog.",
        "integration_candidate", "external_connector", ("simulate", "export"),
        ("esp32", "arduino-uno", "rp2040"),
    ),
    EngineeringCapability(
        "kicad", "engineering_tool", "hardware", "KiCad",
        "Schematic and PCB design tool; editing requires a controlled tool integration.",
        "integration_candidate", "local_agent_or_remote_tool", ("edit", "export", "inspect"),
        ("ngspice",),
    ),
    EngineeringCapability(
        "easyeda", "engineering_tool", "hardware", "EasyEDA",
        "Candidate schematic and PCB design integration; availability depends on supported APIs.",
        "integration_candidate", "external_connector", ("edit", "export", "inspect"),
    ),
    EngineeringCapability(
        "ngspice", "engineering_tool", "hardware", "ngspice",
        "Electrical circuit simulation engine; simulation is not physical validation.",
        "planned", "managed_sandbox", ("simulate",),
        ("kicad",),
    ),
    EngineeringCapability(
        "renode", "engineering_tool", "embedded", "Renode",
        "Candidate embedded firmware and system simulation environment.",
        "planned", "managed_sandbox", ("simulate", "debug"),
        ("esp32", "rp2040", "stm32"),
    ),
    EngineeringCapability(
        "arduino-mega2560", "hardware_target", "hardware", "Arduino Mega 2560",
        "AVR-based Arduino board target; compilation and flashing require an approved AVR toolchain and a local device bridge.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor"),
        ("arduino-cli", "avr-gcc", "avrdude"),
    ),
    EngineeringCapability(
        "arduino-nano", "hardware_target", "hardware", "Arduino Nano",
        "Compact AVR-based Arduino board target; board revision and bootloader compatibility must be selected explicitly.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor"),
        ("arduino-cli", "avr-gcc", "avrdude"),
    ),
    EngineeringCapability(
        "arduino-uno-r4", "hardware_target", "hardware", "Arduino Uno R4",
        "32-bit Renesas-based Arduino board family; not interchangeable with AVR Uno build profiles.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor", "debug"),
        ("arduino-cli", "arduino-core", "openocd"),
    ),
    EngineeringCapability(
        "esp32-c3", "hardware_target", "hardware", "ESP32-C3",
        "RISC-V ESP32 variant requiring a matching ESP-IDF or PlatformIO board profile.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor", "debug"),
        ("esp-idf", "platformio", "esptool", "wokwi"),
    ),
    EngineeringCapability(
        "esp32-s3", "hardware_target", "hardware", "ESP32-S3",
        "Xtensa ESP32 variant with board-specific memory, USB and peripheral configuration.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor", "debug"),
        ("esp-idf", "platformio", "esptool", "wokwi"),
    ),
    EngineeringCapability(
        "pico-w", "hardware_target", "hardware", "Raspberry Pi Pico W",
        "RP2040 wireless board variant; radio support depends on the selected SDK and firmware profile.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor", "debug"),
        ("rp2040", "platformio", "micropython", "circuitpython"),
    ),
    EngineeringCapability(
        "stm32-nucleo", "hardware_target", "hardware", "STM32 Nucleo",
        "STM32 development-board family; exact MCU, ST-LINK and debug profile must be selected.",
        "catalog_only", "local_agent_or_simulator", ("build", "flash", "serial_monitor", "debug"),
        ("stm32", "platformio", "openocd"),
    ),
    EngineeringCapability(
        "arduino-core", "embedded_framework", "embedded", "Arduino board cores",
        "Versioned board-platform packages for supported Arduino architectures; package installation must use an approved offline/cache policy.",
        "planned", "managed_sandbox", ("build", "test"),
        ("arduino-cli", "c-cpp", "arduino-uno", "arduino-mega2560", "arduino-nano", "arduino-uno-r4"),
    ),
    EngineeringCapability(
        "avr-gcc", "compiler_toolchain", "embedded", "AVR-GCC toolchain",
        "Compiler and binutils for supported AVR microcontrollers; exact compiler and board-core versions require pinning.",
        "planned", "managed_sandbox", ("build", "test"),
        ("c-cpp", "arduino-mega2560", "arduino-nano"),
    ),
    EngineeringCapability(
        "avrdude", "engineering_tool", "embedded", "AVRDUDE",
        "AVR programming utility; physical flashing requires an explicitly authorized local device agent.",
        "planned", "local_agent", ("flash", "verify"),
        ("arduino-mega2560", "arduino-nano", "arduino-cli"),
    ),
    EngineeringCapability(
        "esptool", "engineering_tool", "embedded", "esptool",
        "Espressif ROM bootloader utility for supported ESP chips; USB/serial access is not available to cloud jobs.",
        "planned", "local_agent", ("flash", "verify", "inspect"),
        ("esp32", "esp32-c3", "esp32-s3", "esp-idf"),
    ),
    EngineeringCapability(
        "openocd", "engineering_tool", "embedded", "OpenOCD",
        "On-chip debugging and programming server; target configuration and probe access require a compatible local or dedicated runner.",
        "planned", "capability_routed_runner", ("debug", "flash", "inspect"),
        ("stm32", "stm32-nucleo", "rp2040", "arduino-uno-r4"),
    ),
    EngineeringCapability(
        "zephyr", "embedded_framework", "embedded", "Zephyr RTOS",
        "Real-time operating system and project build system for supported microcontroller boards; requires a versioned SDK and board profile.",
        "planned", "managed_sandbox", ("build", "test", "export"),
        ("c-cpp", "esp32", "rp2040", "stm32"),
    ),
    EngineeringCapability(
        "iverilog", "engineering_tool", "hardware", "Icarus Verilog",
        "Open-source Verilog simulation tool; simulation does not prove timing closure or physical hardware correctness.",
        "planned", "managed_sandbox", ("simulate", "test"),
        ("verilog", "systemverilog"),
    ),
    EngineeringCapability(
        "ghdl", "engineering_tool", "hardware", "GHDL",
        "VHDL analysis and simulation tool; supported language standard and simulator version must be pinned.",
        "planned", "managed_sandbox", ("simulate", "test"),
        ("vhdl",),
    ),
    EngineeringCapability(
        "yosys", "engineering_tool", "hardware", "Yosys",
        "Open-source RTL synthesis tool for supported Verilog/SystemVerilog subsets and FPGA flows.",
        "planned", "managed_sandbox", ("synthesize", "inspect"),
        ("verilog", "systemverilog", "fpga"),
    ),
    EngineeringCapability(
        "kotlin", "language", "software", "Kotlin",
        "JVM language; the registered script profile does not imply Android project builds.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("jvm", "kotlin-toolchain"),
    ),
    EngineeringCapability(
        "swift", "language", "software", "Swift",
        "Compiled language with a script runner profile; Apple-platform packaging needs a separate compatible host.",
        "planned", "managed_sandbox", ("edit", "execute", "build", "test"),
        ("swift-toolchain", "apple-xcode"),
    ),
    EngineeringCapability(
        "bash", "language", "software", "Bash",
        "Shell scripting language; scripts execute only inside the isolated container, never on the API host.",
        "planned", "managed_sandbox", ("edit", "execute"),
        ("shell-sandbox",),
    ),
    EngineeringCapability(
        "powershell", "language", "software", "PowerShell",
        "Cross-platform automation shell; scripts execute only inside an isolated PowerShell image.",
        "planned", "managed_sandbox", ("edit", "execute"),
        ("powershell-core",),
    ),
    EngineeringCapability(
        "ruby", "language", "software", "Ruby",
        "General-purpose dynamic language commonly used with Rails.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("ruby-toolchain", "rails"),
    ),
    EngineeringCapability(
        "elixir", "language", "software", "Elixir",
        "Functional language running on the Erlang VM for concurrent applications.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("elixir-toolchain",),
    ),
    EngineeringCapability(
        "r", "language", "software", "R",
        "Language and environment for statistical computing and graphics.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("r-toolchain",),
    ),
    EngineeringCapability(
        "julia", "language", "software", "Julia",
        "High-level language for numerical and scientific computing.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("julia-toolchain",),
    ),
    EngineeringCapability(
        "lua", "language", "software", "Lua",
        "Lightweight embeddable scripting language.",
        "planned", "managed_sandbox", ("edit", "execute"),
        ("lua-runtime",),
    ),
    EngineeringCapability(
        "perl", "language", "software", "Perl",
        "General-purpose scripting language for text processing and automation.",
        "planned", "managed_sandbox", ("edit", "execute", "test"),
        ("perl-runtime",),
    ),
    EngineeringCapability(
        "sql", "query_language", "software", "SQL",
        "Database query language; must run only against disposable or explicitly authorized isolated databases.",
        "planned", "capability_routed_runner", ("edit", "validate", "query"),
        ("sql-sandbox",),
    ),
    EngineeringCapability(
        "plpgsql", "procedural_sql_language", "software", "PL/pgSQL",
        "PostgreSQL procedural language; requires a disposable PostgreSQL instance and isolated schema.",
        "planned", "capability_routed_runner", ("edit", "validate", "test"),
        ("sql-sandbox",),
    ),
    EngineeringCapability(
        "tsql", "procedural_sql_language", "software", "T-SQL",
        "SQL Server procedural dialect; requires a separately licensed and isolated database runner.",
        "planned", "capability_routed_runner", ("edit", "validate", "test"),
        ("sql-sandbox",),
    ),
    EngineeringCapability(
        "plsql", "procedural_sql_language", "software", "PL/SQL",
        "Oracle procedural SQL dialect; requires an appropriately licensed isolated database runner.",
        "planned", "capability_routed_runner", ("edit", "validate", "test"),
        ("sql-sandbox",),
    ),
    EngineeringCapability(
        "objective-c", "language", "software", "Objective-C",
        "Compiled language commonly used in Apple platform development; SDK builds require a compatible host.",
        "planned", "capability_routed_runner", ("edit", "build", "test"),
        ("gcc-clang", "apple-xcode"),
        host_requirements=("Apple SDK builds require macOS and Xcode.",),
    ),
    EngineeringCapability(
        "zig", "language", "software", "Zig",
        "Systems programming language with its own compiler and cross-compilation toolchain.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("zig-toolchain",),
    ),
    EngineeringCapability(
        "assembly", "language", "software", "Assembly",
        "Architecture-specific low-level language; execution requires a constrained emulator, not direct host CPU or device access.",
        "planned", "capability_routed_runner", ("edit", "assemble", "simulate"),
        ("assembly-emulator",),
    ),
    EngineeringCapability(
        "gdscript", "language", "software", "GDScript",
        "Godot engine scripting language; execution and export require a versioned Godot project profile.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("godot",),
    ),
    EngineeringCapability(
        "matlab", "language", "software", "MATLAB",
        "Proprietary numerical computing environment; runtime distribution and licensing require explicit approval.",
        "planned", "capability_routed_runner", ("edit", "execute", "test"),
        ("matlab-toolchain",),
        license_status="review_required",
    ),
    EngineeringCapability(
        "mojo", "language", "software", "Mojo",
        "Emerging AI and high-performance computing language; toolchain maturity and licensing require review.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("mojo-toolchain",),
    ),
    EngineeringCapability(
        "gleam", "language", "software", "Gleam",
        "Functional language targeting the Erlang VM or JavaScript; runtime and target profiles require review.",
        "planned", "managed_sandbox", ("edit", "build", "test"),
        ("gleam-toolchain",),
    ),
    EngineeringCapability(
        "kotlin-toolchain", "compiler_toolchain", "software", "Kotlin toolchain",
        "Kotlin compiler and JVM profile; Android SDK integration is a separate capability.",
        "planned", "managed_sandbox", ("build", "test"),
        ("kotlin", "jvm"),
    ),
    EngineeringCapability(
        "swift-toolchain", "compiler_toolchain", "software", "Swift toolchain",
        "Swift compiler for supported Linux or macOS targets; Apple SDK packaging requires Xcode.",
        "planned", "managed_sandbox", ("build", "test"),
        ("swift", "apple-xcode"),
    ),
    EngineeringCapability(
        "shell-sandbox", "runtime_toolchain", "software", "Isolated shell scripting",
        "Fixed Bash interpreter profile inside the restricted container; never a host shell endpoint.",
        "planned", "managed_sandbox", ("execute",),
        ("bash",),
    ),
    EngineeringCapability(
        "powershell-core", "runtime_toolchain", "software", "PowerShell Core",
        "Cross-platform PowerShell runtime in a separately pinned and isolated image.",
        "planned", "managed_sandbox", ("execute",),
        ("powershell",),
    ),
    EngineeringCapability(
        "rails", "framework_profile", "software", "Ruby on Rails",
        "Ruby web application framework; dependency installation and project scripts require an approved project profile.",
        "planned", "managed_sandbox", ("build", "test"),
        ("ruby", "ruby-toolchain"),
    ),
    EngineeringCapability(
        "ruby-toolchain", "runtime_toolchain", "software", "Ruby toolchain",
        "Ruby interpreter profile; gem installation and package scripts require separate dependency policy.",
        "planned", "managed_sandbox", ("execute", "test"),
        ("ruby",),
    ),
    EngineeringCapability(
        "elixir-toolchain", "runtime_toolchain", "software", "Elixir / OTP toolchain",
        "Elixir runtime and Erlang/OTP compatibility profile.",
        "planned", "managed_sandbox", ("execute", "test"),
        ("elixir",),
    ),
    EngineeringCapability(
        "r-toolchain", "runtime_toolchain", "software", "R toolchain",
        "Rscript runtime; package libraries require an approved offline dependency set.",
        "planned", "managed_sandbox", ("execute", "test"),
        ("r",),
    ),
    EngineeringCapability(
        "julia-toolchain", "runtime_toolchain", "software", "Julia toolchain",
        "Julia runtime and depot profile; package installation is separately controlled.",
        "planned", "managed_sandbox", ("execute", "test"),
        ("julia",),
    ),
    EngineeringCapability(
        "lua-runtime", "runtime_toolchain", "software", "Lua runtime",
        "Lua interpreter profile with a pinned version and standard-library set.",
        "planned", "managed_sandbox", ("execute",),
        ("lua",),
    ),
    EngineeringCapability(
        "perl-runtime", "runtime_toolchain", "software", "Perl runtime",
        "Perl interpreter profile; CPAN installation is not enabled by the single-file runner.",
        "planned", "managed_sandbox", ("execute",),
        ("perl",),
    ),
    EngineeringCapability(
        "sql-sandbox", "database_execution_profile", "software", "Disposable SQL sandbox",
        "Future disposable database execution profile with no production credentials, tenant data or network route to Smart BethG databases.",
        "planned", "capability_routed_runner", ("query", "validate", "test"),
        ("sql", "plpgsql", "tsql", "plsql"),
    ),
    EngineeringCapability(
        "zig-toolchain", "compiler_toolchain", "software", "Zig toolchain",
        "Pinned Zig compiler and standard library for controlled native builds.",
        "planned", "managed_sandbox", ("build", "test"),
        ("zig",),
    ),
    EngineeringCapability(
        "assembly-emulator", "engineering_tool", "software", "Assembly emulator",
        "Architecture-specific emulator profile with explicit instruction, memory and execution limits.",
        "planned", "capability_routed_runner", ("assemble", "simulate"),
        ("assembly",),
    ),
    EngineeringCapability(
        "matlab-toolchain", "sdk_toolchain", "software", "MATLAB toolchain",
        "Licensed MATLAB runtime/compiler environment; no bundling or redistribution before legal clearance.",
        "planned", "capability_routed_runner", ("execute", "test"),
        ("matlab",),
        license_status="review_required",
    ),
    EngineeringCapability(
        "mojo-toolchain", "compiler_toolchain", "software", "Mojo toolchain",
        "Pinned Mojo compiler/runtime candidate pending maturity, security and license review.",
        "planned", "managed_sandbox", ("build", "test"),
        ("mojo",),
    ),
    EngineeringCapability(
        "gleam-toolchain", "compiler_toolchain", "software", "Gleam toolchain",
        "Pinned Gleam compiler and selected target runtime candidate.",
        "planned", "managed_sandbox", ("build", "test"),
        ("gleam",),
    ),
    EngineeringCapability(
        "cloud-sandbox", "execution_profile", "cross_domain", "Managed cloud sandbox",
        "Restricted execution profile for approved runtimes; not a general-purpose host.",
        "implemented", "managed_sandbox", ("build", "run", "test"),
        ("python",),
    ),
    EngineeringCapability(
        "external-connector", "execution_profile", "cross_domain", "External tool connector",
        "Typed, permission-scoped integration to an approved external service or tool.",
        "planned", "external_connector", ("inspect", "edit", "build", "simulate", "export"),
    ),
    EngineeringCapability(
        "local-agent", "execution_profile", "cross_domain", "Smart BethG Local Agent",
        "Future user-approved bridge for local files, USB/serial devices and physical boards.",
        "planned", "local_agent", ("inspect", "build", "flash", "serial_monitor"),
    ),
)

WORKSPACE_TYPES = (
    {
        "id": "software",
        "name": "Software Engineering",
        "status": "foundation_available",
        "description": "Software project workspace; engineering-specific Lab experience is a later UI integration.",
    },
    {
        "id": "hardware",
        "name": "Hardware Engineering",
        "status": "planned",
        "description": "Electronics, embedded firmware, schematics, PCB and simulation workspace.",
    },
    {
        "id": "software_hardware",
        "name": "Software + Hardware",
        "status": "planned",
        "description": "Linked software and hardware workspaces with shared project context and separate histories.",
    },
)


def list_engineering_capabilities(domain: str | None = None) -> dict:
    """Return public capability metadata; never expose images, secrets or host paths."""
    normalized = (domain or "").strip().lower()
    valid_domains = {"", "software", "hardware", "embedded", "cross_domain"}
    if normalized not in valid_domains:
        raise ValueError("Unsupported engineering capability domain.")
    included_domains = {
        "": {"software", "hardware", "embedded", "cross_domain"},
        "software": {"software", "embedded", "cross_domain"},
        "hardware": {"hardware", "embedded", "cross_domain"},
        "embedded": {"embedded", "cross_domain"},
        "cross_domain": {"cross_domain"},
    }[normalized]
    capabilities = [
        item.public_dict()
        for item in CAPABILITIES
        if item.domain in included_domains
    ]
    return {
        "registry_version": 1,
        "workspace_types": [dict(item) for item in WORKSPACE_TYPES],
        "capabilities": capabilities,
        "status_legend": {
            "implemented": "The application contains this execution path; operator configuration may still disable it.",
            "foundation_available": "A general workspace foundation exists; the dedicated engineering interface is not implied.",
            "catalog_only": "The target is identified but no build, simulator or physical-device integration is enabled.",
            "integration_candidate": "An external tool has been identified; no account, connector or tool access is implied.",
            "planned": "Not implemented or enabled.",
        },
    }
