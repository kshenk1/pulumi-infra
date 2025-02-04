import pulumi
import pulumi_aws as paws
import random
import string

RAND_STRING     = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
DEFAULT_EGRESS  = [paws.ec2.SecurityGroupEgressArgs(
    from_port=0,
    to_port=0,
    protocol="-1",
    cidr_blocks=["0.0.0.0/0"],
)]

def create_security_group(resource_prefix: str, vpc_id: str, ingress_data: list, egress_data=[], identifier=None) -> paws.ec2.SecurityGroup:
    ingress = [
        paws.ec2.SecurityGroupIngressArgs(
            from_port=i['from_port'],
            to_port=i['to_port'],
            protocol=i['protocol'],
            cidr_blocks=[i['cidr_ip']]
        ) for i in ingress_data
    ]
    if len(egress_data) > 0:
        egress = [
            paws.ec2.SecurityGroupEgressArgs(
                from_port=i['from_port'],
                to_port=i['to_port'],
                protocol=i['protocol'],
                cidr_blocks=[i['cidr_ip']]
            ) for i in egress_data
        ]
    else:
        egress = DEFAULT_EGRESS

    slug = RAND_STRING if identifier is None else identifier

    security_group = paws.ec2.SecurityGroup(f'{resource_prefix}-{slug}',
        description=f'Security group created for {slug}',
        egress=egress,
        ingress=ingress,
        name_prefix=f'{resource_prefix}-{slug}-sg',
        revoke_rules_on_delete=False,
        vpc_id=vpc_id
    )

    pulumi.export(f'{slug}_sg_id', security_group.id)

    return security_group