import pulumi
import pulumi_aws as paws
import ipaddress
from config import AWSPulumiConfig

azs = paws.get_availability_zones(state='available')

def __slice_up_vpc_subnets(vpc_cidr: str, subnet_bits: int) -> list:
    vpc_net = ipaddress.ip_network(vpc_cidr)

    if (vpc_net.prefixlen >= subnet_bits):
        print(f'Subnet size ({subnet_bits}) must be greater than the VPC network ({vpc_net.prefixlen})')
        return False

    subs = [str(s) for s in vpc_net.subnets(new_prefix=subnet_bits)]
    
    return subs

## Define the VPC
def define_vpc(config: AWSPulumiConfig) -> dict:
    vpc = paws.ec2.Vpc(f'{config.resource_prefix}-vpc',
        cidr_block=config.vpc['cidr'],
        tags=config.tags,
        enable_dns_hostnames=True)

    pulumi.export('vpc_id', vpc.id)

    subnets = __slice_up_vpc_subnets(config.vpc['cidr'], config.vpc['subnet_size'])
    num_private_subnets = config.vpc['num_private_subnets']
    num_public_subnets = config.vpc['num_public_subnets']

    if not subnets:
        return False
    
    private_subs = []
    public_subs = []

    ## Define private subnets
    _add_tags = {
        'Name' : f'{config.resource_prefix}-priv',
        f'kubernetes.io/cluster/{config.resource_prefix}': "shared",
        'kubernetes.io/role/internal-elb': '1'
    }
    _tags = config.tags | _add_tags
    for i in range(num_private_subnets):    
        sub = paws.ec2.Subnet(f'{config.resource_prefix}-privnet-{i}',
            vpc_id=vpc.id,
            availability_zone=azs.names[i],
            cidr_block=subnets[i],
            enable_resource_name_dns_a_record_on_launch=True,
            private_dns_hostname_type_on_launch='ip-name',
            tags=_tags)
        private_subs.append(sub)

    ## Define public subnets
    _add_tags = {
        'Name' : f'{config.resource_prefix}-pub',
        f'kubernetes.io/cluster/{config.resource_prefix}': 'shared',
        'kubernetes.io/role/elb': '1'
    }
    _tags = config.tags | _add_tags
    for i in range(num_private_subnets, num_private_subnets+num_public_subnets):
        try:
            az = azs.names[i]
        except IndexError:
            az = azs.names[i-num_private_subnets]

        sub = paws.ec2.Subnet(f'{config.resource_prefix}-pubnet-{i}',
            vpc_id=vpc.id,
            availability_zone=az,
            cidr_block=subnets[i],
            map_public_ip_on_launch=True,
            tags=_tags)

        public_subs.append(sub)

    ## Define an internet gateway
    gw = paws.ec2.InternetGateway(f'{config.resource_prefix}-igw',
        vpc_id=vpc.id,
        tags=config.tags)

    ## Define an EIP for the public subnet(s)
    eip = paws.ec2.Eip(config.resource_prefix,
        domain='vpc',
        opts=pulumi.ResourceOptions(depends_on=[gw]),
        tags=config.tags)

    ## Define a NAT Gateway
    ngw = paws.ec2.NatGateway(f'{config.resource_prefix}-nat',
        allocation_id=eip.id,
        subnet_id=public_subs[0].id,
        tags=config.tags)

    ## Define the PRIVATE route table
    _tags = config.tags | {'Name': f'{config.resource_prefix}-priv'}
    prv_rt = paws.ec2.RouteTable(f'{config.resource_prefix}-priv',
        vpc_id=vpc.id,
        routes=[
            paws.ec2.RouteTableRouteArgs(
                cidr_block='0.0.0.0/0',
                gateway_id=ngw.id
            )
        ],
        tags=_tags)

    ## Define PUBLIC route table
    _tags = config.tags | {'Name': f'{config.resource_prefix}-pub'}
    pub_rt = paws.ec2.RouteTable(f'{config.resource_prefix}-pub',
        vpc_id=vpc.id,
        routes=[
            paws.ec2.RouteTableRouteArgs(
                cidr_block='0.0.0.0/0',
                gateway_id=gw.id
            )
        ],
        tags=_tags)

    ## Private RT association(s)
    for index, priv_sub in enumerate(private_subs):
        priv_rta = paws.ec2.RouteTableAssociation(f'{config.resource_prefix}-{index}',
            subnet_id=priv_sub,
            route_table_id=prv_rt.id)

    ## Public RT association(s)
    index_start = len(private_subs)
    for index, pub_sub in enumerate(public_subs):
        pub_rta = paws.ec2.RouteTableAssociation(f'{config.resource_prefix}-{index+index_start}',
            subnet_id=pub_sub,
            route_table_id=pub_rt.id)

    return {
        'vpc_id': vpc.id,
        'vpc_cidr': config.vpc['cidr'],
        'public_subnets': public_subs,
        'private_subnets': private_subs
    }
