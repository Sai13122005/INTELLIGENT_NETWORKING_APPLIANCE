import time


class NetworkState:

    def __init__(self):
        self.topology_graph = None
        self.link_metrics = {}
        self.end_to_end_metrics = {}
        self.queue_metrics = {}

    # ==========================================
    # TOPOLOGY MANAGEMENT
    # ==========================================

    def set_topology_graph(self, graph):
        self.topology_graph = graph.copy()

    def get_topology_graph(self):
        if self.topology_graph is None:
            return None
        return self.topology_graph.copy()

    # ==========================================
    # LINK METRICS
    # ==========================================

    def _get_link_key(self, switch_a, switch_b):
        return tuple(sorted((switch_a, switch_b)))

    def update_link_metrics(
        self,
        switch_a,
        switch_b,
        delay_ms=None,
        packet_loss_percent=None,
        utilization_percent=None
    ):
        key = self._get_link_key(switch_a, switch_b)

        metrics = self.link_metrics.get(key, {
            "delay_ms": None,
            "packet_loss_percent": None,
            "utilization_percent": None
        })

        if delay_ms is not None:
            metrics["delay_ms"] = delay_ms

        if packet_loss_percent is not None:
            metrics["packet_loss_percent"] = packet_loss_percent

        if utilization_percent is not None:
            metrics["utilization_percent"] = utilization_percent

        metrics["updated_at"] = time.time()
        self.link_metrics[key] = metrics

    def get_link_metrics(self, switch_a, switch_b):
        key = self._get_link_key(switch_a, switch_b)
        metrics = self.link_metrics.get(key)
        return metrics.copy() if metrics is not None else None

    def remove_link_metrics(self, switch_a, switch_b):
        key = self._get_link_key(switch_a, switch_b)
        self.link_metrics.pop(key, None)

    # ==========================================
    # END-TO-END METRICS
    # ==========================================

    def update_end_to_end_metrics(
        self,
        source,
        destination,
        delay_min_ms=None,
        delay_avg_ms=None,
        delay_max_ms=None,
        delay_variation_ms=None,
        packet_loss_percent=None
    ):
        key = (source, destination)

        metrics = self.end_to_end_metrics.get(key, {
            "delay_min_ms": None,
            "delay_avg_ms": None,
            "delay_max_ms": None,
            "delay_variation_ms": None,
            "packet_loss_percent": None
        })

        values = {
            "delay_min_ms": delay_min_ms,
            "delay_avg_ms": delay_avg_ms,
            "delay_max_ms": delay_max_ms,
            "delay_variation_ms": delay_variation_ms,
            "packet_loss_percent": packet_loss_percent
        }

        for name, value in values.items():
            if value is not None:
                metrics[name] = value

        metrics["updated_at"] = time.time()
        self.end_to_end_metrics[key] = metrics

    def get_end_to_end_metrics(self, source, destination):
        metrics = self.end_to_end_metrics.get((source, destination))
        return metrics.copy() if metrics is not None else None

    def display_end_to_end_metrics(self):
        print("\nEND-TO-END NETWORK METRICS")
        print("--------------------------")

        if not self.end_to_end_metrics:
            print("No end-to-end metrics available.")
            return

        for endpoints, metrics in self.end_to_end_metrics.items():
            print(
                "{} -> {} | Delay: {} ms | Packet Loss: {}%".format(
                    endpoints[0],
                    endpoints[1],
                    metrics["delay_avg_ms"],
                    metrics["packet_loss_percent"]
                )
            )

    # ==========================================
    # QUEUE METRICS
    # ==========================================

    def update_queue_metrics(
        self,
        interface,
        switch_id,
        port_number,
        backlog_bytes=0,
        backlog_packets=0,
        dropped_packets=0,
        overlimits=0
    ):
        self.queue_metrics[interface] = {
            "interface": interface,
            "switch_id": switch_id,
            "port_number": port_number,
            "backlog_bytes": backlog_bytes,
            "backlog_packets": backlog_packets,
            "dropped_packets": dropped_packets,
            "overlimits": overlimits,
            "updated_at": time.time()
        }

    def get_queue_metrics(self, interface):
        metrics = self.queue_metrics.get(interface)
        return metrics.copy() if metrics is not None else None

    def get_all_queue_metrics(self):
        return {
            interface: metrics.copy()
            for interface, metrics in self.queue_metrics.items()
        }

    def remove_queue_metrics(self, interface):
        self.queue_metrics.pop(interface, None)

    def display_queue_metrics(self):
        print("\nNETWORK QUEUE METRICS")
        print("---------------------")

        if not self.queue_metrics:
            print("No queue metrics available.")
            return

        for interface, metrics in sorted(self.queue_metrics.items()):
            print(
                "S{} | {} | Backlog: {} bytes | "
                "Packets: {} | Drops: {} | Overlimits: {}".format(
                    metrics["switch_id"],
                    interface,
                    metrics["backlog_bytes"],
                    metrics["backlog_packets"],
                    metrics["dropped_packets"],
                    metrics["overlimits"]
                )
            )

    # ==========================================
    # PATH METRICS
    # ==========================================

    def get_path_metrics(self, path):
        if len(path) < 2:
            return None

        total_delay = 0.0
        success_probability = 1.0
        maximum_utilization = 0.0

        for index in range(len(path) - 1):
            switch_a = path[index][1]
            switch_b = path[index + 1][1]

            metrics = self.get_link_metrics(switch_a, switch_b)

            if metrics is None:
                return None

            delay = metrics["delay_ms"]
            loss = metrics["packet_loss_percent"]
            utilization = metrics["utilization_percent"]

            if delay is None or loss is None or utilization is None:
                return None

            total_delay += delay
            success_probability *= (1 - loss / 100.0)
            maximum_utilization = max(maximum_utilization, utilization)

        total_packet_loss = (1 - success_probability) * 100.0

        return {
            "delay": total_delay,
            "packet_loss": total_packet_loss,
            "utilization": maximum_utilization
        }

    # ==========================================
    # DISPLAY LINK METRICS
    # ==========================================

    def display_link_metrics(self):
        print("\nNETWORK LINK METRICS")
        print("--------------------")

        if not self.link_metrics:
            print("No link metrics available.")
            return

        for link, metrics in self.link_metrics.items():
            print(
                "S{} - S{} | Delay: {} | Loss: {} | "
                "Utilization: {}%".format(
                    link[0],
                    link[1],
                    metrics["delay_ms"],
                    metrics["packet_loss_percent"],
                    metrics["utilization_percent"]
                )
            )


shared_network_state = NetworkState()
