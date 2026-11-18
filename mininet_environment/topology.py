
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI


class DiamondTopology(Topo):

    def build(self):

        # Create four switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        # Create source and destination hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h4 = self.addHost('h4', ip='10.0.0.4/24')

        # Connect hosts to switches
        self.addLink(h1, s1, bw=10)
        self.addLink(s4, h4, bw=10)

        # Upper path: S1 -> S2 -> S4
        self.addLink(s1, s2, bw=10)
        self.addLink(s2, s4, bw=10)

        # Lower path: S1 -> S3 -> S4
        self.addLink(s1, s3, bw=10)
        self.addLink(s3, s4, bw=10)


def run_network():

    topo = DiamondTopology()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True
    )

    # Connect to our existing Ryu controller
    net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6653
    )

    try:
        print("Starting Diamond Topology...")
        net.start()

        print("\nDiamond topology started successfully!")
        print("Switches: S1, S2, S3, S4")
        print("Hosts: H1, H4")
        print("Available paths:")
        print("Path 1: H1 -> S1 -> S2 -> S4 -> H4")
        print("Path 2: H1 -> S1 -> S3 -> S4 -> H4")

        CLI(net)

    finally:
        net.stop()
        print("Diamond topology stopped.")


if __name__ == '__main__':
    run_network()
