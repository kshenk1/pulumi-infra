import pulumi
import os, sys
from mocks import MyPulumiMocks

pulumi.runtime.set_mocks(MyPulumiMocks(), preview=False)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import AWSPulumiConfig
stack = 'foundation'

import modules.vpc as vpc
config = AWSPulumiConfig(stack)

new_vpc = vpc.define_vpc(config)

@pulumi.runtime.test
def test_vpc():
    def check_vpc(args):
        id = args
        assert id is not None, f"We must obtain a VPC ID"

    return pulumi.Output.all(new_vpc['vpc_id']).apply(check_vpc)

@pulumi.runtime.test
def test_subnet():
    def check_subnets(args):
        pubsubs, privsubs = args
        assert len(pubsubs) > 0, f"We must have public subnets"
        assert len(privsubs) > 0, f"We must have private subnets"

    return pulumi.Output.all(new_vpc['public_subnets'], new_vpc['private_subnets']).apply(check_subnets)
