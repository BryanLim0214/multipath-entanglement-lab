
# ---- skeleton: fill in the blanks (the Splitter template has disjoint_paths and thinnest) ----
# def choose_paths(net, request):
#     roads = disjoint_paths(net, request.src, request.dst)
#     sort the roads by ______ (the widest first)
#     left = request.n
#     for each road:
#         pairs = min(thinnest(net, road) // ______, left)
#         if pairs > 0: add (road, pairs) to the answer and take pairs off left
#     return the answer only if left == ______, otherwise return []
