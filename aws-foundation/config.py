import yaml

from constants import Constants as CONST

class AWSPulumiConfig(object):

    def __init__(self, config_file: str) -> object:
        with open(file=config_file, mode="r", encoding="utf-8") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        if not config:
            raise OSError(f'File {config_file} does not exist')
        
        self.__validation(config)
        
        self.resource_prefix = config.get('resource_prefix')
        self.vpc = config.get('aws')['vpc']
        self.tags = config.get('aws')['tags']
        self.efs = config.get('aws')['efs']
        self.eks = config.get('aws')['eks']

    def instance_requested(self) -> bool:
        return self.rds.get('aws_rds_type') == 'instance'

    def cluster_requested(self) -> bool:
        return self.rds.get('aws_rds_type') == 'cluster'

    def rds_enabled(self) -> bool:
        return self.rds.get('enabled')
    
    def eks_enabled(self) -> bool:
        return self.eks.get('enabled')
    
    def efs_enabled(self) -> bool:
        return self.efs.get('enabled')
    
    def lb_controller_enabled(self) -> bool:
        return self.eks.get('loadbalancer_controller').get('enabled')
    
    def efs_csi_driver_enabled(self) -> bool:
        return self.efs.get('csi_driver').get('enabled')

    def __validation(self, config) -> bool:
        tags = config.get('aws')['tags']
        e = []
        for t in CONST.REQUIRED_TAGS:
            if not tags.get(t):
                e.append(f'Tag: {t} is missing!')

        if not config.get('resource_prefix'):
            e.append('"resource_prefix" must be specified!')

        try:
            vpc_net_size = int(config.get('aws').get('vpc')['cidr'].split('/')[1])
            if vpc_net_size >= int(config.get('aws').get('vpc')['subnet_size']):
                e.append('The vpc network must be larger than the subnets!')
        except IndexError:
            e.append('Is the vpc.cidr missing?')

        if int(config.get('aws').get('vpc')['num_public_subnets']) < CONST.MIN_PUBLIC_SUBNETS:
            e.append(f'There needs to be at least {CONST.MIN_PUBLIC_SUBNETS} public subnet(s)')
        if int(config.get('aws').get('vpc')['num_private_subnets']) < CONST.MIN_PRIVATE_SUBNETS:
            e.append(f'There needs to be at least {CONST.MIN_PRIVATE_SUBNETS} private subnet(s)')

        if config.get('aws').get('rds').get('enabled'):
            self.rds = config.get('aws')['rds']
            self.rds['fqdn_internal'] = f"{self.rds['subdomain']}.{config.get('resource_prefix')}.{self.rds['tld']}"

        if len(e) > 0:
            raise ValueError('\n'.join(e))
        