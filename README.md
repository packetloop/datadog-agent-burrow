Purpose
=======

This datadog agent plugin will connect to instances of Burrow (https://github.com/linkedin/Burrow) and automatically get the offsets for every consumer
and topic and push them into Datadog.

Metrics and Checks
==================
This plugin will push the offsets for all topics (except the `offsets_topic`) and consumers
for every kafka cluster it finds into Datadog as a metric.

It will also push a check `burrow.can_connect` into Datadog to monitor the health of Burrow

The topic and consumer offsets will be a metric called `kafka.topic.offsets` and `kafka.consumer.offsets` respectively.
These metrics are tagged with `cluster`, `topic` and `consumer` to make it easy to filter out in Datadog.

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
