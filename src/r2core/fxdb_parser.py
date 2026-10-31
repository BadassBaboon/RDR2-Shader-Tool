"""High-performance binary parser and repacker for RDR2 SGD1 (.fxdb) shader files."""

import io
import os
import shutil
import struct
from pathlib import Path
from typing import BinaryIO, Callable, Dict, List, Optional, Set, Tuple, Union

from . import hashing, oodle
from .fxdb_models import (
    AnnotationType, EffectRecord, FXDBFile, ImageDimension,
    ResourceClass, ResourceType, ShaderAnnotation, ShaderData,
    ShaderElement, ShaderRecord, ShaderResource, ShaderUsage,
    VariableType
)

STAGES = ("VS", "PS", "GS", "DS", "HS", "CS")
SGD1_MAGIC = b"SGD1"


class FXDBParser:
    """Parses RDR2 SGD1 binary archives."""

    def __init__(self, stream: BinaryIO, decompress_bytecode: bool = True):
        self.stream = stream
        self.decompress_bytecode = decompress_bytecode

    def read_u8(self) -> int:
        return struct.unpack("B", self.stream.read(1))[0]

    def read_u16(self) -> int:
        return struct.unpack("<H", self.stream.read(2))[0]

    def read_u32(self) -> int:
        return struct.unpack("<I", self.stream.read(4))[0]

    def read_u64(self) -> int:
        return struct.unpack("<Q", self.stream.read(8))[0]

    def read_str_1b(self) -> str:
        length = self.read_u8()
        if length == 0:
            return ""
        data = self.stream.read(length)
        # Strip trailing null if present
        return data.decode("latin-1", errors="replace").rstrip("\x00")

    def read_u32_array(self) -> List[int]:
        cnt = self.read_u32()
        if cnt == 0:
            return []
        fmt = f"<{cnt}I"
        return list(struct.unpack(fmt, self.stream.read(cnt * 4)))

    def read_bytes_array(self, elem_size: int) -> bytes:
        cnt = self.read_u32()
        return self.stream.read(cnt * elem_size)

    def parse_shader_data(self) -> ShaderData:
        start_pos = self.stream.tell()
        data_len = self.read_u32()
        raw_start = self.stream.tell()

        res_count = self.read_u16()
        elem_count = self.read_u16()
        ann_count = self.read_u16()
        dlen = self.read_u16()

        raw_resources = self.stream.read(res_count * 24)
        raw_elements = self.stream.read(elem_count * 24)
        raw_annotations = self.stream.read(ann_count * 8)

        # Remaining bytes in data block
        bytes_read = self.stream.tell() - raw_start
        remaining = data_len - bytes_read
        heap_and_defaults = self.stream.read(remaining) if remaining > 0 else b""

        # Calculate default values buffer size
        def_vals_size = 0
        elem_list: List[ShaderElement] = []
        for i in range(elem_count):
            e_offset = i * 24
            e_type, e_ann_count, e_arr_size, e_start_off, e_name_off, e_sem_off, e_def_off, e_ann_off, e_pad, e_nhash, e_shash = struct.unpack_from(
                "<BB7HII", raw_elements, e_offset
            )
            if e_def_off != 0:
                num = 1 if e_arr_size == 0 else e_arr_size
                def_vals_size += num * VariableType.byte_size(e_type)

        name_heap_size = len(heap_and_defaults) - def_vals_size
        name_heap = heap_and_defaults[:name_heap_size]
        default_vals = heap_and_defaults[name_heap_size:]

        def get_string_from_heap(rel_off: int) -> str:
            if rel_off < 0 or rel_off >= len(name_heap):
                return ""
            end = name_heap.find(b"\x00", rel_off)
            if end == -1:
                end = len(name_heap)
            return name_heap[rel_off:end].decode("utf-8", errors="replace")

        # Parse Annotations
        ann_list: List[ShaderAnnotation] = []
        for i in range(ann_count):
            a_off = i * 8
            tn_hash, val = struct.unpack_from("<II", raw_annotations, a_off)
            a_type = AnnotationType(tn_hash & 3)
            a_name_hash = tn_hash >> 2
            a = ShaderAnnotation(
                raw_type_name_hash=tn_hash,
                raw_value=val,
                name_hash=a_name_hash,
                type=a_type
            )
            if a_type == AnnotationType.Int:
                a.val_int = struct.unpack("<i", struct.pack("<I", val))[0]
            elif a_type == AnnotationType.Float:
                a.val_float = struct.unpack("<f", struct.pack("<I", val))[0]
            elif a_type == AnnotationType.String:
                str_off = int(val) - (ann_count - i) * 8
                a.val_str = get_string_from_heap(str_off)
            ann_list.append(a)

        # Parse Elements
        for i in range(elem_count):
            e_offset = i * 24
            e_type, e_ann_count, e_arr_size, e_start_off, e_name_off, e_sem_off, e_def_off, e_ann_off, e_pad, e_nhash, e_shash = struct.unpack_from(
                "<BB7HII", raw_elements, e_offset
            )
            # Resolve name
            name_rel = e_name_off - (elem_count - i) * 24 - ann_count * 8
            elem_name = get_string_from_heap(name_rel)

            sem_name = ""
            if e_sem_off != 0:
                sem_rel = e_sem_off - (elem_count - i) * 24 - ann_count * 8
                sem_name = get_string_from_heap(sem_rel)

            def_val_bytes = None
            if e_def_off != 0:
                d_rel = e_def_off - (elem_count - i) * 24 - ann_count * 8 - name_heap_size
                num = 1 if e_arr_size == 0 else e_arr_size
                sz = num * VariableType.byte_size(e_type)
                if 0 <= d_rel < len(default_vals):
                    def_val_bytes = default_vals[d_rel:d_rel + sz]

            elem = ShaderElement(
                name=elem_name,
                semantic_name=sem_name,
                var_type=VariableType(e_type),
                array_size=e_arr_size,
                start_offset=e_start_off,
                name_hash=e_nhash,
                semantic_name_hash=e_shash,
                default_value=def_val_bytes
            )
            elem_list.append(elem)

        # Parse Resources
        res_list: List[ShaderResource] = []
        for i in range(res_count):
            r_off = i * 24
            r_type_class, r_dim, r_bind, r_ann_c, r_elem_c, r_srt, r_elem_off, r_name_off, r_sem_off, r_bsize, r_ann_off, r_nhash, r_shash = struct.unpack_from(
                "<BBBBBBHHHHHII", raw_resources, r_off
            )
            r_res_type = ResourceType(r_type_class & 0xF)
            r_res_class = ResourceClass((r_type_class >> 4) & 0x3)
            r_dim_enum = ImageDimension(r_dim)

            name_rel = r_name_off - (res_count - i) * 24 - elem_count * 24 - ann_count * 8
            res_name = get_string_from_heap(name_rel)

            sem_name = ""
            if r_sem_off != 0:
                sem_rel = r_sem_off - (res_count - i) * 24 - elem_count * 24 - ann_count * 8
                sem_name = get_string_from_heap(sem_rel)

            # Link sub-elements
            sub_elems: List[ShaderElement] = []
            if r_elem_c > 0 and elem_list:
                e_start = (r_elem_off - (res_count - i) * 24) // 24
                if 0 <= e_start < len(elem_list):
                    sub_elems = elem_list[e_start:e_start + r_elem_c]

            res = ShaderResource(
                name=res_name,
                semantic_name=sem_name,
                resource_type=r_res_type,
                resource_class=r_res_class,
                image_dimension=r_dim_enum,
                bind_point=r_bind,
                byte_size=r_bsize,
                name_hash=r_nhash,
                semantic_name_hash=r_shash,
                elements=sub_elems
            )
            res_list.append(res)

        # Seek back to capture raw blob
        cur = self.stream.tell()
        self.stream.seek(start_pos)
        full_blob = self.stream.read(data_len + 4)
        self.stream.seek(cur)

        return ShaderData(
            raw_blob=full_blob,
            resources=res_list,
            elements=elem_list,
            annotations=ann_list,
            name_heap=name_heap,
            default_values=default_vals
        )

    def parse(self, filepath: Optional[str] = None) -> FXDBFile:
        start_magic = self.stream.read(4)
        if start_magic != SGD1_MAGIC:
            # Check if there is an 8-byte resource header prefix
            self.stream.seek(8)
            magic_8 = self.stream.read(4)
            if magic_8 == SGD1_MAGIC:
                magic = magic_8
            else:
                raise ValueError(f"Invalid magic {start_magic}, expected {SGD1_MAGIC}")
        else:
            magic = start_magic

        fxdb = FXDBFile(path=filepath, magic=magic.decode("latin-1"))

        # Parse Shaders for all 6 stages
        for stage in STAGES:
            count = self.read_u32()
            for idx in range(count):
                name = self.read_str_1b()
                feat = self.read_u8()
                bc_len = self.read_u32()
                blob_offset = self.stream.tell()
                raw_bc = self.stream.read(bc_len)
                sig = self.read_u64()

                usage_bytes = self.stream.read(144)
                in_mask, in_sv = struct.unpack_from("<QQ", usage_bytes, 0)
                out_mask, out_sv = struct.unpack_from("<QQ", usage_bytes, 72)
                usage = ShaderUsage(
                    raw_bytes=usage_bytes,
                    inputs_mask=in_mask, inputs_sv_mask=in_sv,
                    outputs_mask=out_mask, outputs_sv_mask=out_sv
                )

                sdata = self.parse_shader_data()

                # Decompress bytecode if needed
                is_comp = oodle.is_compressed(raw_bc)
                if self.decompress_bytecode and is_comp:
                    decomp_bc = oodle.decompress(raw_bc)
                else:
                    decomp_bc = raw_bc

                crc = hashing.crc32(decomp_bc)

                record = ShaderRecord(
                    stage=stage,
                    index=idx,
                    name=name,
                    feat=feat,
                    bytecode=decomp_bc,
                    raw_bytecode=raw_bc,
                    signature=sig,
                    usage=usage,
                    data=sdata,
                    is_compressed=is_comp,
                    blob_offset=blob_offset,
                    crc=crc
                )
                fxdb.shaders[stage].append(record)

        # Parse Effects Trailer
        eff_count = self.read_u32()
        for _ in range(eff_count):
            ename = self.read_str_1b()
            dbsize = self.read_u32()
            stage_indices = {}
            for s in STAGES:
                stage_indices[s] = self.read_u32_array()
            unk_struct = self.stream.read(72)
            unk1 = self.read_u64()
            rs = self.read_bytes_array(16)
            ds = self.read_bytes_array(24)
            bs = self.read_bytes_array(68)
            ss = self.read_bytes_array(36)
            tech = self.read_bytes_array(4)
            rss = self.read_bytes_array(20)
            unks_raw = self.read_u32_array()
            unks = [unks_raw] if unks_raw else []
            ss_refs = self.read_bytes_array(2)

            sd1 = self.parse_shader_data()
            sd2 = self.parse_shader_data()

            unk_cnt = self.read_u32()
            for _ in range(unk_cnt):
                ulen = self.read_u32()
                self.stream.read(ulen)

            str_table_len = self.read_u32()
            str_table = self.stream.read(str_table_len)

            eff = EffectRecord(
                name=ename,
                data_buffer_size=dbsize,
                stage_indices=stage_indices,
                unk_struct=unk_struct,
                unk1=unk1,
                rasterizer_states=rs,
                depth_stencil_states=ds,
                blend_states=bs,
                sampler_states=ss,
                techniques=tech,
                render_shader_sets=rss,
                unks=unks,
                sampler_state_refs=ss_refs,
                shader_data_raw=sd1.raw_blob,
                prop_shader_data_raw=sd2.raw_blob,
                string_table=str_table
            )
            fxdb.effects.append(eff)

        # Tail padding to 16-byte alignment
        cur_pos = self.stream.tell()
        self.stream.seek(0, 2)
        end_pos = self.stream.tell()
        self.stream.seek(cur_pos)
        rem = end_pos - cur_pos
        fxdb.tail_padding = self.stream.read(rem) if rem > 0 else b""

        return fxdb


