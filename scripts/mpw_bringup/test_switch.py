import niswitch
import pdb

with niswitch.Session("PXI1Slot4") as session:
    relay_name=session.get_relay_name(index=1) #one-indexed
    print(relay_name)
    relay_idx_to_switch = 0
    pdb.set_trace()
    position=session.get_relay_position(relay_name=relay_name)
    
    #toggle the switch
    common = f'com{relay_idx_to_switch}'
    normally_open = f'no{relay_idx_to_switch}'
    normally_closed = f'nc{relay_idx_to_switch}'
    if position==niswitch.RelayPosition.CLOSED:
        session.disconnect(channel1=normally_open, channel2=common)
        session.connect(channel1=normally_closed, channel2=common)
        print('opened the switch')
    elif position==niswitch.RelayPosition.OPEN:
        session.disconnect(channel1=normally_closed, channel2=common) #Set to normally closed
        session.connect(channel1=normally_open, channel2=common)
        print('closed the switch')


    
    count=session.get_relay_count(relay_name=relay_name) #number of times it has been switched