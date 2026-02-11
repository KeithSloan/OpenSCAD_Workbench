def scan_scad_file(filepath: str) -> SCADMeta:
    write_log("Info", f"Scanning SCAD file: {filepath}")

    meta = SCADMeta(
        sourceFile=filepath,
        baseName=os.path.basename(filepath)
    )

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # File hash
    meta.file_hash = hashlib.sha256("".join(lines).encode()).hexdigest()

    inside_module = False
    brace_depth = 0
    current_module = None
    header_comment_block = []

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()

        # ----------------------------------------
        # Capture initial header comments
        # ----------------------------------------
        if idx < 100 and (line.startswith("//") or line.startswith("/*")):
            header_comment_block.append(raw_line)

        # ----------------------------------------
        # include / use
        # ----------------------------------------
        inc_match = re.match(r'include\s*<(.+?)>', line)
        use_match = re.match(r'use\s*<(.+?)>', line)

        if inc_match:
            inc = inc_match.group(1)
            write_log("Info", f"Include found: {inc}")
            meta.includes.append(inc)

        if use_match:
            use = use_match.group(1)
            write_log("Info", f"Use found: {use}")
            meta.uses.append(use)

        # ----------------------------------------
        # $fn, $fa, $fs
        # ----------------------------------------
        fn_match = re.match(r'(\$f[nas])\s*=\s*([^;]+);', line)
        if fn_match:
            key = fn_match.group(1)
            val = fn_match.group(2)
            meta.fn_settings[key] = val
            write_log("Info", f"Found {key} = {val}")

        # ----------------------------------------
        # Module detection
        # ----------------------------------------
        module_match = re.match(r'module\s+([a-zA-Z_]\w*)\s*\((.*?)\)', line)
        if module_match and not inside_module:
            name = module_match.group(1)
            args_raw = module_match.group(2)

            write_log("Info", f"Module found: {name}")

            current_module = SCADModule(
                name=name,
                file_path=filepath,
                start_line=idx + 1
            )

            # Parse arguments
            args = [a.strip() for a in args_raw.split(",") if a.strip()]
            for arg in args:
                if "=" in arg:
                    n, d = arg.split("=", 1)
                    current_module.arguments.append(
                        SCADArgument(name=n.strip(), default=d.strip())
                    )
                else:
                    current_module.arguments.append(
                        SCADArgument(name=arg.strip())
                    )

            meta.modules.append(current_module)
            inside_module = True
            brace_depth = 0

        # ----------------------------------------
        # Track brace depth AFTER module detection
        # ----------------------------------------
        if inside_module:
            brace_depth += raw_line.count("{")
            brace_depth -= raw_line.count("}")

            if brace_depth > 0:
                continue

            # Only close if we've seen opening brace
            if brace_depth <= 0 and current_module:
                current_module.end_line = idx + 1
                inside_module = False
                current_module = None

        # ----------------------------------------
        # Variable assignment (top-level only)
        # ----------------------------------------
        if not inside_module:
            var_match = re.match(r'([a-zA-Z_]\w*)\s*=\s*([^;]+);', line)
            if var_match:
                meta.variables.append(var_match.group(1))

    meta.initial_comments = "".join(header_comment_block)
    meta.classification = classify(meta)

    write_log("Info", f"Classification: {meta.classification}")
    return meta

