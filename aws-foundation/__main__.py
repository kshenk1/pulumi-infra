"""An AWS Python Pulumi program"""

import modules.vpc as vpc
import modules.efs as efs
import modules.eks as eks
import modules.rds as rds

from config import CBPulumiConfig

config_file = 'stack-config.yaml'

config = CBPulumiConfig(config_file)

vpc_data = vpc.define_vpc(config)

if config.efs_enabled():
    efs_data = efs.define_efs(config, vpc_data)

if config.eks_enabled():
    cluster_obj = eks.define_cluster(config, vpc_data)
    node_groups = eks.define_node_groups(config, cluster_obj, vpc_data)

if config.rds_enabled():
    rds_instance = rds.define_rds_cluster(config, vpc_data)
    