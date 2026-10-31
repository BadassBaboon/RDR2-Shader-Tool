# Red Dead Redemption 2 Shader Tool

Shader decompiler, compiler, and modding toolkit for Red Dead Redemption 2 on PC.

Supports both Vulkan (the game's default API) and DirectX 12. Decompiles compiled shaders into HLSL or GLSL, injects modified bytecode back into RAGE `SGD1` (`.fxdb`) databases, and deploys directly to Lenny's Mod Loader (LML).

---

## Technical Specifications

| Property | Vulkan Backend | DirectX 12 Backend |
|---|---|---|
| Default in game | Yes | No |
| Primary shader archive | `sga_vulkan_final.fxdb` (`0xFEEB1B85.bin`) | `sga_win32_60_final.fxdb` (`0x8068F4F9.bin`) |
| Init shader archive | `sga_vulkan_final_init.fxdb` (`0xA8C90D00.bin`) | `sga_win32_60_final_init.fxdb` (`0x2A25B571.bin`) |
| Container format | RAGE `SGD1` (`0x31444753`) | RAGE `SGD1` (`0x31444753`) |
| Bytecode format | Khronos SPIR-V (`0x07230203`) | Microsoft DXBC / DXIL (`DXBC` chunk container) |
| On-disk compression | Oodle Kraken (`0xDCE7` 12-byte header) | Uncompressed raw bytecode |
| Decompiler | `compilers/spirv-cross.exe` | `compilers/decomp.exe` (RenoDX) or `dxil-spirv` |
| Compiler | `compilers/dxc.exe -spirv` or `glslc.exe` | `compilers/dxc.exe -T <stage>_6_0` |
| Deployment target | `G:\Red Dead Redemption 2\lml\<ModName>\shaders_x64\0xFEEB1B85.bin` | `G:\Red Dead Redemption 2\lml\<ModName>\shaders_x64\0x8068F4F9.bin` |

---

## Local Toolchain (`compilers/`)

All binaries and dynamic libraries are self-contained in the repository:

- `spirv-cross.exe`: Translates SPIR-V bytecode into HLSL or GLSL.
- `spirv-dis.exe` and `spirv-as.exe`: SPIR-V disassembler and assembler.
- `spirv-val.exe` and `spirv-opt.exe`: Bytecode validation and optimization.
- `glslc.exe` and `glslangValidator.exe`: Reference SPIR-V compilers from Google and Khronos.
- `dxc.exe`, `dxcompiler.dll`, `dxil.dll`: Microsoft DirectX Shader Compiler with SPIR-V backend.
- `decomp.exe`: DX12 DXBC and DXIL decompiler from the RenoDX project.
- `dxil-spirv.exe`: Direct DXIL to SPIR-V converter.
- `oo2core_5_win64.dll`: Oodle Kraken 64-bit decompression and compression runtime.

---

## Quick Start

### Graphical Interface
Launch the GUI:
```bat
.\r2sm_gui.bat
```
Alternatively:
```bash
python main.py
```

### Command Line Interface
Check toolchain and environment status:
```bat
.\r2sm.bat status
```

---

## CLI Reference

### 1. Catalog and Reflection
Search the indexed database by name, CRC32, stage, or API:
```bash
# Search for water shaders in Vulkan
r2sm find water -s ps -a vulkan

# Search for a shader by 32-bit CRC hash
r2sm find 0xC03F4446

# Print constant buffers, register slots, and variable layouts
r2sm info VS_Rage_TransformPosCpvNrmTex_Wrapped -a vulkan

# List all effect groups in the active library
r2sm effects -a vulkan
```

### 2. Decompilation
Decompile a shader from the game database into editable HLSL:
```bash
# Decompile by shader name
r2sm decompile VS_Clear_Wrapped -a vulkan

# Decompile by library, stage, and index
r2sm decompile --fxdb sga_vulkan_final.fxdb --stage ps --index 0 --lang hlsl

# Decompile a standalone binary file on disk
r2sm decompile path/to/shader.spv -o my_shader.hlsl
```
Decompiled source files are written to `source/<api>/<stage>/<name>.<stage>_6_0.hlsl`.

### 3. Compilation
Compile edited HLSL or GLSL source back to bytecode:
```bash
# Compile Vulkan pixel shader to SPIR-V
r2sm compile source/vulkan/PS/my_shader.ps_6_0.hlsl -a vulkan

# Compile DirectX 12 pixel shader to DXIL CSO
r2sm compile source/dx12/PS/my_shader.ps_6_0.hlsl -a dx12
```
Output bytecode is written to `compiled/<name>.spv` (Vulkan) or `compiled/<name>.cso` (DX12).

### 4. Archive Repacking and Injection
Inject recompiled bytecode into the `.fxdb` container:
```bash
# Single shader injection
r2sm inject --fxdb sga_vulkan_final.fxdb --stage ps --index 0 --input compiled/ps_00000000.spv

# Batch unpack all shaders into directories grouped by stage
r2sm unpack E:/RealityVAddon/RDR2_Shaders/fxdb/sga_vulkan_final.fxdb

# Batch repack all modified files from compiled/ into a target .fxdb
r2sm repack E:/RealityVAddon/RDR2_Shaders/fxdb/sga_vulkan_final.fxdb
```

### 5. Lenny's Mod Loader (LML) Deployment
Deploy repacked shader libraries to Lenny's Mod Loader without modifying base `.rpf` files:
```bash
# Deploy compiled FXDB to LML with mod folder name "RealityV_Shaders"
r2sm lml deploy compiled/sga_vulkan_final.fxdb -n RealityV_Shaders

# Inspect currently active LML mods
r2sm lml status
```

---

## Modding Workflow

1. **Locate the Shader**: Open the tool or run `r2sm find <keyword>` to find the shader associated with the material, lighting pass, or post-process pass you want to change.
2. **Decompile**: Run `r2sm decompile <name>` or click **Decompile to HLSL** in the GUI. The tool writes the source file with annotated constant buffer structures to `source/`.
3. **Modify Code**: Open the `.hlsl` file in your editor. Add or modify equations in the pixel shader entry point.
4. **Compile**: Run `r2sm compile <file>` or save the file in your editor while Watch Mode is active in the GUI.
5. **Inject and Repack**: Click **Repack Modified Shaders** in the FXDB Builder tab, or run `r2sm repack`.
6. **Deploy to LML**: Click **Deploy Mod to Lenny's Mod Loader** or run `r2sm lml deploy`. Launch Red Dead Redemption 2.

---

## Model Context Protocol (MCP) Integration

The repository includes a JSON-RPC 2.0 stdio MCP server for agentic pair programming:
```bash
python r2mcp.py
```

To configure in Claude Desktop or Antigravity, add the following entry to your `mcpServers` configuration:
```json
{
  "mcpServers": {
    "rdr2-shader-tool": {
      "command": "python",
      "args": ["E:\\RealityVAddon\\RDR2-Shader-Tool\\r2mcp.py"]
    }
  }
}
```

Registered tools:
- `r2sm_status`: Check toolchain and game path configuration.
- `r2sm_find`: Search shader catalog by keyword, stage, or CRC32.
- `r2sm_info`: Inspect shader parameters, register bindings, and cbuffer layouts.
- `r2sm_effects`: List effect groups.
- `r2sm_decompile`: Decompile a shader to HLSL or GLSL.
- `r2sm_compile`: Recompile source code to SPIR-V or DXIL bytecode.
- `r2sm_unpack`: Unpack `.fxdb` containers into loose stage folders.
- `r2sm_repack`: Repack modified bytecode into `.fxdb` containers.
- `r2sm_inject`: Inject a single bytecode file into an `.fxdb`.
- `r2sm_lml_deploy`: Deploy repacked `.fxdb` files into the LML virtual filesystem.
- `r2sm_lml_status`: Inspect installed LML mods.

---

## Project Structure

```
├── compilers/                    # Shipped compilers, decompilers, and DLLs
├── source/                       # Decompiled and editable HLSL/GLSL files
├── compiled/                     # Recompiled .spv and .cso binary blobs
├── decompiled/                   # Unpacked loose shaders and disassemblies
├── fxdb_files/                   # Working .fxdb shader databases
├── src/
│   ├── r2core/                   # SGD1 parser, Oodle compression, compilers, LML VFS
│   ├── r2cli/                    # Command-line subcommands
│   ├── r2ui/                     # Dark RDR2-themed desktop interface
│   └── r2mcp/                    # Model Context Protocol server
├── main.py                       # CLI and GUI entry point
├── r2sm.bat                      # CLI batch script
├── r2sm_gui.bat                  # GUI batch script
└── r2mcp.py                      # MCP server runner
```

---

## Credits and Reference Implementations

- Base architecture and workflow patterns: [GTA V Shader Manager](https://github.com/RealityVAddon/gta5-shadermanager) by RealityVAddon.
- RAGE binary formats and Rpf8 parsing: [CodeX](https://github.com/dexyfex/CodeWalker) by dexyfex.
- Vulkan toolchain: Khronos Group (`spirv-cross`, `spirv-tools`, `glslang`).
- DX12 compiler: Microsoft DirectX Shader Compiler.
- DX12 decompiler: RenoDX (`decomp.exe`).
- Compression runtime: RAD Game Tools and Epic Games (Oodle Kraken).

---

## License

MIT License.
