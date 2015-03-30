#!/usr/bin/env python
"""Determine if the instances in an autoscaling group are InService in its ELBs 
attached to that group.
"""

import os
import sys
import boto.ec2.elb
import boto.ec2.autoscale
import argparse

parser = argparse.ArgumentParser(description='Given an ASG, check if its instances are InService in an ELB')
parser.add_argument('-a', '--autoscale-group',
                    required=True,
                    help='Name of an autoscale group')
parser.add_argument('-r', '--region',
                    required=True,
                    help='AWS region')
parser.add_argument('-k', '--access-key',
                    required=False,
                    help='AWS Access Key')
parser.add_argument('-s', '--secret-key',
                    required=False,
                    help='AWS Secret Key')
args = parser.parse_args()

AWS_ACCESS_KEY = args.access_key
AWS_SECRET_KEY = args.secret_key
AWS_REGION = args.region
AWS_ASG = args.autoscale_group

conn_as = boto.ec2.autoscale.connect_to_region(AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
try: 
    asg = conn_as.get_all_groups(names=[AWS_ASG])[0]
except IndexError:
    sys.exit("ASG not found")
if asg.health_check_type != "ELB":
    sys.exit("ASG does not use ELB health checks. Quitting.")
instances = [i.instance_id for i in asg.instances]
if len(instances) != asg.desired_capacity:
    sys.exit("Number of instances do not yet match desired capacity")

conn_elb = boto.ec2.elb.connect_to_region(AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)
for lb in asg.load_balancers:
    for i in conn_elb.describe_instance_health(lb, instances=instances):
        if i.state != "InService":
            sys.exit("Instance {} is not InService".format(i.instance_id))
