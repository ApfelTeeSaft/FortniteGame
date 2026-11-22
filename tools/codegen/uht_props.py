"""Decode UE4.20 UFunction property parameters and write UHT's thunk and declaration text.

Records (UObjectGlobals.h, UE4CodeGen_Private, shipping: no metadata). Every record starts
{EPropertyClass Type; const char* NameUTF8; EObjectFlags; EPropertyFlags PropertyFlags (+0x18);
int32 ArrayDim (+0x20); const char* RepNotify (+0x28)}, then Offset (+0x30) and the kind's
pointers (+0x38: ClassFunc / ScriptStructFunc / EnumFunc / SignatureFunctionFunc; Class:
MetaClassFunc +0x38, ClassFunc +0x40). Bool has ElementSize +0x30, NativeBool +0x34.

Order. ConstructUProperties builds the records in PropertyArray order and each property is
prepended to its function's chain, so the array lists the parameters in reverse declaration
order. Array and Set records are followed by one inner record, Map by two, Enum by its
underlying property. The Offset fields (decreasing along the array) confirm the order.

Text. For each parameter, UHT 4.20's ExportFunctionThunk writes P_GET_<macro>[_REF] with
GetCPPMacroType's macro and type, names it Z_Param_<Name> (Z_Param_Out_<Name> for
CPF_OutParm), and passes it to the native in declaration order. The native's declaration
follows UProperty::ExportCppDeclaration: "const" for CPF_ConstParm, "&" for CPF_OutParm or
CPF_ReferenceParm. Only types whose C++ form the generated headers model are supported:
bool, the integer and floating-point types, uint8 without an enum, FName, and pointers to
reflected classes (UClass* for class properties without TSubclassOf), the core structs
ScriptRecovered.h defines (FVector, FRotator, FVector2D, FLinearColor, FGuid, FGameplayTag,
FGameplayAbilitySpecHandle; P_GET_STRUCT), enums, FString, TArrays of trivially
copyable elements (ContainersRecovered.h), FText and TSubclassOf (TextRecovered.h).

FString parameters. HeaderParser drops CPF_ConstParm from 'const FString&' parameters (only
UHT's own data keeps the reference), so a by-value FString and a const reference carry the
same flags (none). The caller decides: RPC parameters must be const references (UHT
reports an error otherwise); for other functions the form is read from the reference
thunk (tools/codegen/uht_exec.py). An enum is
a raw parameter when passed by value or returned, TEnumAsByte<E>& (E& for an enum class)
when an out parameter, as UByteProperty/UEnumProperty::GetCPPType export them.
"""
from __future__ import annotations

import struct

TYPES = ("Byte Int8 Int16 Int Int64 UInt16 UInt32 UInt64 UnsizedInt UnsizedUInt Float Double Bool SoftClass "
         "WeakObject LazyObject SoftObject Class Object Interface Name Str Array Map Set Struct Delegate "
         "MulticastDelegate Text Enum").split()
INNER = {"Array": 1, "Set": 1, "Map": 2, "Enum": 1}
CPF_CONSTPARM, CPF_OUTPARM, CPF_RETURNPARM = 0x2, 0x100, 0x400
CPF_REFERENCEPARM, CPF_UOBJECTWRAPPER = 0x08000000, 0x0004000000000000
# EPropertyClass -> (C++ type, property class) for P_GET_PROPERTY.
NUMERIC = {"Byte": ("uint8", "UByteProperty"), "Int8": ("int8", "UInt8Property"),
           "Int16": ("int16", "UInt16Property"), "Int": ("int32", "UIntProperty"),
           "Int64": ("int64", "UInt64Property"), "UInt16": ("uint16", "UUInt16Property"),
           "UInt32": ("uint32", "UUInt32Property"), "UInt64": ("uint64", "UUInt64Property"),
           "Float": ("float", "UFloatProperty"), "Double": ("double", "UDoubleProperty"),
           "Name": ("FName", "UNameProperty")}
