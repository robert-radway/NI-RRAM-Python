import niswitch

with niswitch.Session("2571_2") as session:
    #to close an open switch:
    session.disconnect(channel1='no0', channel2='com0')    
    session.connect(channel1='nc0', channel2='com0')
    
    #session.disconnect(channel1='nc0', channel2='com0')    
    #session.connect(channel1='no0', channel2='com0')


    relay_name=session.get_relay_name(index=1) #one-indexed
    count=session.get_relay_count(relay_name=relay_name)
    position=session.get_relay_position(relay_name=relay_name)
    print(f"{count}, {position}")
    if position==niswitch.RelayPosition.CLOSED: #closed is actually
        print("closed")
    else:
        print("open")