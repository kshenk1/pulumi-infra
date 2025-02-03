import pulumi
import pulumi_aws as paws
from config import AWSPulumiConfig

def define_dns(config: AWSPulumiConfig, lb_dns: str) -> paws.route53.Record:
    zone = paws.route53.get_zone(name=config.hosted_zone)

    record = paws.route53.Record(
        f'{config.resource_prefix}-record',
        name=config.domain_name,
        type=paws.route53.RecordType.A,
        zone_id=zone.zone_id,
        aliases=[{
            "name": lb_dns,
            "zone_id": config.zone_alias_id,
            "evaluate_target_health": False,
        }]
    )

    pulumi.export('dns_record', record.fqdn.apply(lambda x: x))

    url = record.fqdn.apply(
        lambda dns: f"http://{dns}"
    )

    pulumi.export("Jenkins URL", url)

    return record