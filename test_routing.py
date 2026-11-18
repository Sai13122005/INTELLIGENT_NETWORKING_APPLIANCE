import networkx as nx

from appliance.routing.path_calculation import PathCalculation


graph = nx.Graph()

graph.add_edges_from([
    (("switch", 1), ("switch", 2)),
    (("switch", 1), ("switch", 3)),
    (("switch", 2), ("switch", 4)),
    (("switch", 3), ("switch", 4))
])


routing = PathCalculation()

source = ("switch", 1)
destination = ("switch", 4)

paths = routing.find_all_paths(
    graph,
    source,
    destination
)

routing.display_paths(paths)

shortest_path = routing.find_shortest_path(
    graph,
    source,
    destination
)

print("\nSHORTEST PATH")
print("-------------")
routing.display_paths([shortest_path])
