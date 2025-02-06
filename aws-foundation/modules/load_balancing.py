import pulumi
import pulumi_aws as paws
import modules.common as common
from config import AWSPulumiConfig

def define_lb(config: AWSPulumiConfig, vpc_data: dict, instances: list) -> paws.lb.LoadBalancer:
    def _get_subnet_ids(pub, priv) -> list:
        combined_subnet_ids = pulumi.Output.all(pub, priv).apply(
            lambda lists: lists[0] + lists[1]
        )
        return combined_subnet_ids
    
    lb_sec = common.create_security_group(
        resource_prefix=config.resource_prefix, 
        vpc_id=vpc_data['vpc_id'], 
        ingress_data=config.lb.get('security_group').get('rules')['ingress'], 
        identifier='alb'
    )

    lb = paws.lb.LoadBalancer(f'{config.resource_prefix}-lb',
        load_balancer_type=config.lb.get('type'),
        enable_deletion_protection=False,
        idle_timeout=5,
        internal=False,
        name_prefix=config.resource_prefix[0:5],
        security_groups=[lb_sec.id],
        subnets=_get_subnet_ids(vpc_data['public_subnets'], vpc_data['private_subnets'])
    )

    target_group = paws.lb.TargetGroup(
        f'{config.resource_prefix}-tg',
        port=8080,
        protocol="HTTP",
        target_type="instance",
        vpc_id=vpc_data['vpc_id'],
        health_check={
            "enabled": True,
            "healthy_threshold": 2,
            "interval": 10,
            "matcher": "200",
            "path": "/login",
            "port": "8080",
            "protocol": "HTTP",
            "timeout": 5,
            "unhealthy_threshold": 2,
        },
        stickiness={
            "type": "lb_cookie",
        }
    )

    for index, i in enumerate(instances):
        paws.lb.TargetGroupAttachment(
            f'{config.resource_prefix}-tg-attachment-{index }',
            target_group_arn=target_group.arn,
            target_id=i.id,
            port=8080
        )

    _define_redirect_listener(config, lb)
    _define_ssl_listener(config, lb, target_group)

    pulumi.export('lb_dns_name', lb.dns_name)
    pulumi.export('lb_arn', lb.arn)

    return lb

def _define_ssl_listener(config: AWSPulumiConfig, lb: paws.lb.LoadBalancer, target_group) -> paws.lb.Listener:
    listener = paws.lb.Listener(
        f'{config.resource_prefix}-ssl',
        load_balancer_arn=lb.arn,
        port=443,
        protocol="HTTPS",
        ssl_policy="ELBSecurityPolicy-2016-08",
        certificate_arn=config.lb.get('certificate_arn'),
        default_actions=[
            paws.lb.ListenerDefaultActionArgs(
                type="forward",
                target_group_arn=target_group.arn
            )
        ]
    )
    return listener

def _define_redirect_listener(config: AWSPulumiConfig, lb: paws.lb.LoadBalancer) -> paws.lb.Listener:
    listener = paws.lb.Listener(
        f'{config.resource_prefix}-redirect',
        load_balancer_arn=lb.arn,
        port=80,
        protocol="HTTP",
        default_actions=[{
            "type": "redirect",
            "redirect": {
                "port": "443",
                "protocol": "HTTPS",
                "status_code": "HTTP_301",
            },
        }]
    )
    return listener

