import pulumi
import pulumi_aws as paws
from config import AWSPulumiConfig
import modules.common as common


def _define_db_subnet_group(config: AWSPulumiConfig, subnets: list) -> pulumi.Output:
    subnet_group = paws.rds.SubnetGroup(config.resource_prefix,
        name_prefix=config.resource_prefix,
        subnet_ids=[s.id for s in subnets]
    )
    return subnet_group

def _define_parameter_group(config: AWSPulumiConfig) -> pulumi.Output:
    parameters = []
    if config.rds['parameters']:
        for k, v in config.rds['parameters'].items():
            parameters.append(paws.rds.ClusterParameterGroupParameterArgs(name=k, value=v))

    param_group = paws.rds.ClusterParameterGroup(f'{config.resource_prefix}-pgroup',
        name_prefix=config.resource_prefix,
        family=config.rds['family'],
        parameters=parameters
    )
    return param_group

def define_rds(config: AWSPulumiConfig, vpc_data: dict) -> pulumi.Output:
    return define_rds_cluster(config, vpc_data)

def define_rds_cluster(config: AWSPulumiConfig, vpc_data: dict) -> pulumi.Output:
    parameter_group = _define_parameter_group(config)
    subnet_group = _define_db_subnet_group(config, vpc_data['private_subnets'])
    
    ingress_rules = [{
        'from_port': config.rds['port'],
        'to_port': config.rds['port'],
        'protocol': 'tcp',
        'cidr_ip': [config.vpc['cidr']]
    }]
    security_group = common.create_security_group(
        resource_prefix=config.resource_prefix,
        vpc_id=vpc_data['vpc_id'], 
        ingress_data=ingress_rules, 
        identifier='rds'
    )

    db_cluster = paws.rds.Cluster(config.resource_prefix,
        allocated_storage=config.rds['storage'],
        storage_type=config.rds['storage_type'],
        cluster_identifier=config.resource_prefix,
        engine=config.rds['engine'],
        engine_version=config.rds['engine_version'],
        database_name=config.rds['db_name'],
        master_username=config.rds['db_user'],
        manage_master_user_password=True,
        port=config.rds['port'],
        db_cluster_instance_class=config.rds['instance_class'],
        db_subnet_group_name=subnet_group.name,
        skip_final_snapshot=True,
        vpc_security_group_ids=[security_group.id],
        db_cluster_parameter_group_name=parameter_group.name,
        opts=pulumi.ResourceOptions(
            depends_on=[parameter_group, subnet_group, security_group]
        )
    )

    pulumi.export('rds_endpoint', db_cluster.endpoint)
    pulumi.export('rds_master_password', db_cluster.master_password)

    return db_cluster