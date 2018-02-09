#!/bin/bash

set -e

cp examples/* .

# test unix:
./server-simple.py unix:@varlink$$ &
sleep 1
./client-simple-stop.py unix:@varlink$$
wait %1

./server-twisted.py unix:@varlink$$ &
sleep 1
./client-simple-stop.py unix:@varlink$$
wait %1

# test ip: IPv4
./server-simple.py 'ip:0.0.0.0:25645' &
sleep 1
./client-simple-stop.py 'ip:127.0.0.1:25645'
wait

./server-twisted.py 'ip:0.0.0.0:25645' &
sleep 1
./client-simple-stop.py 'ip:127.0.0.1:25645'
wait

if ! [[ $TRAVIS ]]; then
    # test ip: IPv6
    ./server-simple.py 'ip:[::1]:25645' &
    sleep 1
    ./client-simple-stop.py 'ip:[::1]:25645'
    wait

    ./server-twisted.py 'ip:[::1]:25645' &
    sleep 1
    ./client-simple-stop.py 'ip:[::1]:25645'
    wait
fi

# test exec:
./client-simple.py
./client-twisted.py
