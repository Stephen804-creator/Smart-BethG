# Lab and Runtime Registry Rules (agents: read before touching the Lab)

## Structure
- One Lab entry (menu drawer). It opens 3 workspaces: Software, Hardware, Software + Hardware (Beta).
- Each workspace has its own history. Both-sessions link to a Software version and a Hardware version; they never copy them.
- The Lab has no competition rules. A future arena app opens the same workspace and adds rules.
- "Runtimes & tools" stays a separate screen from Connectors. Do not merge them.

## One engine, two layouts
Phone and desktop use the same data, tools and AI. Only the layout changes with screen width.

### Desktop/tablet (see smartbethg-lab-desktop.html)
Top bar (Software/Hardware/Both, Export, Run) | icon bar | side panel | editor or canvas with tabs | bottom panel | AI chat on the right | status bar.

### Phone (see smartbethg-mockup.html)
One panel at a time with a bottom bar.
- Hardware: Lab > Hardware > Choose tools > workspace. Bottom bar: Board, Simulate, AI, More. Board = same dense board file (layers, pinch to zoom, checks). Detailed manual editing (routing) is for tablet/desktop via Edit in KiCad; say this plainly in the app.
- Software: Lab > Software > workspace. Bottom bar: Code, Preview, AI, More.
- More holds Files, Tools, History, Export.

## Tool picker (Hardware)
User ticks tools (only license-approved ones are listed). The workspace builds from the choice: top chips, Simulate tabs and AI abilities follow the selected tools. Untick a tool and its tab disappears. If two tools do the same job, choose by language or show a Simulator dropdown. Limit how many heavy tools run at once; streamed KiCad costs credits per minute.

## Software and hardware features
- Software: code files + Preview (app runs in a sandboxed frame, tested before export).
- Hardware tabs: Schematic, PCB, 3D, Simulation, Edit in KiCad.
- Hardware View = KiCanvas dense board view (read-only). Edit in KiCad = real KiCad streamed from the sandbox. The AI edits project files; the view reloads.
- Simulation = Renode (firmware) + ngspice (electrical). Always label: simulated, not a guarantee of real-world behavior.
- Export: Project ZIP, Gerber ZIP, Parts CSV, Push to GitHub.

## Branding
Do not use the VS Code name, logo or Marketplace. Extensions come from Open VSX. Embedded third-party tools (KiCad) stay unmodified with their own look. Do not use the KiCad logo until the KiCad project confirms permission; plain-text name only.

## Registry entry must record
type (software/firmware/hdl/pcb), toolchain + pinned version, how it is checked, target (virtual board/real board/none), limits, license, review status.

## License policy (never skip)
No tool joins the registry until its license/terms are checked and written down here.

Approved (checked Oct 2026): KiCad (GPL-3+, libs CC-BY-SA-4.0), Renode (MIT), PlatformIO Core (Apache-2.0), Verilator (LGPL-3 or Artistic-2), GHDL (GPL-2), ngspice (BSD-3), QEMU (GPL-2), KiCanvas (MIT), tscircuit (MIT), atopile (MIT), KasmVNC (GPL-2), Eclipse Theia (EPL-2.0).
Needs license or deal: Wokwi (personal non-commercial only), Altium (developer license + partner agreement), Vivado (licensing changing).
Not reviewed: Onshape, Tinkercad, Proteus, Arduino toolchains, OpenVSCode Server, code-server, PlatformIO downloaded toolchains/board packages.

Rules: keep GPL/LGPL tools unmodified and separate; do not embed Verilator in a closed simulator product; set PLATFORMIO_SETTING_ENABLE_TELEMETRY=No on servers; credit KiCad libraries and keep KiCanvas's MIT notice.
This is not legal advice. Get a lawyer to confirm before launch.

## Safety
User code runs only in an isolated sandbox service, never in the main app server.
