from os.path import join

class Constants:
    
    PATH_DATA           = 'data'
    PATH_STACK_CONFIGS  = 'stack-configs'
    PATH_README         = join('data', 'doc-readme')

    INSTANCE_COUNT_LIMIT = 10

    REQUIRED_TAGS = ('user', 'environment', 'purpose')
    MIN_PUBLIC_SUBNETS = 1
    MIN_PRIVATE_SUBNETS = 1

    _EKS_CLUSTER_MANAGED_ARNS = [
        'arn:aws:iam::aws:policy/AmazonEKSClusterPolicy',
        'arn:aws:iam::aws:policy/AmazonEKSServicePolicy'
    ]
    
    _EKS_NODES_MANAGED_ARNS = [
        'arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy',
        'arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy',
        'arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy',
        'arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly',
        'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'
    ]

    EKS_MANAGED_ARNS = {}
    EKS_MANAGED_ARNS['cluster'] = _EKS_CLUSTER_MANAGED_ARNS
    EKS_MANAGED_ARNS['nodegroups'] = _EKS_NODES_MANAGED_ARNS

    RDS_CHOICES                 = ('instance', 'cluster')

    FILE_AUTOSCALING_POLICY     = 'autoscaling.iam-policy.json'
    FILE_LB_CONTROLLER_VALUES   = 'aws-load-balancer-controller.values.yaml'
    FILE_CLUSTER_ROLE_POLICY    = 'cluster.role-policy.json'
    FILE_EFS_CSI_DRIVER_POLICY  = 'efs-csi-driver.iam-policy.json'
    FILE_LB_CONTROLLER_POLICY   = 'lb-controller.iam-policy.json'
    FILE_NODEGROUP_ROLE_POLICY  = 'nodegroup.role-policy.json'
    