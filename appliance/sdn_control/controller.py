from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib import hub
from ryu.topology import event

from appliance.sdn_control.flow_manager import FlowManager
from appliance.orchestration.routing_orchestrator import RoutingOrchestrator
from appliance.common.network_state import shared_network_state


class ApplianceController(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ApplianceController, self).__init__(*args, **kwargs)

        self.datapaths = {}

        # Initialize Flow Manager
        self.flow_manager = FlowManager(self)

        # Initialize Routing Orchestrator
        self.routing_orchestrator = RoutingOrchestrator(
            controller=self
        )

        self.routing_orchestrator.logger = self.logger
        self.routing_orchestrator.path_measurement.logger = self.logger

        self.test_path_installed = False
        self.routing_evaluation_started = False

        # Failure recovery protection
        self.failure_rerouting_pending = False

        self.logger.info(
            "Intelligent Networking Appliance Controller started"
        )
        self.logger.info("Flow Manager initialized")
        self.logger.info("Routing Orchestrator initialized")

    # ==========================================
    # SWITCH CONNECTION
    # ==========================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(ofproto.OFPP_NORMAL)
        ]

        self.add_flow(
            datapath,
            priority=0,
            match=match,
            actions=actions
        )

        self.logger.info(
            "Switch connected: %s | NORMAL forwarding enabled",
            datapath.id
        )

        # Temporary initial forwarding test
        if (
            len(self.datapaths) == 4
            and not self.test_path_installed
        ):

            test_path = [
                ("switch", 1),
                ("switch", 3),
                ("switch", 4)
            ]

            self.logger.info(
                "Installing temporary test path: S1 -> S3 -> S4"
            )

            result = self.install_selected_path(
                path=test_path,
                source_mac="00:00:00:00:00:01",
                destination_mac="00:00:00:00:00:02"
            )

            if result:
                self.test_path_installed = True

    # ==========================================
    # DATAPATH REGISTRATION
    # ==========================================

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):

        datapath = ev.datapath
        dpid = datapath.id

        if ev.state == MAIN_DISPATCHER:

            self.datapaths[dpid] = datapath

            self.logger.info(
                "DATAPATH REGISTERED | Switch: %s",
                dpid
            )

        elif ev.state == DEAD_DISPATCHER:

            self.datapaths.pop(dpid, None)

            self.logger.warning(
                "DATAPATH REMOVED | Switch: %s",
                dpid
            )

    # ==========================================
    # INITIAL TOPOLOGY DISCOVERY
    # ==========================================

    @set_ev_cls(event.EventLinkAdd)
    def topology_link_add_handler(self, ev):

        link = ev.link

        src = link.src.dpid
        dst = link.dst.dpid

        # Process only one direction of each physical link
        if src < dst:

            self.logger.info(
                "ROUTING ORCHESTRATOR | "
                "Topology link detected: S%s <--> S%s",
                src,
                dst
            )

            # Allow topology discovery and monitoring
            # to populate shared network state.
            hub.spawn_after(
                8,
                self.check_and_start_routing
            )

    # ==========================================
    # LINK FAILURE DETECTION
    # ==========================================

    @set_ev_cls(event.EventLinkDelete)
    def topology_link_delete_handler(self, ev):

        link = ev.link

        src = link.src.dpid
        dst = link.dst.dpid

        # Process only one direction of each physical link
        if src >= dst:
            return

        self.logger.warning(
            "LINK FAILURE DETECTED | S%s <--> S%s",
            src,
            dst
        )

        if not self.routing_evaluation_started:

            self.logger.warning(
                "Initial routing has not started yet; "
                "failure recovery will be handled after topology discovery"
            )
            return

        if self.failure_rerouting_pending:

            self.logger.info(
                "Failure recovery already pending; "
                "additional failure event will be included"
            )
            return

        self.failure_rerouting_pending = True

        self.logger.warning(
            "FAILURE RECOVERY SCHEDULED | "
            "Waiting for topology update"
        )

        # Allow Topology Manager to remove the failed edge
        # and publish the updated graph.
        hub.spawn_after(
            2,
            self.handle_failure_rerouting
        )

    # ==========================================
    # FAILURE RECOVERY
    # ==========================================

    def handle_failure_rerouting(self):

        # Wait until the previous path evaluation finishes.
        if self.routing_orchestrator.evaluation_in_progress:

            self.logger.info(
                "ROUTING EVALUATION BUSY | "
                "Retrying failure recovery in 2 seconds"
            )

            hub.spawn_after(
                2,
                self.handle_failure_rerouting
            )
            return

        # Ensure all switches are still connected.
        if len(self.datapaths) < 4:

            self.logger.error(
                "FAILURE RECOVERY ABORTED | "
                "Not all four switches are connected"
            )

            self.failure_rerouting_pending = False
            return

        graph = shared_network_state.get_topology_graph()

        if graph is None:

            self.logger.error(
                "FAILURE RECOVERY ABORTED | "
                "Topology graph is unavailable"
            )

            self.failure_rerouting_pending = False
            return

        self.logger.warning(
            "FAILURE RECOVERY STARTED | "
            "Evaluating available alternative paths"
        )

        try:
            self.run_intelligent_routing()

        finally:
            self.failure_rerouting_pending = False

            self.logger.info(
                "FAILURE RECOVERY PROCESS FINISHED"
            )

    # ==========================================
    # START INITIAL ROUTING EVALUATION
    # ==========================================

    def check_and_start_routing(self):

        if self.routing_evaluation_started:
            return

        graph = shared_network_state.get_topology_graph()

        if graph is None:
            return

        if graph.number_of_edges() < 4:

            self.logger.info(
                "Waiting for complete topology | Links: %s/4",
                graph.number_of_edges()
            )

            return

        if len(self.datapaths) < 4:

            self.logger.warning(
                "Waiting for all four switches to connect"
            )
            return

        self.routing_evaluation_started = True

        self.logger.info(
            "NETWORK TOPOLOGY READY | "
            "Starting intelligent path evaluation"
        )

        self.run_intelligent_routing()

    # ==========================================
    # INTELLIGENT ROUTING
    # ==========================================

    def run_intelligent_routing(self):

        self.logger.info(
            "INTELLIGENT ROUTING STARTED"
        )

        result = (
            self.routing_orchestrator
            .evaluate_and_install_best_path()
        )

        if result:

            self.logger.info(
                "INTELLIGENT ROUTING COMPLETED SUCCESSFULLY"
            )

        else:

            self.logger.error(
                "INTELLIGENT ROUTING COULD NOT COMPLETE"
            )

        return result

    # ==========================================
    # FLOW INSTALLATION
    # ==========================================

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions
    ):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

    # ==========================================
    # INSTALL SELECTED PATH
    # ==========================================

    def install_selected_path(
        self,
        path,
        source_mac,
        destination_mac
    ):

        self.logger.info(
            "ROUTING REQUEST RECEIVED | Path: %s",
            path
        )

        result = self.flow_manager.install_path(
            datapaths=self.datapaths,
            path=path,
            source_mac=source_mac,
            destination_mac=destination_mac
        )

        if result:

            self.logger.info(
                "ROUTING REQUEST COMPLETED SUCCESSFULLY"
            )

        else:

            self.logger.error(
                "ROUTING REQUEST FAILED"
            )

        return result

    # ==========================================
    # PACKET IN HANDLER
    # ==========================================

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == 0x88cc:
            return

        self.logger.info(
            "Packet received by controller | "
            "Switch: %s | Source: %s | Destination: %s",
            datapath.id,
            eth.src,
            eth.dst
        )
