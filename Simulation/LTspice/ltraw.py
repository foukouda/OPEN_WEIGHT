"""Minimal reader for LTspice binary .raw files (transient and AC)."""
import numpy as np


def read_raw(path):
    # header is UTF-16LE (LTspice >= 17), terminated by "Binary:\n"
    marker = "Binary:\n".encode("utf-16-le")
    with open(path, "rb") as f:
        head = f.read(1 << 20)
    idx = head.find(marker)
    if idx < 0:
        raise ValueError(f"{path}: not a binary LTspice raw file")
    header = head[:idx].decode("utf-16-le")
    offset = idx + len(marker)

    names, npts, flags, in_vars = [], 0, "", False
    for line in header.splitlines():
        if line.startswith("No. Points:"):
            npts = int(line.split(":")[1])
        elif line.startswith("Flags:"):
            flags = line.split(":", 1)[1].lower()
        elif line.startswith("Variables:"):
            in_vars = True
        elif in_vars and line.startswith("\t"):
            names.append(line.split("\t")[2])
    nvar = len(names)

    # the data block is memory-mapped, not loaded: the 600 ms switching run is
    # about 2 GB, so the traces are returned as views on the file
    if "complex" in flags:
        arr = np.memmap(path, dtype=np.complex128, mode="r", offset=offset, shape=(npts, nvar))
        out = {n: arr[:, i] for i, n in enumerate(names)}
        out[names[0]] = arr[:, 0].real
    elif "double" in flags:
        arr = np.memmap(path, dtype=np.float64, mode="r", offset=offset, shape=(npts, nvar))
        out = {n: arr[:, i] for i, n in enumerate(names)}
    else:
        # time/frequency as float64, other vectors as float32
        rec = np.dtype([("t", "<f8")] + [(f"v{i}", "<f4") for i in range(1, nvar)])
        arr = np.memmap(path, dtype=rec, mode="r", offset=offset, shape=(npts,))
        out = {names[0]: np.abs(arr["t"])}
        for i in range(1, nvar):
            out[names[i]] = arr[f"v{i}"]
    return {k.lower(): v for k, v in out.items()}
