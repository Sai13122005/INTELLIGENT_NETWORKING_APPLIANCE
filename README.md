# Intelligent Networking Appliance

## 1. Project Overview

The **Intelligent Networking Appliance** is an SDN-based networking system designed to improve network management through centralized control, real-time monitoring, intelligent path selection, MPLS forwarding, and network orchestration.

The project integrates multiple networking functionalities into a single modular appliance using Software Defined Networking (SDN).

The system monitors network conditions, evaluates available paths, selects a suitable route, establishes MPLS Label Switched Paths (LSPs), and handles network link failures through automatic recovery mechanisms.

## 2. Problem Statement

Traditional IP-based routing primarily makes forwarding decisions using destination IP addresses and routing information.

However, network performance can change dynamically due to:

- Network congestion
- Increased packet delay
- Packet loss
- Link failures
- Changes in link utilization

There is a need for a centralized and modular system that can monitor network conditions, evaluate available paths, coordinate forwarding decisions, and respond to network failures.

## 3. Proposed Solution

The proposed appliance integrates the following functionalities:

1. SDN-based centralized network control.
2. Automatic network topology discovery.
3. Network performance monitoring.
4. Intelligent path calculation and selection.
5. MPLS-based packet forwarding.
6. Routing and MPLS orchestration.
7. Link failure detection and recovery.

## 4. System Architecture

The project follows a modular architecture controlled by the Ryu SDN Controller.

### Major Components

**1. SDN Controller**
- Acts as the centralized control plane.
- Communicates with Open vSwitch switches using OpenFlow 1.3.
- Coordinates network operations.

**2. Topology Manager**
- Discovers network switches and links.
- Uses LLDP for topology discovery.
- Maintains the network topology information.

**3. Monitoring Engine**

The monitoring subsystem consists of:

- Link Status Monitor – identifies link availability.
- Delay Monitor – measures network delay.
- Packet Loss Monitor – estimates packet loss.
- Queue Monitor – collects queue and port statistics.
- Path Measurement – measures candidate-path performance.

**4. Routing Module**
- Calculates available network paths.
- Evaluates path costs.
- Selects a suitable path based on collected network information.

**5. Routing Orchestrator**
- Coordinates path selection and route installation.
- Handles path changes during network failures.

**6. MPLS Orchestrator**
- Coordinates MPLS Label Switched Path establishment.
- Allocates MPLS labels.
- Installs forwarding rules into Open vSwitch switches.
- Manages MPLS forwarding operations.

## 5. MPLS Implementation

The project implements MPLS forwarding using OpenFlow-programmed Open vSwitch switches.

Three primary MPLS operations are implemented:

- **Push:** Adds an MPLS label to an incoming IP packet.
- **Swap:** Replaces the existing MPLS label at an intermediate switch.
- **Pop:** Removes the MPLS label before forwarding the packet to its destination.

Example forwarding sequence:

H1 → S1 → S3 → S4 → H4

| Switch | MPLS Operation |
|---|---|
| S1 | Push label 100 |
| S3 | Swap label 100 to 101 |
| S4 | Pop label 101 |

## 6. Network Orchestration

Orchestration coordinates network operations across different modules.

The general workflow is:

1. Obtain topology information.
2. Collect network performance metrics.
3. Evaluate available paths.
4. Select the preferred path.
5. Allocate MPLS labels.
6. Install forwarding rules.
7. Monitor the network for failures.
8. Recalculate and establish an alternative path when required.

## 7. Failure Detection and Recovery

The appliance includes a link failure detection and recovery mechanism.

When an active network link fails:

1. The controller receives the link status change.
2. The Topology Manager updates the network topology.
3. The Routing Orchestrator evaluates available alternative paths.
4. A suitable alternative path is selected.
5. The MPLS Orchestrator coordinates the new LSP installation.
6. Connectivity is tested after recovery.

## 8. Experimental Environment

The project is implemented and tested using the following technologies:

| Technology | Purpose |
|---|---|
| Ubuntu 20.04.1 | Operating system |
| Python 3.8.10 | Implementation language |
| Mininet 2.3.0 | Network emulation |
| Open vSwitch 2.13.8 | Software switches |
| Ryu 4.30 | SDN controller |
| OpenFlow 1.3 | Controller-switch communication |
| NetworkX 2.4 | Graph and path operations |

