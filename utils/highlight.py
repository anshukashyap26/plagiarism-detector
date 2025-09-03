import html

def highlight_matches_html(text: str, spans: list[tuple[int, int]]):
    if not text:
        return "<em>No text</em>"
    marks = [0] * (len(text) + 1)
    for s, l in spans:
        if 0 <= s < len(text) and l > 0:
            l = min(l, len(text) - s)
            marks[s] += 1
            marks[s + l] -= 1
    out = []
    active = 0
    buf_start = 0
    for i in range(len(text)):
        if marks[i] != 0:
            seg = html.escape(text[buf_start:i])
            if seg:
                if active:
                    out.append(seg + "</mark>")
                else:
                    out.append(seg)
            buf_start = i
            active += marks[i]
            if marks[i] > 0 and active > 0:
                out.append("<mark>")
    tail = html.escape(text[buf_start:])
    if tail:
        if active:
            out.append(tail + "</mark>")
        else:
            out.append(tail)
    return "<div style='white-space:pre-wrap;font-family:monospace'>" + "".join(out) + "</div>"
