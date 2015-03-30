#!/usr/bin/env python
"""Given a list of ELBs, determines what autoscale group(s) its instances are in.
"""

import sys
import json
import boto.ec2
import boto.ec2.elb
import boto.ec2.autoscale

from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *


def find_asgs(conn_as, prefix, module):
    asgs = conn_as.get_all_groups()
    suspect_asgs = []
    for asg in asgs:
        if asg.name.startswith(prefix):
            suspect_asgs.append(asg)

    if len(suspect_asgs) > 1:
        module.fail_json(msg="More than one ASG with prefix={} found. manual intervention required!".format(prefix))
    elif len(suspect_asgs) == 1:
        asg = suspect_asgs[0]
        output = {
            "changed" : True,
            "rc" : 0,
            "ansible_facts" : {
                "current_asg_name": asg.name,
                "current_lc_name": asg.launch_config_name
            }
        }
    else:
        output = {
            "changed" : False,
            "rc" : 0
        }

    module.exit_json(**output)

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(asg_name_prefix=dict(type='str')))
    module = AnsibleModule(argument_spec=argument_spec)
    prefix = module.params.get('asg_name_prefix')
    region, ec2_url, aws_connect_params = get_aws_connection_info(module)
    try:
        conn_as = connect_to_aws(boto.ec2.autoscale, region, **aws_connect_params)
        if not conn_as:
            module.fail_json(msg="failed to connect to AWS for the given region: %s" % str(region))
    except boto.exception.NoAuthHandlerFound, e:
        module.fail_json(msg=str(e))

    find_asgs(conn_as, prefix, module)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

main()
