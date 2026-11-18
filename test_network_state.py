from appliance.common.network_state import NetworkState


network_state = NetworkState()


# Store measurements for each link
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


# Display all stored measurements
network_state.display_link_metrics()


# Calculate metrics for both paths
path_1 = [
    ("switch", 1),
    ("switch", 2),
    ("switch", 4)
]

path_2 = [
    ("switch", 1),
    ("switch", 3),
    ("switch", 4)
]


print("\nPATH 1 METRICS")
print(network_state.get_path_metrics(path_1))

print("\nPATH 2 METRICS")
print(network_state.get_path_metrics(path_2))
