# AWS Foundation
The purpose of this stack is to provide the basic networking, route tables and gateways to house additional infrastructure.

There are no clusters, ec2 instances, volumes or anything created at this point - just networking resources.

## Prerequisites
 * Active AWS Account
 * Sufficient authorization to create VPC, Route53, EKS, EC2, and RDS resources
 * An existing hosted zone capable of accepting new records
 * An ACM Certificate - wildcard for the domain or at least to cover `jenkins`.yourHostedZone
 * Access to AWS via the CLI
