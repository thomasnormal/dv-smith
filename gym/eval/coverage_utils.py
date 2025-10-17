import re


def parse_coverage_text(path):
    """Parse a Questa vcover text report into a flat {bin_name: hits} dict.

    Tries to extract both functional coverage bins and (optionally) assertion/directive items.
    Falls back to binary 0/1 if exact counts are not present.
    """
    bins = {}
    current_cp = None
    with open(path, "r", errors="ignore") as f:
        for line in f:
            # Capture coverpoint names like 'AWSIZE_CP', 'ARBURST_CP' etc.
            mcp = re.search(r"^\s*Coverpoint\s*:\s*([A-Za-z0-9_\.]+)", line)
            if mcp:
                current_cp = mcp.group(1)
                continue

            # Common bin line formats; try to capture name and hits
            # Example patterns:
            #  bin AWSIZE_2BYTES ... Hits: 3
            #  bin [value] ... Count: 1
            mb = re.search(r"\b(bin|Bin)\s+([A-Za-z0-9_\[\]\-\:]+).*?(Hits|Count)\s*:\s*(\d+)", line)
            if mb and current_cp:
                bname = f"{current_cp}.{mb.group(2)}"
                hits = int(mb.group(4))
                bins[bname] = bins.get(bname, 0) + hits
                continue

            # Fallback: detect a named bin without explicit hits; treat as 1
            mb2 = re.search(r"\b(bin|Bin)\s+([A-Za-z0-9_]+)\b", line)
            if mb2 and current_cp:
                bname = f"{current_cp}.{mb2.group(2)}"
                bins.setdefault(bname, 1)

            # Assertion/directive items
            ma = re.search(r"^\s*(Assertion|Directive)\s*:\s*([A-Za-z0-9_\.]+).*?(Hits|Count)\s*:\s*(\d+)", line)
            if ma:
                bname = f"{ma.group(1)}.{ma.group(2)}"
                hits = int(ma.group(4))
                bins[bname] = bins.get(bname, 0) + hits
                continue

    return bins


def diff_bins(bins_test, bins_base):
    """Return a signature dict = positive differences bins_test - bins_base (per bin)."""
    sig = {}
    keys = set(bins_test.keys()) | set(bins_base.keys())
    for k in keys:
        v = bins_test.get(k, 0) - bins_base.get(k, 0)
        if v > 0:
            sig[k] = v
    return sig


def weighted_jaccard(a, b):
    """Weighted Jaccard between two dicts of {item: weight}.
    Returns 0..1, where 1 means identical.
    """
    keys = set(a.keys()) | set(b.keys())
    num = 0.0
    den = 0.0
    for k in keys:
        av = float(a.get(k, 0))
        bv = float(b.get(k, 0))
        num += min(av, bv)
        den += max(av, bv)
    return (num / den) if den > 0 else 1.0

