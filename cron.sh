#!/bin/bash
# https://blog.knoldus.com/running-a-cron-job-in-docker-container/
# Start the run once job.
echo "Docker container with cron ist starting"
declare -p | grep -E 'REDIS|ACCOUNT' > /container.env
/usr/sbin/cron -f
