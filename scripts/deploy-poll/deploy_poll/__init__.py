"""Polls an SQS queue for deploy objects.
Invokes ansible when a deploy object is found.
"""
import sys
import logging
import json
import datetime
import subprocess

import boto.sqs
import boto.sqs.queue
import boto.exception

import config

logger = logging.getLogger('deploy-poll')


class DeployPoll(object):
    def __init__(self, queue_url, interval=1):
        self.interval = interval
        self.q = self.sqs_setup(queue_url)

    def sqs_setup(self, queue_url):
        try:
            q_conn = boto.sqs.connect_to_region(config.AWS_REGION)
        except boto.exception.NoAuthHandlerFound:
            logger.error("Unable to connect to AWS, are your credentials valid?")
            sys.exit(1)
        return boto.sqs.queue.Queue(q_conn, queue_url)

    def poll_queue(self):
        while True:
            messages = self.q.get_messages(1, attributes='SentTimestamp', message_attributes=['SenderIp'])
            if len(messages) > 0:
                message = messages.pop()
                logger.debug("Found new message!")
                (payload, sender) = self.check_object(message)
                if payload is not None and sender is not None:
                    self.fork_ansible_playbook(payload, sender)
                self.delete(message)

    def delete(self, message):
        self.q.delete_message(message)

    def check_object(self, message):
        try:
            message_sent = datetime.datetime.fromtimestamp(int(message.attributes['SentTimestamp'])/1000)
        except KeyError:
            logger.warn("Error reading message timestamp. Discarding this message.")
            self.delete(message)
            return (None, None)

        try:
            message_sender = message.message_attributes['SenderIp']['string_value']
        except KeyError:
            logger.warn("SQS message missing SenderIp")
            self.delete(message)
            return (None, None)

        message_body = message.get_body()

        logger.debug("Message details - timestamp: {}, ip: {}, contents: {}".format(
            message_sent.strftime("%Y-%m-%d %H:%M:%S"),
            message_sender,
            message_body))

        try:
            message_json = json.loads(message_body)
        except ValueError:
            logger.warn("Unable to deserialize JSON. Discarding.")
            self.delete(message)
            return

        if datetime.datetime.now() - datetime.timedelta(minutes=1) > message_sent:
            logger.warn("Message is older than 60 seconds. Assuming it's no longer relevant and discarding")
            self.delete(message)
            return

        for k in config.REQUIRED_PARAMETERS:
            if not k in message_json:
                logger.warn("Message missing required parameter {}. Discarding".format(k))
                return

        return message_json, message_sender

    def fork_ansible_playbook(self, payload, sender):
        logger.info("Deploying {}".format(",".join(["{}={}".format(k, v) for k, v in payload.items()])))
        ansible_runtime_vars = " ".join(["-e {}={}".format(k, v) for k, v in payload.items()])
        playbook_cmd = [
            "ansible-playbook",
            "--private-key",
            config.PRIVATE_KEY_FILE,
            "-i",
            "{},".format(sender),
            ansible_runtime_vars,
            config.ANSIBLE_PLAYBOOKS + "/site.yml"
        ]
        logger.debug("Ansible playbook command: {0}".format(' '.join(playbook_cmd)))
        subprocess.Popen(playbook_cmd)
