import pulumi
import pulumi_aws as paws
import modules.common as common
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from config import AWSPulumiConfig
from modules.eks import k8sProvider

def define_efs(config: AWSPulumiConfig, vpc_data: dict) -> dict:
    ingress = [{
        'from_port': 0,
        'to_port': 0,
        'protocol': '-1',
        'cidr_ip': config.vpc['cidr']
    }]
    efs_sec = common.create_security_group(
        resource_prefix=config.resource_prefix,
        vpc_id=vpc_data['vpc_id'],
        ingress_data=ingress,
        identifier='efs'
    )

    efs = paws.efs.FileSystem(config.resource_prefix,
        creation_token=config.resource_prefix,
        lifecycle_policies=[paws.efs.FileSystemLifecyclePolicyArgs(
            transition_to_ia=config.efs['transition_to_ia'],
        )]
    )

    mount_targets = vpc_data['private_subnets'].apply(
        lambda subnets: [
            paws.efs.MountTarget(
                f"{config.resource_prefix}-{subnet_id[:-4]}",
                file_system_id=efs.id,
                security_groups=[efs_sec.id],
                subnet_id=subnet_id
            )
            for subnet_id in subnets
        ]
    )

    # mount_target_dns_names = mount_targets.apply(
    #     lambda targets: [target.mount_target_dns_name for target in targets]
    # )

    # Export the list to Pulumi output
    #pulumi.export('mount_target_dns_names', mount_target_dns_names)

    pulumi.export('efs_fs_id', efs.id)

    return {
        'mount_targets': mount_targets,
        'efs': efs
    }

def define_efs_controller(config: AWSPulumiConfig, k8s_provider: k8sProvider, node_groups: list) -> Release:
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
            provider=k8s_provider.get_provider(), depends_on=node_groups
        )
    )

    combined = pulumi.Output.all(release.name, release.version, release.status['status'])
    pulumi.export(f'helm_eks_efs_controller', combined.apply(lambda x: f'Name: {x[0]}, Version: {x[1]}, Status: {x[2]}'))

    return release