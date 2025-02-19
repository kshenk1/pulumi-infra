"""An AWS Python Pulumi program"""
import os
import pulumi
import modules.vpc as vpc
import modules.efs as efs
import modules.eks as eks
import modules.ec2 as ec2
import modules.eks_lb_controller as ekslb
import modules.load_balancing as lb
import modules.route53 as route53
from modules.autotag import register_auto_tags
from config import AWSPulumiConfig
from pulumi import StackReference
from constants import Constants as CONST
# NOTE CONDITIONAL IMPORTS BELOW FOR RDS

project = pulumi.get_project()
org     = pulumi.get_organization()
stack   = pulumi.get_stack()
config  = AWSPulumiConfig(stack)

config.add_tags({
    'pulumi-project': project, 
    'pulumi-stack': stack
})

# This pretty much enables the tagging of everything
register_auto_tags(config.tags)

def get_readme(stack):
    _readme = os.path.join(CONST.PATH_README, f'{stack}.md')
    if os.path.isfile(_readme):
        with open(_readme, 'r') as f:
            return f.read()
    return 'No documentation found'

if stack == 'foundation':
    vpc_data = vpc.define_vpc(config)
else:
    stack_ref = StackReference(f'{org}/{project}/foundation')
    vpc_data = stack_ref.get_output('vpc_data')

if stack == 'jenkins-ec2':
    if config.ec2_enabled():
        instances = ec2.define_ec2(config, vpc_data)
        if config.lb_enabled():
            load_balancer = lb.define_lb(config, vpc_data, instances)
            route53.define_dns(config, load_balancer.dns_name)

if config.rds_enabled():
    if config.instance_requested():
        import modules.rds_instance as rds
    elif config.cluster_requested():
        import modules.rds_cluster as rds
    else:
        raise ValueError('Unable to load an RDS module. Check your rds.aws_rds_type value')

    rds_install = rds.define_rds(config, vpc_data)

if config.efs_enabled():
    efs_data = efs.define_efs(config, vpc_data)

if stack.endswith('-eks'):
    if config.eks_enabled():
        _data = eks.define_cluster(config, vpc_data)
        cluster_obj = _data['cluster']
        node_role = _data['node_role']

        node_groups = eks.define_node_groups(config, cluster_obj, node_role, vpc_data)
        k8s_provider = eks.k8sProvider(config, cluster_obj)

        if config.lb_controller_enabled():
            lb_resources = ekslb.define_lb_controller(config, k8s_provider, node_groups, vpc_data['vpc_id'])

        if config.efs_csi_driver_enabled():
            efs_controller = efs.define_efs_controller(config, k8s_provider, node_groups)

        addons = eks.define_addons(config, k8s_provider, node_groups)

pulumi.export('readme', get_readme(stack))
