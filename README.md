# Red Dead Redemption 2 Shader Tool

A modern GUI & CLI shader management toolkit and decompiler/recompiler for **Red Dead Redemption 2 (RDR2)**. 

Supports both **Vulkan (SPIR-V)** — the game's default rendering backend — and **DirectX 12 (DXIL / SM 6.x)**. Designed for writing custom shader math, enhancing visual rendering, adding custom post-processing, and packaging mods cleanly with **Lenny's Mod Loader (LML)** without modifying `.rpf` archives.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![Vulkan](https://img.shields.io/badge/Vulkan-SPIR--V-red) ![DirectX 12](https://img.shields.io/badge/DirectX12-SM%206.x-green) ![LML](https://img.shields.io/badge/LML-Ready-orange)

---

## Features

### 🔧 Decompile & Compile
- **Vulkan (Default)**: Decompile Khronos SPIR-V bytecode back to editable HLSL or GLSL using `spirv-cross` and SPIR-V assembly using `spirv-dis`.
- **DirectX 12**: Decompile DXIL/DXBC bytecode to high-level HLSL using RenoDX `decomp.exe` or `dxil-spirv + spirv-cross`.
- **Reflection Metadata Restoration**: Automatically annotates decompiled source code with constant buffer structures, slot bindings, and variable names extracted directly from the game's `SGD1` reflection heap.
- **Auto-Compile (Watch Mode)**: Saving your `.hlsl` or `.glsl` file in VS Code or Notepad++ automatically triggers instant recompilation and validation in the background.
- **Bytecode Validation & Optimization**: Built-in validation via `spirv-val` and optional optimization via `spirv-opt`.

### 📦 RAGE SGA v1 (`SGD1` / FXDB) Architecture
- Native binary parser and streaming injector for RDR2's proprietary `SGD1` shader library format.
- **Oodle Kraken Decompression & Compression**: Handles native compressed shader blobs (`0xDCE7` header) transparently via local `oo2core_5_win64.dll`.
- **Byte-Identical Round-Trip**: Guarantees bit-for-bit identical repacking when no shaders are mutated.
- **Unpack & Repack**: Batch-extract all shaders from an archive into organized folders by stage, edit them, and stream them back into the `.fxdb` library.

### 🚀 Lenny's Mod Loader (LML) Integration (Zero RPF Editing)
- **1-Click Deployment**: Packages modified `.fxdb` files into `G:\Red Dead Redemption 2\lml\<ModName>\shaders_x64\` with the required virtual hashes (`0xFEEB1B85.bin` for Vulkan, `0x8068F4F9.bin` for DX12).
- **Auto-Generated `install.xml`**: Emits `<FileReplacement>` nodes targeting the game's VFS.
- Keeps your base game files completely clean and untouched.

### 🤖 Model Context Protocol (MCP) Server
- Ships a built-in MCP server (`python r2mcp.py`) so AI coding agents can search shaders, inspect constant buffer layouts, decompile, patch math, and test recompiled shaders automatically.

---

## Included Local Toolchain (`compilers/`)

All compiler and decompiler executables and runtime DLLs ship locally inside `compilers/`:

| Tool | Purpose | Source |
|---|---|---|
| `spirv-cross.exe` | SPIR-V → HLSL / GLSL Decompiler | [KhronosGroup/SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross) |
| `spirv-dis.exe` | SPIR-V Binary → Assembly Disassembler | [KhronosGroup/SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |
| `spirv-as.exe` | SPIR-V Assembly → Binary Assembler | [KhronosGroup/SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |
| `spirv-val.exe` | SPIR-V Bytecode Validator | [KhronosGroup/SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |
| `spirv-opt.exe` | SPIR-V Bytecode Optimizer | [KhronosGroup/SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) |
| `glslc.exe` | GLSL / HLSL → SPIR-V Compiler | [Google/shaderc](https://github.com/google/shaderc) |
| `glslangValidator.exe` | Khronos Reference Compiler | [KhronosGroup/glslang](https://github.com/KhronosGroup/glslang) |
| `dxc.exe` | DX12 Compiler (with SPIR-V support) | [DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler) |
| `decomp.exe` | DX12 Shader Decompiler | [RenoDX](https://github.com/clshortfuse/renodx) |
| `dxil-spirv.exe` | DXIL → SPIR-V Converter | [HansKristian-Work/dxil-spirv](https://github.com/HansKristian-Work/dxil-spirv) |
| `oo2core_5_win64.dll` | Oodle Kraken Decompression/Compression | Epic Games / RAD Game Tools |

---

## Quick Start

### Graphical User Interface (GUI)
Run with Python:
```bash
python main.py
```
Or double-click `r2sm_gui.bat`.

### Command Line Interface (CLI)
Inspect system status:
```bash
python main.py status
```
Or via `r2sm.bat`:
```bash
r2sm status
```

---

## CLI Command Reference

### 1. System & Catalog Lookup
```bash
# Check status of compilers, game installation, and LML
r2sm status

# Search shaders by name, hash, stage, or effect
r2sm find clear -s vs -a vulkan
r2sm find 0x4CFE91CC

# Display registers, constant buffers, and reflection metadata
r2sm info VS_Clear_Wrapped -a vulkan

# List all effects present in the database
r2sm effects -a vulkan
```

### 2. Decompile & Compile
```bash
# Decompile a shader to editable HLSL
r2sm decompile VS_Clear_Wrapped -a vulkan

# Decompile a raw binary file on disk
r2sm decompile path/to/shader.spv -o my_shader.hlsl

# Compile HLSL source to Vulkan SPIR-V
r2sm compile source/vulkan/VS/VS_Clear_Wrapped.vs_6_0.hlsl -a vulkan

# Compile HLSL source to DirectX 12 DXIL CSO
r2sm compile source/dx12/PS/my_shader.ps_6_0.hlsl -a dx12
```

### 3. Archive Management (Unpack & Repack)
```bash
# Unpack all shaders from an FXDB library into stage folders
r2sm unpack E:/RealityVAddon/RDR2_Shaders/fxdb/sga_vulkan_final_init.fxdb

# Repack modified shaders back into the FXDB library (preserving everything else)
r2sm repack E:/RealityVAddon/RDR2_Shaders/fxdb/sga_vulkan_final_init.fxdb
```

### 4. Lenny's Mod Loader Deployment
```bash
# Deploy modified libraries to game via LML
r2sm lml deploy sga_vulkan_final_init_modified.fxdb -n RealityV_Shaders

# Inspect currently installed LML mods
r2sm lml status
```

---

## Directory Structure

```
├── compilers/                    ← Local self-contained compilers and tools
├── source/
│   ├── vulkan/                   ← Editable Vulkan HLSL/GLSL source files
│   └── dx12/                     ← Editable DX12 HLSL source files
├── compiled/
│   ├── vulkan/                   ← Recompiled .spv binaries
│   └── dx12/                     ← Recompiled .cso binaries
├── decompiled/                   ← Disassembly and reference decompilations
├── fxdb_files/                   ← Working .fxdb shader libraries
├── src/
│   ├── r2core/                   ← Binary parser, compilers, Oodle, catalog, LML
│   ├── r2cli/                    ← Command-line interface
│   ├── r2ui/                     ← Modern Tkinter GUI
│   └── r2mcp/                    ← Model Context Protocol server
├── main.py                       ← Unified entry point
├── r2sm.bat                      ← CLI launcher
├── r2sm_gui.bat                  ← GUI launcher
└── r2mcp.py                      ← MCP launcher
```

---

## Modding Workflow Tutorial

1. **Browse**: Open the tool, switch API to **Vulkan** (or DX12), and use the **Shader Browser** to search for the effect you want to modify (e.g. lighting, sky, water, postfx).
2. **Decompile**: Click **▼ Decompile to HLSL**. The shader code is saved to `source/<api>/<stage>/<name>.hlsl`.
3. **Edit Math**: Open the file in your preferred editor (VS Code, Notepad++, etc.) and edit or add custom shader math.
4. **Compile**: With **Watch Mode** enabled, saving your file automatically compiles and validates the shader into `compiled/<api>/`.
5. **Repack**: On the **FXDB Builder** tab, click **📤 Repack** to inject your modified bytecode into the library.
6. **Deploy**: On the **Lenny's Mod Loader** tab, click **🚀 Deploy to Game**. Launch RDR2 and enjoy your custom shaders!

---

## Credits & Acknowledgments

- Architecture patterns based on [GTA V Shader Manager](https://github.com/RealityVAddon/gta5-shadermanager).
- Binary structures and format reversal based on [CodeX](https://github.com/dexyfex/CodeWalker) (RDR2 Rpf8 & FxdbFile).
- Vulkan tools: [KhronosGroup/SPIRV-Cross](https://github.com/KhronosGroup/SPIRV-Cross) (Apache 2.0) and [KhronosGroup/SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools).
- DX12 compiler: [Microsoft DirectXShaderCompiler](https://github.com/microsoft/DirectXShaderCompiler) (MIT License).
- DX12 decompiler: [RenoDX](https://github.com/clshortfuse/renodx).
- Compression: RAD Game Tools / Epic Games (Oodle Kraken).

---

## License

MIT License
