
class Constants:
    
    REQUIRED_TAGS = ('cb-owner', 'cb-user', 'cb-environment', 'cb-purpose')
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

