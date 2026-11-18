import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.topology import event

from appliance.common.network_state import shared_network_state


class MonitoringEngine(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MonitoringEngine, self).__init__(*args, **kwargs)

        self.datapaths = {}
        self.previous_stats = {}
        self.port_metrics = {}

        # Maps each switch port to its neighboring switch port
        self.link_ports = {}

        # Stores the latest utilization for each switch port
        self.link_port_utilization = {}

        # Configured link capacity: 10 Mbps
        self.link_capacity_bps = 10_000_000

        self.logger.info("Monitoring Engine started")

        self.monitor_thread = hub.spawn(self.monitor_loop)

    # Register and remove connected switches
    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):

        datapath = ev.datapath
        dpid = datapath.id

        if dpid is None:
            return

        if ev.state == MAIN_DISPATCHER:

            if dpid not in self.datapaths:
                self.logger.info(
                    "Monitoring registered switch: %s", dpid
                )

            self.datapaths[dpid] = datapath

        elif ev.state == DEAD_DISPATCHER:

            self.datapaths.pop(dpid, None)

            self.previous_stats = {
                key: value
                for key, value in self.previous_stats.items()
                if key[0] != dpid
            }

            self.port_metrics = {
                key: value
                for key, value in self.port_metrics.items()
                if key[0] != dpid
            }

            # Remove links associated with the disconnected switch
            affected_links = [
                (local, peer)
                for local, peer in self.link_ports.items()
                if local[0] == dpid or peer[0] == dpid
            ]

            for local, peer in affected_links:
                self.link_ports.pop(local, None)
                self.link_ports.pop(peer, None)

                self.link_port_utilization.pop(local, None)
                self.link_port_utilization.pop(peer, None)

                shared_network_state.remove_link_metrics(
                    local[0], peer[0]
                )

            self.logger.warning(
                "Monitoring removed disconnected switch: %s",
                dpid
            )

    # Discover physical switch-to-switch links
    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):

        link = ev.link

        src = (link.src.dpid, link.src.port_no)
        dst = (link.dst.dpid, link.dst.port_no)

        self.link_ports[src] = dst
        self.link_ports[dst] = src

        self.logger.info(
            "Monitoring link discovered: S%s Port %s <--> S%s Port %s",
            src[0], src[1], dst[0], dst[1]
        )

    # Remove disconnected physical links
    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):

        link = ev.link

        src = (link.src.dpid, link.src.port_no)
        dst = (link.dst.dpid, link.dst.port_no)

        self.link_ports.pop(src, None)
        self.link_ports.pop(dst, None)

        self.link_port_utilization.pop(src, None)
        self.link_port_utilization.pop(dst, None)

        shared_network_state.remove_link_metrics(
            src[0], dst[0]
        )

        self.logger.warning(
            "Monitoring link removed: S%s <--> S%s",
            src[0], dst[0]
        )

    # Periodically request port statistics
    def monitor_loop(self):

        while True:

            for datapath in list(self.datapaths.values()):
                self.request_port_stats(datapath)

            hub.sleep(5)

    # Send port statistics request
    def request_port_stats(self, datapath):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        request = parser.OFPPortStatsRequest(
            datapath,
            0,
            ofproto.OFPP_ANY
        )

        datapath.send_msg(request)

        self.logger.info(
            "Requested port statistics from switch %s",
            datapath.id
        )

    # Receive statistics replies
    @set_ev_cls(
        ofp_event.EventOFPPortStatsReply,
        MAIN_DISPATCHER
    )
    def port_stats_reply_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        current_time = time.time()

        for stat in ev.msg.body:

            port_no = stat.port_no

            if port_no >= datapath.ofproto.OFPP_MAX:
                continue

            key = (dpid, port_no)

            current = {
                "rx_bytes": stat.rx_bytes,
                "tx_bytes": stat.tx_bytes,
                "rx_packets": stat.rx_packets,
                "tx_packets": stat.tx_packets,
                "rx_dropped": stat.rx_dropped,
                "tx_dropped": stat.tx_dropped,
                "rx_errors": stat.rx_errors,
                "tx_errors": stat.tx_errors
            }

            previous = self.previous_stats.get(key)

            if previous is not None:

                elapsed = current_time - previous["time"]

                if elapsed > 0:

                    rx_delta = max(
                        0,
                        current["rx_bytes"] - previous["rx_bytes"]
                    )

                    tx_delta = max(
                        0,
                        current["tx_bytes"] - previous["tx_bytes"]
                    )

                    rx_rate = rx_delta * 8 / elapsed
                    tx_rate = tx_delta * 8 / elapsed

                    rx_utilization = (
                        rx_rate / self.link_capacity_bps
                    ) * 100

                    tx_utilization = (
                        tx_rate / self.link_capacity_bps
                    ) * 100

                    self.port_metrics[key] = {
                        **current,
                        "rx_bps": rx_rate,
                        "tx_bps": tx_rate,
                        "rx_utilization": rx_utilization,
                        "tx_utilization": tx_utilization,
                        "timestamp": current_time
                    }

                    self.logger.info(
                        "MONITOR S%s Port %s | "
                        "RX: %.2f bps (%.2f%%) | "
                        "TX: %.2f bps (%.2f%%) | "
                        "RX drops: %s | TX drops: %s",
                        dpid,
                        port_no,
                        rx_rate,
                        rx_utilization,
                        tx_rate,
                        tx_utilization,
                        current["rx_dropped"],
                        current["tx_dropped"]
                    )

                    # Update shared Network State for switch links
                    self.update_link_utilization(
                        dpid,
                        port_no,
                        max(rx_utilization, tx_utilization)
                    )

            current["time"] = current_time
            self.previous_stats[key] = current

    # Transfer calculated port utilization into Network State
    def update_link_utilization(
        self,
        dpid,
        port_no,
        utilization
    ):

        local = (dpid, port_no)
        peer = self.link_ports.get(local)

        # Ignore host-facing ports
        if peer is None:
            return

        self.link_port_utilization[local] = utilization

        peer_utilization = self.link_port_utilization.get(peer)

        # Use the higher observed utilization of the two link ends
        link_utilization = max(
            utilization,
            peer_utilization if peer_utilization is not None else 0.0
        )

        shared_network_state.update_link_metrics(
            dpid,
            peer[0],
            utilization_percent=link_utilization
        )

        self.logger.info(
            "NETWORK STATE UPDATED | S%s <--> S%s | "
            "Utilization: %.4f%%",
            dpid,
            peer[0],
            link_utilization
        )
