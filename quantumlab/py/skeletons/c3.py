
# ---- skeleton: fill in the blanks (start from your Challenge 2 answer) ----
# def choose_paths(net, request):
#     roads = the roads from disjoint_paths within the middle-city limit, widest first
#     left = request.n
#     for each road:
#         pairs = min(thinnest(net, road) // ______, left)   # divide by 1 to keep no spare seat
#         if pairs > 0: add (road, pairs) to the answer and take pairs off left
#     return the answer only if left == ______, otherwise return []
