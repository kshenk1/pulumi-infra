"""An AWS Python Pulumi program"""

import modules.vpc as vpc
import modules.efs as efs
import modules.eks as eks
# NOTE CONDITIONAL IMPORTS BELOW

from config import AWSPulumiConfig

config_file = 'stack-config.yaml'

config = AWSPulumiConfig(config_file)

vpc_data = vpc.define_vpc(config)

if config.efs_enabled():
    efs_data = efs.define_efs(config, vpc_data)

if config.eks_enabled():
    _data = eks.define_cluster(config, vpc_data)
    cluster_obj = _data['cluster']
    node_groups = eks.define_node_groups(config, cluster_obj, _data['node_role'], vpc_data)

if config.rds_enabled():
    if config.instance_requested():
        import modules.rds_instance as rds
    elif config.cluster_requested():
        import modules.rds_cluster as rds
    else:
        raise ValueError('Unable to load an RDS module. Check your rds.aws_rds_type value')

    rds = rds.define_rds(config, vpc_data)
