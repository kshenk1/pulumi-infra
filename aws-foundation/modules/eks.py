import pulumi
import pulumi_aws as paws
import pulumi_eks as peks
from config import AWSPulumiConfig
from constants import Constants as CONST
import os

def __get_datafile(filename: str) -> str:
    parent_dir = os.path.abspath(os.getcwd())
    data_dir = os.path.join(parent_dir, 'data')
    data_file = os.path.join(data_dir, filename)

    if not os.path.isfile(data_file):
        raise OSError(f'{data_file} not found')
    
    with open(data_file, 'r') as f:
        return f.read()

def __policy_attachments(resource_prefix: str, type: str, role: pulumi.Output, suffix_count_start=0) -> list:
    arns = CONST.EKS_MANAGED_ARNS.get(type)
    if not arns:
        raise ValueError(f'No arns found for type: {type}. Supported types: {CONST.EKS_MANAGED_ARNS.keys()}')

    attachments = []
    for index, arn in enumerate(arns):
        i = index+suffix_count_start
        _att = paws.iam.RolePolicyAttachment(f'{resource_prefix}-grouped-{i}',
            role=role.name,
            policy_arn=arn
        )
        attachments.append(_att)

    return attachments

def __cluster_role_attachments(resource_prefix: str, tags: list) -> dict:
    cluster_role = paws.iam.Role(f'{resource_prefix}-cluster',
        assume_role_policy=__get_datafile('cluster.role-policy.json'))
    
    efs_policy = paws.iam.Policy(f'{resource_prefix}-efs-csi-driver-policy',
        name_prefix=resource_prefix,
        policy=__get_datafile('efs-csi-driver.iam-policy.json'),
        tags=tags
    )
    _efs_att = paws.iam.RolePolicyAttachment(f'{resource_prefix}-efs-att',
        role=cluster_role.name,
        policy_arn=efs_policy.arn
    )

    autoscaling_policy = paws.iam.Policy(f'{resource_prefix}-autoscaling',
        name_prefix=resource_prefix,
        policy=__get_datafile('autoscaling.iam-policy.json'),
        tags=tags
    )
    _auto_att = paws.iam.RolePolicyAttachment(f'{resource_prefix}-auto-att',
        role=cluster_role.name,
        policy_arn=autoscaling_policy.arn
    )

    cluster_policy_attachments = __policy_attachments(resource_prefix, 'cluster', cluster_role)
    cluster_policy_attachments.append(_efs_att)
    cluster_policy_attachments.append(_auto_att)

    return {
        'attachments': cluster_policy_attachments,
        'cluster_role': cluster_role
    }

def define_cluster(config: AWSPulumiConfig, vpc: dict) -> pulumi.Output:
    
    _attachments = __cluster_role_attachments(config.resource_prefix, config.tags)
    cluster_policy_attachments = _attachments['attachments']
    cluster_role = _attachments['cluster_role']

    sec_group = paws.ec2.SecurityGroup(f'{config.resource_prefix}-eks',
        vpc_id=vpc['vpc_id'],
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

    _tags = config.tags | {'Name': config.resource_prefix}

    cluster_args = peks.ClusterArgs(
        enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
        name=config.resource_prefix,
        skip_default_node_group=True,
        tags=_tags,
        version=config.eks['version'],
        vpc_id=vpc['vpc_id'],
        cluster_security_group=sec_group,
        private_subnet_ids=[s.id for s in vpc['private_subnets']],
        create_oidc_provider=True,
        instance_roles=[cluster_role],
    )

    cluster = peks.Cluster(config.resource_prefix,
        cluster_args,
        opts=pulumi.ResourceOptions(
            depends_on=cluster_policy_attachments
        )
    )

    pulumi.export('cluster_name', cluster.name)

    return cluster

def _define_launch_template(config: AWSPulumiConfig) -> pulumi.Output:
    ## Setting up for a launch template based on data from the yaml config
    instance_requirements_args = paws.ec2.LaunchTemplateInstanceRequirementsArgs(
        memory_mib=paws.ec2.LaunchTemplateInstanceRequirementsMemoryMibArgs(
            min=config.eks['node_groups']['memory_mib']['min'],
            max=config.eks['node_groups']['memory_mib']['max']
        ),
        vcpu_count=paws.ec2.LaunchTemplateInstanceRequirementsVcpuCountArgs(
            min=config.eks['node_groups']['vcpu_count']['min'],
            max=config.eks['node_groups']['vcpu_count']['max']
        ),
        allowed_instance_types=config.eks['node_groups']['instance_types']
    )

    ## Define the launch template for nodes in the node group
    _tags = config.tags | {'Name': f'{config.resource_prefix}-nodes'}
    launch_template = paws.ec2.LaunchTemplate(f'{config.resource_prefix}-nodegroup',
        instance_requirements=instance_requirements_args,
        tag_specifications=[paws.ec2.LaunchTemplateTagSpecificationArgs(
            resource_type='instance',
            tags=_tags
        )],
        tags=config.tags
    )
    return launch_template

def define_node_groups(config: AWSPulumiConfig, cluster: pulumi.Output, vpc: dict) -> list:

    ## The standard node group policy...
    node_role = paws.iam.Role(f'{config.resource_prefix}-nodegroup',
        assume_role_policy=__get_datafile('nodegroup.role-policy.json'))

    ## Attachments for the managed policies
    node_policy_attachments = __policy_attachments(config.resource_prefix, 'nodegroups', node_role, 20)

    ## Launch template to be used to define nodes in our node groups
    launch_template = _define_launch_template(config)

    ## Required tags for k8s scheduling
    ng_tags = {
        'k8s.io/cluster-autoscaler/enabled': 'true',
        f'k8s.io/cluster-autoscaler/{config.resource_prefix}': 'owned',
        f'k8s.io/cluster/{config.resource_prefix}': 'owned'
    }

    ## Set up managed node group definition
    managed_nodegroup_args = peks.ManagedNodeGroupArgs(
        capacity_type='ON_DEMAND',
        cluster=cluster,
        cluster_name=config.resource_prefix,
        node_group_name_prefix=config.resource_prefix,
        launch_template=paws.eks.NodeGroupLaunchTemplateArgs(
            id=launch_template.id,
            version=launch_template.latest_version
        ),
        scaling_config=paws.eks.NodeGroupScalingConfigArgs(
            desired_size=config.eks['desired_nodes_per_group'],
            max_size=config.eks['max_nodes_per_group'],
            min_size=config.eks['desired_nodes_per_group']
        ),
        node_role_arn=node_role.arn,
        tags=(config.tags | ng_tags)
    )

    ## Create a managed node group in EACH of the private subnets defined
    node_groups = []
    for index, s in enumerate(vpc['private_subnets']):
        group = peks.ManagedNodeGroup(f'{config.resource_prefix}-mng-{index}',
            cluster_name=cluster.eks_cluster,
            args=managed_nodegroup_args,
            subnet_ids=s.id,
            opts=pulumi.ResourceOptions(
                depends_on=[cluster, node_role] + node_policy_attachments
            )
        )
        node_groups.append(group)

    pulumi.export('nodegroups', [n.node_group_name for n in node_groups])

    return node_groups
