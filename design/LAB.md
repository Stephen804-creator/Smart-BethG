# Lab and Runtime Registry Rules (agents: read before touching the Lab)

## Structure
- One Lab entry (menu drawer). It opens 3 workspaces: Software, Hardware, Software + Hardware (Beta).
- Each workspace has its own history. Both-sessions link to a Software version and a Hardware version; they never copy them.
- The Lab has no competition rules. A future arena app opens the same workspace and adds rules.

## Registry entry must record
type (software/firmware/hdl/pcb), toolchain + pinned version, how it is checked, target (virtual board/real board/none), limits, license, review status.

## License policy (never skip)
No tool joins the registry until its license/terms are checked and written down here.

Approved (checked Oct 2026): KiCad (GPL-3+, libs CC-BY-SA-4.0), Renode (MIT), PlatformIO Core (Apache-2.0), Verilator (LGPL-3 or Artistic-2), GHDL (GPL-2), ngspice (BSD-3), QEMU (GPL-2), KiCanvas (MIT), tscircuit (MIT), atopile (MIT).
Needs license or deal: Wokwi (personal non-commercial only), Altium (developer license + partner agreement), Vivado (licensing changing).
Not reviewed: Onshape, Tinkercad, Proteus, Arduino toolchains, PlatformIO downloaded toolchains/board packages.

Rules: keep GPL/LGPL tools unmodified and separate; do not embed Verilator in a closed simulator product; set PLATFORMIO_SETTING_ENABLE_TELEMETRY=No on servers; credit KiCad libraries.
This is not legal advice. Get a lawyer to confirm before launch.

## Safety
User code runs only in an isolated sandbox service, never in the main app server.
