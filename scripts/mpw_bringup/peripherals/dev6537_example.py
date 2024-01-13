#inspo from https://github.com/ni/nidaqmx-python/tree/master/examples

import nidaqmx, pprint, pdb
from nidaqmx.constants import LineGrouping

#P0.0-3: 65, 31, 63, 29

#digital output
def digital_output_test():
    #system = nidaqmx.system.System.local()
    #system.set_digital_logic_family_power_up_state("PXI1Slot6", nidaqmx.constants.LogicFamily.TWO_POINT_FIVE_V)
    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(
            "PXI1Slot6/port0/line0:3", line_grouping=LineGrouping.CHAN_FOR_ALL_LINES
        )
        task.do_channels.all.do_logic_family = nidaqmx.constants.LogicFamily.TWO_POINT_FIVE_V

        """
        try:
            print("N Lines 1 Sample Boolean Write (Error Expected): ")
            print(task.write([True, False, True, False]), auto_start = True)
        except nidaqmx.DaqError as e:
            print(e)
        """
        print("1 Channel N Lines 1 Sample Unsigned Integer Write: ")
        print(task.write([3,0,3,0,3,0], auto_start=True))

def system_info():
    system = nidaqmx.system.System.local()
    for device in system.devices:
        print(device)
    


if __name__ == "__main__":
    digital_output_test()