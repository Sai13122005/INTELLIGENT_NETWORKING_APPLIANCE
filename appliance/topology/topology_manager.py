import networkx as nx

from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.topology import event

from appliance.common.network_state import shared_network_state


class TopologyManager(app_manager.RyuApp):

    def __init__(self, *args, **kwargs):
        super(TopologyManager, self).__init__(*args, **kwargs)

        self.switches = set()
        self.links = {}
        self.hosts = {}

        self.graph = nx.Graph()

        self.logger.info("Topology Manager started")

        self.publish_topology()

    # ==========================================
    # PUBLISH TOPOLOGY
    # ==========================================

    def publish_topology(self):

        shared_network_state.set_topology_graph(
            self.graph
        )

        self.logger.info(
            "TOPOLOGY PUBLISHED | Nodes: %s | Links: %s",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges()
        )

    # ==========================================
    # SWITCH DISCOVERY
    # ==========================================

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):

        dpid = ev.switch.dp.id

        self.switches.add(dpid)

        self.graph.add_node(
            ("switch", dpid),
            type="switch"
        )

        self.logger.info("Switch discovered: %s", dpid)

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # SWITCH REMOVAL
    # ==========================================

    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):

        dpid = ev.switch.dp.id

        self.switches.discard(dpid)

        node = ("switch", dpid)

        if node in self.graph:
            self.graph.remove_node(node)

        self.links = {
            key: value for key, value in self.links.items()
            if key[0] != dpid and key[2] != dpid
        }

        for mac, attachment in list(self.hosts.items()):
            if attachment[0] == dpid:
                self.hosts.pop(mac, None)

        self.logger.warning(
            "Switch disconnected: %s", dpid
        )

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # LINK DISCOVERY
    # ==========================================

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):

        link = ev.link

        src = link.src.dpid
        src_port = link.src.port_no

        dst = link.dst.dpid
        dst_port = link.dst.port_no

        if src < dst:
            key = (src, src_port, dst, dst_port)
            port_a, port_b = src_port, dst_port
        else:
            key = (dst, dst_port, src, src_port)
            port_a, port_b = dst_port, src_port

        self.links[key] = "UP"

        self.graph.add_edge(
            ("switch", src),
            ("switch", dst),
            port_a=port_a,
            port_b=port_b,
            status="UP"
        )

        self.logger.info(
            "Link discovered: S%s:%s <--> S%s:%s",
            src, src_port, dst, dst_port
        )

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # LINK REMOVAL
    # ==========================================

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):

        link = ev.link

        src = link.src.dpid
        src_port = link.src.port_no

        dst = link.dst.dpid
        dst_port = link.dst.port_no

        if src < dst:
            key = (src, src_port, dst, dst_port)
        else:
            key = (dst, dst_port, src, src_port)

        self.links.pop(key, None)

        if self.graph.has_edge(
            ("switch", src),
            ("switch", dst)
        ):
            self.graph.remove_edge(
                ("switch", src),
                ("switch", dst)
            )

        self.logger.warning(
            "Link removed: S%s:%s <--> S%s:%s",
            src, src_port, dst, dst_port
        )

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # HOST DISCOVERY
    # ==========================================

    @set_ev_cls(event.EventHostAdd)
    def host_add_handler(self, ev):

        host = ev.host
        mac = host.mac

        if host.port is None:
            return

        dpid = host.port.dpid
        port_no = host.port.port_no

        old_attachment = self.hosts.get(mac)

        if old_attachment:
            old_dpid, old_port = old_attachment

            old_node = ("switch", old_dpid)

            if self.graph.has_edge(
                ("host", mac), old_node
            ):
                self.graph.remove_edge(
                    ("host", mac), old_node
                )

        self.hosts[mac] = (dpid, port_no)

        host_node = ("host", mac)
        switch_node = ("switch", dpid)

        self.graph.add_node(
            host_node,
            type="host"
        )

        self.graph.add_edge(
            host_node,
            switch_node,
            port=port_no,
            type="host_connection"
        )

        self.logger.info(
            "Host discovered: %s connected to S%s port %s",
            mac, dpid, port_no
        )

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # HOST REMOVAL
    # ==========================================

    @set_ev_cls(event.EventHostDelete)
    def host_delete_handler(self, ev):

        mac = ev.host.mac
        host_node = ("host", mac)

        if host_node in self.graph:
            self.graph.remove_node(host_node)

        self.hosts.pop(mac, None)

        self.logger.info("Host removed: %s", mac)

        self.publish_topology()
        self.show_topology()

    # ==========================================
    # DISPLAY TOPOLOGY
    # ==========================================

    def show_topology(self):

        self.logger.info(
            "========== NETWORK GRAPH =========="
        )

        self.logger.info(
            "Switches: %s", sorted(self.switches)
        )

        self.logger.info(
            "Hosts: %s", self.hosts
        )

        self.logger.info(
            "Graph nodes: %s",
            list(self.graph.nodes(data=True))
        )

        self.logger.info(
            "Graph edges: %s",
            list(self.graph.edges(data=True))
        )

        self.logger.info(
            "Total nodes: %s",
            self.graph.number_of_nodes()
        )

        self.logger.info(
            "Total edges: %s",
            self.graph.number_of_edges()
        )

        self.logger.info(
            "==================================="
        )
