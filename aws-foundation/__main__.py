"""An AWS Python Pulumi program"""

import modules.vpc as vpc
import modules.efs as efs
import modules.eks as eks
import pulumi_kubernetes as pk8s
# NOTE CONDITIONAL IMPORTS BELOW

from config import AWSPulumiConfig

config = AWSPulumiConfig('stack-config.yaml')

vpc_data = vpc.define_vpc(config)

if config.efs_enabled():
    efs_data = efs.define_efs(config, vpc_data)

if config.rds_enabled():
    if config.instance_requested():
        import modules.rds_instance as rds
    elif config.cluster_requested():
        import modules.rds_cluster as rds
    else:
        raise ValueError('Unable to load an RDS module. Check your rds.aws_rds_type value')

    rds = rds.define_rds(config, vpc_data)

if config.eks_enabled():
    _data = eks.define_cluster(config, vpc_data)
    cluster_obj = _data['cluster']
    node_groups = eks.define_node_groups(config, cluster_obj, _data['node_role'], vpc_data)

    service_role_policy = eks.create_service_role_policy(config)
    _role_name = f'aws-load-balancer-controller-iam-role-{config.resource_prefix}'
    _service_role_name = 'aws-load-balancer-controller'
    service_account_role = eks.create_service_account_role(
        config=config,
        role_name=_role_name,
        oidc_provider_url=cluster_obj.core.oidc_provider.url,
        oidc_provider_arn=cluster_obj.core.oidc_provider.arn,
        service_account_name=_service_role_name,
        policy=service_role_policy
    )

    k8s_provider = eks.get_provider(config, cluster_obj)

    if config.lb_controller_enabled():
        release = eks.create_lb_controller(
            config=config,
            cluster=cluster_obj,
            k8s_provider=k8s_provider,
            vpc_id=vpc_data['vpc_id'],
            node_groups=node_groups,
            role=service_account_role
        )

    k8s_service_account = eks.create_k8s_service_account(config, cluster_obj, True, k8s_provider, service_account_role, _service_role_name)

    addons = eks.create_addons(config, cluster_obj, k8s_provider, node_groups)

