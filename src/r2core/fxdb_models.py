"""Data structures and enums for RDR2 RAGE SGA v1 (SGD1) shader files."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


class ResourceClass(IntEnum):
    ShaderResource = 0
    UnorderedAccess = 1
    Sampler = 2
    CBuffer = 3


class ResourceType(IntEnum):
    CBuffer = 0
    Typed = 1
    Texture = 2
    Sampler = 3
    UavRwTyped = 4
    Structured = 5
    UavRwStructured = 6
    ByteAddress = 7
    UavRwByteAddress = 8
    UavAppendStructured = 9
    UavConsumeStructured = 10
    UavRwStructuredWithCounter = 11
    UavRwTexture = 12
    Invalid = 13


class ImageDimension(IntEnum):
    Texture1D = 0
    Texture2D = 1
    TextureCUBE = 2
    Texture3D = 3
    Buffer = 4
    Invalid = 5


class VariableType(IntEnum):
    Bool = 0
    Int = 1
    Int2 = 2
    Int3 = 3
    Int4 = 4
    UInt = 5
    UInt2 = 6
    UInt3 = 7
    UInt4 = 8
    Float = 9
    Float2 = 10
    Float3 = 11
    Float4 = 12
    Matrix34 = 13
    Matrix44 = 14
    Invalid = 15

    @classmethod
    def get_hlsl_type(cls, val: int) -> str:
        names = {
            cls.Bool: "bool",
            cls.Int: "int", cls.Int2: "int2", cls.Int3: "int3", cls.Int4: "int4",
            cls.UInt: "uint", cls.UInt2: "uint2", cls.UInt3: "uint3", cls.UInt4: "uint4",
            cls.Float: "float", cls.Float2: "float2", cls.Float3: "float3", cls.Float4: "float4",
            cls.Matrix34: "float3x4", cls.Matrix44: "float4x4",
        }
        return names.get(val, f"var_type_{val}")

    @classmethod
    def byte_size(cls, val: int) -> int:
        sizes = {
            cls.Bool: 4, cls.Int: 4, cls.UInt: 4, cls.Float: 4,
            cls.Int2: 8, cls.UInt2: 8, cls.Float2: 8,
            cls.Int3: 12, cls.UInt3: 12, cls.Float3: 12,
            cls.Int4: 16, cls.UInt4: 16, cls.Float4: 16,
            cls.Matrix34: 64, cls.Matrix44: 64,
        }
        return sizes.get(val, 4)


class AnnotationType(IntEnum):
    Int = 0
    Float = 1
    String = 2


@dataclass
class ShaderAnnotation:
    raw_type_name_hash: int
    raw_value: int
    name_hash: int
    type: AnnotationType
    val_int: int = 0
    val_float: float = 0.0
    val_str: str = ""


@dataclass
class ShaderElement:
    name: str
    semantic_name: str
    var_type: VariableType
    array_size: int
    start_offset: int
    name_hash: int
    semantic_name_hash: int
    default_value: Optional[bytes] = None
    annotations: List[ShaderAnnotation] = field(default_factory=list)


@dataclass
class ShaderResource:
    name: str
    semantic_name: str
    resource_type: ResourceType
    resource_class: ResourceClass
    image_dimension: ImageDimension
    bind_point: int
    byte_size: int
    name_hash: int
    semantic_name_hash: int
    elements: List[ShaderElement] = field(default_factory=list)
    annotations: List[ShaderAnnotation] = field(default_factory=list)


@dataclass
class ShaderData:
    raw_blob: bytes
    resources: List[ShaderResource] = field(default_factory=list)
    elements: List[ShaderElement] = field(default_factory=list)
    annotations: List[ShaderAnnotation] = field(default_factory=list)
    name_heap: bytes = b""
    default_values: bytes = b""


@dataclass
class ShaderUsage:
    raw_bytes: bytes  # 144 bytes total (72 inputs + 72 outputs)
    inputs_mask: int = 0
    inputs_sv_mask: int = 0
    outputs_mask: int = 0
    outputs_sv_mask: int = 0


@dataclass
class ShaderRecord:
    stage: str                 # "VS", "PS", "GS", "DS", "HS", "CS"
    index: int                 # 0-based index in stage array
    name: str                  # e.g. "VS_Clear_Wrapped"
    feat: int                  # Feature level / wavesize (e.g. 50)
    bytecode: bytes            # Raw or decompressed shader binary
    raw_bytecode: bytes        # As stored in file (may be Oodle compressed)
    signature: int             # 64-bit signature / hash
    usage: ShaderUsage
    data: ShaderData
    is_compressed: bool = False
    blob_offset: int = 0
    crc: int = 0               # CRC32 of decompressed bytecode

    @property
    def is_spirv(self) -> bool:
        return len(self.bytecode) >= 4 and self.bytecode[:4] == b'\x03\x02#\x07'

    @property
    def is_dxbc(self) -> bool:
        return len(self.bytecode) >= 4 and self.bytecode[:4] == b'DXBC'


@dataclass
class EffectRecord:
    name: str
    data_buffer_size: int
    stage_indices: Dict[str, List[int]]   # {"VS": [...], "PS": [...], ...}
    unk_struct: bytes                     # 72 bytes
    unk1: int                             # u64
    rasterizer_states: bytes              # array of 16-byte structs
    depth_stencil_states: bytes           # array of 24-byte structs
    blend_states: bytes                   # array of 68-byte structs
    sampler_states: bytes                 # array of 36-byte structs
    techniques: bytes                     # array of 4-byte structs
    render_shader_sets: bytes             # array of 20-byte structs
    unks: List[List[int]]
    sampler_state_refs: bytes             # array of 2-byte structs
    shader_data_raw: bytes
    prop_shader_data_raw: bytes
    string_table: bytes


@dataclass
class FXDBFile:
    path: Optional[str]
    magic: str = "SGD1"
    shaders: Dict[str, List[ShaderRecord]] = field(default_factory=lambda: {
        "VS": [], "PS": [], "GS": [], "DS": [], "HS": [], "CS": []
    })
    effects: List[EffectRecord] = field(default_factory=list)
    tail_padding: bytes = b""

    @property
    def total_shaders(self) -> int:
        return sum(len(arr) for arr in self.shaders.values())

    @property
    def total_effects(self) -> int:
        return len(self.effects)
