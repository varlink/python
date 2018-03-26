#!/bin/bash

set -e

cp examples/*.py examples/*.varlink .

# test unix:
./server-simple.py --varlink=unix:@varlink$$ &
sleep 2
./client-simple-stop.py unix:@varlink$$
wait %1

./server-twisted.py --varlink=unix:@varlink$$ &
sleep 2
./client-simple-stop.py unix:@varlink$$
wait %1

# test tcp: IPv4
./server-simple.py --varlink=tcp:0.0.0.0:25645 &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25645'
wait

./server-twisted.py --varlink=tcp:0.0.0.0:25645 &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25645'
wait

if ! [[ $TRAVIS ]]; then
    # test tcp: IPv6
    ./server-simple.py '--varlink=tcp:[::1]:25645' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25645'
    wait

    ./server-twisted.py '--varlink=tcp:[::1]:25645' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25645'
    wait
fi

# test exec:
./client-simple.py
./client-twisted.py
