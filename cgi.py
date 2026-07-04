def parse_header(line):
    if not line:
        return "", {}
    parts = line.split(";")
    key = parts[0].strip().lower()
    params = {}
    for part in parts[1:]:
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            name, _, value = part.partition("=")
            name = name.strip().lower()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            params[name] = value
        else:
            params[part.lower()] = ""
    return key, params
