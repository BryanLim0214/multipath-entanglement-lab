# Splitter: a request may be split over roads that share no link.
# disjoint_paths finds such roads for you. Your job is the TODO at the bottom.
# net.neighbors(u), net.pairs(u, v), net.max_middle, net.spare as in Lazy Walker.
# request.src, request.dst, request.n, request.last_chance


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
    roads = disjoint_paths(net, request.src, request.dst)
    # TODO: give each road a number of pairs so that the numbers add up to request.n.
    # A road can never carry more pairs than thinnest(net, road). Keeping a spare seat (dividing by net.spare) is your choice.
    # Return a list of (road, pairs), or [] if the request cannot be served.
    return []
