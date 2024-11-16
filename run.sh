#!/bin/bash

# Note: Mininet must be run as root. Invoke this script using sudo.

time=90
bwnet=1.5
delay=10  # Para RTT total de 20ms (ida e volta)
iperf_port=5001

for qsize in 20 100; do
    dir="bb-q$qsize"

    # Executa o experimento
    python3 bufferbloat.py \
        --bw-host 1000 \
        --bw-net $bwnet \
        --delay $delay \
        --dir $dir \
        --time $time \
        --maxq $qsize

    # Gera os gráficos
    python3 plot_queue.py -f $dir/q.txt -o reno-buffer-q$qsize.png
    python3 plot_ping.py -f $dir/ping.txt -o reno-rtt-q$qsize.png
done