# Ajustando o código Python fornecido no bufferbloat.py com base nas instruções dadas.

# Código atualizado para implementar as partes que faltam.

# Parte principal do script ajustada para implementar a lógica necessária no experimento.

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

import os
import sys
import math

parser = ArgumentParser(description="Bufferbloat tests")
parser.add_argument('--bw-host', '-B', type=float, help="Bandwidth of host links (Mb/s)", default=1000)
parser.add_argument('--bw-net', '-b', type=float, help="Bandwidth of bottleneck (network) link (Mb/s)", required=True)
parser.add_argument('--delay', type=float, help="Link propagation delay (ms)", required=True)
parser.add_argument('--dir', '-d', help="Directory to store outputs", required=True)
parser.add_argument('--time', '-t', help="Duration (sec) to run the experiment", type=int, default=10)
parser.add_argument('--maxq', type=int, help="Max buffer size of network interface in packets", default=100)
parser.add_argument('--cong', help="Congestion control algorithm to use", default="reno")

args = parser.parse_args()

class BBTopo(Topo):
    "Simple topology for bufferbloat experiment."

    def build(self):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        switch = self.addSwitch('s0')

        # Links
        self.addLink(h1, switch, bw=args.bw_host, delay='1ms', max_queue_size=args.maxq, use_htb=True)
        self.addLink(switch, h2, bw=args.bw_net, delay=f'{args.delay}ms', max_queue_size=args.maxq, use_htb=True)

def start_iperf(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    print("Starting iperf server...")
    server = h2.popen("iperf -s -w 16m")
    client = h1.popen(f"iperf -c {h2.IP()} -t {args.time} -i 1")

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen, args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def start_ping(net):
    h1 = net.get('h1')
    h2 = net.get('h2')
    print("Starting ping train...")
    ping_cmd = f"ping {h2.IP()} -i 0.1 -c {10 * args.time} > {args.dir}/ping.txt"
    h1.popen(ping_cmd, shell=True)

def start_webserver(net):
    h1 = net.get('h1')
    proc = h1.popen("python3 -m http.server 80", shell=True)
    sleep(1)
    return [proc]

def measure_web_download(net):
    h2 = net.get('h2')
    download_times = []
    for _ in range(3):  # Executa 3 vezes
        start_time = time()
        result = h2.popen("curl -o /dev/null -s -w %{time_total} http://10.0.0.1/index.html", shell=True)
        time_taken = float(result.stdout.read().strip())
        download_times.append(time_taken)
        elapsed = time() - start_time
        sleep_time = max(0, 5 - elapsed)  # Garante que sleep seja não-negativo
        sleep(sleep_time)
    return download_times

def bufferbloat():
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)
    os.system(f"sysctl -w net.ipv4.tcp_congestion_control={args.cong}")
    topo = BBTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()

    dumpNodeConnections(net.hosts)
    net.pingAll()

    qmon = start_qmon(iface='s0-eth2', outfile=f'{args.dir}/q.txt')
    start_iperf(net)
    start_ping(net)
    start_webserver(net)

    print("Starting webpage downloads...")
    download_times = measure_web_download(net)

    avg_time = sum(download_times) / len(download_times)
    std_dev = math.sqrt(sum([(x - avg_time) ** 2 for x in download_times]) / len(download_times))
    print(f"Average download time: {avg_time:.3f}s, Std Dev: {std_dev:.3f}s")
    
    
    
    
    qmon.terminate()

    CLI(net)

    net.stop()
    Popen("pgrep -f 'http.server' | xargs kill -9", shell=True).wait()

if __name__ == "__main__":
    bufferbloat()
