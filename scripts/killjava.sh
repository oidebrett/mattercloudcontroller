#! /bin/bash
PID=`ps -C java -o pid=`
kill -9 $PID

