import os
import re
import subprocess
import time

from ryu.base import app_manager
from ryu.lib import hub

from appliance.common.network_state import shared_network_state


class DelayMonitor(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(DelayMonitor, self).__init__(*args, **kwargs)

        self.source_host = "h1"
        self.destination_ip = "10.0.0.4"
        self.packet_count = 5
        self.measurement_interval = 10

        self.logger.info("Delay Monitoring Module started")

        self.monitor_thread = hub.spawn(self.monitor_loop)

    def find_host_pid(self):

        result = subprocess.run(
            ["ps", "-eo", "pid=,args="],
            capture_output=True,
            text=True
        )

        expected_command = (
            "bash --norc --noediting -is mininet:h1"
        )

        for line in result.stdout.splitlines():

            parts = line.strip().split(None, 1)

            if len(parts) == 2 and parts[1] == expected_command:
                return int(parts[0])

        return None

    def measure_delay(self):

        if os.geteuid() != 0:
            self.logger.error(
                "Delay monitoring requires root privileges "
                "to enter the Mininet host namespace"
            )
            return None

        host_pid = self.find_host_pid()

        if host_pid is None:
            self.logger.warning(
                "Mininet host H1 not found. "
                "Delay measurement skipped."
            )
            return None

        command = [
            "mnexec",
            "-a", str(host_pid),
            "ping",
            "-n",
            "-c", str(self.packet_count),
            "-W", "2",
            self.destination_ip
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.packet_count * 2 + 5
            )

            if result.returncode != 0:
                self.logger.warning(
                    "Ping failed: %s",
                    result.stderr.strip()
                )
                return None

            match = re.search(
                r"rtt min/avg/max/(?:mdev|stddev) = "
                r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
                result.stdout
            )

            if not match:
                self.logger.warning(
                    "Could not extract RTT statistics"
                )
                return None

            metrics = {
                "min_delay": float(match.group(1)),
                "avg_delay": float(match.group(2)),
                "max_delay": float(match.group(3)),
                "variation": float(match.group(4))
            }

            return metrics

        except subprocess.TimeoutExpired:

            self.logger.warning("Delay measurement timed out")
            return None

        except Exception as error:

            self.logger.exception(
                "Delay measurement error: %s", error
            )
            return None

    def monitor_loop(self):

        while True:

            metrics = self.measure_delay()

            if metrics is not None:

                shared_network_state.update_end_to_end_metrics(
                    source="H1",
                    destination="H4",
                    delay_min_ms=metrics["min_delay"],
                    delay_avg_ms=metrics["avg_delay"],
                    delay_max_ms=metrics["max_delay"],
                    delay_variation_ms=metrics["variation"]
                )

                self.logger.info(
                    "END-TO-END NETWORK STATE UPDATED | "
                    "H1 -> H4 | Average delay: %.3f ms | "
                    "Minimum: %.3f ms | Maximum: %.3f ms",
                    metrics["avg_delay"],
                    metrics["min_delay"],
                    metrics["max_delay"]
                )

            hub.sleep(self.measurement_interval)
