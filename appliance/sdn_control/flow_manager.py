class FlowManager:

    def __init__(self, controller):
        self.controller = controller
        self.logger = controller.logger

        self.active_path = None

        # Verified Mininet switch-to-switch port mappings
        self.port_map = {
            (1, 2): 2,
            (2, 1): 1,
            (2, 4): 2,
            (4, 2): 2,
            (1, 3): 3,
            (3, 1): 1,
            (3, 4): 2,
            (4, 3): 3
        }

        # Host-facing ports
        self.host_ports = {
            1: 1,
            4: 1
        }

        # Priority reserved for appliance forwarding rules
        self.flow_priority = 100

    def delete_existing_path_rules(
        self,
        datapaths,
        source_mac,
        destination_mac
    ):

        for datapath in datapaths.values():

            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            # Delete H1 -> H4 rule
            forward_match = parser.OFPMatch(
                eth_src=source_mac,
                eth_dst=destination_mac
            )

            forward_delete = parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE_STRICT,
                priority=self.flow_priority,
                match=forward_match,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY
            )

            datapath.send_msg(forward_delete)

            # Delete H4 -> H1 rule
            reverse_match = parser.OFPMatch(
                eth_src=destination_mac,
                eth_dst=source_mac
            )

            reverse_delete = parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE_STRICT,
                priority=self.flow_priority,
                match=reverse_match,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY
            )

            datapath.send_msg(reverse_delete)

        self.logger.info(
            "Previous H1-H4 forwarding rules removed"
        )

    def install_path(
        self,
        datapaths,
        path,
        source_mac,
        destination_mac
    ):

        if not path or len(path) < 2:
            self.logger.error("Invalid path supplied")
            return False

        switch_path = []

        for node in path:

            if isinstance(node, tuple) and node[0] == "switch":
                switch_path.append(node[1])
            else:
                self.logger.error(
                    "Only switch-to-switch paths are supported"
                )
                return False

        if len(switch_path) < 2:
            self.logger.error("Path must contain at least two switches")
            return False

        if len(set(switch_path)) != len(switch_path):
            self.logger.error("Path contains repeated switches")
            return False

        # Validate all switches before changing existing rules
        for dpid in switch_path:

            if dpid not in datapaths:
                self.logger.error(
                    "Switch %s is not connected", dpid
                )
                return False

        # Calculate forward output ports
        forward_outputs = {}

        for index in range(len(switch_path) - 1):

            current = switch_path[index]
            next_switch = switch_path[index + 1]

            port = self.port_map.get((current, next_switch))

            if port is None:
                self.logger.error(
                    "No port mapping for S%s -> S%s",
                    current, next_switch
                )
                return False

            forward_outputs[current] = port

        if switch_path[-1] not in self.host_ports:
            self.logger.error(
                "No host-facing port configured for S%s",
                switch_path[-1]
            )
            return False

        forward_outputs[switch_path[-1]] = self.host_ports[
            switch_path[-1]
        ]

        # Calculate reverse output ports
        reverse_outputs = {}

        for index in range(len(switch_path) - 1, 0, -1):

            current = switch_path[index]
            previous = switch_path[index - 1]

            port = self.port_map.get((current, previous))

            if port is None:
                self.logger.error(
                    "No reverse port mapping for S%s -> S%s",
                    current, previous
                )
                return False

            reverse_outputs[current] = port

        if switch_path[0] not in self.host_ports:
            self.logger.error(
                "No host-facing port configured for S%s",
                switch_path[0]
            )
            return False

        reverse_outputs[switch_path[0]] = self.host_ports[
            switch_path[0]
        ]

        # All validation is complete. Remove old rules.
        self.delete_existing_path_rules(
            datapaths,
            source_mac,
            destination_mac
        )

        # Install forward-direction rules
        for dpid, output_port in forward_outputs.items():

            datapath = datapaths[dpid]
            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_src=source_mac,
                eth_dst=destination_mac
            )

            self.controller.add_flow(
                datapath,
                priority=self.flow_priority,
                match=match,
                actions=[
                    parser.OFPActionOutput(output_port)
                ]
            )

        # Install reverse-direction rules
        for dpid, output_port in reverse_outputs.items():

            datapath = datapaths[dpid]
            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_src=destination_mac,
                eth_dst=source_mac
            )

            self.controller.add_flow(
                datapath,
                priority=self.flow_priority,
                match=match,
                actions=[
                    parser.OFPActionOutput(output_port)
                ]
            )

        self.active_path = list(switch_path)

        self.logger.info(
            "PATH INSTALLED | %s",
            " -> ".join(
                "S%s" % dpid for dpid in switch_path
            )
        )

        return True
