"""Export IDA function ranges or detailed evidence for selected RVAs.

Run with IDA's -S option. Output is local-only because it can contain disassembly,
decompiler output and strings. Pass one or more RVAs after the output to select
specific functions. With no RVAs, export a resumable range inventory.
"""

import json
from pathlib import Path

import ida_auto
import ida_bytes
import ida_funcs
import ida_hexrays
import ida_ida
import ida_kernwin
import ida_loader
import ida_nalt
import ida_segment
import idautils
import idc


def describe(function, base, details):
    start = function.start_ea
    record = {
        "start_rva": start - base,
        "end_rva": function.end_ea - base,
        "file_offset": ida_loader.get_fileregion_offset(start),
        "name": ida_funcs.get_func_name(start),
        "chunks": [[first - base, last - base] for first, last in idautils.Chunks(start)],
        "thunk": bool(function.flags & ida_funcs.FUNC_THUNK),
        "library": bool(function.flags & ida_funcs.FUNC_LIB),
        "segment": ida_segment.get_segm_name(ida_segment.getseg(start)),
    }
    if not details:
        return record

    record["incoming_refs"] = [
        {"from_rva": ref.frm - base, "type": ref.type}
        for ref in idautils.XrefsTo(start)
    ]
    record["instructions"] = [
        {
            "rva": ea - base,
            "disassembly": idc.generate_disasm_line(ea, 0),
            "outgoing_refs": [
                {"to_rva": ref.to - base, "type": ref.type}
                for ref in idautils.XrefsFrom(ea)
            ],
        }
        for ea in idautils.FuncItems(start)
        if ida_bytes.is_code(ida_bytes.get_flags(ea))
    ]
    record["pseudocode"] = None
    if ida_hexrays.init_hexrays_plugin():
        try:
            decompiled = ida_hexrays.decompile(start)
            if decompiled is not None:
                record["pseudocode"] = str(decompiled)
        except ida_hexrays.DecompilationFailure as error:
            record["decompiler_error"] = str(error)
    return record


def main():
    output, *selected = idc.ARGV[1:]
    target = Path(output)
    if "local-output" not in target.resolve().parts:
        raise ValueError("IDA output must be under an ignored local-output directory")

    ida_kernwin.msg("Starting Stage 1 IDA export\n")
    if not ida_auto.auto_wait():
        raise RuntimeError("IDA analysis was interrupted")
    base = ida_nalt.get_imagebase()
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({
            "schema_version": 1,
            "image_base": base,
            "reference_sha256": ida_nalt.retrieve_input_file_sha256().hex(),
            "processor": ida_ida.inf_get_procname(),
            "ida_version": ida_kernwin.get_kernel_version(),
            "scope": "selected" if selected else "all",
        }) + "\n")
        addresses = [base + int(value, 0) for value in selected] if selected else idautils.Functions()
        for ea in addresses:
            function = ida_funcs.get_func(ea)
            if function is None or function.start_ea != ea:
                stream.write(json.dumps({
                    "requested_rva": ea - base,
                    "error": "No IDA function begins at the requested address",
                }) + "\n")
                continue
            stream.write(json.dumps(describe(function, base, bool(selected))) + "\n")
    temporary.replace(target)


try:
    main()
except Exception:
    import traceback

    traceback.print_exc()
    idc.qexit(1)
else:
    idc.qexit(0)
