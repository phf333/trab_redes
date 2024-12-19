#!/bin/bash

# Note: Mininet must be run as root. Invoke this shell script using sudo.

time=90
bwnet=1.5
# Para obter um RTT de 20ms, cada link precisa ter um atraso de 10ms (ida e volta).
delay=10

iperf_port=5001

for qsize in 20 100; do
    dir=bb-q$qsize

    # Cria o diretório de saída se ele ainda não existir.
    mkdir -p $dir

    # Executa o bufferbloat.py com os parâmetros apropriados.
    python3 bufferbloat.py \
        --bw-host 1000 \
        --bw-net $bwnet \
        --delay $delay \
        --dir $dir \
        --time $time \
        --maxq $qsize \
        --cong reno

    # Gera os gráficos usando os dados de saída.
    python3 plot_queue.py -f $dir/q.txt -o reno-buffer-q$qsize.png
    python3 plot_ping.py -f $dir/ping.txt -o reno-rtt-q$qsize.png
done
