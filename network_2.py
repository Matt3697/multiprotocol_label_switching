import queue
import threading
from link_2 import LinkFrame


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    #  @param capacity - the capacity of the link in bps
    def __init__(self, name = "default", maxsize=0, capacity=500):
        self.name = name
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)
        self.capacity = capacity #serialization rate
        self.next_avail_time = 0 #the next time the interface can transmit a packet

    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                return pkt_S
        except queue.Empty:
            return None

    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            self.out_queue.put(pkt, block)
        else:
            self.in_queue.put(pkt, block)


## Implements a network layer packet
# NOTE: You will need to extend this class for the packet to include
# the fields necessary for the completion of this assignment.
class NetworkPacket:
    ## packet encoding lengths
    dst_S_length = 5

    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param priority: packet priority
    def __init__(self, dst, data_S, priority=0):
        self.dst = dst
        self.data_S = data_S
        #TODO: add priority to the packet class

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        byte_S += self.data_S
        return byte_S

    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        data_S = byte_S[NetworkPacket.dst_S_length : ]
        return self(dst, data_S)


## Implements a network host for receiving and transmitting data
class Host:

    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination

    ## called when printing the object
    def __str__(self):
        return self.addr

    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    # @param priority: packet priority
    def udt_send(self, dst, data_S, priority=0):
        pkt = NetworkPacket(dst, data_S)
        print('%s: sending packet "%s" with priority %d' % (self, pkt, priority))
        #encapsulate network packet in a link frame (usually would be done by the OS)
        fr = LinkFrame('Network', pkt.to_byte_S())
        #enque frame onto the interface for transmission
        self.intf_L[0].put(fr.to_byte_S(), 'out')

    ## receive frame from the link layer
    def udt_receive(self):
        fr_S = self.intf_L[0].get('in')
        if fr_S is None:
            return
        #decapsulate the network packet
        fr = LinkFrame.from_byte_S(fr_S)
        assert(fr.type_S == 'Network') #should be receiving network packets by hosts
        pkt_S = fr.data_S
        print('%s: received packet "%s"' % (self, pkt_S))

    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return



## Implements a multi-interface router
class Router:

    ##@param name: friendly router name for debugging
    # @param intf_capacity_L: capacities of outgoing interfaces in bps
    # @param encap_tbl_D: table used to encapsulate network packets into MPLS frames
    # @param frwd_tbl_D: table used to forward MPLS frames
    # @param decap_tbl_D: table used to decapsulate network packets from MPLS frames
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, intf_capacity_L, encap_tbl_D, frwd_tbl_D, decap_tbl_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(name = name, maxsize = max_queue_size, capacity = cap) for name, cap in intf_capacity_L]
        #save MPLS tables
        self.encap_tbl_D = encap_tbl_D
        self.frwd_tbl_D = frwd_tbl_D
        self.decap_tbl_D = decap_tbl_D


    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            fr_S = None #make sure we are starting the loop with a blank frame
            fr_S = self.intf_L[i].get('in') #get frame from interface i
            if fr_S is None:
                continue # no frame to process yet
            #decapsulate the packet
            fr = LinkFrame.from_byte_S(fr_S)
            pkt_S = fr.data_S
            #process the packet as network, or MPLS
            if fr.type_S == "Network":
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                self.process_network_packet(p, i)
            elif fr.type_S == "MPLS":
                # TODO: handle MPLS frames
                #for now, we just relabel the packet as an MPLS frame without encapsulation
                m_fr = MPLSlabel.from_byte_S(pkt_S)
                #send the MPLS frame for processing
                self.process_MPLS_frame(m_fr, i)
            else:
                raise('%s: unknown frame type: %s' % (self, fr.type_S))

    ## process a network packet incoming to this router
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def process_network_packet(self, pkt, i):
        #TODO: encapsulate the packet in an MPLS frame based on self.encap_tbl_D
        intfName = self.intf_L[i].name
        #if self.name is in the encapsulation list, then encapsulate the fram. I.e first hop router
        if self.name in self.encap_tbl_D[intfName]:
            m_fr = MPLSlabel(pkt, intfName)
        print('%s: encapsulated packet "%s" as MPLS frame "%s"' % (self, pkt, m_fr))
        #send the encapsulated packet for processing as MPLS frame
        self.process_MPLS_frame(m_fr, i)


    ## process an MPLS frame incoming to this router
    #  @param m_fr: MPLS frame to process
    #  @param i Incoming interface number for the frame
    def process_MPLS_frame(self, m_fr, i):
        #TODO: implement MPLS forward, or MPLS decapsulation if this is the last hop router for the path
        print('%s: processing MPLS frame "%s"' % (self, m_fr))
        ## From the label received, we determine where it's going
        table = self.frwd_tbl_D[m_fr.label]
        m_fr.label = table["outLabel"]
        outIntf = table["interface"]
        #if the queue is not full, try to decapsulate
        try:
            #if the next hop is the destination then we can decapsulate the mpls frame
            if m_fr.label == table['dest']:
                print('%s: decapsulating MPLS frame "%s"' % (self, m_fr))
                fr = LinkFrame("Network", m_fr.frame)
            else:
                fr = LinkFrame("MPLS", m_fr.to_byte_S())
            self.intf_L[outIntf].put(fr.to_byte_S(), 'out', True)
            print('%s: forwarding frame "%s" from interface %d to %d' % (self, fr, i, outIntf))
        except queue.Full:
            print('%s: frame "%s" lost on interface %d' % (self, m_fr, i))
            pass


    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return

class MPLSlabel:

    labelLen = 5

    def __init__(self, frame, label):#initialize MPLSlabel with fame and label
        self.frame = frame
        self.label = label

    # Adds the label to the end of the byte_S, which is added to the end of the packet
    def to_byte_S(self):
        byte_S = str(self.label).zfill(self.labelLen)
        byte_S += str(self.frame)
        return byte_S

    def __str__(self):
        return self.to_byte_S()

    #gets the label using from the byte_S
    @classmethod
    def from_byte_S(self, byte_S):
        frame = byte_S[self.labelLen : ]
        label = byte_S[ : self.labelLen].strip('0')
        return self(frame, label)
