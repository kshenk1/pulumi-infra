import pulumi
import pulumi_aws as paws
from config import CBPulumiConfig
from constants import Constants as CONST
import os

def _define_security_group(config: CBPulumiConfig, vpc_id: str) -> pulumi.Output:
    sec_group = paws.ec2.SecurityGroup(f'{config.resource_prefix}-rds',
        vpc_id=vpc_id,
        name_prefix=config.resource_prefix,
        egress=[paws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"]
        )],
        ingress=[paws.ec2.SecurityGroupEgressArgs(
            from_port=config.rds['port'],
            to_port=config.rds['port'],
            protocol='tcp',
            cidr_blocks=[config.vpc['cidr']]
        )],
        tags=config.tags
    )
    return sec_group

def _define_db_subnet_group(config: CBPulumiConfig, subnets: list) -> pulumi.Output:
    subnet_group = paws.rds.SubnetGroup(config.resource_prefix,
        name_prefix=config.resource_prefix,
        subnet_ids=[s.id for s in subnets],
        tags=config.tags
    )
    return subnet_group

def _define_parameter_group(config: CBPulumiConfig) -> pulumi.Output:
    parameters = []
    if config.rds['parameters']:
        for k, v in config.rds['parameters'].items():
            parameters.append(paws.rds.ParameterGroupParameterArgs(name=k, value=v))

    param_group = paws.rds.ParameterGroup(config.resource_prefix,
        name_prefix=config.resource_prefix,
        family=config.rds['family'],
        parameters=parameters
    )
    return param_group

def define_rds_cluster(config: CBPulumiConfig, vpc_data: dict) -> pulumi.Output:
    parameter_group = _define_parameter_group(config)
    subnet_group = _define_db_subnet_group(config, vpc_data['private_subnets'])
    security_group = _define_security_group(config, vpc_data['vpc_id'])

    db_cluster = paws.rds.Cluster(config.resource_prefix,
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