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
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        switch = self.addSwitch('s0')
        self.addLink(h1, switch, bw=args.bw_host, delay='1ms')
        self.addLink(switch, h2, bw=args.bw_net, delay=f'{args.delay}ms', max_queue_size=args.maxq)

def start_iperf(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    print("Starting iperf server...")
    server = h2.popen("iperf -s -w 16m")
    client = h1.popen(f"iperf -c {h2.IP()} -t {args.time}")
    return server, client

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen, args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def start_ping(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    cmd = f"ping -i 0.1 -c {10 * args.time} {h2.IP()} > {args.dir}/ping.txt"
    h1.popen(cmd, shell=True)

def start_webserver(net):
    h1 = net.get('h1')
    proc = h1.popen("python3 webserver.py", shell=True)
    sleep(1)
    return proc

def measure_webpage(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    url = f"http://{h1.IP()}/index.html"
    times = []
    for _ in range(3):
        start = time()
        result = h2.cmd(f"curl -o /dev/null -s -w '%{{time_total}}' {url}")
        times.append(float(result.strip()))
        sleep(5)
    return times

def bufferbloat():
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)
    os.system(f"sysctl -w net.ipv4.tcp_congestion_control={args.cong}")
    topo = BBTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    dumpNodeConnections(net.hosts)
    net.pingAll()
    qmon = start_qmon(iface='s0-eth2', outfile=f"{args.dir}/q.txt")
    start_iperf(net)
    start_ping(net)
    web_proc = start_webserver(net)
    web_times = measure_webpage(net)
    avg_time = sum(web_times) / len(web_times)
    print(f"Média de tempo para carregar a página: {avg_time:.3f} segundos")
    qmon.terminate()
    net.stop()
    web_proc.terminate()

if __name__ == "__main__":
    bufferbloat()