# UScriptStruct name -> (SizeOf, AlignOf) of the structs ScriptRecovered.h defines from the
# UE4.20 headers; a struct parameter is supported only when its FStructParams agree.
MODELLED_STRUCTS = {"Vector": (12, 4), "Rotator": (12, 4), "Vector2D": (8, 4), "LinearColor": (16, 4),
                    "Guid": (16, 4), "GameplayTag": (8, 8), "GameplayAbilitySpecHandle": (4, 4),
                    # EngineStructsRecovered.h
                    "Vector_NetQuantize": (12, 4), "Vector_NetQuantize10": (12, 4),
                    "Vector_NetQuantize100": (12, 4), "Vector_NetQuantizeNormal": (12, 4),
                    "HitResult": (136, 8), "PredictionKey": (24, 8), "Color": (4, 4), "Margin": (16, 4),
                    "Key": (24, 8), "UniqueNetIdRepl": (40, 8), "GameplayEffectContextHandle": (24, 8),
                    "GameplayTagContainer": (32, 8), "GameplayCueParameters": (184, 8), "Transform": (48, 16),
                    "ViewTargetTransitionParams": (16, 4), "GameplayAbilityActivationInfo": (32, 8),
                    "GameplayAbilityTargetDataHandle": (32, 8), "GameplayEventData": (168, 8)}
# Enums EngineStructsRecovered.h defines, with the reference's enumerator values, for the
# structs' constructors; enum_declarations does not redeclare them.
MODELLED_ENUMS = {"EViewTargetBlendFunction", "EGameplayAbilityActivationMode::Type"}
REGISTER_RETURN = {"bool", "uint8", "int8", "int16", "int32", "int64", "uint16", "uint32", "uint64", "float", "double"}


def _cstr(dimg, base: int, va: int) -> str:
    return dimg.read(va - base, 256).split(b"\0")[0].decode()


def decode(dimg, base: int, props: int, nprops: int) -> list[dict]:
    """Top-level properties in declaration order, each with its inner records."""
    recs = []
    for i in range(nprops):
        p = struct.unpack("<Q", dimg.read(props - base + 8 * i, 8))[0] - base
        t, name, pflags, dim = struct.unpack("<I4xQ8xQi", dimg.read(p, 0x24))
        extra = dimg.read(p + 0x30, 0x18)
        recs.append({"type": TYPES[t], "name": _cstr(dimg, base, name), "flags": pflags, "dim": dim,
                     "offset": struct.unpack_from("<i", extra)[0], "func": struct.unpack_from("<Q", extra, 8)[0],
                     "func2": struct.unpack_from("<Q", extra, 16)[0], "bool": struct.unpack_from("<IB", extra),
                     "rva": p})
    out, i = [], 0
    while i < len(recs):
        r = dict(recs[i])
        k = INNER.get(r["type"], 0)
        r["inner"] = recs[i + 1:i + 1 + k]
        out.append(r)
        i += 1 + k
    return out[::-1]


class Names:
    """Reflected types by their Z_Construct_* RVA: classes (name) and enums (UEnum name,
    UEnum::ECppForm and C++ type, from the enum's FEnumParams)."""

    def __init__(self, classes: dict[int, str], enums: dict[int, dict], structs: dict[int, tuple] | None = None):
        self.classes, self.enums = classes, enums
        self.structs = structs if structs is not None else {}   # a lazily filled mapping may be empty
        self.used_enums: dict[str, dict] = {}     # C++ declarations the signatures need

    def enum(self, va: int, base: int, underlying: str | None) -> dict | None:
        e = self.enums.get(va - base) if va else None
        if e is None:
            return None
        if e["form"] == ENUM_CLASS:
            if underlying is None:
                return None
            seen = self.used_enums.get(e["cpp"])
            if seen and seen.get("underlying") != underlying:
                return None
            self.used_enums[e["cpp"]] = dict(e, underlying=underlying)
        else:
            self.used_enums.setdefault(e["cpp"], dict(e))
        return e


ENUM_REGULAR, ENUM_NAMESPACED, ENUM_CLASS = 0, 1, 2
# UEnumProperty's underlying property -> C++ type of an enum class.
UNDERLYING = {"Byte": "uint8", "Int8": "int8", "Int16": "int16", "Int": "int32", "Int64": "int64",
              "UInt16": "uint16", "UInt32": "uint32", "UInt64": "uint64"}


def _with_qualifiers(p: dict, ctype: str, name: str) -> str:
    """UProperty::ExportCppDeclaration: "const" for CPF_ConstParm, "&" for out/reference."""
    const = p["flags"] & CPF_CONSTPARM and p["type"] != "Bool"
    ref = p["flags"] & (CPF_OUTPARM | CPF_REFERENCEPARM)
    if const and not ref:
        ctype = f"const {ctype}"
    elif const:
        ctype = f"{ctype} const"
    return f"{ctype}{'&' if ref else ''} {name}"


