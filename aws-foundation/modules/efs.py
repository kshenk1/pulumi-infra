import pulumi
import pulumi_aws as paws
from config import CBPulumiConfig
import pprint

pp = pprint.PrettyPrinter(indent=4)

def _define_security_group(config: CBPulumiConfig, vpc_data: dict) -> pulumi.Output:
    efs_sec = paws.ec2.SecurityGroup(f'{config.resource_prefix}-efs',
        vpc_id=vpc_data['vpc_id'],
        name_prefix=config.resource_prefix,
        egress=[paws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"]
        )],
        ingress=[paws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol='-1',
            cidr_blocks=[config.vpc['cidr']]
        )],
        tags=config.tags
    )
    return efs_sec

def define_efs(config: CBPulumiConfig, vpc_data: dict) -> bool:

    efs_sec = _define_security_group(config, vpc_data)

    efs = paws.efs.FileSystem(config.resource_prefix,
        creation_token=config.resource_prefix,
        lifecycle_policies=[paws.efs.FileSystemLifecyclePolicyArgs(
            transition_to_ia=config.efs['transition_to_ia'],
        )]
    )

    mount_targets = []
    for i, s in enumerate(vpc_data['private_subnets']):
        efs_mount = paws.efs.MountTarget(f'{config.resource_prefix}-{i}',
            file_system_id=efs.id,
            security_groups=[efs_sec.id],
            subnet_id=s
        )
        mount_targets.append(efs_mount)

    pulumi.export('efs_fs_id', efs.id)
    pulumi.export('efs_mount_targets', [mt.mount_target_dns_name for mt in mount_targets])

    return {
        'mount_targets': mount_targets,
        'efs': efs
    }

    