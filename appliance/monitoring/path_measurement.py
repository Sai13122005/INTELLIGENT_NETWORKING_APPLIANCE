import os
import re
import subprocess


class PathMeasurement:

    def __init__(self, logger=None):

        self.logger = logger

        self.source_host = "h1"
        self.destination_ip = "10.0.0.4"

        self.packet_count = 10
        self.packet_timeout = 2

    # ==========================================
    # FIND MININET HOST PROCESS
    # ==========================================

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

    # ==========================================
    # MEASURE CURRENT PATH
    # ==========================================

    def measure_path(self):

        if os.geteuid() != 0:

            self._log_error(
                "Path measurement requires root privileges"
            )

            return None

        host_pid = self.find_host_pid()

        if host_pid is None:

            self._log_error(
                "Mininet host H1 not found"
            )

            return None

        command = [
            "mnexec",
            "-a", str(host_pid),
            "ping",
            "-n",
            "-c", str(self.packet_count),
            "-W", str(self.packet_timeout),
            self.destination_ip
        ]

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.packet_count * self.packet_timeout + 5
            )

            output = result.stdout

            # Extract transmitted and received packets
            packet_match = re.search(
                r"(\d+) packets transmitted,\s*(\d+) "
                r"(?:packets )?received",
                output
            )

            if not packet_match:

                self._log_error(
                    "Could not extract packet statistics"
                )

                return None

            sent = int(packet_match.group(1))
            received = int(packet_match.group(2))

            if sent == 0:
                return None

            lost = sent - received

            packet_loss = (
                lost / sent
            ) * 100.0

            # Extract RTT statistics
            rtt_match = re.search(
                r"rtt min/avg/max/(?:mdev|stddev) = "
                r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms",
                output
            )

            if rtt_match:

                min_delay = float(rtt_match.group(1))
                avg_delay = float(rtt_match.group(2))
                max_delay = float(rtt_match.group(3))
                variation = float(rtt_match.group(4))

            else:

                min_delay = None
                avg_delay = None
                max_delay = None
                variation = None

            metrics = {
                "sent": sent,
                "received": received,
                "lost": lost,
                "packet_loss": packet_loss,
                "min_delay": min_delay,
                "avg_delay": avg_delay,
                "max_delay": max_delay,
                "variation": variation
            }

            self._log_info(
                "PATH MEASUREMENT | "
                "Sent: %s | Received: %s | "
                "Loss: %.2f%% | Average RTT: %s",
                sent,
                received,
                packet_loss,
                avg_delay
            )

            return metrics

        except subprocess.TimeoutExpired:

            self._log_error(
                "Path measurement timed out"
            )

            return None

        except Exception as error:

            self._log_error(
                "Path measurement error: %s",
                error
            )

            return None

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
