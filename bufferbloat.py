from mininet.topo import Topo
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.log import lg, info
from mininet.util import dumpNodeConnections
from mininet.cli import CLI

from subprocess import Popen, PIPE
from time import sleep, time
from multiprocessing import Process
from argparse import ArgumentParser

from monitor import monitor_qlen

import sys
import os
import math

parser = ArgumentParser(description="Bufferbloat tests")
parser.add_argument('--bw-host', '-B',
                    type=float,
                    help="Bandwidth of host links (Mb/s)",
                    default=1000)

parser.add_argument('--bw-net', '-b',
                    type=float,
                    help="Bandwidth of bottleneck (network) link (Mb/s)",
                    required=True)

parser.add_argument('--delay',
                    type=float,
                    help="Link propagation delay (ms)",
                    required=True)

parser.add_argument('--dir', '-d',
                    help="Directory to store outputs",
                    required=True)

parser.add_argument('--time', '-t',
                    help="Duration (sec) to run the experiment",
                    type=int,
                    default=10)

parser.add_argument('--maxq',
                    type=int,
                    help="Max buffer size of network interface in packets",
                    default=100)

# Linux uses CUBIC-TCP by default that doesn't have the usual sawtooth
# behaviour.  For those who are curious, invoke this script with
# --cong cubic and see what happens...
# sysctl -a | grep cong should list some interesting parameters.
parser.add_argument('--cong',
                    help="Congestion control algorithm to use",
                    default="reno")

# Expt parameters
args = parser.parse_args()

class BBTopo(Topo):
    "Simple topology for bufferbloat experiment."

    def build(self, n=2):
        # Hosts
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')

        # Switch
        switch = self.addSwitch('s0')

        # Links
        self.addLink(h1, switch, bw=args.bw_host, delay=f"{args.delay}ms", max_queue_size=args.maxq)
        self.addLink(h2, switch, bw=args.bw_net, delay=f"{args.delay}ms", max_queue_size=args.maxq)


def start_iperf(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    print("Starting iperf server...")
    server = h2.popen("iperf -s -w 16m")

    print("Starting iperf client...")
    client = h1.popen(f"iperf -c {h2.IP()} -t {args.time}")

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen,
                      args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def start_ping(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    print("Starting ping train...")
    h1.popen(f"ping {h2.IP()} -i 0.1 > {args.dir}/ping.txt", shell=True)


def start_webserver(net):
    h1 = net.get('h1')
    proc = h1.popen("python webserver.py", shell=True)
    sleep(1)
    return [proc]


def fetch_webpage(net):
    h2 = net.get('h2')
    h1_ip = net.get('h1').IP()
    times = []
    for _ in range(3):
        result = h2.popen(f"curl -o /dev/null -s -w '%{{time_total}}' http://{h1_ip}/index.html", shell=True).communicate()[0]
        times.append(float(result))
    return times


def bufferbloat():
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)
    os.system("sysctl -w net.ipv4.tcp_congestion_control=%s" % args.cong)

    topo = BBTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    dumpNodeConnections(net.hosts)
    net.pingAll()

    # Monitoring queue sizes
    qmon = start_qmon(iface='s0-eth2', outfile=f"{args.dir}/q.txt")

    # Start iperf, ping, and webserver
    start_iperf(net)
    start_ping(net)
    webserver_proc = start_webserver(net)

    # Measure webpage fetch times
    start_time = time()
    while True:
        times = fetch_webpage(net)
        print(f"Fetch times: {times}")
        sleep(5)
        if time() - start_time > args.time:
            break

    # Stop processes
    qmon.terminate()
    webserver_proc[0].terminate()
    net.stop()
    Popen("pgrep -f webserver.py | xargs kill -9", shell=True).wait()

if __name__ == "__main__":
    bufferbloat()
