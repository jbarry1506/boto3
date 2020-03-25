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
******************************************************************************

Altered!  This is not the original code.  I should have forked it, but I abide
by any and all licenses associated with this piece of code.

jbarry1506

"""

import sys
import boto3
from pprint import pprint
import vars

"""
To delete a VPC, it is necessary to handle the following preliminary items
    # Terminate all instances
    # Delete all subnets
    # Delete custom security groups 
    # and custom route tables
    # Detach any internet gateways 
    # or virtual private gateways

This code should get any necessary information for that purpose
"""

def vpc_cleanup(vpcid):
    """Remove VPC from AWS
    Set your region/access-key/secret-key from env variables or boto config.

    :param vpcid: id of vpc to delete
    """

    # TODO:  Throw a valid error here
    if not vpcid:
        return

    ec2client = boto3.client('ec2')
    ec2 = boto3.resource('ec2')
    
    # identify the VPC    
    vpc_response = ec2client.describe_vpcs(
        VpcIds = [vpcid]
    )
    pprint(vpc_response)

    print('Start Removing VPC ({}) from AWS'.format(vpcid))

    vpc = ec2.Vpc(vpc_response['Vpcs'][0]['VpcId'])

    # TODO this is not complete
    # get endpoints for deletion
    vpc_endpoints = ec2client.describe_vpc_endpoints()
    for vpce in vpc_endpoints:
        pprint(vpce)

    # detach and delete all gateways associated with the vpc
    for gw in vpc.internet_gateways.all():
        print("detatching and deleting ({})".format(gw))
        vpc.detach_internet_gateway(InternetGatewayId=gw.id)
        gw.delete()

    # delete any vpc peering connections
    for vpcpeer in ec2client.describe_vpc_peering_connections(
            Filters=[{
                'Name': 'requester-vpc-info.vpc-id',
                'Values': [vpcid]
            }])['VpcPeeringConnections']:
        ec2client.VpcPeeringConnection(vpcpeer['VpcPeeringConnectionId']).delete()

    # delete our security groups
    for sg in vpc.security_groups.all():
        if sg.group_name != 'default':
            sg.delete()

    # delete all route table associations
    for rt in vpc.route_tables.all():
        pprint(rt.id)
        for rta in rt.associations:
            pprint(rta)
            if not rta.main:
                print("detatching and deleting ({})".format(rta))
                rta.delete()
            else:
                rta_sr = rta.get_available_subresources()
                pprint(rta_sr)
        print("Deleting route table {}".format(rt.id))
        if not rt.associations: rt.delete()

    # delete any subnets
    for subnet in vpc.subnets.all():
        for instance in subnet.instances.all():
            print("detatching and deleting ({})".format(instance))
            instance.terminate()

    # delete our endpoints
    for ep in ec2client.describe_vpc_endpoints(
            Filters=[{
                'Name': 'vpc-id',
                'Values': [vpcid]
            }])['VpcEndpoints']:
        ec2client.delete_vpc_endpoints(VpcEndpointIds=[ep['VpcEndpointId']])

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
    print("Deleting VPC {}".format(vpcid))
    try:
        ec2client.delete_vpc(VpcId=vpcid)
    except:
        print('VPC DELETE FAILED!')
        pprint(ec2client.__exception__[1]['args'])
        pprint(ec2client.__exception__[1]['operation_name'])
        exit(1)

def main():
    vpc_id = vars.unknown_vpc_id
    vpc_cleanup(vpc_id)


if __name__ == '__main__':
    main()