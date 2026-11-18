from appliance.routing.path_calculation import PathCalculation
from appliance.routing.cost_calculation import CostCalculation


class PathSelection:

    def __init__(self):

        self.path_calculator = PathCalculation()
        self.cost_calculator = CostCalculation()

    def select_best_path(
        self,
        network_graph,
        source,
        destination,
        network_state
    ):

        # Step 1: Find all possible paths
        available_paths = self.path_calculator.find_all_paths(
            network_graph,
            source,
            destination
        )

        if not available_paths:
            print("No available paths found.")
            return None

        # Step 2: Retrieve metrics for every path
        path_metrics = {}
        path_objects = {}

        for path in available_paths:

            readable_path = []

            for node in path:

                if isinstance(node, tuple) and node[0] == "switch":
                    readable_path.append("S" + str(node[1]))
                else:
                    readable_path.append(str(node))

            path_name = " -> ".join(readable_path)

            metrics = network_state.get_path_metrics(path)

            if metrics is None:
                print(
                    "Skipping {}: incomplete link metrics".format(
                        path_name
                    )
                )
                continue

            path_metrics[path_name] = metrics
            path_objects[path_name] = path

        if not path_metrics:
            print("No paths have complete monitoring metrics.")
            return None

        # Step 3: Calculate cost for each path
        path_costs = self.cost_calculator.calculate_all_path_costs(
            path_metrics
        )

        print("\nPATH METRICS AND COSTS")
        print("----------------------")

        for path_name, metrics in path_metrics.items():

            print("\n{}".format(path_name))
            print("Delay: {} ms".format(metrics["delay"]))
            print("Packet loss: {:.2f}%".format(
                metrics["packet_loss"]
            ))
            print("Utilization: {}%".format(
                metrics["utilization"]
            ))
            print("Cost: {:.4f}".format(
                path_costs[path_name]
            ))

        # Step 4: Select the lowest-cost path
        best_path_name = self.cost_calculator.select_best_path(
            path_costs
        )

        print("\nSELECTED BEST PATH")
        print("------------------")
        print(best_path_name)

        return path_objects[best_path_name]
