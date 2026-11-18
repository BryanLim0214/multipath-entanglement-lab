# Lazy Walker: take the shortest road and put every pair on it.
# net.neighbors(u)  -> cities next to u over a link with a free seat
# net.pairs(u, v)   -> free seats on the link u-v
# net.max_middle    -> most middle cities a road may have
# net.spare         -> 2: the paper's methods keep one spare seat per pair. Your choice, the referee does not require it
# request.src, request.dst, request.n, request.last_chance


def shortest_roads(net, src, dst):
    """All roads from src to dst with the fewest links."""
    dist = {src: 0}
    queue = [src]
    for city in queue:
        for nxt in net.neighbors(city):
            if nxt not in dist:
                dist[nxt] = dist[city] + 1
                queue.append(nxt)
    if dst not in dist:
        return []
    roads = []

    def extend(road):
        city = road[-1]
        if city == dst:
            roads.append(road)
            return
        for nxt in net.neighbors(city):
            if dist.get(nxt) == dist[city] + 1 and dist[nxt] <= dist[dst]:
                extend(road + [nxt])

    extend([src])
    return roads


def thinnest(net, road):
    """Free seats on the thinnest link of the road."""
    return min(net.pairs(u, v) for u, v in zip(road, road[1:]))


def choose_paths(net, request):
    roads = shortest_roads(net, request.src, request.dst)
    if not roads:
        return []
    best = min(roads, key=lambda road: (-thinnest(net, road), road))
    if len(best) - 2 > net.max_middle:
        return []
    if thinnest(net, best) < request.n * net.spare:
        return []
    return [(best, request.n)]
