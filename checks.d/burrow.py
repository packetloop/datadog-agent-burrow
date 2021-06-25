# stdlib
from urlparse import urljoin

# 3rd Party
import requests
import json

# project
from checks import AgentCheck

SERVICE_CHECK_NAME = 'burrow.can_connect'

DEFAULT_BURROW_URI = 'http://localhost:8000'

CLUSTER_ENDPOINT = '/v3/kafka'

CHECK_TIMEOUT = 10

class BurrowCheck(AgentCheck):
    '''
    Extract consumer offsets, topic offsets and offset lag from Burrow REST API
    '''
    def check(self, instance):
        burrow_address = instance.get("burrow_uri", DEFAULT_BURROW_URI)
        target_clusters = instance.get("clusters")
        extra_tags = instance.get("tags", [])

        self._check_burrow(burrow_address, extra_tags)

        clusters = self._find_clusters(burrow_address, target_clusters)

        self.log.debug("Collecting Topic Offsets")
        self._topic_offsets(clusters, burrow_address, extra_tags)

        self.log.debug("Collecting Consumer Group Offsets")
        self._consumer_groups_offsets(clusters, burrow_address, extra_tags)

        self.log.debug("Collecting Consumer Group lags")
        self._consumer_groups_lags(clusters, burrow_address, extra_tags)

    def _consumer_groups_lags(self, clusters, burrow_address, extra_tags):
        """
        Retrieve the offsets for all consumer groups in the clusters
        Getting Consumer list could be factored out
        """
        for cluster in clusters:
            consumers_path = "%s/%s/consumer" % (CLUSTER_ENDPOINT, cluster)
            consumers_list = self._rest_request_to_json(burrow_address, consumers_path).get("consumers", [])
            for consumer in consumers_list:
                lags_path = "%s/%s/lag" % (consumers_path, consumer)
                lag_json = self._rest_request_to_json(burrow_address, lags_path)
                if not lag_json:
                    continue
                status = lag_json["status"]
                consumer_tags = ["cluster:%s" % cluster, "consumer:%s" % consumer] + extra_tags

                self.gauge("kafka.consumer.totallag", status["totallag"], tags=consumer_tags)
                self._submit_lag_status("kafka.consumer.lag_status", status["status"], tags=consumer_tags)

                for partition in status.get("partitions", []):
                    partition_tags = consumer_tags + ["topic:%s" % partition["topic"], "partition:%s" % partition["partition"]]
                    self._submit_partition_lags(partition, partition_tags)
                    self._submit_lag_status("kafka.consumer.partition_lag_status", partition["status"], tags=partition_tags)

    def _submit_lag_status(self, metric_namespace, status, tags):
        burrow_status = {
                "UNKNOWN" : 0,
                "OK": 0,
                "WARN": 0,
                "ERR": 0,
                "STOP": 0,
                "STALL": 0,
                "REWIND": 0
        }

        if status not in burrow_status.keys():
            self.log.error("Invalid lag status: '%s' for '%s'" % (status, tags))
            return

        burrow_status[status] = 1

        for metric_name, value in burrow_status.iteritems():
            self.gauge("%s.%s" % (metric_namespace, metric_name.lower()), value, tags=tags)

    def _submit_partition_lags(self, partition, tags):
        end = partition.get("end")
        if end is not None:
            lag = end.get("lag")
            self.gauge("kafka.consumer.partition_lag", lag, tags=tags, timestamp=end.get("timestamp"))

    def _check_burrow(self, burrow_address, extra_tags):
        """
        Check the Burrow health endpoint
        """
        url = urljoin(burrow_address, "/burrow/admin")
        try:
            tags = ['instance:%s' % self.hostname] + extra_tags
            response = requests.get(url, timeout=CHECK_TIMEOUT)
            response.raise_for_status()
        except Exception as e:
            self.service_check(SERVICE_CHECK_NAME,
                               AgentCheck.CRITICAL, tags=tags,
                               message=str(e))
            raise
        else:
            self.service_check(SERVICE_CHECK_NAME, AgentCheck.OK,
                               tags=tags,
                               message='Connection to %s was successful' % url)

    def _topic_offsets(self, clusters, burrow_address, extra_tags):
        """
        Retrieve the offsets for all topics in the clusters
        """
        for cluster in clusters:
            topics_path = "%s/%s/topic" % (CLUSTER_ENDPOINT, cluster)
            topics_list = self._rest_request_to_json(burrow_address, topics_path).get("topics", [])
            for topic in topics_list:
                if topic == '__consumer_offsets':
                    continue
                topic_path = "%s/%s" % (topics_path, topic)
                offsets = self._rest_request_to_json(burrow_address, topic_path).get("offsets", [])
                tags = ["topic:%s" % topic, "cluster:%s" % cluster] + extra_tags
                self._submit_offsets_for_topic(offsets=offsets, tags=tags)

    def _consumer_groups_offsets(self, clusters, burrow_address, extra_tags):
        """
        Retrieve the offsets for all consumer groups in the clusters
        """
        for cluster in clusters:
            consumers_path = "%s/%s/consumer" % (CLUSTER_ENDPOINT, cluster)
            consumers_list = self._rest_request_to_json(burrow_address, consumers_path).get("consumers", [])
            for consumer in consumers_list:
                if consumer == "burrow-local":
                    continue
                consumer_path = "%s/%s" % (consumers_path, consumer)
                topics_dict = self._rest_request_to_json(burrow_address, consumer_path).get("topics", {})
                for topic in topics_dict.keys():
                    tags = ["topic:%s" % topic, "cluster:%s" % cluster,
                            "consumer:%s" % consumer] + extra_tags
                    self._submit_offsets_for_consumer(topic_dict=topics_dict[topic], tags=tags)

    def _submit_offsets_for_topic(self, offsets, tags):
        """
        Find the offsets and push them into the metrics
        """
        if offsets:
            # for unconsumed or empty partitions, change an offset of -1 to 0 so the
            # sum isn't affected by the number of empty partitions.
            offsets = [max(offset, 0) for offset in offsets]
            self.gauge("kafka.topic.offsets.total", sum(offsets), tags=tags)
            for partition_number, offset in enumerate(offsets):
                new_tags = tags + ["partition:%s" % partition_number]
                self.gauge("kafka.topic.offsets", offset, tags=new_tags)

    def _submit_offsets_for_consumer(self, topic_dict, tags):
        """
        Find the offsets and push them into the metrics
        """
        offsets = []
        if topic_dict:
            for partition_number, partition in enumerate(topic_dict):
                new_tags = tags + ["partition:%s" % partition_number]
                offset_info = max([offset_info for offset_info in partition["offsets"] if offset_info is not None], key=lambda offset_info: offset_info["offset"])
                offset = offset_info["offset"]
                self.gauge("kafka.consumer.offsets", offset, tags=new_tags, timestamp=offset_info["timestamp"])
                offsets.append(offset)

            self.gauge("kafka.consumer.offsets.total", sum(offsets), tags=tags)

    def _find_clusters(self, address, target):
        """
        Find the available clusters in Burrow, return all clusters if
        target is not set.
        """
        available_clusters = self._rest_request_to_json(address, CLUSTER_ENDPOINT).get("clusters")

        if not available_clusters:
            raise Exception("There are no clusters in Burrow")

        if not target:
            return available_clusters
        else:
            clusters = []
            for name in target:
                if name in available_clusters:
                    clusters.append(name)
                else:
                    self.log.error("Cluster '%s' does not exist" % name )
            return clusters

    def _rest_request_to_json(self, address, object_path):
        '''
        Query the given URL and return the JSON response
        '''
        response_json = None

        service_check_tags = ['instance:%s' % self.hostname]

        url = urljoin(address, object_path)

        try:
            response = requests.get(url)
            response.raise_for_status()
            response_json = response.json()

            if response_json["error"]:
                self.log.error("Burrow Request failed: %s: %s" % (object_path, response_json["message"]))
                return {}

        except requests.exceptions.Timeout as e:
            self.log.error("Request timeout: {0}, {1}".format(url, e))
            raise

        except (requests.exceptions.HTTPError,
                requests.exceptions.InvalidURL,
                requests.exceptions.ConnectionError) as e:
            self.log.error("Request failed: {0}, {1}".format(url, e))
            raise

        except ValueError as e:
            self.log.error(str(e))
            raise

        else:
            self.log.debug('Connection to %s was successful' % url)

        return response_json
