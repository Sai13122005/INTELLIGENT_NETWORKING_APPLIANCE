import networkx as nx

from appliance.common.network_state import NetworkState
from appliance.routing.path_selection import PathSelection


# Create diamond topology
graph = nx.Graph()

graph.add_edges_from([
    (("switch", 1), ("switch", 2)),
    (("switch", 1), ("switch", 3)),
    (("switch", 2), ("switch", 4)),
    (("switch", 3), ("switch", 4))
])


# Create shared network state
network_state = NetworkState()


# Store metrics for each individual link

network_state.update_link_metrics(
    1, 2,
    delay_ms=4,
    packet_loss_percent=1,
    utilization_percent=70
)

network_state.update_link_metrics(
    2, 4,
    delay_ms=6,
    packet_loss_percent=1,
    utilization_percent=80
)

network_state.update_link_metrics(
    1, 3,
    delay_ms=2,
    packet_loss_percent=0,
    utilization_percent=20
)

network_state.update_link_metrics(
    3, 4,
    delay_ms=3,
    packet_loss_percent=0,
    utilization_percent=30
)


# Create Path Selection module
selector = PathSelection()


# Select the best path using Network State
best_path = selector.select_best_path(
    graph,
    ("switch", 1),
    ("switch", 4),
    network_state
)


print("\nFINAL ROUTING DECISION")
print("----------------------")
print(best_path)