def parameter(p: dict, names: Names, base: int, strings_by_ref: bool = False) -> dict | None:
    """UHT 4.20 text for a supported property: decl (native declaration), line (P_GET macro),
    arg (argument), ret (declared return type) and store (Z_Param__Result cast type)."""
    if p["dim"] != 1:
        return None
    t, out, retp = p["type"], p["flags"] & CPF_OUTPARM, p["flags"] & CPF_RETURNPARM
    pname = f"Z_Param_{'Out_' if out else ''}{p['name']}"
    ref = "_REF" if out else ""
    ctype = line = arg = store = None
    if t == "Bool" and p["bool"] == (1, 1):
        ctype, line = "bool", f"P_GET_UBOOL{ref}({pname});"
    elif t == "Byte" and p["func"]:
        e = names.enum(p["func"], base, "uint8")
        if e is None:
            return None
        cls_form = e["form"] == ENUM_CLASS
        wrapped = e["cpp"] if cls_form else f"TEnumAsByte<{e['cpp']}>"
        # GetCPPType with CPPF_ArgumentOrReturnValue: the raw enum unless an out parameter.
        ctype = wrapped if out and not retp else e["cpp"]
        store = wrapped
        line = f"P_GET_PROPERTY{ref}(UByteProperty,{pname});"
        arg = f"({wrapped}&)({pname})" if out else f"{e['cpp']}({pname})"
    elif t == "Enum":
        inner = p["inner"][0]["type"] if p["inner"] else None
        e = names.enum(p["func"], base, UNDERLYING.get(inner))
        if e is None or e["form"] != ENUM_CLASS:
            return None
        ctype = store = e["cpp"]
        line = f"P_GET_ENUM{ref}({e['name']},{pname});"
        arg = f"({e['cpp']}&)({pname})" if out else f"{e['cpp']}({pname})"
    elif t == "Str":
        ctype, line = "FString", f"P_GET_PROPERTY{ref}(UStrProperty,{pname});"
        if strings_by_ref and not p["flags"] & (CPF_OUTPARM | CPF_REFERENCEPARM | CPF_CONSTPARM | CPF_RETURNPARM):
            # 'const FString&' parameters carry no flags (HeaderParser drops CPF_ConstParm).
            return {"decl": f"const FString& {p['name']}", "line": line, "arg": pname, "ret": ctype, "store": ctype}
    elif t == "Array":
        elem = element_type(p["inner"][0], names, base) if p["inner"] else None
        if elem is None:
            return None
        ctype = f"TArray<{elem}>"
        line = f"P_GET_TARRAY{ref}({elem},{pname});"
    elif t == "Struct":
        info = names.structs.get(p["func"] - base) if p["func"] else None
        if info is None or MODELLED_STRUCTS.get(info[0]) != info[1:]:
            return None                # only structs the shims define, at the reference's size/alignment
        ctype = f"F{info[0]}"
        line = f"P_GET_STRUCT{ref}({ctype},{pname});"
    elif t in NUMERIC:
        ctype, line = NUMERIC[t][0], f"P_GET_PROPERTY{ref}({NUMERIC[t][1]},{pname});"
    elif t == "Object":
        c = names.classes.get(p["func"] - base) if p["func"] else None
        if c is None:
            return None
        ctype, line = f"{c}*", f"P_GET_OBJECT{ref}({c},{pname});"
    elif t == "Class" and not p["flags"] & CPF_UOBJECTWRAPPER:
        ctype, line = "UClass*", f"P_GET_OBJECT{ref}(UClass,{pname});"
    elif t == "Class":
        # TSubclassOf<MetaClass> (FClassPropertyParams: MetaClassFunc +0x38). ExportFunctionThunk
        # reads it as a UClass*, except an out parameter, which it passes as the wrapper itself
        # (bPassAsNoPtr: P_GET_OBJECT_REF_NO_PTR).
        meta = names.classes.get(p["func"] - base) if p["func"] else None
        if meta is None:
            return None
        ctype = f"TSubclassOf<{meta}>"
        line = (f"P_GET_OBJECT_REF_NO_PTR({ctype},{pname});" if out and not retp
                else f"P_GET_OBJECT(UClass,{pname});")
    elif t == "Text":
        ctype, line = "FText", f"P_GET_PROPERTY{ref}(UTextProperty,{pname});"
    elif t == "SoftObject":
        # USoftObjectProperty::GetCPPMacroType: SOFTOBJECT, TSoftObjectPtr<PropertyClass>.
        c = names.classes.get(p["func"] - base) if p["func"] else None
        if c is None:
            return None
        ctype = f"TSoftObjectPtr<{c}>"
        line = f"P_GET_SOFTOBJECT{ref}({ctype},{pname});"
    else:
        return None
    return {"decl": _with_qualifiers(p, ctype, p["name"]), "line": line, "arg": arg or pname,
            "ret": ctype, "store": store or ctype}


