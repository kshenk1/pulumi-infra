import pulumi
import pulumi_aws as paws
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from config import AWSPulumiConfig

def _define_security_group(config: AWSPulumiConfig, vpc_data: dict) -> pulumi.Output:
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

def define_efs(config: AWSPulumiConfig, vpc_data: dict) -> dict:
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

def define_efs_controller(config: AWSPulumiConfig, k8s_provider: pulumi.Output, node_groups: list) -> Release:
    repo_opt_args = RepositoryOptsArgs(
        repo='https://kubernetes-sigs.github.io/aws-efs-csi-driver/'
    )
    release_args = ReleaseArgs(
        chart='aws-efs-csi-driver',
        create_namespace=True,
        force_update=True,
        namespace='kube-system',
        repository_opts=repo_opt_args,
        timeout=300,
        version=config.efs.get('csi_driver').get('version')
    )
    release = Release(
        resource_name=f'{config.resource_prefix}-efs-controller',
        args=release_args,
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=node_groups
        )
    )

    combined = pulumi.Output.all(release.name, release.version, release.status['status'])
    pulumi.export(f'{config.resource_prefix}-efs-controller', combined.apply(lambda x: f'Name: {x[0]}, Version: {x[1]}, Status: {x[2]}'))

    return release