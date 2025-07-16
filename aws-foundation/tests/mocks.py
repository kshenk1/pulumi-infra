import pulumi


class MyPulumiMocks(pulumi.runtime.Mocks):
    def new_resource(self, args: pulumi.runtime.MockResourceArgs):
        outputs = args.inputs
        if args.typ == "aws:ec2/vpc:Vpc":
            outputs = {
                **args.inputs,
                "id": "vpc-12345678"
            }
        if args.typ == "aws:ec2/instance:Instance":
            outputs = {
                **args.inputs,
                "publicIp": "192.168.1.5",
                "publicDns": "ec2-192-168-1-5.compute-1.amazonaws.com",
                "instance_type": 't3a.'
            }
        return [args.name + "_id", outputs]

    def call(self, args: pulumi.runtime.MockCallArgs):
        ret = {}
        
        if args.token == "aws:ec2/getAmi:getAmi":
            ret = {
                "architecture": "x86_64",
                "id": "ami-0eb1f3cdeeb8eed2a",
            }
        elif "getAvailabilityZones" in args.token:
            ret = {
                "names": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"],
                "zone_ids": ["use1-az1", "use1-az2", "use1-az3", "use1-az4"],
                "state": "available",
            }

        return ret
    