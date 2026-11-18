import ipaddress
import secrets
import subprocess

from appliance.mpls.label_manager import LabelManager


class MPLSForwardingManager:
    """Manages MPLS PUSH, SWAP and POP rules in Open vSwitch."""

    def __init__(self, label_manager=None, port_map=None,
                 host_ports=None, priority=200):

        self.label_manager = label_manager or LabelManager()

        self.port_map = port_map or {
            ("S1", "S2"): 2,
            ("S2", "S1"): 1,
            ("S2", "S4"): 2,
            ("S4", "S2"): 2,
            ("S1", "S3"): 3,
            ("S3", "S1"): 1,
            ("S3", "S4"): 2,
            ("S4", "S3"): 3
        }

        self.host_ports = host_ports or {
            "S1": 1,
            "S4": 1
        }

        self.priority = priority
        self.installed_lsps = {}

    def _normalize_switch(self, switch):
        if isinstance(switch, int):
            switch = "S{}".format(switch)

        switch = str(switch).upper()

        if not switch.startswith("S") or not switch[1:].isdigit():
            raise ValueError("Invalid switch: {}".format(switch))

        return switch

    def _bridge_name(self, switch):
        return self._normalize_switch(switch).lower()

    def _get_port(self, source, destination):
        source = self._normalize_switch(source)
        destination = self._normalize_switch(destination)

        port = self.port_map.get((source, destination))

        if port is None:
            raise ValueError(
                "No port mapping for {} -> {}".format(
                    source, destination
                )
            )

        return port

    def _run_ofctl(self, bridge, operation, flow):
        command = [
            "ovs-ofctl",
            "-O", "OpenFlow13",
            operation,
            bridge,
            flow
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        if result.returncode != 0:
            raise RuntimeError(
                "OVS command failed on {}: {}".format(
                    bridge, result.stderr.strip()
                )
            )

        return result.stdout.strip()

    def _delete_cookie(self, bridge, cookie):
        flow_filter = "cookie=0x{:x}/0xffffffffffffffff".format(cookie)
        self._run_ofctl(bridge, "del-flows", flow_filter)

    def _build_forwarding_rules(
        self, lsp, source_ip, destination_ip, cookie
    ):
        path = [
            self._normalize_switch(switch)
            for switch in lsp["path"]
        ]

        lsp_id = lsp["lsp_id"]

        if len(path) < 2:
            raise ValueError("An LSP requires at least two switches.")

        if len(set(path)) != len(path):
            raise ValueError("Repeated switches are not allowed.")

        if path[0] not in self.host_ports:
            raise ValueError("Source switch has no host-facing port.")

        if path[-1] not in self.host_ports:
            raise ValueError("Destination switch has no host-facing port.")

        labels = [int(lsp["label"])]
        additional_label_ids = []

        for edge_index in range(1, len(path) - 1):
            label_id = "{}:segment:{}".format(lsp_id, edge_index)

            label = self.label_manager.allocate_label(label_id)

            labels.append(label)
            additional_label_ids.append(label_id)

        rules = []

        # Destination switch: POP
        destination = path[-1]
        previous_switch = path[-2]

        # Incoming port on the destination switch.
        incoming_port = self._get_port(
            destination, previous_switch
        )

        destination_host_port = self.host_ports[destination]

        destination_flow = (
            "cookie=0x{cookie:x},"
            "table=0,"
            "priority={priority},"
            "in_port={in_port},"
            "mpls,"
            "mpls_label={label},"
            "actions=pop_mpls:0x0800,output:{host_port}"
        ).format(
            cookie=cookie,
            priority=self.priority,
            in_port=incoming_port,
            label=labels[-1],
            host_port=destination_host_port
        )

        rules.append((
            self._bridge_name(destination),
            destination_flow
        ))

        # Intermediate switches: SWAP
        for index in range(len(path) - 2, 0, -1):

            current_switch = path[index]
            previous_switch = path[index - 1]
            next_switch = path[index + 1]

            # Incoming port on the current switch.
            incoming_port = self._get_port(
                current_switch, previous_switch
            )

            # Outgoing port towards the next switch.
            outgoing_port = self._get_port(
                current_switch, next_switch
            )

            incoming_label = labels[index - 1]
            outgoing_label = labels[index]

            swap_flow = (
                "cookie=0x{cookie:x},"
                "table=0,"
                "priority={priority},"
                "in_port={in_port},"
                "mpls,"
                "mpls_label={incoming_label},"
                "actions=set_field:{outgoing_label}->mpls_label,"
                "output:{outgoing_port}"
            ).format(
                cookie=cookie,
                priority=self.priority,
                in_port=incoming_port,
                incoming_label=incoming_label,
                outgoing_label=outgoing_label,
                outgoing_port=outgoing_port
            )

            rules.append((
                self._bridge_name(current_switch),
                swap_flow
            ))

        # Source switch: PUSH
        source = path[0]

        source_host_port = self.host_ports[source]
        outgoing_port = self._get_port(source, path[1])

        source_flow = (
            "cookie=0x{cookie:x},"
            "table=0,"
            "priority={priority},"
            "in_port={in_port},"
            "ip,"
            "nw_src={source_ip},"
            "nw_dst={destination_ip},"
            "actions=push_mpls:0x8847,"
            "set_field:{label}->mpls_label,"
            "output:{outgoing_port}"
        ).format(
            cookie=cookie,
            priority=self.priority,
            in_port=source_host_port,
            source_ip=source_ip,
            destination_ip=destination_ip,
            label=labels[0],
            outgoing_port=outgoing_port
        )

        rules.append((
            self._bridge_name(source),
            source_flow
        ))

        return rules, labels, additional_label_ids

    def install_lsp(self, lsp, source_ip, destination_ip):
        """Install downstream rules before the ingress rule."""

        lsp_id = lsp["lsp_id"]

        if lsp_id in self.installed_lsps:
            raise ValueError(
                "Forwarding already installed for {}".format(lsp_id)
            )

        source_ip = str(ipaddress.ip_address(source_ip))
        destination_ip = str(ipaddress.ip_address(destination_ip))

        cookie = secrets.randbits(64)

        rules, labels, additional_label_ids = (
            self._build_forwarding_rules(
                lsp, source_ip, destination_ip, cookie
            )
        )

        installed_bridges = set()

        try:
            for bridge, flow in rules:
                self._run_ofctl(bridge, "add-flow", flow)
                installed_bridges.add(bridge)

                print(
                    "[MPLS FORWARDING] Installed rule on {}: {}".format(
                        bridge, flow
                    )
                )

        except Exception:
            for bridge in installed_bridges:
                try:
                    self._delete_cookie(bridge, cookie)
                except Exception:
                    pass

            for label_id in additional_label_ids:
                self.label_manager.release_label(label_id)

            raise

        self.installed_lsps[lsp_id] = {
            "cookie": cookie,
            "path": list(lsp["path"]),
            "labels": list(labels),
            "additional_label_ids": list(additional_label_ids),
            "bridges": sorted(installed_bridges)
        }

        print(
            "[MPLS FORWARDING] LSP {} installed successfully".format(
                lsp_id
            )
        )

        return dict(self.installed_lsps[lsp_id])

    def remove_lsp(self, lsp_id):
        """Remove forwarding rules and release additional labels."""

        installation = self.installed_lsps.get(lsp_id)

        if installation is None:
            return False

        errors = []

        for bridge in installation["bridges"]:
            try:
                self._delete_cookie(
                    bridge, installation["cookie"]
                )
            except Exception as error:
                errors.append(str(error))

        if errors:
            raise RuntimeError(
                "Could not completely remove LSP {}: {}".format(
                    lsp_id, "; ".join(errors)
                )
            )

        for label_id in installation["additional_label_ids"]:
            self.label_manager.release_label(label_id)

        del self.installed_lsps[lsp_id]

        print(
            "[MPLS FORWARDING] Removed forwarding for {}".format(
                lsp_id
            )
        )

        return True

    def get_installation(self, lsp_id):
        installation = self.installed_lsps.get(lsp_id)

        return dict(installation) if installation else None

    def display_installations(self):
        print("\n======= MPLS FORWARDING DATABASE =======")

        if not self.installed_lsps:
            print("No MPLS forwarding paths installed.")

        for lsp_id, details in self.installed_lsps.items():
            print("LSP ID: {}".format(lsp_id))
            print("Path: {}".format(" -> ".join(details["path"])))
            print("Labels: {}".format(details["labels"]))
            print("Bridges: {}".format(details["bridges"]))
            print("----------------------------------------")

        print("========================================\n")
