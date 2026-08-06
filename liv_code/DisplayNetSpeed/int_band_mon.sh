#!/bin/bash

SERVER="bouygues.iperf.fr"
PORT=5209

declare -a DOWN
declare -a UP

while true
do
    echo
    echo "[$(date '+%H:%M:%S')] Running speed test..."

    # Download test
    down=$(iperf3 -c "$SERVER" -p "$PORT" -R -J -t 10 2>/dev/null | \
           jq '.end.sum_received.bits_per_second/1000000')

    # Upload test
    up=$(iperf3 -c "$SERVER" -p "$PORT" -J -t 10 2>/dev/null | \
         jq '.end.sum_sent.bits_per_second/1000000')

    if [[ "$down" != "null" && "$up" != "null" ]]
    then
        DOWN+=($down)
        UP+=($up)

        if [ ${#DOWN[@]} -gt 5 ]
        then
            DOWN=("${DOWN[@]:1}")
            UP=("${UP[@]:1}")
        fi

        dsum=0
        usum=0

        for i in "${DOWN[@]}"
        do
            dsum=$(awk "BEGIN{print $dsum+$i}")
        done

        for i in "${UP[@]}"
        do
            usum=$(awk "BEGIN{print $usum+$i}")
        done

        n=${#DOWN[@]}

        davg=$(awk "BEGIN{printf \"%.2f\", $dsum/$n}")
        uavg=$(awk "BEGIN{printf \"%.2f\", $usum/$n}")

        echo "Download: ${down} Mbps"
        echo "Upload  : ${up} Mbps"
        echo
        echo "5-Test Average"
        echo "Download: ${davg} Mbps"
        echo "Upload  : ${uavg} Mbps"
    else
        echo "Speed test failed."
    fi

    echo
    sleep 60
done
