
# ---- skeleton: fill in the blanks (the Splitter template has disjoint_paths and thinnest) ----
# def choose_paths(net, request):
#     roads = the roads from disjoint_paths that have at most ______ middle cities
#     sort the roads by ______ (the widest first)
#     left = request.n
#     for each road:
#         pairs = min(thinnest(net, road) // ______, left)    # half the thinnest link keeps a spare seat
#         if pairs > 0: add (road, pairs) to the answer and take pairs off left
#     return the answer only if left == ______, otherwise return []   # a half answer is illegal