def element_type(inner: dict, names: Names, base: int) -> str | None:
    """C++ type of a TArray element (UArrayProperty::GetCPPMacroType: Inner->GetCPPType()).
    ContainersRecovered.h's ConstructItems/DestructItems copy and destroy any element type
    as 4.20's MemoryOps.h does."""
    if inner["dim"] != 1:
        return None
    t = inner["type"]
    if t == "Bool":
        return "bool" if inner["bool"] == (1, 1) else None
    if t in NUMERIC and not (t == "Byte" and inner["func"]):
        return NUMERIC[t][0]
    if t == "Object":
        c = names.classes.get(inner["func"] - base) if inner["func"] else None
        return f"{c}*" if c else None
    if t == "Class" and not inner["flags"] & CPF_UOBJECTWRAPPER:
        return "UClass*"
    if t == "Str":
        return "FString"
    if t == "Text":
        return "FText"
    if t == "SoftObject":
        c = names.classes.get(inner["func"] - base) if inner["func"] else None
        return f"TSoftObjectPtr<{c}>" if c else None
    if t == "Struct":
        info = names.structs.get(inner["func"] - base) if inner["func"] else None
        return f"F{info[0]}" if info and MODELLED_STRUCTS.get(info[0]) == info[1:] else None
    return None


def plain_strings(dimg, base: int, rec: int) -> int:
    """Number of FString parameters without flags: passed by value or by const reference."""
    nprops, props = _props(dimg, rec)
    return sum(1 for p in (decode(dimg, base, props, nprops) if nprops else [])
               if p["type"] == "Str" and not p["flags"] & (CPF_OUTPARM | CPF_REFERENCEPARM | CPF_CONSTPARM | CPF_RETURNPARM))


def _props(dimg, rec: int) -> tuple[int, int]:
    props, nprops = struct.unpack("<Qi", dimg.read(rec + 0x30, 0xC))
    return nprops, props


def function_signature(dimg, base: int, rec: int, names: Names, strings_by_ref: bool = False) -> dict | None:
    """Parameters and return of a UFunction (FFunctionParams at rec), or None if a type is not
    supported. Keys: flags, params [(declaration, P_GET line, argument)], ret (declared C++
    return type), store (the type UHT casts Z_Param__Result to)."""
    fflags, props, nprops = struct.unpack("<I12xQi", dimg.read(rec + 0x20, 0x1C))
    ps = decode(dimg, base, props, nprops) if nprops else []
    ret = store = None
    params = []
    for p in ps:
        t = parameter(p, names, base, strings_by_ref)
        if t is None:
            return None
        if p["flags"] & CPF_RETURNPARM:
            r = t["ret"]
            if ret is not None or not (r in REGISTER_RETURN or r.endswith("*") or r == "FName"
                                       or r in names.used_enums or r[1:] in MODELLED_STRUCTS
                                       or r in ("FString", "FText") or r.startswith(("TArray<", "TSubclassOf<", "TSoftObjectPtr<"))):
                return None
            ret, store = r, t["store"]
            continue
        params.append((t["decl"], t["line"], t["arg"]))
    return {"flags": fflags, "params": params, "ret": ret, "store": store}


def enum_declarations(names: Names) -> list[str]:
    """C++ declarations of the enums the generated signatures use, in their UEnum::ECppForm.
    Only the form and underlying type are recovered; the enumerators are not declared."""
    out = []
    for cpp, e in sorted(names.used_enums.items()):
        if cpp in MODELLED_ENUMS:
            continue
        if e["form"] == ENUM_CLASS:
            out.append(f"enum class {cpp} : {e['underlying']} {{}};")
        elif e["form"] == ENUM_NAMESPACED:
            ns, inner = cpp.split("::", 1)
            out.append(f"namespace {ns} {{ enum {inner} {{}}; }}")
        else:
            out.append(f"enum {cpp} {{}};")
    return out
