import pulumi
import pulumi_aws as paws
import pulumi_eks as peks
import pulumi_kubernetes as pk8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from config import AWSPulumiConfig
from constants import Constants as CONST
import os
import json, yaml

def __get_datafile(filename: str) -> str:
    parent_dir = os.path.abspath(os.getcwd())
    data_dir = os.path.join(parent_dir, 'data')
    data_file = os.path.join(data_dir, filename)

    if not os.path.isfile(data_file):
        raise OSError(f'{data_file} not found')
    
    with open(data_file, 'r') as f:
        if data_file.endswith('yaml'):
            return yaml.safe_load(f)
        else:
            return f.read()

def __write_kubeconfig(config: AWSPulumiConfig):
    _cluster = paws.eks.get_cluster(config.resource_prefix)
    kubeconfig = f"""
apiVersion: v1
clusters:
- cluster:
    server: {_cluster.endpoint}
    certificate-authority-data: {_cluster.certificate_authorities[0]['data']}
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: aws
  name: {_cluster.name}
current-context: {_cluster.name}
kind: Config
preferences: {{}}
users:
- name: aws
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1alpha1
      command: aws-iam-authenticator
      args:
        - "token"
        - "-i"
        - "{_cluster.name}"
"""

    # Export the kubeconfig.
    pulumi.export('kubeconfig', kubeconfig)

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

def define_cluster(config: AWSPulumiConfig, vpc: dict) -> dict:
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

    ## The standard node group policy...
    ## This needs to be created here because:
    ## Exception: A managed node group cannot be created without first setting its role in the cluster's instanceRoles
    node_role = paws.iam.Role(f'{config.resource_prefix}-nodegroup',
        name=f'{config.resource_prefix}-nodegroup',
        assume_role_policy=__get_datafile('nodegroup.role-policy.json'))

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
        instance_roles=[cluster_role, node_role],
    )

    cluster = peks.Cluster(config.resource_prefix,
        cluster_args,
        opts=pulumi.ResourceOptions(
            depends_on=cluster_policy_attachments
        )
    )

    pulumi.export('cluster_name', cluster.name)

    ## This has been problematic...
    #__write_kubeconfig(config)

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

    pulumi.export('nodegroups', [n.node_group.node_group_name for n in node_groups])

    return node_groups

def create_service_role_policy(config: AWSPulumiConfig):
    service_policy = __get_datafile('lb-controller.iam-policy.json')

    pargs = paws.iam.PolicyArgs(
        name=f'AWSLoadBalancerControllerIAMPolicy-{config.resource_prefix}',
        policy=service_policy,
        description='Policy for LB controller',
        tags=config.tags
    )

    return paws.iam.Policy(f'AWSLoadBalancerControllerIAMPolicy-{config.resource_prefix}', pargs)

def create_service_account_role(config: AWSPulumiConfig, role_name: str, oidc_provider_url: pulumi.Output, oidc_provider_arn: pulumi.Output, service_account_name: str,
    policy: pulumi.Output) -> paws.iam.Role:

    assume_policy = pulumi.Output.all(oidc_provider_url, oidc_provider_arn).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {
                            "Federated": f"{args[1]}",
                        },
                        "Action": "sts:AssumeRoleWithWebIdentity",
                        "Condition": {
                            "StringEquals": {
                                f"{args[0]}:aud": "sts.amazonaws.com",
                                f"{args[0]}:sub": f"system:serviceaccount:kube-system:{service_account_name}"
                            }
                        }
                    }
                ]
            }
        )
    )

    role_args = paws.iam.RoleArgs(name=role_name,
        assume_role_policy=assume_policy,
        tags=config.tags | {"Name": role_name}
    )

    role = paws.iam.Role(resource_name=role_name, args=role_args)

    pa = paws.iam.RolePolicyAttachment(resource_name=f"{role_name}-attachment",
        role=role.name,
        policy_arn=policy.arn
    )

    pulumi.export('oidc_provider_url', oidc_provider_url)

    return role

def get_provider(config: AWSPulumiConfig, cluster: pulumi.Output) -> pulumi.Output:
    k8s_provider = pk8s.Provider(config.resource_prefix, kubeconfig=cluster.kubeconfig)

    return k8s_provider

def create_k8s_service_account(config: AWSPulumiConfig, cluster: pulumi.Output, auto_mount_token: bool, k8s_provider: pulumi.Output, service_account_role: pulumi.Output, service_account_name: str) -> pulumi.Output:
    sa_args = pk8s.core.v1.ServiceAccountInitArgs(
        automount_service_account_token=auto_mount_token,
        metadata=pk8s.meta.v1.ObjectMetaArgs(
            name=cluster.eks_cluster,
            namespace='kube-system',
            annotations={
                # Annotate with the IAM role ARN
                "eks.amazonaws.com/role-arn": service_account_role.arn
            }
        )
    )

    return pk8s.core.v1.ServiceAccount(
        service_account_name, 
        args=sa_args, 
        opts=pulumi.ResourceOptions(provider=k8s_provider)
    )

def create_addons(config: AWSPulumiConfig, cluster: pulumi.Output, k8s_provider: pulumi.Output, node_groups: list) -> list:
    addons = config.eks['addons']
    if not addons:
        ## Just to show in the outputs that we didn't install any
        pulumi.export('addons', [])
        return []

    installed_addons = []

    for addon in addons:
        args = paws.eks.AddonArgs(
            cluster_name=cluster.eks_cluster,
            addon_name=addon['name'],
            addon_version=addon['version'],
            resolve_conflicts_on_create="OVERWRITE",
            resolve_conflicts_on_update="PRESERVE",
            tags=config.tags
        )

        installed_addons.append(paws.eks.Addon(
            resource_name=f'{config.resource_prefix}-{addon["name"]}',
            args=args,
            opts=pulumi.ResourceOptions(
                provider=k8s_provider,
                depends_on=node_groups
            )
        ))

    pulumi.export('addons', [a.arn for a in installed_addons])

    return installed_addons

def create_lb_controller(config: AWSPulumiConfig, cluster: pulumi.Output, k8s_provider: pulumi.Output, vpc_id: str, node_groups: list, role: pulumi.Output) -> Release:
    lb_chart = __get_datafile('aws-load-balancer-controller.values.yaml')

    lb_chart['values'].update({'clusterName': cluster.eks_cluster})
    lb_chart['values'].update({'vpcId': vpc_id})
    lb_chart['values']['serviceAccount']['annotations'].update({
        'eks.amazonaws.com/role-arn': role.arn
    })

    repo_opts_args = RepositoryOptsArgs(
        repo=lb_chart.get('source').get('url'),
    )

    release_args = ReleaseArgs(
        chart=lb_chart.get('chart_name'),
        create_namespace=True,
        force_update=True,
        namespace=lb_chart.get('namespace'),
        repository_opts=repo_opts_args,
        timeout=300,
        values=lb_chart.get('values'),
        version=lb_chart.get('version')
    )

    release = Release(
        resource_name=f'{config.resource_prefix}-lb-controller',
        args=release_args,
        opts=pulumi.ResourceOptions(
            provider=k8s_provider, depends_on=node_groups
        )
    )

    combined = pulumi.Output.all(release.name, release.version, release.status)
    pulumi.export('aws-lb', combined.apply(lambda x: f'Name: {x[0]}, Version: {x[1]}, Status: {x[2]}'))

    return release