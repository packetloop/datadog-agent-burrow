Purpose
=======

This datadog agent plugin will connect to instances of Burrow (https://github.com/linkedin/Burrow) and automatically get the offsets for every consumer
and topic and push them into Datadog.

Metrics and Checks
==================
This plugin will push the offsets for all topics (except the `offsets_topic`) and consumers
for every kafka cluster it finds into Datadog as a metric.

The reported lags for each consumer group are also pushed up, along with the burrow consumer group status.

It will also push a check `burrow.can_connect` into Datadog to monitor the health of Burrow

Metrics
-------

*Topic Offsets*
* `kafka.topic.offsets` - Per partition offsets of each topic
* `kafka.topic.offsets.total` - Total offset of each topic

*Consumer Offsets*
* `kafka.consumer.offsets` - Per partition offsets of each consumer groups
* `kafka.consumer.offsets.total` - Total offset of each consumer group

*Lag*
* `kafka.consumer.maxlag` - Maximum lag of each consumer group
* `kafka.consumer.totallag` - Total lag of each consumer group
* `kafka.consumer.partition_lag` - Lag of each partition of a consumer group

The lag statuses are defined in burrow here: https://github.com/linkedin/Burrow/wiki/Consumer-Lag-Evaluation-Rules

Consumer group lag status:
* `kafka.consumer.lag_status.unknown`
* `kafka.consumer.lag_status.ok`
* `kafka.consumer.lag_status.warn`
* `kafka.consumer.lag_status.err`
* `kafka.consumer.lag_status.stop`
* `kafka.consumer.lag_status.stall`
* `kafka.consumer.lag_status.rewind`

Per Partition lag status of a consumer group:
* `kafka.consumer.partition_lag_status.unknown`
* `kafka.consumer.partition_lag_status.ok`
* `kafka.consumer.partition_lag_status.warn`
* `kafka.consumer.partition_lag_status.err`
* `kafka.consumer.partition_lag_status.stop`
* `kafka.consumer.partition_lag_status.stall`
* `kafka.consumer.partition_lag_status.rewind`

All metrics are tagged with `cluster`, `topic`, `consumer` and `partition` (where applicable)  to make it easy to filter out in Datadog.

Development
===========

1. Start zookeeper and kafka up before Burrow
   ```
   docker-compose up -d kafka zookeeper
   ```

2. Start up burrow
   ```
   docker-compose up burrow
   ```

3. Populate some data into the kafka topic. Replace the IP address with whatever IP your kafka docker container
   is running as.
   ```
   cat ./sample_messages | kafka-console-producer --broker-list 192.168.99.100:9092 --topic test-topic
   ```

4. Consume some messages from the topic to get consumer offsets
   ```
   docker-compose run datadog-agent /opt/datadog-agent/embedded/bin/python2.7 /test.py
   ```

5. Execute the burrow check
   ```
   docker-compose run datadog-agent /opt/datadog-agent/agent/agent.py check burrow
   ```
