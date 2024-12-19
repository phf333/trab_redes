#!/bin/bash

# Note: Mininet must be run as root. Invoke this shell script using sudo.

time=90
bwnet=1.5
# Para obter um RTT de 20ms, cada link precisa ter um atraso de 10ms (ida e volta).
delay=10

iperf_port=5001

for qsize in 20 100; do
    dir=bb-q$qsize

    mkdir -p $dir

    for cong in reno bbr quic; do
        python3 bufferbloat.py \
            --bw-host 1000 \
            --bw-net $bwnet \
            --delay $delay \
            --dir $dir/$cong \
            --time $time \
            --maxq $qsize \
            --cong $cong

        if [ "$cong" == "quic" ]; then
            python3 plot_queue.py -f $dir/$cong/q.txt -o quic-buffer-q$qsize.png
            python3 plot_ping.py -f $dir/$cong/ping.txt -o quic-rtt-q$qsize.png
        else
            python3 plot_queue.py -f $dir/$cong/q.txt -o $cong-buffer-q$qsize.png
            python3 plot_ping.py -f $dir/$cong/ping.txt -o $cong-rtt-q$qsize.png
        fi

        # Geração de gráficos para streaming
        #python3 plot_streaming.py -f $dir/$cong/streaming.txt -o $cong-streaming-q$qsize.png
    done
done
