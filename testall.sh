#!/bin/bash

set -e

cp examples/* .

# test unix:
./server-simple.py unix:@varlink$$ &
sleep 2
./client-simple-stop.py unix:@varlink$$
wait %1

./server-twisted.py unix:@varlink$$ &
sleep 2
./client-simple-stop.py unix:@varlink$$
wait %1

# test tcp: IPv4
./server-simple.py 'tcp:0.0.0.0:25645' &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25645'
wait

./server-twisted.py 'tcp:0.0.0.0:25645' &
sleep 2
./client-simple-stop.py 'tcp:127.0.0.1:25645'
wait

if ! [[ $TRAVIS ]]; then
    # test tcp: IPv6
    ./server-simple.py 'tcp:[::1]:25645' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25645'
    wait

    ./server-twisted.py 'tcp:[::1]:25645' &
    sleep 2
    ./client-simple-stop.py 'tcp:[::1]:25645'
    wait
fi

# test exec:
./client-simple.py
./client-twisted.py
