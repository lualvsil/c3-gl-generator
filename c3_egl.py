import xml.etree.ElementTree as ET
import argparse
import os
import urllib.request

# Fundamental C to C3 type mapping
C_TO_C3 = {
    'void': 'void',
    'char': 'CChar',
    'unsigned char': 'char',
    'short': 'CShort',
    'unsigned short': 'CUShort',
    'int': 'CInt',
    'unsigned int': 'CUInt',
    'long': 'CLong',
    'unsigned long': 'CULong',
    'float': 'float',
    'double': 'double',
    'ptrdiff_t': 'isz',
    'intptr_t': 'isz',
    'size_t': 'isz',
    'khronos_float_t': 'float',
    'khronos_intptr_t': 'isz',
    'khronos_ssize_t': 'isz',
    'khronos_uint64_t': 'CULongLong',
    'ull': 'CULongLong',
    'khronos_utime_nanoseconds_t': 'CULongLong',
    'khronos_stime_nanoseconds_t': 'CLongLong',
}

def fix_c3_type_name(name):
    """Applies PascalCase for EGL types."""
    name = name.replace("struct ", "")
    if name[0] == "_":
        name = "Ext" + name
    if name.isupper():
        return name[0] + name[1:].lower()
    return name[0].upper() + name[1:]

def get_c3_type_and_name(element):
    """Extracts type and parameter name."""
    ptype = element.find('ptype')
    pname_tag = element.find('name')
    pname = pname_tag.text if pname_tag is not None else "param"
    
    if pname in ["type", "module", "inline", "return"]:
        pname = "_" + pname

    if ptype is not None:
        if ptype.text == "__eglMustCastToProperFunctionPointerType":
            return "void*", pname
        type_base = ptype.text
        suffix = ptype.tail if ptype.tail else ""
    else:
        full_text = "".join(element.itertext())
        clean_text = full_text.replace(pname, "").replace("const", "").strip()
        type_base = clean_text.replace("*", "").strip()
        suffix = "*" if "*" in clean_text else ""
    
    stars = suffix.count('*')
    return f"{type_base}{'*' * stars}", pname

