from ryu.lib import hub

from appliance.common.network_state import shared_network_state
from appliance.routing.path_calculation import PathCalculation
from appliance.routing.cost_calculation import CostCalculation
from appliance.monitoring.path_measurement import PathMeasurement
from appliance.mpls.mpls_orchestrator import MPLSOrchestrator


class RoutingOrchestrator:

    def __init__(self, network_state=None, controller=None):

        self.network_state = (
            network_state
            if network_state is not None
            else shared_network_state
        )

        self.controller = controller
        self.logger = None

        self.path_calculator = PathCalculation()
        self.cost_calculator = CostCalculation()
        self.path_measurement = PathMeasurement()

        # MPLS integration
        self.mpls_orchestrator = MPLSOrchestrator()
        self.mpls_lsp_id = "H1-H4"

        self.evaluation_in_progress = False

        self.source_mac = "00:00:00:00:00:01"
        self.destination_mac = "00:00:00:00:00:02"

        self.source_ip = "10.0.0.1"
        self.destination_ip = "10.0.0.4"

    # ==========================================
    # DISCOVER CANDIDATE PATHS
    # ==========================================

    def discover_candidate_paths(self, source, destination):

        network_graph = self.network_state.get_topology_graph()

        if network_graph is None:
            self._log_error("Network topology is not available")
            return []

        if source not in network_graph:
            self._log_error("Source switch does not exist")
            return []

        if destination not in network_graph:
            self._log_error("Destination switch does not exist")
            return []

        try:
            available_paths = self.path_calculator.find_all_paths(
                network_graph,
                source,
                destination
            )

        except ValueError as error:
            self._log_error(str(error))
            return []

        self._log_info("AVAILABLE CANDIDATE PATHS")
        self.path_calculator.display_paths(available_paths)

        self._log_info(
            "Total candidate paths discovered: %s",
            len(available_paths)
        )

        return available_paths

    # ==========================================
    # REMOVE EXISTING MPLS LSP
    # ==========================================

    def remove_existing_mpls_lsp(self):

        existing_lsp = self.mpls_orchestrator.get_lsp(
            self.mpls_lsp_id
        )

        if existing_lsp is None:
            return True

        self._log_info(
            "EXISTING MPLS LSP FOUND | Removing before path evaluation"
        )

        try:
            result = self.mpls_orchestrator.remove_lsp(
                self.mpls_lsp_id
            )

            if result:
                self._log_info(
                    "EXISTING MPLS LSP REMOVED SUCCESSFULLY"
                )
                return True

            self._log_error(
                "Could not remove existing MPLS LSP"
            )
            return False

        except Exception as error:
            self._log_error(
                "MPLS LSP removal failed: %s",
                str(error)
            )
            return False

    # ==========================================
    # GET PATH UTILIZATION
    # ==========================================

    def get_path_utilization(self, path):

        maximum_utilization = 0.0

        for index in range(len(path) - 1):

            switch_a = path[index][1]
            switch_b = path[index + 1][1]

            metrics = self.network_state.get_link_metrics(
                switch_a,
                switch_b
            )

            if metrics is None:
                return None

            utilization = metrics["utilization_percent"]

            if utilization is None:
                return None

            maximum_utilization = max(
                maximum_utilization,
                utilization
            )

        return maximum_utilization

    # ==========================================
    # EVALUATE AND SELECT BEST PATH
    # ==========================================

    def evaluate_and_install_best_path(self):

        if self.evaluation_in_progress:
            self._log_info(
                "Path evaluation already in progress"
            )
            return False

        if self.controller is None:
            self._log_error("SDN Controller is not connected")
            return False

        self.evaluation_in_progress = True

        try:

            # Remove previous MPLS forwarding before
            # measuring alternative IP paths.
            if not self.remove_existing_mpls_lsp():
                return False

            source = ("switch", 1)
            destination = ("switch", 4)

            paths = self.discover_candidate_paths(
                source,
                destination
            )

            if not paths:
                self._log_error("No candidate paths available")
                return False

            measured_paths = {}

            # Measure each candidate path separately
            for index, path in enumerate(paths, start=1):

                path_name = " -> ".join(
                    "S%s" % node[1]
                    for node in path
                )

                self._log_info(
                    "MEASURING PATH %s | %s",
                    index,
                    path_name
                )

                # Install temporary IP forwarding
                installed = self.controller.install_selected_path(
                    path,
                    self.source_mac,
                    self.destination_mac
                )

                if not installed:
                    self._log_error(
                        "Could not install candidate path: %s",
                        path_name
                    )
                    continue

                hub.sleep(2)

                # Measure end-to-end metrics
                metrics = self.path_measurement.measure_path()

                if metrics is None:
                    self._log_error(
                        "Measurement failed for %s",
                        path_name
                    )
                    continue

                if metrics["avg_delay"] is None:
                    self._log_error(
                        "No valid RTT available for %s",
                        path_name
                    )
                    continue

                utilization = self.get_path_utilization(path)

                if utilization is None:
                    self._log_error(
                        "Link utilization unavailable for %s",
                        path_name
                    )
                    continue

                measured_paths[path_name] = {
                    "delay": metrics["avg_delay"],
                    "packet_loss": metrics["packet_loss"],
                    "utilization": utilization
                }

            if not measured_paths:
                self._log_error(
                    "No candidate paths have complete measurements"
                )
                return False

            # Calculate path costs
            path_costs = (
                self.cost_calculator.calculate_all_path_costs(
                    measured_paths
                )
            )

            self._log_info("PATH COST COMPARISON")

            for path_name, metrics in measured_paths.items():

                self._log_info(
                    "%s | Delay: %.3f ms | Loss: %.2f%% | "
                    "Utilization: %.4f%% | Cost: %.4f",
                    path_name,
                    metrics["delay"],
                    metrics["packet_loss"],
                    metrics["utilization"],
                    path_costs[path_name]
                )

            # Select the lowest-cost path
            best_path_name = (
                self.cost_calculator.select_best_path(
                    path_costs
                )
            )

            best_path = None

            for path in paths:

                path_name = " -> ".join(
                    "S%s" % node[1]
                    for node in path
                )

                if path_name == best_path_name:
                    best_path = path
                    break

            if best_path is None:
                self._log_error("Selected path could not be found")
                return False

            self._log_info(
                "BEST PATH SELECTED | %s",
                best_path_name
            )

            # Install selected bidirectional IP path.
            # This provides the reverse H4 -> H1 route.
            result = self.controller.install_selected_path(
                best_path,
                self.source_mac,
                self.destination_mac
            )

            if not result:
                self._log_error(
                    "Could not install selected IP path"
                )
                return False

            # Convert routing nodes into MPLS switch names.
            mpls_path = [
                "S{}".format(node[1])
                for node in best_path
            ]

            self._log_info(
                "ESTABLISHING MPLS LSP | %s",
                " -> ".join(mpls_path)
            )

            # Establish MPLS forwarding over selected path.
            try:
                mpls_result = self.mpls_orchestrator.create_lsp(
                    lsp_id=self.mpls_lsp_id,
                    source=mpls_path[0],
                    destination=mpls_path[-1],
                    path=mpls_path,
                    source_ip=self.source_ip,
                    destination_ip=self.destination_ip
                )

            except Exception as error:

                self._log_error(
                    "MPLS establishment failed: %s",
                    str(error)
                )

                self._log_info(
                    "IP forwarding remains installed as fallback"
                )

                return False

            if not mpls_result.get("success"):
                self._log_error(
                    "MPLS LSP establishment was unsuccessful"
                )
                return False

            self._log_info(
                "MPLS LSP ESTABLISHED SUCCESSFULLY"
            )

            self._log_info(
                "INTELLIGENT ROUTING AND MPLS INTEGRATION "
                "COMPLETED SUCCESSFULLY"
            )

            return True

        finally:
            self.evaluation_in_progress = False

    # ==========================================
    # LOGGING
    # ==========================================

    def _log_info(self, message, *args):

        if self.logger:
            self.logger.info(message, *args)
        else:
            print(message % args if args else message)

    def _log_error(self, message, *args):

        if self.logger:
            self.logger.error(message, *args)
        else:
            print(
                "ERROR: " +
                (message % args if args else message)
            )
