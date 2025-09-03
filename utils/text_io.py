def read_files_as_texts(files):
    texts, names = [], []
    if not files:
        return texts, names
    for f in files:
        data = f.read()
        try:
            txt = data.decode("utf-8", errors="ignore")
        except AttributeError:
            txt = str(data)
        texts.append(txt)
        names.append(getattr(f, "name", "uploaded.txt"))
    return texts, names
