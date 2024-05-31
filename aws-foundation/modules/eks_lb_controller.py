import pulumi
import pulumi_aws as paws
import pulumi_eks as peks
import pulumi_kubernetes as pk8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from modules.eks import k8sProvider
from config import AWSPulumiConfig
from constants import Constants as CONST

from modules.eks import get_datafile
import json

def define_lb_controller(config: AWSPulumiConfig, k8s_provider: k8sProvider, node_groups: list, vpc_id: str) -> dict:
    service_role_policy = create_service_role_policy(config)
    cluster = k8s_provider.cluster
    _role_name = f'{config.resource_prefix}-{config.eks.get("loadbalancer_controller").get("role_name_prefix")}'
    _service_role_name = f'{config.resource_prefix}-{config.eks.get("loadbalancer_controller").get("service_role_name")}'

    service_account_role = create_service_account_role(
        config=config,
        role_name=_role_name,
        oidc_provider_url=cluster.core.oidc_provider.url,
        oidc_provider_arn=cluster.core.oidc_provider.arn,
        service_account_name=_service_role_name,
        policy=service_role_policy
    )

    lb_chart = get_datafile(CONST.FILE_LB_CONTROLLER_VALUES)

    lb_chart['values'].update({'clusterName': cluster.eks_cluster})
    lb_chart['values'].update({'vpcId': vpc_id})
    lb_chart['values']['serviceAccount']['annotations'].update({
        'eks.amazonaws.com/role-arn': service_account_role.arn
    })

    release_args = ReleaseArgs(
        chart=lb_chart.get('chart_name'),
        create_namespace=True,
        force_update=True,
        namespace=lb_chart.get('namespace'),
        repository_opts=RepositoryOptsArgs(
            repo=lb_chart.get('source').get('url'),
        ),
        timeout=300,
        values=lb_chart.get('values'),
        version=lb_chart.get('version')
    )

    release = Release(
        resource_name=f'{config.resource_prefix}-lb-controller',
        args=release_args,
        opts=pulumi.ResourceOptions(
            provider=k8s_provider.get_provider(), depends_on=node_groups
        )
    )

    combined = pulumi.Output.all(release.name, release.version, release.status['status'])
    pulumi.export(f'helm_eks_lb_controller', combined.apply(lambda x: f'Name: {x[0]}, Version: {x[1]}, Status: {x[2]}'))

    k8s_service_account = create_k8s_service_account(config, cluster, True, k8s_provider, service_account_role, _service_role_name)

    return {
        'service_role_policy': service_role_policy,
        'service_account_role': service_account_role,
        'lb_release': release,
        'k8s_service_account': k8s_service_account
    }


def create_service_role_policy(config: AWSPulumiConfig) -> paws.iam.Policy:
    service_policy = get_datafile(CONST.FILE_LB_CONTROLLER_POLICY)

    pargs = paws.iam.PolicyArgs(
        name=f'AWSLoadBalancerControllerIAMPolicy-{config.resource_prefix}',
        policy=service_policy,
        description='Policy for LB controller'
    )

    return paws.iam.Policy(f'{config.resource_prefix}-AWSLoadBalancerControllerIAMPolicy', pargs)

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

def create_k8s_service_account(config: AWSPulumiConfig, cluster: pulumi.Output, auto_mount_token: bool, k8s_provider: k8sProvider, service_account_role: pulumi.Output, service_account_name: str) -> pulumi.Output:
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
        opts=pulumi.ResourceOptions(provider=k8s_provider.get_provider())
    )