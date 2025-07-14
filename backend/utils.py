def neighbors(q: int, r: int):
    # axial‑hex neighbors
    for dq, dr in [(+1,0), (+1,-1), (0,-1), (-1,0), (-1,+1), (0,+1)]:
        yield (q + dq, r + dr)