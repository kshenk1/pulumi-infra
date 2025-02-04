import pulumi
import pulumi_aws as paws
import modules.common as common
from config import AWSPulumiConfig

def define_ec2(config: AWSPulumiConfig, vpc_data: dict) -> list:
    _ingresses = []
    instances = []
    for i in config.ec2.get('security_group').get('rules')['ingress']:
        _ingresses.append({
            'from_port': i.get('from_port'),
            'to_port': i.get('to_port'),
            'protocol': i.get('protocol'),
            'cidr_ip': i.get('cidr_ip') if i.get('cidr_ip') else vpc_data['vpc_cidr']
        })

    sec_group = common.create_security_group(
        resource_prefix=config.resource_prefix,
        vpc_id=vpc_data['vpc_id'], 
        ingress_data=_ingresses, 
        identifier=config.ec2.get('tags')['Name']
    )

    for i in range(config.ec2.get('count')):
        instance = paws.ec2.Instance(f"{config.resource_prefix}-{config.ec2.get('tags')['Name']}-{i}",
            ami=config.ec2.get('ami'),
            instance_type=paws.ec2.get_instance_type(instance_type=config.ec2.get('instance_type')).instance_type,
            iam_instance_profile=config.ec2.get('iam_instance_profile'),
            key_name=config.ec2.get('key_name'),
            root_block_device={
                "delete_on_termination": True,
                "encrypted": False,
                "volume_size": 25,
                "volume_type": "gp3",
            },
            tags=config.ec2.get('tags'),
            subnet_id=vpc_data['private_subnets'][0].apply(lambda x: x),
            vpc_security_group_ids=[sec_group.id],
        )
        instances.append(instance)

    pulumi.export("instance_ids", pulumi.Output.all(*[instance.id for instance in instances]))

    return instances

