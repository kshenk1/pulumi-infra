import pulumi
import pulumi_aws as paws
import random
import string
import os
import yaml

def get_datafile(filename: str) -> str:
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

def create_security_group(resource_prefix: str, vpc_id: str, ingress_data: list, egress_data=[], identifier=None) -> paws.ec2.SecurityGroup:
    rand_str        = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    default_egress  = [
        paws.ec2.SecurityGroupEgressArgs(
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"],
        )
    ]
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
        egress = default_egress

    slug = rand_str if identifier is None else identifier

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