#!/bin/bash

IFACE=$(ip route | awk '/default/ {print $5; exit}')

declare -a RX
declare -a TX

while true
do
    rx1=$(cat /sys/class/net/$IFACE/statistics/rx_bytes)
    tx1=$(cat /sys/class/net/$IFACE/statistics/tx_bytes)

    sleep 60

    rx2=$(cat /sys/class/net/$IFACE/statistics/rx_bytes)
    tx2=$(cat /sys/class/net/$IFACE/statistics/tx_bytes)

    RX+=($((rx2-rx1)))
    TX+=($((tx2-tx1)))

    if [ ${#RX[@]} -gt 5 ]; then
        RX=("${RX[@]:1}")
        TX=("${TX[@]:1}")
    fi

    rxsum=0
    txsum=0

    for x in "${RX[@]}"; do
        ((rxsum+=x))
    done

    for x in "${TX[@]}"; do
        ((txsum+=x))
    done

    mins=${#RX[@]}

    down=$(awk "BEGIN{printf \"%.2f\", ($rxsum/60/$mins)/1024}")
    up=$(awk "BEGIN{printf \"%.2f\", ($txsum/60/$mins)/1024}")

    echo "$(date '+%H:%M')  Download: ${down} KB/s   Upload: ${up} KB/s"
done
