"""Minimal YAML reader for the territory-rules machine spec (block maps, block lists, flow lists and maps, scalars, comments). Stdlib only."""
import re, json

def _strip_comment(s):
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == q: q = None
        elif ch in "\"'": q = ch; out.append(ch)
        elif ch == "#" and (i == 0 or s[i-1] in " \t"): break
        else: out.append(ch)
    return "".join(out).rstrip()

def _scalar(s):
    s = s.strip()
    if s == "" or s == "~" or s == "null": return None
    if s[0] in "\"'" and s[-1] == s[0]: return s[1:-1]
    if s in ("true", "True"): return True
    if s in ("false", "False"): return False
    if re.fullmatch(r"-?\d+", s): return int(s)
    if re.fullmatch(r"-?\d*\.\d+", s): return float(s)
    if s[0] == "[": return _flow_list(s)
    if s[0] == "{": return _flow_map(s)
    return s

def _split_top(s, sep=","):
    parts, depth, q, cur = [], 0, None, []
    for ch in s:
        if q:
            cur.append(ch)
            if ch == q: q = None
            continue
        if ch in "\"'": q = ch; cur.append(ch); continue
        if ch in "[{": depth += 1
        if ch in "]}": depth -= 1
        if ch == sep and depth == 0: parts.append("".join(cur)); cur = []
        else: cur.append(ch)
    if "".join(cur).strip(): parts.append("".join(cur))
    return parts

def _flow_list(s):
    inner = s.strip()[1:-1].strip()
    return [_scalar(p) for p in _split_top(inner)] if inner else []

def _flow_map(s):
    inner = s.strip()[1:-1].strip()
    out = {}
    for p in _split_top(inner):
        k, v = p.split(":", 1); out[_scalar(k)] = _scalar(v)
    return out

def _indent(l): return len(l) - len(l.lstrip(" "))

def parse(text):
    lines = [(_indent(l), _strip_comment(l).strip()) for l in text.splitlines()]
    lines = [(i, t) for i, t in lines if t]
    pos = [0]
    def block(ind):
        if pos[0] >= len(lines): return None
        i, t = lines[pos[0]]
        if t.startswith("- "):
            out = []
            while pos[0] < len(lines) and lines[pos[0]][0] == ind and lines[pos[0]][1].startswith("- "):
                item = lines[pos[0]][1][2:].strip(); pos[0] += 1
                if ":" in item and not item.startswith(("[", "{", "\"", "'")):   # "- key: value" block map item
                    k, v = item.split(":", 1); d = {_scalar(k): _scalar(v) if v.strip() else block(ind + 2)}
                    while pos[0] < len(lines) and lines[pos[0]][0] > ind:
                        k2, v2 = lines[pos[0]][1].split(":", 1); pos[0] += 1
                        d[_scalar(k2)] = _scalar(v2) if v2.strip() else block(lines[pos[0]][0] if pos[0] < len(lines) else ind + 2)
                    out.append(d)
                else: out.append(_scalar(item))
            return out
        out = {}
        while pos[0] < len(lines) and lines[pos[0]][0] == ind:
            t = lines[pos[0]][1]
            if ":" not in t: raise ValueError(f"bad line {t!r}")
            k, v = t.split(":", 1); pos[0] += 1
            if v.strip(): out[_scalar(k)] = _scalar(v)
            elif pos[0] < len(lines) and lines[pos[0]][0] > ind: out[_scalar(k)] = block(lines[pos[0]][0])
            else: out[_scalar(k)] = None
        return out
    return block(lines[0][0]) if lines else {}

def load_rules(path):
    text = open(path).read()
    m = re.search(r"```ya?ml\n(.*?)```", text, re.S)
    return parse(m.group(1))

if __name__ == "__main__":
    import sys
    print(json.dumps(load_rules(sys.argv[1]), indent=1))
