#!/usr/bin/env python
import sys,ipaddress

if __name__=="__main__":
    ipi = ipaddress.ip_interface(sys.argv[1])
    net = ipaddress.ip_network(sys.argv[1])
    print(net.prefixlen)
    nets = net.subnets(new_prefix=24)

    for n in nets:
        print(n)

    #print("Address", ipi.ip)
    #print("Mask", ipi.netmask)
    #print("Cidr", str(ipi.network).split('/')[1])
    #print("Network", str(ipi.network).split('/')[0])
    #print("Broadcast", ipi.network.broadcast_address)

    #print(f"NETWORK: {ipi.network.network_address}")

    #for host in net.hosts():
    #    print(f'Host: {host}')