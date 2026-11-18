# Challenge 2 solution: split over roads that share no link, and only ever return legal answers.
# Idea: the widest roads first, each carrying half its thinnest link (the paper's spare seat), within the middle-city limit.


def fewest_links_road(net, src, dst, banned):
    """One road with the fewest links that avoids the links in `banned`, or None."""
    came = {src: None}
    queue = [src]
    for city in queue:
        for nxt in net.neighbors(city):
            if nxt not in came and frozenset((city, nxt)) not in banned:
                came[nxt] = city
                queue.append(nxt)
    if dst not in came:
        return None
    road = [dst]
    while came[road[-1]] is not None:
        road.append(came[road[-1]])
    return road[::-1]


def disjoint_paths(net, src, dst):
    """Roads from src to dst that share no link, each found after removing the links of the one before."""
    banned = set()
    roads = []
    while True:
        road = fewest_links_road(net, src, dst, banned)
        if road is None:
            return roads
        roads.append(road)
        banned.update(frozenset(pair) for pair in zip(road, road[1:]))


def thinnest(net, road):
    """Free seats on the thinnest link of the road."""
    return min(net.pairs(u, v) for u, v in zip(road, road[1:]))


def choose_paths(net, request):
    roads = [r for r in disjoint_paths(net, request.src, request.dst) if len(r) - 2 <= net.max_middle]
    roads.sort(key=lambda road: -thinnest(net, road))
    answer, left = [], request.n
    for road in roads:
        pairs = min(thinnest(net, road) // net.spare, left)
        if pairs > 0:
            answer.append((road, pairs))
            left -= pairs
    return answer if left == 0 else []
