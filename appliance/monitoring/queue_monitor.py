import re
import subprocess

from ryu.base import app_manager
from ryu.lib import hub

from appliance.common.network_state import shared_network_state


class QueueMonitor(app_manager.RyuApp):

    MONITOR_INTERVAL = 5

    def __init__(self, *args, **kwargs):
        super(QueueMonitor, self).__init__(*args, **kwargs)

        self.logger.info("QUEUE MONITOR INITIALIZED")
        self.monitor_thread = hub.spawn(self.monitor_queues)

    def run_command(self, command):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )

            if result.returncode != 0:
                return None

            return result.stdout.strip()

        except (subprocess.TimeoutExpired, OSError) as error:
            self.logger.warning(
                "Command failed: %s | Error: %s",
                command,
                error
            )
            return None

    def discover_switches(self):
        output = self.run_command(["ovs-vsctl", "list-br"])

        return output.splitlines() if output else []

    def discover_interfaces(self, bridge):
        output = self.run_command(
            ["ovs-vsctl", "list-ports", bridge]
        )

        if not output:
            return []

        match = re.fullmatch(r"s(\d+)", bridge)

        if not match:
            return []

        switch_id = int(match.group(1))
        interfaces = []

        for interface in output.splitlines():

            port_output = self.run_command([
                "ovs-vsctl", "get",
                "Interface", interface, "ofport"
            ])

            if not port_output:
                continue

            try:
                port_number = int(port_output.strip())
            except ValueError:
                continue

            if port_number <= 0:
                continue

            interfaces.append({
                "interface": interface,
                "switch_id": switch_id,
                "port_number": port_number
            })

        return interfaces

    def collect_queue_statistics(self, interface):
        output = self.run_command([
            "tc", "-s", "class", "show", "dev", interface
        ])

        if not output:
            return None

        backlog_bytes = 0
        backlog_packets = 0
        dropped_packets = 0
        overlimits = 0

        backlog_found = False
        class_found = False

        for match in re.finditer(
            r"backlog\s+(\d+)b\s+(\d+)p",
            output
        ):
            backlog_bytes += int(match.group(1))
            backlog_packets += int(match.group(2))
            backlog_found = True

        for match in re.finditer(
            r"dropped\s+(\d+),\s*overlimits\s+(\d+)",
            output
        ):
            dropped_packets += int(match.group(1))
            overlimits += int(match.group(2))
            class_found = True

        if not backlog_found or not class_found:
            return None

        return {
            "backlog_bytes": backlog_bytes,
            "backlog_packets": backlog_packets,
            "dropped_packets": dropped_packets,
            "overlimits": overlimits
        }

    def monitor_queues(self):
        self.logger.info("QUEUE MONITOR STARTED")

        while True:

            try:
                bridges = self.discover_switches()

                for bridge in bridges:

                    interfaces = self.discover_interfaces(bridge)

                    for item in interfaces:

                        interface = item["interface"]

                        metrics = self.collect_queue_statistics(
                            interface
                        )

                        if metrics is None:
                            continue

                        shared_network_state.update_queue_metrics(
                            interface=interface,
                            switch_id=item["switch_id"],
                            port_number=item["port_number"],
                            backlog_bytes=metrics["backlog_bytes"],
                            backlog_packets=metrics["backlog_packets"],
                            dropped_packets=metrics["dropped_packets"],
                            overlimits=metrics["overlimits"]
                        )

                        self.logger.info(
                            "QUEUE METRICS | %s | Backlog: %s bytes, "
                            "%s packets | Dropped: %s | Overlimits: %s",
                            interface,
                            metrics["backlog_bytes"],
                            metrics["backlog_packets"],
                            metrics["dropped_packets"],
                            metrics["overlimits"]
                        )

                # Read the values back from the shared Network State.
                stored_metrics = (
                    shared_network_state.get_all_queue_metrics()
                )

                self.logger.info(
                    "QUEUE STATE READBACK | Stored interfaces: %s | "
                    "Stored metrics: %s",
                    len(stored_metrics),
                    stored_metrics
                )

            except Exception:
                self.logger.exception(
                    "Unexpected error in queue monitoring"
                )

            hub.sleep(self.MONITOR_INTERVAL)
