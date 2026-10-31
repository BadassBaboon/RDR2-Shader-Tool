# Red Dead Redemption 2 Shader Tool

Shader decompiler, compiler, and modding toolkit for Red Dead Redemption 2 on PC.

Supports both Vulkan (the game's default API) and DirectX 12. Decompiles compiled shaders into HLSL or GLSL, injects modified bytecode back into RAGE `SGD1` (`.fxdb`) databases, maps RenoDX shader hashes directly to game shaders, and deploys directly to Lenny's Mod Loader (LML).

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
| RenoDX hash formula | CRC32 of uncompressed SPIR-V bytecode | CRC32 of uncompressed DXBC bytecode |
| Decompiler | `compilers/spirv-cross.exe` | `compilers/decomp.exe` (RenoDX) or `dxil-spirv` |
| Compiler | `compilers/dxc.exe -spirv` or `glslc.exe` | `compilers/dxc.exe -T <stage>_6_0` |
| Deployment target | `<GamePath>\lml\<ModName>\shaders_x64\0xFEEB1B85.bin` | `<GamePath>\lml\<ModName>\shaders_x64\0x8068F4F9.bin` |

---

## RenoDX Workflow & Shader Cross-Referencing

RenoDX uses standard IEEE 802.3 CRC32 over uncompressed shader bytecode (`renodx::utils::hash::ComputeCRC32`) to identify shaders in memory. In RDR2, this corresponds to the uncompressed SPIR-V bytecode (Vulkan) and the uncompressed DXBC container (DX12).

### RenoDX to LML Modding Cycle
1. **Identify in Game**: In game, identify what shader draws an object or effect using RenoDX devkit or the ReShade overlay. Note the 32-bit hash (for example, `0x2FFB1EF2`).
2. **Search in Shader Tool**: Paste the hash (or the RenoDX dump filename, such as `0x2FFB1EF2.vert.spv` or `0x59C1A819.ps_6_0.cso`) into the search bar in the **Shaders** tab, or run:
   ```bash
   r2sm find 0x2FFB1EF2
   ```
3. **Inspect Reflection**: View the shader's constant buffers, matrix bindings, and parameter names.
4. **Decompile**: Click **Decompile to HLSL** or run `r2sm decompile <name>`.
5. **Edit Math**: Open the generated `.hlsl` file in your preferred editor. Add custom lighting math, color grading, or post-processing adjustments.
6. **Compile**: Save the file. If Watch Mode is enabled in the GUI, the tool compiles it automatically.
7. **Repack**: Repack the modified shader into the target `.fxdb` container.
8. **Deploy to LML**: Click **Deploy Mod to Lenny's Mod Loader** or run `r2sm lml deploy`. Launch RDR2 to test the change in-game.

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

## Extracting Game Shaders with CodeX

Red Dead Redemption 2 stores its shader databases inside `shaders_x64.rpf` in your game installation folder. Use your own copy of CodeX (or OpenIV) to extract them:

1. Open `shaders_x64.rpf` in CodeX.
2. Extract the shader binary files to a folder on your PC or directly into `fxdb_files/` in this repository.
3. CodeX exports these entries using their Rage hash filenames. The tool automatically maps them, or you can rename them:
   - `0xFEEB1B85.bin` = `sga_vulkan_final.fxdb` (Main Vulkan shader library, 12,883 shaders)
   - `0x8068F4F9.bin` = `sga_win32_60_final.fxdb` (Main DirectX 12 shader library, 12,255 shaders)
   - `0xA8C90D00.bin` = `sga_vulkan_final_init.fxdb` (Vulkan initialization shaders, 369 shaders)
   - `0x2A25B571.bin` = `sga_win32_60_final_init.fxdb` (DirectX 12 initialization shaders, 367 shaders)
4. Launch the shader tool and point to your extracted folder using the **Folder...** button or the **Extraction Guide** dialog.

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
Search the indexed database by name, RenoDX hash, CRC32, stage, or API:
```bash
# Search by RenoDX hash (from in-game overlay or RenoDX dump)
r2sm find 0x2FFB1EF2

# Search by RenoDX dump filename
r2sm find 0x2FFB1EF2.vert.spv

# Search for water shaders in Vulkan
r2sm find water -s ps -a vulkan

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
r2sm unpack shaders_dump/sga_vulkan_final.fxdb

# Batch repack all modified files from compiled/ into a target .fxdb
r2sm repack shaders_dump/sga_vulkan_final.fxdb
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
      "args": ["<PathToRepository>\\r2mcp.py"]
    }
  }
}
```

Registered tools:
- `r2sm_status`: Check toolchain and game path configuration.
- `r2sm_find`: Search shader catalog by keyword, RenoDX hash, stage, or CRC32.
- `r2sm_info`: Inspect shader parameters, RenoDX dump names, register bindings, and cbuffer layouts.
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
├── shaders_dump/                 # Optional local extracted shader dump directory
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
