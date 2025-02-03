import pulumi
import pulumi_aws as paws
import modules.common as common
from config import AWSPulumiConfig

def define_ec2(config: AWSPulumiConfig, vpc_data: dict) -> paws.ec2.Instance:
    sec_group = common.create_security_group(
        resource_prefix=config.resource_prefix,
        vpc_id=vpc_data['vpc_id'], 
        ingress_data=config.ec2.get('security_group').get('rules')['ingress'], 
        identifier=config.ec2.get('tags')['Name']
    )

    instance = paws.ec2.Instance(f"{config.resource_prefix}-{config.ec2.get('tags')['Name']}",
        ami=config.ec2.get('ami'),
        instance_type=paws.ec2.get_instance_type(instance_type=config.ec2.get('instance_type')).instance_type,
        iam_instance_profile=config.ec2.get('iam_instance_profile'),
        key_name=config.ec2.get('key_name'),
        root_block_device={
            "delete_on_termination": True,
            "encrypted": False,
            "volume_size": 50,
            "volume_type": "gp3",
        },
        tags=config.ec2.get('tags'),
        subnet_id=vpc_data['private_subnets'][0].id,
        vpc_security_group_ids=[sec_group.id],
    )

    pulumi.export('ec2_instance_id', instance.id)

    return instance

