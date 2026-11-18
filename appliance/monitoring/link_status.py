from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.topology import event

from appliance.common.network_state import shared_network_state


class LinkStatusMonitor(app_manager.RyuApp):

    OFP_VERSIONS = [0x04]

    def __init__(self, *args, **kwargs):
        super(LinkStatusMonitor, self).__init__(*args, **kwargs)

        self.port_status = {}
        self.active_links = {}

        self.logger.info("Link Status Monitor started")

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        dpid = datapath.id
        port_no = msg.desc.port_no

        ofproto = datapath.ofproto

        if port_no > ofproto.OFPP_MAX:
            return

        port_state = msg.desc.state

        if port_state & ofproto.OFPPS_LINK_DOWN:
            status = "DOWN"
        else:
            status = "UP"

        self.port_status[(dpid, port_no)] = status

        self.logger.info(
            "PORT STATUS | Switch: S%d | Port: %d | Status: %s",
            dpid,
            port_no,
            status
        )

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):

        link = ev.link

        source = (link.src.dpid, link.src.port_no)
        destination = (link.dst.dpid, link.dst.port_no)

        link_key = tuple(sorted([source, destination]))

        self.active_links[link_key] = "UP"

        self.logger.info(
            "LINK STATUS | S%d Port %d <--> S%d Port %d | UP",
            link.src.dpid,
            link.src.port_no,
            link.dst.dpid,
            link.dst.port_no
        )

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):

        link = ev.link

        source = (link.src.dpid, link.src.port_no)
        destination = (link.dst.dpid, link.dst.port_no)

        link_key = tuple(sorted([source, destination]))

        self.active_links.pop(link_key, None)

        graph = shared_network_state.get_topology_graph()

        if graph is not None:
            node_a = ("switch", link.src.dpid)
            node_b = ("switch", link.dst.dpid)

            if graph.has_edge(node_a, node_b):
                graph.remove_edge(node_a, node_b)
                shared_network_state.set_topology_graph(graph)

        self.logger.warning(
            "LINK STATUS | S%d Port %d <--> S%d Port %d | DOWN",
            link.src.dpid,
            link.src.port_no,
            link.dst.dpid,
            link.dst.port_no
        )

        self.logger.warning(
            "NETWORK STATE UPDATED | Failed link removed from topology graph"
        )
