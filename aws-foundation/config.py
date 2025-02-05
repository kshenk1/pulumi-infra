import yaml

from constants import Constants as CONST

class AWSPulumiConfig(object):

    def __init__(self, stack_name: str) -> object:
        config_file = f'stack-configs/sc-{stack_name}.yaml'

        with open(file=config_file, mode="r", encoding="utf-8") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)

        if not config:
            raise OSError(f'File {config_file} does not exist')
        
        self.stack_name         = stack_name 
        self.hosted_zone        = config.get('hosted_zone')
        self.domain_name        = config.get('domain_name')
        self.zone_alias_id      = config.get('zone_alias_id')
        self.resource_prefix    = config.get('resource_prefix') if config.get('resource_prefix') else stack_name
        self.vpc                = config.get('aws').get('vpc')
        self.rds                = config.get('aws').get('rds')
        self.tags               = config.get('aws').get('tags')
        self.efs                = config.get('aws').get('efs')
        self.eks                = config.get('aws').get('eks')
        self.ec2                = config.get('aws').get('ec2')
        self.lb                 = config.get('aws').get('lb')

        self.__validation(config)

    def add_tags(self, tags: dict):
        if not isinstance(tags, dict):
            raise ValueError('tags must be a dictionary.')
        
        self.tags.update(tags)

    def instance_requested(self) -> bool:
        return self.rds.get('aws_rds_type') == 'instance'

    def cluster_requested(self) -> bool:
        return self.rds.get('aws_rds_type') == 'cluster'

    def lb_enabled(self) -> bool:
        return self.lb.get('enabled')

    def ec2_enabled(self) -> bool:
        return self.ec2.get('enabled')

    def rds_enabled(self) -> bool:
        return self.rds.get('enabled') if self.rds else False
    
    def eks_enabled(self) -> bool:
        return self.eks.get('enabled')
    
    def efs_enabled(self) -> bool:
        return self.efs.get('enabled') if self.efs else False
    
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

        if config.get('aws').get('ec2') and self.ec2_enabled():
            if self.ec2.get('count') > CONST.INSTANCE_COUNT_LIMIT:
                e.append(f'Instance count cannot exceed {CONST.INSTANCE_COUNT_LIMIT}')

        if self.stack_name == 'foundation':
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

        if config.get('aws').get('rds') and config.get('aws').get('rds').get('enabled'):
            self.rds['fqdn_internal'] = f"{self.rds['subdomain']}.{config.get('resource_prefix')}.{self.rds['tld']}"

            _rds_type = self.rds.get('aws_rds_type')
            if _rds_type not in CONST.RDS_CHOICES:
                e.append(f'Invalid RDS type: "{_rds_type}". This must be one of {", ".join(CONST.RDS_CHOICES)}')

        if len(e) > 0:
            raise ValueError('\n'.join(e))
        