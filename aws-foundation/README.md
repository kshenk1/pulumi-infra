# Pulumi AWS VPC Foundation

> [!IMPORTANT]
> This README will walk through the steps necessary to create an EKS Cluster in AWS that is _NOT_ opinionated in anyway towards CI or CD. This is, however; opinionated in regards to how to create an EKS cluster, with what tools, and what permissions in order for things to work. 

## Pulumi
Let's cut right to the chase: [Terraform vs Pulumi](https://www.pulumi.com/docs/concepts/vs/terraform/). Read up a bit, and come back. This was my initial journey with pulumi....

### All configuration is driven from the `stack-config.yaml` file.
**The `ROOT` directory to refer to during this doc is `pulumi-infra/aws-foundation`.**

`__main__.py` is the entrypoint for Pulumi. In `config.py` we read in that yaml file which dictates how resources are created.

## VPC Configuration
You can define the vpc CIDR, subnet size, and number of public/private subnets. 

### EFS Configuration
If `efs.enabled`: One EFS is created at this time.

### EKS Configuration
If `eks.enabled`: One EKS Cluster is created, driven by the specifications made available in the `stack-config.yaml`

### RDS Configuration
If `rds.enabled`: One RDS Cluster (currently no additional instances) is created. I have only tested **mysql** so far...

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

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp stack-config.example.yaml stack-config.yaml

## Make any modifications you need to stack-config.yaml

pulumi stack init <resource_prefix from stack-condig.yaml>
pulumi up
```
> [!NOTE]
> About `<resource_prefix from stack-condig.yaml>`: This can be whatever you want it to be. I've found it easy to track things by using the resource_prefix as my stack. Seems to make sense so far, perhaps until another scenario is hit...

