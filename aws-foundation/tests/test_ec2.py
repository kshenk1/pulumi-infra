import pulumi
import sys, os

from mocks import Ec2Mocks

pulumi.runtime.set_mocks(Ec2Mocks(), preview=False)

# Now actually import the code that creates resources, and then test it.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import AWSPulumiConfig

# Mock the foundation stack first
stack = 'foundation'
import modules.vpc as vpc
config = AWSPulumiConfig(stack)
new_vpc = vpc.define_vpc(config)

# Mock the jenkins-ec2 stack
stack = 'jenkins-ec2'
import modules.ec2 as ec2
config = AWSPulumiConfig(stack)

instances = ec2.define_ec2(config, new_vpc)
ec2_security_group = ec2.define_ec2_security_group(config, new_vpc)
instance = instances[0]

# See if the instance type is of the same family listed in Ec2Mocks
@pulumi.runtime.test
def test_instance_type():
    def check_instance_type(args):
        urn, i_type, _config = args
        config_type = _config.ec2.get('instance_type')
        assert config_type.startswith(i_type), f"Type '{i_type}' of resource does not match the value specified in the config: {config_type}"

    return pulumi.Output.all(instance.urn, instance.instance_type, config).apply(check_instance_type)


# Test if the instance is configured with user_data.
@pulumi.runtime.test
def test_instance_userdata():
    def check_user_data(args):
        urn, user_data = args
        assert user_data is None, f"illegal use of user_data on server {urn}"

    return pulumi.Output.all(instance.urn, instance.user_data).apply(check_user_data)


# Test if port 22 for ssh is exposed.
@pulumi.runtime.test
def test_security_group_rules():
    def check_security_group_rules(args):
        urn, ingress = args
        ssh_open = any(
            [
                rule["from_port"] == 22
                and any([block == "0.0.0.0/0" for block in rule["cidr_blocks"]])
                for rule in ingress
            ]
        )
        assert (
            ssh_open is False
        ), f"security group {urn} exposes port 22 to the Internet (CIDR 0.0.0.0/0)"

    # Return the results of the unit tests.
    return pulumi.Output.all(ec2_security_group.urn, ec2_security_group.ingress).apply(check_security_group_rules)