def parse_file(filepath: Union[str, Path], decompress_bytecode: bool = True) -> FXDBFile:
    """Parse an FXDB file from disk."""
    with open(filepath, "rb") as f:
        parser = FXDBParser(f, decompress_bytecode=decompress_bytecode)
        return parser.parse(filepath=str(filepath))


def inject_shaders(
    source_fxdb_path: Union[str, Path],
    output_fxdb_path: Union[str, Path],
    replacements: Dict[Tuple[str, int], bytes],
    recompress_oodle: bool = True
) -> Dict[str, Union[int, List[str]]]:
    """Inject modified shader bytecodes into an FXDB library using streaming copy.
    
    replacements is keyed by (stage, index) -> new_bytecode.
    """
    src = Path(source_fxdb_path)
    dst = Path(output_fxdb_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # First parse the source to find offsets and compression state
    parsed = parse_file(src, decompress_bytecode=False)

    injected_count = 0
    injected_names = []

    # Map (stage, index) to ShaderRecord
    slot_map: Dict[Tuple[str, int], ShaderRecord] = {}
    for stage, records in parsed.shaders.items():
        for r in records:
            slot_map[(stage, r.index)] = r

    # Sort replacements by original file offset for sequential streaming
    ordered_changes = []
    for (st, idx), new_bc in replacements.items():
        if (st, idx) in slot_map:
            rec = slot_map[(st, idx)]
            ordered_changes.append((rec.blob_offset, rec, new_bc))

    ordered_changes.sort(key=lambda x: x[0])

    tmp_out = dst.with_name(dst.name + ".tmp")
    with open(src, "rb") as fi, open(tmp_out, "wb") as fo:
        pos = 0
        for blob_off, rec, new_bc in ordered_changes:
            # If original was compressed and recompress requested, compress new_bc
            final_blob = new_bc
            if rec.is_compressed and recompress_oodle and not oodle.is_compressed(new_bc):
                final_blob = oodle.compress(new_bc)

            # Copy everything up to the length field (blob_off - 4)
            size_off = blob_off - 4
            _copy_chunk(fi, fo, pos, size_off - pos)

            # Write new length and new blob
            fo.write(struct.pack("<I", len(final_blob)))
            fo.write(final_blob)

            pos = blob_off + len(rec.raw_bytecode)
            injected_count += 1
            injected_names.append(f"{rec.stage}[{rec.index}] {rec.name}")

        # Copy the rest of the file
        fi.seek(pos)
        shutil.copyfileobj(fi, fo, 1 << 20)

    # Pad to 16 bytes alignment if necessary
    cur_len = tmp_out.stat().st_size
    pad_needed = (16 - (cur_len % 16)) % 16
    if pad_needed > 0:
        with open(tmp_out, "ab") as fo:
            fo.write(b"\x00" * pad_needed)

    tmp_out.replace(dst)
    return {
        "injected_count": injected_count,
        "injected_shaders": injected_names,
        "output_path": str(dst),
        "output_size": dst.stat().st_size
    }


def _copy_chunk(fi: BinaryIO, fo: BinaryIO, start: int, length: int):
    fi.seek(start)
    remaining = length
    while remaining > 0:
        chunk = fi.read(min(remaining, 1 << 20))
        if not chunk:
            raise IOError("Unexpected end of source file while copying")
        fo.write(chunk)
        remaining -= len(chunk)
