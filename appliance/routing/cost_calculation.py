class CostCalculation:

    def __init__(self, delay_weight=0.5,
                 loss_weight=0.3,
                 utilization_weight=0.2):

        total = delay_weight + loss_weight + utilization_weight

        if total <= 0:
            raise ValueError("Total weights must be positive")

        self.delay_weight = delay_weight / total
        self.loss_weight = loss_weight / total
        self.utilization_weight = utilization_weight / total

    def calculate_path_cost(
        self,
        delay_ms,
        packet_loss_percent,
        utilization_percent
    ):

        # Normalize delay using a 100 ms reference
        normalized_delay = min(max(delay_ms / 100.0, 0), 1)

        # Normalize packet loss and utilization
        normalized_loss = min(max(packet_loss_percent / 100.0, 0), 1)
        normalized_utilization = min(max(utilization_percent / 100.0, 0), 1)

        cost = (
            self.delay_weight * normalized_delay
            + self.loss_weight * normalized_loss
            + self.utilization_weight * normalized_utilization
        )

        return cost

    def calculate_all_path_costs(self, path_metrics):

        results = {}

        for path_name, metrics in path_metrics.items():

            cost = self.calculate_path_cost(
                metrics["delay"],
                metrics["packet_loss"],
                metrics["utilization"]
            )

            results[path_name] = cost

        return results

    def select_best_path(self, path_costs):

        if not path_costs:
            return None

        return min(path_costs, key=path_costs.get)