def generate(args):
    if not os.path.exists('egl.xml'):
        print("Downloading egl.xml from Khronos Registry...")
        url = "https://raw.githubusercontent.com/KhronosGroup/EGL-Registry/refs/heads/main/api/egl.xml"
        urllib.request.urlretrieve(url, 'egl.xml')

    tree = ET.parse('egl.xml')
    root = tree.getroot()

    # Process Types
    types_map = {
        'EGLint': 'CInt',
        'EGLBoolean': 'CUInt',
        'EGLenum': 'CUInt',
        'EGLNativeDisplayType': 'void*',
        'EGLNativeWindowType': 'void*',
        'EGLNativePixmapType': 'void*',
        'EGLConfig': 'void*',
        'EGLContext': 'void*',
        'EGLDisplay': 'void*',
        'EGLSurface': 'void*',
        'EGLClientBuffer': 'void*'
    }
    for t in root.findall(".//types/type"):
        name_tag = t.find('name')
        egl_name = name_tag.text if name_tag is not None else t.get('name')
        if not egl_name: continue
        if egl_name in types_map: continue
        
        c3_name = fix_c3_type_name(egl_name)
        raw_text = "".join(t.itertext())
        if 'struct' in raw_text or '(' in raw_text or 'apientry' in raw_text:
            types_map[egl_name] = "void*"
            continue

        clean_c = raw_text.replace(egl_name, "").replace('typedef', '').replace(';', '').replace('const', '').strip()
        base_c = clean_c.replace('*', '').split()[-1] if clean_c.replace('*', '').split() else "void"
        types_map[egl_name] = C_TO_C3.get(base_c, "void") + ('*' * clean_c.count('*'))

    # Map Commands
    commands = {}
    for cmd in root.findall('.//commands/command'):
        name = cmd.find('proto/name').text
        ret_type = get_c3_type_and_name(cmd.find('proto'))[0]
        params = [get_c3_type_and_name(p) for p in cmd.findall('param')]
        param_str = ", ".join([f"{p[0]} {p[1]}" for p in params])
        commands[name] = (ret_type, param_str)

    # Cumulative Filter for EGL API
    all_enums = {e.get('name'): e.get('value') for e in root.findall('.//enums/enum')}
    req_enums, req_cmds = set(), []
    target_ver = float(args.ver)
    
    for feature in root.findall(f".//feature[@api='egl']"):
        if float(feature.get('number')) <= target_ver:
            for req in feature.findall('require'):
                for e in req.findall('enum'): req_enums.add(e.get('name'))
                for c in req.findall('command'): 
                    if c.get('name') not in req_cmds: req_cmds.append(c.get('name'))

    if args.ext:
        for ex in args.ext:
            ext_node = root.find(f".//extension[@name='{ex}']")
            if ext_node is not None:
                for req in ext_node.findall('require'):
                    # Check for EGL api tag in extension
                    for e in req.findall('enum'): req_enums.add(e.get('name'))
                    for c in req.findall('command'):
                        if c.get('name') not in req_cmds: req_cmds.append(c.get('name'))

    # Output Generation
    with open(args.out, 'w') as f:
        f.write(f"/** EGL Generated for EGL {args.ver} **/\n")
        f.write("\n// Copyright 2013-2020 The Khronos Group Inc.\n// SPDX-License-Identifier: Apache-2.0\n\n")
        f.write("// This file was generated using data from the Khronos EGL Registry (egl.xml).\n// The canonical version of the registry,\n// together with documentation, schema, and Python generator scripts used\n// to generate C header files for EGL, can be found in the Khronos Registry\n// at\n//    https://www.github.com/KhronosGroup/EGL-Registry\n\n")
        f.write(f"module {args.module};\n\n")
        
        f.write("// --- Type Aliases ---\n")
        for name, base in sorted(types_map.items()):
            c3_t = fix_c3_type_name(name)
            # Prevent shadowing native C3 types
            if c3_t != base and c3_t not in ["Void", "Int", "Float", "Bool", "Char"]:
                f.write(f"alias {c3_t} = {base};\n")

        f.write("\n// --- Constants ---\n")
        for e_name in sorted(req_enums):
            if e_name in all_enums:
                val = all_enums[e_name]
                # EGL constants usually start with EGL_
                c3_const = e_name[4:].upper()
                if c3_const[0].isdigit(): c3_const = "_" + c3_const
                c3_type = "uint"
                if "CAST" in val or "(" in val:
                    line = val.replace("EGL_CAST",'').replace('(','').replace(')','').split(',')
                    c3_type = line[0]
                    val = line[1]
                    if types_map[c3_type] == "void*":
                        val = "null"
                try:
                    v = int(val, 0)
                    if v > 0xFFFFFFFF or v < 0: c3_type = "ulong"
                except: pass
                f.write(f"const {c3_type} {c3_const} = {val};\n")

        f.write("\n// --- Function Pointers ---\n")
        for name in req_cmds:
            if name in commands:
                ret, p_str = commands[name]
                f.write(f"alias PFN{name} = fn {ret}({p_str});\n")
                # EGL functions start with egl (3 chars)
                f.write(f"PFN{name} {name[3].lower() + name[4:]};\n")

        f.write("\n// --- Symbol Loader ---\n")
        f.write("alias LoadFN = fn void*(char*);\n")
        f.write("fn bool loadSymbols(LoadFN loader) {\n")
        for name in req_cmds:
            c3_fn = name[3].lower() + name[4:]
            f.write(f"    {c3_fn} = (PFN{name})loader(\"{name}\");\n")
            f.write(f"    if ({c3_fn} == null) return false;\n")
        f.write("    return true;\n")
        f.write("}\n")

    print(f"Generated {args.out} with {len(req_cmds)} functions.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ver", default="1.5")
    parser.add_argument("--module", default="egl")
    parser.add_argument("--ext", nargs="*", default=[])
    parser.add_argument("--out", default="egl.c3l/egl.c3")
    generate(parser.parse_args())
