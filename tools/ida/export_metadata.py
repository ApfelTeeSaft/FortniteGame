"""IDAPython batch exporter: segments, functions and user/auto names as JSON.

Run headless with the local IDA installation (verified with IDA Professional 9.4):

  idat.exe -A -L<log> -S"tools/ida/export_metadata.py <out.json>" <input binary or .i64>

The output is local analysis data. Keep the .i64/.id* databases and any export
that contains code bytes out of Git (.gitignore covers the database files).
"""
import json

import ida_auto
import ida_funcs
import ida_nalt
import ida_pro
import ida_segment
import idautils
import idc


def main():
    out = idc.ARGV[1] if len(idc.ARGV) > 1 else "ida-export.json"
    ida_auto.auto_wait()
    base = ida_nalt.get_imagebase()
    segs = []
    for ea in idautils.Segments():
        s = ida_segment.getseg(ea)
        segs.append({"name": ida_segment.get_segm_name(s), "start_rva": s.start_ea - base,
                     "end_rva": s.end_ea - base, "perm": s.perm})
    funcs = []
    for ea in idautils.Functions():
        f = ida_funcs.get_func(ea)
        funcs.append({"start_rva": f.start_ea - base, "end_rva": f.end_ea - base,
                      "name": idc.get_func_name(ea), "flags": f.flags,
                      "tails": [(a - base, b - base) for a, b in idautils.Chunks(ea)][1:]})
    data = {
        "ida_version": idc.get_inf_attr(idc.INF_VERSION) if hasattr(idc, "INF_VERSION") else None,
        "input_sha256": ida_nalt.retrieve_input_file_sha256().hex(),
        "image_base": base,
        "segments": segs,
        "functions": funcs,
    }
    with open(out, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"exported {len(funcs)} functions to {out}")


try:
    main()
    code = 0
except Exception:  # report in the IDA log, then exit non-zero
    import traceback
    traceback.print_exc()
    code = 1
ida_pro.qexit(code)
