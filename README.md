# Pulumi AWS VPC Foundation

> [!NOTE]
> This README will walk through the steps necessary to create an EKS Cluster in AWS using Pulumi with python. 
> Currently this project has 3 _pre-configured_ stacks: `foundation`, `jenkins-ec2`, and `std-eks`. These only require minor changes such as IP addresses, your username, etc. The `std-eks` stack provisions a fully-functional EKS cluster with 4 nodes as a default (2 in 2 different private subnets) and is completed with 2 autoscaling groups. 

## Pulumi
Let's cut right to the chase: [Terraform vs Pulumi](https://www.pulumi.com/docs/concepts/vs/terraform/). Read up a bit, and come back. This was my initial journey with pulumi....

### All configuration is driven from the `stack-configs/sc-*.yaml` files.
**The `ROOT` directory to refer to during this doc is `pulumi-infra/aws-foundation`.**

`__main__.py` is the entrypoint for Pulumi. In `config.py` we read in a yaml file depending on the stack which dictates how resources are created.

## VPC Configuration
You can define the vpc CIDR, subnet size, and number of public/private subnets. 

## EFS Configuration
If `efs.enabled`: One EFS is created at this time.

## EKS Configuration
If `eks.enabled`: One EKS Cluster is created, driven by the specifications made available in the `stack-configs/sc-std-eks.example.yaml` file.

### RDS Configuration
If `rds.enabled`: One RDS _database_ is created. I have only tested **mysql** so far... You can choose to bring up an RDS **Instance**, or **Cluster** via `rds.aws_rds_type` which can be any of: `[ cluster | instance ]`.

## EC2 Configuration
If `ec2.enabled`: `ec2.count` number of instances are created (safety cap at 10). Currently this is geared towards installing jenkins.

# How to make it all go
* [Install Pulumi](https://www.pulumi.com/docs/install/)
* [AWS & Pulumi](https://www.pulumi.com/docs/clouds/aws/get-started/begin/) - _Most of us have this going in our local shells already_
* [Login to Pulumi Cloud](https://app.pulumi.com/signin) - If this is your first time, you may have to create an account. I used GitHub as my signin, therefore:
```
pulumi whoami
kshenk1
```
* Login via the CLI: `pulumi login`
* Follow the steps below 

> [!WARNING]
> You might have a different python version, and take note there's different `activate` scripts depending on your shell.
> These steps should lead you in the general direction, but might not be exact

```
git clone git@github.com:kshenk1/pulumi-infra.git
cd pulumi-infra/aws-foundation

cp stack-configs/sc-foundation.example.yaml stack-configs/sc-foundation.yaml

## Make any modifications you need to stack-configs/sc-foundation.yaml

pulumi stack init foundation
pulumi up
```
