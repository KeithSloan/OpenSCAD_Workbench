import re

def parse_scad_for_modules(scad_path):
    """
    Parse a SCAD file and extract library header info and documented modules.

    Returns a dictionary:
    {
        "filename": <basename>,
        "summary": <FileSummary>,
        "includes": [<included files>],
        "modules": [
            {
                "name": <module_name>,
                "synopsis": <synopsis>,
                "usage": <usage>,
                "description": <description>,
                "arguments": [
                    {"name": <arg_name>, "default": <default_value>, "description": <desc>}
                ]
            }
        ]
    }
    """
    meta = {
        "filename": "",
        "summary": "",
        "includes": [],
        "modules": []
    }

    try:
        with open(scad_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading SCAD file: {e}")
        return meta

    meta["filename"] = re.sub(r"\.scad$", "", scad_path.split("/")[-1])

    # Header parsing
    summary_match = re.search(r"FileSummary:\s*(.*)", text)
    if summary_match:
        meta["summary"] = summary_match.group(1).strip()

    include_matches = re.findall(r"include\s+<([^>]+)>", text)
    meta["includes"] = include_matches

    # Module parsing
    module_pattern = re.compile(
        r"//\s*Module:\s*(\w+)\s*\((.*?)\)\s*.*?"
        r"(?:Synopsis:\s*(.*?)\n)?"
        r"(?:Usage:\s*(.*?)\n)?"
        r"(?:Description:\s*(.*?)\n)?"
        r"(?:Arguments:\s*(.*?)(?:\n---|\nAnchor Types:|\nExamples:|\nmodule\s|\Z))",
        re.DOTALL | re.IGNORECASE
    )

    for m in module_pattern.finditer(text):
        mod_name = m.group(1).strip()
        args_line = m.group(2).strip()
        synopsis = m.group(3).strip() if m.group(3) else ""
        usage = m.group(4).strip() if m.group(4) else ""
        description = m.group(5).strip() if m.group(5) else ""
        arguments_text = m.group(6).strip() if m.group(6) else ""

        # Extract individual arguments
        arguments = []
        for line in arguments_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("---"):
                continue
            # Match: name = default  or name
            arg_match = re.match(r"(\w+)(?:\s*=\s*(.*))?", line)
            if arg_match:
                arguments.append({
                    "name": arg_match.group(1),
                    "default": arg_match.group(2).strip() if arg_match.group(2) else None,
                    "description": None  # Could be extended to capture inline descriptions
                })

        meta["modules"].append({
            "name": mod_name,
            "arguments": arguments,
            "synopsis": synopsis,
            "usage": usage,
            "description": description
        })

    return meta

