#!/usr/bin/env bash

. utils.sh

for i in $(seq 1 10); do
  echo "stdout: $i";
  echoerr "stderr: $i"
  sleep 0.3;
done