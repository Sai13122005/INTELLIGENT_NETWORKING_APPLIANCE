import networkx as nx


class PathCalculation:

    def find_all_paths(self, network_graph, source, destination):

        if source not in network_graph:
            raise ValueError("Source node does not exist")

        if destination not in network_graph:
            raise ValueError("Destination node does not exist")

        try:
            return list(
                nx.all_simple_paths(
                    network_graph,
                    source,
                    destination
                )
            )
        except nx.NetworkXNoPath:
            return []

    def find_shortest_path(self, network_graph, source, destination):

        if source not in network_graph:
            raise ValueError("Source node does not exist")

        if destination not in network_graph:
            raise ValueError("Destination node does not exist")

        try:
            return nx.shortest_path(
                network_graph,
                source,
                destination
            )
        except nx.NetworkXNoPath:
            return []

    def display_paths(self, paths):

        if not paths:
            print("No available paths found.")
            return

        print("\nAVAILABLE NETWORK PATHS")
        print("-----------------------")

        for index, path in enumerate(paths, start=1):

            readable_path = []

            for node in path:
                if isinstance(node, tuple) and node[0] == "switch":
                    readable_path.append("S" + str(node[1]))
                else:
                    readable_path.append(str(node))

            print(
                "Path {}: {}".format(
                    index,
                    " -> ".join(readable_path)
                )
            )
