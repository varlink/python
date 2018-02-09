#!/bin/bash

set -e

cp examples/* .

# test exec:
./client-simple.py
./client-twisted.py

# test unix:
./server-simple.py unix:@test &
sleep 1
./client-simple-stop.py unix:@test
wait %1

./server-twisted.py unix:@test &
sleep 1
./client-simple-stop.py unix:@test
wait %1

# test ip: IPv4
./server-simple.py 'ip:0.0.0.0:12345' &
sleep 1
./client-simple-stop.py 'ip:127.0.0.1:12345'
wait

./server-twisted.py 'ip:0.0.0.0:12345' &
sleep 1
./client-simple-stop.py 'ip:127.0.0.1:12345'
wait

# test ip: IPv6
./server-simple.py 'ip:[::1]:12345' &
sleep 1
./client-simple-stop.py 'ip:[::1]:12345'
wait

./server-twisted.py 'ip:[::1]:12345' &
sleep 1
./client-simple-stop.py 'ip:[::1]:12345'
wait



