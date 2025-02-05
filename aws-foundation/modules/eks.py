import pulumi
import pulumi_aws as paws
import pulumi_eks as peks
import pulumi_kubernetes as pk8s
import modules.common as common
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from config import AWSPulumiConfig
from constants import Constants as CONST
import os
import yaml

class k8sProvider(pulumi.ComponentResource):

    cluster = None
    config = None
    provider = None

    def __init__(self, config: AWSPulumiConfig, cluster: peks.Cluster, provider_id: str = None) -> object:
        self.config = config
        self.cluster = cluster
        
        self.__set_provider(provider_id)
    
    def __set_provider(self, provider_id: str = None):
        if provider_id:
            self.provider = self.get_provider(provider_id)
        else:
            self.provider = pk8s.Provider(self.config.resource_prefix, kubeconfig=self.cluster.kubeconfig)

    def get_provider(self, provider_id: str = None) -> pk8s.Provider:
        if self.provider and not provider_id:
            return self.provider
        
        if provider_id:
            return pulumi.get_resource(resource_type=pk8s.Provider, id=provider_id)
        
        raise ValueError('You should not be here')

def __write_kubeconfig(config: AWSPulumiConfig):
    pulumi.export('kubeconfig_update_command', f'aws eks update-kubeconfig --name {config.resource_prefix} --alias {config.resource_prefix}')

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
        assume_role_policy=common.get_datafile(CONST.FILE_CLUSTER_ROLE_POLICY))
    
    efs_policy = paws.iam.Policy(f'{resource_prefix}-efs-csi-driver-policy',
        name_prefix=resource_prefix,
        policy=common.get_datafile(CONST.FILE_EFS_CSI_DRIVER_POLICY)
    )
    _efs_att = paws.iam.RolePolicyAttachment(f'{resource_prefix}-efs-att',
        role=cluster_role.name,
        policy_arn=efs_policy.arn
    )

    autoscaling_policy = paws.iam.Policy(f'{resource_prefix}-autoscaling',
        name_prefix=resource_prefix,
        policy=common.get_datafile(CONST.FILE_AUTOSCALING_POLICY)
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

def __get_asg_name(cluster_name: str, node_group_name: str) -> str:
    node_group_info = paws.eks.get_node_group(
        cluster_name=cluster_name,
        node_group_name=node_group_name
    )
    try:
        return node_group_info.resources[0]['autoscaling_groups'][0]['name']
    except (KeyError, IndexError) as e:
        raise(e)

def _tag_asgs(config: AWSPulumiConfig, asg_names: list, node_groups: list):

    for k, v in config.tags.items():
        asg_names.apply(
            lambda asg: [
                paws.autoscaling.Tag(f'{config.resource_prefix}-asg-tag-{k}',
                    autoscaling_group_name=asg,
                    tag=paws.autoscaling.TagTagArgs(
                        key=k,
                        propagate_at_launch=False, # no, we'll get them from the launch template
                        value=v
                    ),
                    opts=pulumi.ResourceOptions(
                        depends_on=node_groups
                    )
                )
            ]
        )

def _define_launch_template(config: AWSPulumiConfig) -> paws.ec2.LaunchTemplate:
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
        )]
    )
    return launch_template

def define_cluster(config: AWSPulumiConfig, vpc: dict) -> dict:
    _attachments = __cluster_role_attachments(config.resource_prefix, config.tags)
    cluster_policy_attachments = _attachments['attachments']
    cluster_role = _attachments['cluster_role']

    ingress = [{
        'from_port': 0,
        'to_port': 0,
        'protocol': '-1',
        'cidr_ip': config.vpc['cidr']
    }]

    sec_group = common.create_security_group(
        resource_prefix=config.resource_prefix,
        vpc_id=vpc['vpc_id'].apply(lambda x: x),
        ingress_data=ingress,
        identifier='eks'
    )

    ## The standard node group policy...
    ## This needs to be created here because:
    ## Exception: A managed node group cannot be created without first setting its role in the cluster's instanceRoles
    node_role = paws.iam.Role(f'{config.resource_prefix}-nodegroup',
        name=f'{config.resource_prefix}-nodegroup',
        assume_role_policy=common.get_datafile(CONST.FILE_NODEGROUP_ROLE_POLICY))

    _tags = config.tags | {'Name': config.resource_prefix}
    cluster_args = peks.ClusterArgs(
        enabled_cluster_log_types=["api", "audit", "authenticator", "controllerManager", "scheduler"],
        name=config.resource_prefix,
        skip_default_node_group=True,
        tags=_tags,
        version=config.eks['version'],
        vpc_id=vpc['vpc_id'],
        cluster_security_group=sec_group,
        private_subnet_ids=vpc['private_subnets'],
        create_oidc_provider=True,
        instance_roles=[cluster_role, node_role],
    )

    cluster = peks.Cluster(config.resource_prefix,
        cluster_args,
        opts=pulumi.ResourceOptions(
            depends_on=cluster_policy_attachments
        )
    )

    pulumi.export('cluster_name', cluster.name)

    __write_kubeconfig(config)

    return {
        'cluster': cluster,
        'node_role': node_role
    }

def define_node_groups(config: AWSPulumiConfig, cluster: pulumi.Output, node_role: pulumi.Output, vpc: dict) -> list:
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

    node_groups = vpc['private_subnets'].apply(
        lambda subnets: [
            peks.ManagedNodeGroup(f'{config.resource_prefix}-mng-{subnet_id[-4:]}',
                cluster_name=cluster.eks_cluster,
                args=managed_nodegroup_args,
                subnet_ids=subnet_id,
                opts=pulumi.ResourceOptions(
                    depends_on=[cluster, node_role] + node_policy_attachments
                )
            )
            for subnet_id in subnets
        ]
    )

    asgs = node_groups.apply(
        lambda group: [
            pulumi.Output.all(cluster.eks_cluster, g.node_group.node_group_name).apply(
                lambda args: __get_asg_name(args[0], args[1])
            ) for g in group
        ]
    )

    # Currently... very troublesome to tag the ASGs
    #_tag_asgs(config, asgs, node_groups)
    ng_export = node_groups.apply(
        lambda groups: [g.node_group.node_group_name for g in groups]
    )
    pulumi.export('nodegroups', ng_export)

    return node_groups

def define_addons(config: AWSPulumiConfig, k8s_provider: k8sProvider, node_groups: list) -> list:
    addons = config.eks['addons']
    if not addons:
        ## Just to show in the outputs that we didn't install any
        pulumi.export('addons', [])
        return []

    installed_addons = []
    cluster = k8s_provider.cluster

    for addon in addons:
        args = paws.eks.AddonArgs(
            cluster_name=cluster.eks_cluster,
            addon_name=addon['name'],
            addon_version=addon['version'],
            resolve_conflicts_on_create="OVERWRITE",
            resolve_conflicts_on_update="PRESERVE"
        )

        installed_addons.append(paws.eks.Addon(
            resource_name=f'{config.resource_prefix}-{addon["name"]}',
            args=args,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider.get_provider(),
                depends_on=node_groups
            )
        ))

    pulumi.export('addons', [a.arn for a in installed_addons])

    return installed_addons