## 9. Mininet Network Topology

The experimental environment uses a diamond-shaped network topology.

**Network components:**
- 2 hosts: H1 and H4
- 4 switches: S1, S2, S3 and S4
- 2 alternative paths between the hosts

**Path A:**
H1 → S1 → S2 → S4 → H4

**Path B:**
H1 → S1 → S3 → S4 → H4

This topology allows the system to evaluate alternative paths and demonstrate failure recovery.

## 10. Project Directory Structure

```text
INTELLIGENT_NETWORKING_APPLIANCE/
│
├── appliance/
│   ├── common/
│   │   └── network_state.py
│   │
│   ├── monitoring/
│   │   ├── delay.py
│   │   ├── link_status.py
│   │   ├── monitoring_engine.py
│   │   ├── packet_loss.py
│   │   ├── path_measurement.py
│   │   └── queue_monitor.py
│   │
│   ├── mpls/
│   │   ├── forwarding.py
│   │   ├── label_manager.py
│   │   ├── lsp_manager.py
│   │   └── mpls_orchestrator.py
│   │
│   ├── orchestration/
│   │   └── routing_orchestrator.py
│   │
│   ├── routing/
│   │   ├── cost_calculation.py
│   │   ├── path_calculation.py
│   │   └── path_selection.py
│   │
│   ├── sdn_control/
│   │   ├── controller.py
│   │   └── flow_manager.py
│   │
│   └── topology/
│       └── topology_manager.py
│
├── mininet_environment/
│   └── topology.py
│
├── test_cost.py
├── test_network_state.py
├── test_path_selection.py
├── test_routing.py
├── test_routing_integration.py
│
├── .gitignore
└── README.md
```

## 11. Execution Instructions

### Step 1: Start Mininet

Open the first terminal:

```bash
cd ~/INTELLIGENT_NETWORKING_APPLIANCE

sudo python3 mininet_environment/topology.py
```

### Step 2: Start Ryu Controller

Open a second terminal:

```bash
cd ~/INTELLIGENT_NETWORKING_APPLIANCE

sudo env PYTHONPATH="$PWD" ryu-manager --observe-links --ofp-tcp-listen-port 6653 \
appliance.sdn_control.controller \
appliance.topology.topology_manager \
appliance.monitoring.monitoring_engine \
appliance.monitoring.link_status \
appliance.monitoring.delay \
appliance.monitoring.packet_loss \
appliance.monitoring.queue_monitor
```

### Step 3: Test Network Connectivity

At the Mininet prompt:

```bash
pingall
```

Test communication between H1 and H4:

```bash
h1 ping -c 10 h4
```

### Step 4: Inspect MPLS Forwarding Rules

Inspect the flow tables of the switches:

```bash
sh ovs-ofctl -O OpenFlow13 dump-flows s1
sh ovs-ofctl -O OpenFlow13 dump-flows s3
sh ovs-ofctl -O OpenFlow13 dump-flows s4
```

### Step 5: Test Link Failure

Simulate failure of the S1–S3 link:

```bash
link s1 s3 down
```

Test connectivity again:

```bash
h1 ping -c 10 h4
```

## 12. Implementation Results

The following functionalities have been demonstrated in the Mininet environment:

- Successful topology discovery.
- Network monitoring through the Ryu controller.
- End-to-end host connectivity.
- MPLS Push, Swap and Pop operations on the initial path.
- Link failure detection.
- Alternative path selection.
- Controller-reported MPLS LSP recovery.
- Successful host connectivity following the tested link failure.

Further post-failure MPLS flow-table validation is required to confirm the complete forwarding-rule installation on every switch.

## 13. Future Enhancements

- Web-based network monitoring dashboard.
- Real-time visualization of network topology.
- Graphical display of delay, packet loss and utilization.
- MPLS label and LSP visualization.
- Interactive network management.
- Historical performance analysis.
- Extended testing with larger network topologies.

## 14. Project Objective

The overall objective is to develop a modular Intelligent Networking Appliance that combines SDN, network monitoring, intelligent routing, MPLS forwarding, and orchestration into one integrated system.

The project aims to make network management more centralized, performance-aware, and adaptable to network failures.

---

**Project:** Intelligent Networking Appliance  
**Author:** Saikrishna Penta  
**Roll Number:** 24MCCE36
