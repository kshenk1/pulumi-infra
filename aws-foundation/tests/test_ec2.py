import pulumi
import sys, os

from mocks import MyPulumiMocks

pulumi.runtime.set_mocks(MyPulumiMocks(), preview=False)

# Now actually import the code that creates resources, and then test it.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import AWSPulumiConfig

# Mock the foundation stack first
stack = 'foundation'
import modules.vpc as vpc
config = AWSPulumiConfig(stack)
new_vpc = vpc.define_vpc(config)

# Mock the jenkins-ec2 stack
NON_SSL_PORTS = (80, 8080, 9080)
SSL_PORTS = (443, 8443, 9443)
stack = 'jenkins-ec2'
import modules.ec2 as ec2
import modules.load_balancing as lb
config = AWSPulumiConfig(stack)

instances = ec2.define_ec2(config, new_vpc)
ec2_security_group = ec2.define_ec2_security_group(config, new_vpc)
instance = instances[0]

lb_sec_group = None
if config.lb_enabled():
    lb_sec_group = lb.define_lb_security_group(config, new_vpc)

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
        assert user_data is None, f"Illegal use of user_data on server {urn}"

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
        ), f"Security group {urn} exposes port 22 to the Internet (CIDR 0.0.0.0/0)"

    # Return the results of the unit tests.
    return pulumi.Output.all(ec2_security_group.urn, ec2_security_group.ingress).apply(check_security_group_rules)


# If the load balancer is enabled, check the configuration and error if port 80/8080 only (typical non-SSL ports)
# The thought is, we could redirect non-ssl to ssl, so if we find both, ok, but if we only find what appears to be
# a non-SSL port open to the world, bark
@pulumi.runtime.test
def test_load_balancer_ports_poor_man_check():
    def check_lb_port(args):
        from_ports = []
        urn, ingress = args
        # does the security group ingress contain a from_port that appears to be SSL ?
        from_ports = [rule['from_port'] for rule in ingress]
        found_ssl = any([rule["from_port"] in SSL_PORTS for rule in ingress])

        # Do we appear to expose a non-SSL port to the world?
        http_open = any(
            [
                rule["from_port"] in NON_SSL_PORTS
                and any([block == "0.0.0.0/0" for block in rule["cidr_blocks"]]) for rule in ingress
            ]
        )

        if http_open:
            msg = f'Security group {urn} exposes a non-SSL port ({from_ports}) to the world AND we did not found an obvious SSL port.'
            msg = f'{msg} This check is a failsafe - depending on what ports you are using this may need adjusted'
            assert found_ssl is True, msg

    return pulumi.Output.all(lb_sec_group.urn, lb_sec_group.ingress).apply(check_lb_port)