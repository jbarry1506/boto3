#!/usr/bin/env python
"""I was trying to programatically remove a Virtual Private Cloud (VPC) in
AWS and the error message was not helpful:

    botocore.exceptions.ClientError: An error occurred (DependencyViolation)
    when calling the DeleteVpc operation: The vpc 'vpc-c12029b9' has
    dependencies and cannot be deleted.

Searching for a quick solution was not fruitful but I was able to glean some
knowledge from Neil Swinton's gist:
https://gist.github.com/neilswinton/d37787a8d84387c591ff365594bd26ed

Using that, and some trial and error, I was able to develop this function
that does all the cleanup necessary.

Word of warning: This will delete the VPC and all instances/resources
associated with it. As far as I know, this is complete. It's just like
selecting Delete from the context menu on a VPC in the AWS Console except
that this also deletes internet gateways that are attached to the VPC.
"""

import sys
import boto3


def vpc_cleanup(vpcid):
    """Remove VPC from AWS
    Set your region/access-key/secret-key from env variables or boto config.

    :param vpcid: id of vpc to delete
    """
    if not vpcid:
        return
    print('Removing VPC ({}) from AWS'.format(vpcid))
    ec2 = boto3.resource('ec2')
    ec2client = ec2.meta.client
    vpc = ec2.Vpc(vpcid)
    # detach and delete all gateways associated with the vpc
    for gw in vpc.internet_gateways.all():
        vpc.detach_internet_gateway(InternetGatewayId=gw.id)
        gw.delete()
    # delete all route table associations
    for rt in vpc.route_tables.all():
        for rta in rt.associations:
            if not rta.main:
                rta.delete()
    # delete any instances
    for subnet in vpc.subnets.all():
        for instance in subnet.instances.all():
            instance.terminate()
    # delete our endpoints
    for ep in ec2client.describe_vpc_endpoints(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [vpcid]
            }])['VpcEndpoints']:
        ec2client.delete_vpc_endpoints(VpcEndpointIds=[ep['VpcEndpointId']])
    # delete our security groups
    for sg in vpc.security_groups.all():
        if sg.group_name != 'default':
            sg.delete()
    # delete any vpc peering connections
    for vpcpeer in ec2client.describe_vpc_peering_connections(
            Filters=[{
                'Name': 'requester-vpc-info.vpc-id',
                'Values': [vpcid]
            }])['VpcPeeringConnections']:
        ec2.VpcPeeringConnection(vpcpeer['VpcPeeringConnectionId']).delete()
    # delete non-default network acls
    for netacl in vpc.network_acls.all():
        if not netacl.is_default:
            netacl.delete()
    # delete network interfaces
    for subnet in vpc.subnets.all():
        for interface in subnet.network_interfaces.all():
            interface.delete()
        subnet.delete()
    # finally, delete the vpc
    ec2client.delete_vpc(VpcId=vpcid)


def main(argv=None):
    vpc_cleanup(argv[1])


if __name__ == '__main__':
    main(sys.argv)