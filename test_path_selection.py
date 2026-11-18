import networkx as nx

from appliance.routing.path_selection import PathSelection


# Create diamond topology
graph = nx.Graph()

graph.add_edges_from([
    (("switch", 1), ("switch", 2)),
    (("switch", 1), ("switch", 3)),
    (("switch", 2), ("switch", 4)),
    (("switch", 3), ("switch", 4))
])


# Sample monitoring metrics for each path
path_metrics = {

    "S1 -> S2 -> S4": {
        "delay": 10,
        "packet_loss": 2,
        "utilization": 80
    },

    "S1 -> S3 -> S4": {
        "delay": 5,
        "packet_loss": 0,
        "utilization": 30
    }
}


# Create Path Selection module
selector = PathSelection()

best_path = selector.select_best_path(
    graph,
    ("switch", 1),
    ("switch", 4),
    path_metrics
)


print("\nFINAL ROUTING DECISION")
print("----------------------")
print(best_path)
