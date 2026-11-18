import os
import re
import subprocess

from ryu.base import app_manager
from ryu.lib import hub

from appliance.common.network_state import shared_network_state


class PacketLossMonitor(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(PacketLossMonitor, self).__init__(*args, **kwargs)

        self.source_host = "h1"
        self.destination_ip = "10.0.0.4"
        self.packet_count = 10
        self.measurement_interval = 10

        self.logger.info("Packet Loss Monitoring Module started")

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

    def measure_packet_loss(self):
        if os.geteuid() != 0:
            self.logger.error(
                "Packet-loss monitoring requires root privileges."
            )
            return None

        host_pid = self.find_host_pid()

        if host_pid is None:
            self.logger.warning(
                "Mininet host H1 not found. Measurement skipped."
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

            match = re.search(
                r"(\d+) packets transmitted,\s*(\d+) "
                r"(?:packets )?received",
                result.stdout
            )

            if not match:
                self.logger.warning(
                    "Could not obtain valid ping statistics. "
                    "Output: %s",
                    result.stdout.strip()
                )
                return None

            sent = int(match.group(1))
            received = int(match.group(2))

            if sent == 0:
                return None

            lost = sent - received
            loss_percentage = (lost / sent) * 100.0

            self.logger.info(
                "PACKET LOSS | H1 -> H4 | "
                "Sent: %s | Received: %s | Lost: %s | Loss: %.2f%%",
                sent,
                received,
                lost,
                loss_percentage
            )

            return loss_percentage

        except subprocess.TimeoutExpired:
            self.logger.warning("Packet-loss measurement timed out.")
            return None

        except Exception as error:
            self.logger.exception(
                "Packet-loss measurement error: %s", error
            )
            return None

    def monitor_loop(self):
        while True:
            loss_percentage = self.measure_packet_loss()

            if loss_percentage is not None:
                shared_network_state.update_end_to_end_metrics(
                    source="H1",
                    destination="H4",
                    packet_loss_percent=loss_percentage
                )

                self.logger.info(
                    "END-TO-END PACKET LOSS UPDATED | "
                    "H1 -> H4 | Packet loss: %.2f%%",
                    loss_percentage
                )

            hub.sleep(self.measurement_interval)
