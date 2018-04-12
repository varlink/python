#!/bin/bash

set -e

cp examples/*.py examples/*.varlink .

# test exec:
./client-simple.py
./client-twisted.py

./client-simple.py exec:./server-twisted.py
./client-twisted.py exec:./server-simple.py

# test unix:
./server-simple.py --varlink=unix:@varlink$(($$+1)) &
sleep 2
./client-simple-stop.py unix:@varlink$(($$+1))
wait %1

./server-twisted.py --varlink=unix:@varlink$(($$+2)) &
sleep 2
./client-simple-stop.py unix:@varlink$(($$+2))
wait %1

# test tcp: IPv4
./server-simple.py --varlink=tcp:0.0.0.0:25645 &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25645'
wait

./server-twisted.py --varlink=tcp:0.0.0.0:25646 &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25646'
wait

if ! [[ $TRAVIS ]]; then
    # test tcp: IPv6
    ./server-simple.py '--varlink=tcp:[::1]:25647' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25647'
    wait

    ./server-twisted.py '--varlink=tcp:[::1]:25648' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25648'
    wait
fi

