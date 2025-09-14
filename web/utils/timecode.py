def hhmmss_to_seconds(value: str) -> float:
    """Parse 'HH:MM:SS.mmm' | 'MM:SS.mmm' | 'SS.mmm' into seconds (float)."""
    if not isinstance(value, str):
        return 0.0
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s = float(parts[2])
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m = int(parts[0])
            s = float(parts[1])
            return m * 60 + s
        else:
            return float(parts[0])
    except Exception:
        return 0.0
